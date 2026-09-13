#!/usr/bin/env python3
"""Convert the approved Markdown through Pandoc AST without changing source data.

Run from any directory. Compile the parent main.tex at journal_layout root.
The four generated TeX files are content fragments, not document environments.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
import struct
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
READER = "markdown+pipe_tables+tex_math_dollars+raw_tex-implicit_figures-smart-blank_before_header"
EXPECTED = {"tables": 36, "figures": 11, "tagged_equations": 11}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def walk(value):
    if isinstance(value, dict):
        yield value
        yield from walk(value.get("c", []))
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def text(value) -> str:
    if isinstance(value, list):
        return "".join(text(x) for x in value)
    if not isinstance(value, dict):
        return ""
    kind, c = value["t"], value.get("c")
    if kind == "Str":
        return c
    if kind in {"Space", "SoftBreak", "LineBreak"}:
        return " "
    if kind in {"Code", "Math"}:
        return c[1]
    if kind == "RawInline" and c[0] == "latex" and c[1].startswith("\\nolinkurl{"):
        return c[1][11:-1]
    if kind in {"Link", "Image"}:
        return text(c[1])
    if kind == "Header":
        return text(c[2])
    if kind in {"Para", "Plain"}:
        return text(c)
    return text(c) if isinstance(c, list) else ""


def strip_prefix(inlines, pattern: str):
    """Remove only the matched leading text; retain remaining inline structure."""
    result = copy.deepcopy(inlines)
    if len(result) == 1 and result[0]["t"] in {"Strong", "Emph"}:
        result = result[0]["c"]
    match = re.match(pattern, text(result))
    if not match:
        raise ValueError(f"Expected prefix {pattern!r}: {text(result)!r}")
    remaining = len(match.group())
    while remaining:
        node = result[0]
        if node["t"] not in {"Str", "Space", "SoftBreak"}:
            raise ValueError("Caption/heading prefix unexpectedly contains markup")
        size = len(text(node))
        if size <= remaining:
            result.pop(0)
            remaining -= size
        else:
            node["c"] = node["c"][remaining:]
            remaining = 0
    return result


def rows(table):
    c = table["c"]
    head = c[3][1]
    body = [row for part in c[4] for row in part[2] + part[3]]
    foot = c[5][1]
    return head, body, foot


def cell_blocks(row):
    for cell in row[1]:
        if cell[2:4] != [1, 1]:
            raise ValueError("Unexpected spanning cell in a pipe table")
        yield cell[4]


def cells(table):
    return [blocks for group in rows(table) for row in group for blocks in cell_blocks(row)]


def code_to_url(block, changes):
    for node in walk(block):
        if node["t"] == "Code":
            literal = node["c"][1]
            if any(char in literal for char in "{}\n\r"):
                raise ValueError(f"Code needs a different safe URL delimiter: {literal!r}")
            changes.append(literal)
            node.update(t="RawInline", c=["latex", "\\nolinkurl{" + literal + "}"])


def wrap_doi_labels(block):
    changed = []
    for node in walk(block):
        if node["t"] == "Link" and re.fullmatch(r"doi:[^{}\s]+", text(node)):
            literal = text(node)
            node["c"][1] = [{"t": "RawInline", "c": ["latex", "\\nolinkurl{" + literal + "}"]}]
            changed.append({"label": literal, "target": node["c"][2][0]})
    return changed


def table_layout(table, number, available_pt):
    head, body, _ = rows(table)
    headers = [text(x) for x in cell_blocks(head[0])]
    data = [[text(x) for x in cell_blocks(row)] for row in body]
    count = len(headers)
    font = 8.3 if count >= 6 else (8.6 if count == 5 else 9.0)
    numeric_pattern = re.compile(r"^[+−-]?[\d,]+(?:\.\d+)?%?$")
    weights, numeric = [], []
    for col in range(count):
        values = [row[col] for row in data if row[col] not in {"", "—", "-", "None"}]
        ratio = sum(bool(numeric_pattern.fullmatch(v)) for v in values) / max(1, len(values))
        is_number = ratio >= 0.60
        numeric.append(is_number)
        longest = max((len(v) for v in values), default=len(headers[col]))
        mean = sum(len(v) for v in values) / max(1, len(values))
        if is_number:
            desire = max(48, min(90, longest * font * 0.50 + 5))
        elif longest <= 5:
            desire = max(28, longest * font * 0.50 + 5)
        else:
            desire = max(55, min(230, mean * font * 0.34 + 26))
            desire = max(desire, min(160, max((len(w) for v in values for w in v.split()), default=0) * font * 0.39))
        weights.append(desire)
    if number == 2:
        # The first compile showed a 0.68 pt overflow in the Branch heading.
        widths = [0.080, 0.285, 0.265, 0.175, 0.195]
    elif number == 4:
        widths = [0.25, 0.59, 0.16]
        numeric = [False] * count
    else:
        widths = [w / sum(weights) for w in weights]
    for i, width in enumerate(widths):
        table["c"][2][i] = [{"t": "AlignRight" if numeric[i] else "AlignLeft"}, {"t": "ColWidth", "c": width}]
    content_width = available_pt - 2 * (count - 1) * 3.2
    def row_height(row):
        return max(math.ceil(len(v) * font * 0.48 / max(12, content_width * widths[i])) for i, v in enumerate(row))
    keep_all = number == 9 or (len(body) <= 6 and any(numeric))
    keep_final = 4 if headers[0] == "Period / instant" else 0
    if headers[0] == "Interval / scope" and any("purchase" in row[1].lower() for row in data):
        keep_final = sum(row[0] == "Daily total" for row in data)
    protected_start = data if keep_all else data[:3]
    required_lines = 4 + row_height(headers) + sum(row_height(row) for row in protected_start)
    needspace = min(260, max(66, required_lines * font * 1.18))
    return {"number": number, "columns": count, "header_rows": len(head), "body_rows": len(body),
            "cell_count": len(cells(table)), "headers": headers, "width_fractions": widths,
            "numeric_columns": numeric, "font_pt": font, "leading_pt": round(font * 1.20, 2),
            "needspace_pt": round(needspace, 1), "keep_all_rows": keep_all,
            "keep_final_rows": keep_final}


class Converter:
    def __init__(self, pandoc: Path, api):
        self.pandoc, self.api = pandoc, api

    def latex(self, blocks):
        value = {"pandoc-api-version": self.api, "meta": {}, "blocks": blocks}
        result = subprocess.run([str(self.pandoc), "--from=json", "--to=latex", "--wrap=none",
                                 "--top-level-division=section", "--number-sections"],
                                input=json.dumps(value, ensure_ascii=False), capture_output=True, text=True, check=True)
        return result.stdout

    def inlines(self, value):
        return self.latex([{"t": "Plain", "c": value}]).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "manuscript_EN.md")
    parser.add_argument("--pandoc", type=Path, default=ROOT / "tools/pandoc-3.11-arm64/bin/pandoc")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--table-width-pt", type=float, default=160.0 * 72.27 / 25.4)
    parser.add_argument("--figure-max-height-mm", type=float, default=150.0)
    args = parser.parse_args()
    source, pandoc, build = args.source.resolve(), args.pandoc.resolve(), args.build_dir.resolve()
    if not pandoc.is_file():
        raise SystemExit(f"Pandoc not found at {pandoc}; pass --pandoc with the local executable.")
    if ROOT not in build.parents or build == ROOT:
        raise SystemExit("Build directory must be inside the journal-layout output directory.")
    build.mkdir(parents=True, exist_ok=True)
    original_hash = sha(source)
    immutable = build / "source_manuscript.md"
    if immutable.exists() and sha(immutable) != original_hash:
        raise SystemExit("Immutable Markdown copy differs; choose a fresh build directory for the changed source.")
    if not immutable.exists():
        shutil.copyfile(source, immutable)
        immutable.chmod(0o444)
    version = subprocess.run([str(pandoc), "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    parsed = subprocess.run([str(pandoc), "--from=" + READER, "--to=json", str(immutable)],
                            capture_output=True, text=True, check=True)
    ast = json.loads(parsed.stdout)
    write_json(build / "source_ast.json", ast)
    conv = Converter(pandoc, ast["pandoc-api-version"])
    blocks = ast["blocks"]
    source_headings = [(len(m.group(1)), m.group(2)) for m in re.finditer(r"^(#{1,6})[ \t]+(.+?)\s*$", source.read_text(), re.M)]
    parsed_headings = [(b["c"][0], text(b)) for b in blocks if b["t"] == "Header"]
    assert parsed_headings == source_headings, "A Markdown heading was swallowed into prose or changed during parsing"
    main_section_numbers = [int(re.match(r"^(\d+)\s", title).group(1)) for level, title in parsed_headings if level == 1 and re.match(r"^\d+\s", title)]
    assert main_section_numbers == list(range(1, 10)), "Expected nine correctly ordered numbered main sections"
    assert blocks[0]["t"] == "Header" and text(blocks[1]) == "Abstract"
    keywords_index = next(i for i, b in enumerate(blocks) if re.match(r"^Keywords:", text(b)))
    title = blocks[0]["c"][2]
    abstract = copy.deepcopy(blocks[2:keywords_index])
    keywords = strip_prefix(blocks[keywords_index]["c"], r"^Keywords:\s*") if blocks[keywords_index]["c"][0]["t"] != "Strong" else copy.deepcopy(blocks[keywords_index]["c"][1:])
    while keywords and keywords[0]["t"] == "Space":
        keywords.pop(0)
    body_source = blocks[keywords_index + 1:]
    source_tables = [b for b in blocks if b["t"] == "Table"]
    source_cells = [text(c) for t in source_tables for c in cells(t)]
    source_math = [n["c"] for n in walk(ast["blocks"]) if n["t"] == "Math"]
    equation_tags = [tag for kind, value in source_math for tag in re.findall(r"\\tag\{([^}]+)\}", value)]
    assert len(source_tables) == EXPECTED["tables"] and equation_tags == [str(i) for i in range(1, EXPECTED["tagged_equations"] + 1)]
    transformed, tables, figures, heading_changes, code_changes = [], [], [], [], []
    prose_checks, doi_changes, math_introducers, algorithm_introducers = [], [], [], []
    protected_prose_prefixes = (
        "Figure 9 compares ", "For candidate ", "Figure 10 shows ",
        "Figure 11 extends ", "Against the frozen two-search v5 selections,",
        "Circular block resampling retains neighboring daily differences and wraps at the endpoints",
        "The first difference combines observed-state feedback and revision permission.",
        "We retain the causal forecasting structure selected during January as the common input to the procurement comparisons.",
        "Independent verification rebuilt the source inputs and refitted historical forecasts",
        "Problem 3 adds forecasts released at 00:00, 06:00, 12:00 and 18:00",
    )
    protected_figure_prose = []
    in_references = False
    i = 0
    while i < len(body_source):
        original = body_source[i]
        block = copy.deepcopy(original)
        if in_references and block["t"] == "Header":
            transformed.append({"t": "RawBlock", "c": ["latex", "\\endgroup"]})
            in_references = False
        if block["t"] == "Header":
            heading = text(block)
            if heading == "References" or heading.startswith("Appendix "):
                transformed.append({"t": "RawBlock", "c": ["latex", "\\clearpage"]})
            if heading in {"4 Q1: Deterministic daily storage scheduling", "3.2 Complete empirical program and settlement"}:
                # These observed boundary headings need room for the opening
                # paragraph/equation as well as the heading itself.
                transformed.append({"t": "RawBlock", "c": ["latex", "\\Needspace{100pt}"]})

            if re.match(r"^\d+(?:\.\d+)*\s", heading):
                block["c"][2] = strip_prefix(block["c"][2], r"^\d+(?:\.\d+)*\s+")
                numbered = True
            else:
                block["c"][1][1].append("unnumbered")
                numbered = False
            heading_changes.append({"before": heading, "after": text(block), "automatic_numbering": numbered})
        if block["t"] == "Para" and re.match(r"^Table \d+\.\s", text(block)):
            number = int(re.match(r"^Table (\d+)\.", text(block)).group(1))
            table = copy.deepcopy(body_source[i + 1])
            assert table["t"] == "Table" and number == len(tables) + 1
            caption = strip_prefix(block["c"], rf"^Table {number}\.\s+")
            assert text(caption) == re.sub(rf"^Table {number}\.\s+", "", text(block))
            table["c"][1] = [None, [{"t": "Plain", "c": caption}]]
            layout = table_layout(table, number, args.table_width_pt)
            layout.update(caption=text(caption), original_caption=text(block))
            tables.append(layout)
            for header_row in rows(table)[0]:
                for header_cell in cell_blocks(header_row):
                    for header_block in header_cell:
                        if header_block["t"] in {"Plain", "Para"}:
                            header_block["c"] = [{"t": "Strong", "c": header_block["c"]}]
            code_to_url(table, code_changes)
            start = (f"% TABLE-BEGIN {number}\n\\Needspace{{{layout['needspace_pt']}pt}}\n\\begingroup\n"
                     f"\\fontsize{{{layout['font_pt']}}}{{{layout['leading_pt']}}}\\selectfont\n"
                     "\\setlength{\\tabcolsep}{3.2pt}\n\\renewcommand{\\arraystretch}{1.12}\n"
                     "\\setlength{\\LTleft}{0pt plus 1fill}\\setlength{\\LTright}{0pt plus 1fill}\n"
                     "\\setlength{\\LTcapwidth}{\\linewidth}")
            transformed.extend([{"t": "RawBlock", "c": ["latex", start]}, table,
                                {"t": "RawBlock", "c": ["latex", f"\\endgroup\n% TABLE-END {number}"]}])
            i += 2
            continue
        image_nodes = [n for n in walk(block) if n["t"] == "Image"]
        if image_nodes:
            assert block["t"] == "Para" and len(block["c"]) == 1 and len(image_nodes) == 1
            number = len(figures) + 1
            caption_block = copy.deepcopy(body_source[i + 1])
            caption = strip_prefix(caption_block["c"], rf"^Figure {number}\.\s+")
            assert text(caption) == re.sub(rf"^Figure {number}\.\s+", "", text(caption_block))
            image = image_nodes[0]
            image_source = (source.parent / unquote(image["c"][2][0])).resolve()
            destination = build / f"figure-{number:02d}.png"
            assert image_source.suffix.lower() == ".png" and image_source.is_file()
            shutil.copyfile(image_source, destination)
            assert sha(image_source) == sha(destination)
            png_header = image_source.read_bytes()[:24]
            assert png_header[:8] == b"\x89PNG\r\n\x1a\n", "Expected a valid PNG signature"
            pixel_width, pixel_height = struct.unpack(">II", png_header[16:24])
            available_width_mm = args.table_width_pt * 25.4 / 72.27
            height_at_full_width_mm = available_width_mm * pixel_height / pixel_width
            height_limited = height_at_full_width_mm > args.figure_max_height_mm
            # The five advanced multi-panel figures must use the full text width.
            # Refuse a silently narrower rendering if their aspect ratio changes.
            if number in {3, 4, 9, 10, 11}:
                assert not height_limited, f"Figure {number} needs more than the allowed height at full text width"
            rendered_height_mm = min(height_at_full_width_mm, args.figure_max_height_mm)
            rendered_width_mm = rendered_height_mm * pixel_width / pixel_height
            figures.append({"number": number, "source": str(image_source), "copy": str(destination.relative_to(ROOT)),
                            "source_sha256": sha(image_source), "copy_sha256": sha(destination),
                            "original_alt_text": text(image), "original_caption": text(caption_block), "caption": text(caption),
                            "source_pixels": [pixel_width, pixel_height], "width_limit_mm": available_width_mm,
                            "height_limit_mm": args.figure_max_height_mm, "height_limited": height_limited,
                            "rendered_width_mm": rendered_width_mm, "rendered_height_mm": rendered_height_mm,
                            "caption_font_pt": 9.0, "automatic_figure_label_bold": True})
            code_to_url(caption, code_changes)
            graphic = destination.relative_to(ROOT).as_posix()
            placement = "!tp" if number == 11 else "!htbp"
            figure = (f"\\begin{{figure}}[{placement}]\n\\centering\n"
                      f"\\includegraphics[width=\\linewidth,height={args.figure_max_height_mm:g}mm,keepaspectratio]{{{graphic}}}\n"
                      f"\\caption{{{conv.inlines(caption)}}}\n\\label{{fig:{number}}}\n\\end{{figure}}")
            transformed.append({"t": "RawBlock", "c": ["latex", figure]})
            i += 2
            continue
        assert block["t"] != "Table", "A table was not paired with its preceding caption"
        if block["t"] == "Para" and re.match(r"^Algorithm \d+\.", text(block)):
            transformed.append({"t": "RawBlock", "c": ["latex", "\\Needspace{5\\baselineskip}"]})
            algorithm_introducers.append(text(block))
        if block["t"] == "Para" and len(text(block).split()) <= 70 and i + 1 < len(body_source):
            next_block = body_source[i + 1]
            if any(n["t"] == "Math" and n["c"][0]["t"] == "DisplayMath" for n in walk(next_block)):
                needed_lines = 14 if text(block).startswith("The causal forecast uses ordinary least squares") else 5
                transformed.append({"t": "RawBlock", "c": ["latex", f"\\Needspace{{{needed_lines}\\baselineskip}}"]})
                math_introducers.append(text(block))
        if in_references and block["t"] == "Para":
            transformed.append({"t": "RawBlock", "c": ["latex", "\\hangindent=1.8em\\hangafter=1"]})
        doi_changes.extend(wrap_doi_labels(block))
        code_to_url(block, code_changes)
        if block["t"] != "Header":
            assert text(original) == text(block), "Visible prose changed during inline formatting"
            prose_checks.append(text(original))
        protect_figure_prose = block["t"] == "Para" and text(block).startswith(protected_prose_prefixes)
        if protect_figure_prose:
            # Permit normal figure floats but never splice one into these short
            # figure-related paragraphs at a page break or hyphenated word.
            transformed.append({"t": "RawBlock", "c": ["latex", "\\begingroup\n\\interlinepenalty=10000\n\\brokenpenalty=10000"]})
            protected_figure_prose.append(text(block))
        transformed.append(block)
        if protect_figure_prose:
            transformed.append({"t": "RawBlock", "c": ["latex", "\\par\n\\endgroup"]})
        if block["t"] == "Header" and text(block) == "References":
            transformed.append({"t": "RawBlock", "c": ["latex", "\\begingroup\n\\bibfont\n\\raggedright\n\\setlength{\\parindent}{0pt}"]})
            in_references = True
        i += 1
    if in_references:
        transformed.append({"t": "RawBlock", "c": ["latex", "\\endgroup"]})
    assert len(protected_figure_prose) == len(protected_prose_prefixes), "Expected all protected local figure-related paragraphs"
    assert len(figures) == EXPECTED["figures"] and len(tables) == EXPECTED["tables"]
    target_cells = [text(c) for t in transformed if t["t"] == "Table" for c in cells(t)]
    assert target_cells == source_cells, "Table cell content changed during conversion"
    target_math = [n["c"] for n in walk(abstract + transformed) if n["t"] == "Math"]
    assert target_math == source_math, "Math payload/order changed during conversion"
    body_tex = conv.latex(transformed)
    # Pandoc already emits booktabs longtables with repeated column headers.
    # Repeat the caption without another list-of-tables entry or counter step.
    for table in tables:
        number = table["number"]
        pattern = rf"(% TABLE-BEGIN {number}\n)(.*?)(% TABLE-END {number})"
        match = re.search(pattern, body_tex, flags=re.S)
        assert match
        content = match.group(2)
        caption_match = re.search(r"(\\caption\{.*?\})\\tabularnewline", content, re.S)
        assert caption_match
        continued = caption_match.group(1).replace("\\caption{", "\\caption[]{", 1)
        continued = continued[:-1] + " (continued)}\\tabularnewline\n"
        content = content.replace("\\endfirsthead\n", "\\endfirsthead\n" + continued, 1)
        prefix, data = content.split("\\endlastfoot\n", 1)
        if number == 4:
            # Inset data accents only; a column preamble space displaces the header.
            data = re.sub(r"(?m)^(?=\\\()", lambda m: r"\hspace{0.5pt}", data)
        # longtable reserves the ordinary footer height while placing rows.
        # A taller last footer can otherwise create a header-only final page
        # inside LT@output, independently of row-break penalties.
        footer = "\\bottomrule\\noalign{}\n"
        assert prefix.endswith("\\endhead\n" + footer)
        prefix = prefix.replace("\\endhead\n", "\\endhead\n" + footer + "\\endfoot\n", 1)
        row_count = table["body_rows"]
        protected = set(range(min(2, row_count - 1)))
        protected.add(row_count - 1)
        if table["keep_all_rows"]:
            protected.update(range(row_count - 1))
        elif table["keep_final_rows"]:
            protected.update(range(row_count - table["keep_final_rows"], row_count - 1))
        row_index = 0
        def protect_row(match):
            nonlocal row_index
            replacement = match.group() + ("*" if row_index in protected else "")
            row_index += 1
            return replacement
        data = re.sub(r" \\\\$", protect_row, data, flags=re.M)
        assert row_index == row_count, f"Unexpected rendered row count in table {number}"
        assert re.search(r" \\\\\*\n\\end\{longtable\}", data), f"Unprotected final row in table {number}"
        content = prefix + "\\endlastfoot\n" + data
        body_tex = body_tex[:match.start(2)] + content + body_tex[match.end(2):]
    assert body_tex.count("\\begin{longtable}") == EXPECTED["tables"]
    assert body_tex.count("\\bottomrule\\noalign{}\n\\endfoot\n\\bottomrule\\noalign{}\n\\endlastfoot") == EXPECTED["tables"]
    assert body_tex.count("\\begin{figure}") == EXPECTED["figures"]
    assert re.findall(r"\\tag\{([^}]+)\}", body_tex) == equation_tags
    title_tex = conv.inlines(title)
    title_tex = title_tex.replace(" with Forecast Errors and Paid Revisions", "\\\\\nwith Forecast Errors and Paid Revisions")
    (build / "title.tex").write_text(title_tex + "\n")
    (build / "abstract.tex").write_text(conv.latex(abstract))
    (build / "keywords.tex").write_text(conv.inlines(keywords).replace(";", " \\sep ") + "\n")
    (build / "body.tex").write_text(body_tex)
    write_json(build / "body_ast.json", {"pandoc-api-version": ast["pandoc-api-version"], "meta": {}, "blocks": transformed})
    write_json(build / "table_cell_manifest.json", [{"table": index + 1, "cells": [text(c) for c in cells(t)]} for index, t in enumerate(source_tables)])
    assert sha(source) == original_hash == sha(immutable)
    report = {"source": str(source), "source_sha256": original_hash, "immutable_copy_sha256": sha(immutable),
              "source_unchanged": True, "pandoc_version": version, "pandoc_path": str(pandoc), "reader": READER,
              "counts": {"tables": len(tables) + 1, "markdown_tables": len(tables), "external_inventory_tables": 1, "figures": len(figures), "table_cells_including_headers": len(source_cells),
                         "table_body_rows": sum(t["body_rows"] for t in tables), "tagged_equations": len(equation_tags),
                         "all_math_nodes": len(source_math), "inline_code_occurrences": len(code_changes),
                         "ordinary_body_blocks_text_verified": len(prose_checks)},
              "all_table_cells_preserved": target_cells == source_cells, "all_math_payloads_preserved": target_math == source_math,
              "ordinary_body_text_preserved": True, "all_caption_text_preserved_except_automatic_number_prefix": True,
              "short_math_introducers_protected": math_introducers, "breakable_doi_labels": doi_changes,
              "algorithm_introducers_protected": algorithm_introducers,
              "figure_related_paragraphs_kept_unbroken": protected_figure_prose,
              "longtables_with_equal_footer_heights_and_protected_final_row": len(tables),
              "external_inventory": {"table": 37, "source": "appendix_programs.tex", "title": "Complete supporting-file inventory"},
              "all_source_headings_recognized": True, "source_heading_count": len(source_headings),
              "parsed_heading_count": len(parsed_headings), "numbered_main_sections": main_section_numbers,
              "equation_tags": equation_tags, "tables": tables, "figures": figures, "heading_transformations": heading_changes,
              "code_literals_preserved_as_nolinkurl": code_changes,
              "unicode_characters_in_source": {f"U+{ord(k):04X}": {"character": k, "count": v} for k, v in Counter(source.read_text()).items() if ord(k) > 127},
              "required_preamble_packages": ["graphicx", "longtable", "booktabs", "array", "calc", "needspace", "amsmath", "amssymb", "hyperref", "xurl"],
              "required_class_macros": ["bibfont (provided by elsarticle)"],
              "possible_pandoc_helper_macros": ["tightlist"] if "\\tightlist" in body_tex else [],
              "transformations": ["Split title, abstract and keyword content into separate fragments; keyword semicolons become Elsevier sep delimiters.",
                  "Strip existing numeric heading prefixes and enable automatic section numbering; other headings remain unnumbered.",
                  "Disable blank-before-header parsing so every source ATX heading is retained, verified against the source line list.",
                  "Balance the unchanged title with an explicit line break before with Forecast Errors and Paid Revisions; protect the Algorithm 1 introduction with Needspace.",
                  "Replace each standalone image and following caption with a numbered LaTeX floating figure and byte-identical local PNG copy.",
                  "Pair table captions with native Pandoc longtables, set content-sensitive proportional widths and local 8.3–9 pt fonts.",
                  "Keep longtables left anchored with stretchable right glue to absorb sub-point column-width rounding residue without suppressing TeX warnings.",
                  "Repeat captions and column headers; Needspace estimates protect the start, and starred first two data row breaks keep the first three rows together.",
                  "Keep numeric tables of at most six data rows together; retain the last four rows of storage-block tables as one boundary-energy group.",
                  "Keep the final midnight/final/emergency daily-total rows together in specified-purchase tables 10, 16, 21 and 26.",
                  "Reserve identical ordinary and final bottom-rule footers, and star the final data-row break, to prevent header-only final continuations.",
                  "Bold column headers; protect short equation-introducing paragraphs with five baselines of Needspace.",
                  "Use the official elsarticle bibfont in a local ragged-right, hanging-indent reference group; retain DOI link targets and visible labels while allowing labels to break.",
                  "Preserve all inline code literal text using nolinkurl for breakable paths/identifiers; original hyperlinks remain hyperlinks.",
                  "No changes to data values, mathematical payloads, original prose or source files; document rendering is verified separately."],
              "outputs": {name: sha(build / name) for name in ["title.tex", "abstract.tex", "keywords.tex", "body.tex"]}}
    write_json(build / "conversion_report.json", report)
    print(json.dumps({"source_sha256": original_hash, **report["counts"], "report": str(build / "conversion_report.json")}, indent=2))


if __name__ == "__main__":
    main()
