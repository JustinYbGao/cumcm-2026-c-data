from pathlib import Path
import csv
import re

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "papers" / "Problem_Restatement_EN.md"
DATES = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
SLOTS = {61, 73, 85, 97, 109, 121}


def rows(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def money(x):
    return f"{float(x):,.2f}"


def energy(x):
    return f"{float(x):,.3f}"


def clock(ts):
    return ts.split(" ")[-1][:5]


def interval(a, b):
    return f"{clock(a)}-{clock(b)}"


def block_label(start, end):
    def c(m):
        return "24:00" if int(m) == 1440 else f"{int(m)//60:02d}:{int(m)%60:02d}"
    return f"{c(start)}-{c(end)}"


def md_table(caption, headers, body):
    out = [f"**{caption}**", "", "| " + " | ".join(headers) + " |",
           "|" + "|".join("---:" if i else "---" for i in range(len(headers))) + "|"]
    out.extend("| " + " | ".join(r) + " |" for r in body)
    return "\n".join(out)


def representative_tables(folder, first_caption, q2=False):
    ledger = rows(ROOT / folder / "ledger.csv")
    picked = [r for r in ledger if r["date"] in DATES and int(r["slot_id"]) in SLOTS]
    body = []
    for r in picked:
        if q2:
            body.append([r["date"], interval(r["interval_start"], r["interval_end"]),
                         energy(r["grid_plan_kwh"]), money(r["planned_cost_yuan"]),
                         money(r["emergency_cost_yuan"]), money(r["total_cost_yuan"])])
        else:
            body.append([r["date"], interval(r["interval_start"], r["interval_end"]),
                         energy(r["grid_original_kwh"]), energy(r["grid_effective_kwh"]),
                         money(r["original_cost_yuan"]), money(r["increase_cost_yuan"]),
                         money(r["decrease_adjustment_yuan"]), money(r["contract_cost_yuan"]),
                         money(r["emergency_cost_yuan"]), money(r["total_cost_yuan"])])
    if q2:
        headers = ["Date", "Interval", "Original plan (kWh)", "Plan fee (CNY)", "Emergency fee (CNY)", "All-in cost (CNY)"]
    else:
        headers = ["Date", "Interval", "Original q0", "Final qbar", "Original fee", "Increase fee", "Decrease adjustment", "Final contract fee", "Emergency fee", "All-in cost"]
    t1 = md_table(f"Table {first_caption}. Required-date purchases and fee components", headers, body)

    blocks = rows(ROOT / folder / "table2_representative.csv")
    bbody = [[r["date"], block_label(r["block_start_minute"], r["block_end_minute"]),
              energy(r["charge_actual_kwh"]), energy(r["discharge_actual_kwh"])] for r in blocks]
    t2 = md_table(f"Table {first_caption+1}. Required-date four-hour battery operation",
                  ["Date", "Block", "Charge at AC bus (kWh)", "Discharge at AC bus (kWh)"], bbody)

    events = rows(ROOT / folder / ("table3_merged_representative.csv" if q2 else "table3_representative.csv"))
    ebody = []
    for d in DATES:
        dr = [r for r in events if r["date"] == d]
        if not dr:
            ebody.append([d, "None", "0", "0.000"])
        else:
            for r in dr:
                n = r.get("ten_minute_intervals", r.get("intervals", "1"))
                ebody.append([d, interval(r["interval_start"], r["interval_end"]), n, energy(r["emergency_kwh"])])
    t3 = md_table(f"Table {first_caption+2}. Required-date emergency-purchase episodes",
                  ["Date", "Interval or merged episode", "Ten-minute intervals", "Emergency purchase (kWh)"], ebody)
    return "\n\n".join([t1, t2, t3])


text = PAPER.read_text(encoding="utf-8")
if "**Table 18." in text:
    raise SystemExit("manuscript already revised; refusing to duplicate generated tables")

# State the working conventions without presenting them as confirmed problem facts.
text = text.replace(
    "Each ten-minute load or PV power record is the interval-average power, and hourly PV forecasts can be converted to ten-minute energy through a fixed interpolation convention.",
    "Each ten-minute timestamp is treated as the interval end, each power record is treated as the interval-average power, and hourly PV point forecasts are converted to the ten-minute grid by a fixed interpolation convention."
)
text = text.replace(
    "The base case interprets the stated 90% efficiency as a one-way charging efficiency and a one-way discharging efficiency; the symmetric 90% round-trip interpretation is retained as a sensitivity case.",
    "The base case interprets the stated 90% efficiency in each direction and applies the 5,000 kW charge/discharge limit to energy crossing the AC bus; the symmetric 90% round-trip interpretation is retained as a sensitivity case."
)
text = text.replace(
    "At every decision time, the schedule uses only completed actual observations, forecasts already released by that time, the current actual SOC, and price information permitted by the chosen scenario; actual SOC is propagated continuously across days.",
    "At every decision time, the schedule uses only completed actual observations, forecasts already released by that time, the current actual SOC, and causally available price information; actual SOC is propagated continuously across days."
)

text = text.replace(
    "The physical outputs of every question use the same symbols and units defined in Chapter 4.",
    "The physical outputs of every question use the same AC-bus variables q, c, and b and the same internal stored-energy state E defined in Chapter 4. The original commitment is q0, an update produces qk, and the last commitment for an interval is qbar."
)

# Make the planned terminal policy explicit and distinguish it from actual state continuity.
text = text.replace(
    "The final equality is a planning baseline; realized SOC is not reset.",
    "The final equality is an added planning policy for Problems 2-4, not a task requirement. It returns the planned terminal state to that day's initial reference; the actual interval-end SOC is never reset and carries continuously into the next day."
)
text = text.replace(
    "The current measured SOC initializes each update, and the daily midnight SOC is used as the planning terminal reference.",
    "The current measured SOC initializes each update. The planned terminal state is constrained to the original midnight plan's terminal reference as an added policy, while actual interval-end SOC continues without a reset."
)

# Q1 alone restricts disposal to PV. In later fixed-commitment branches paid grid energy may be unused, with no revenue.
text = text.replace(
    "In particular, the surplus-disposal constraint prevents regular grid purchases from being treated as disposable energy.",
    "In Problem 1 alone, the bound w <= forecast PV prevents regular grid purchases from being disposed of. In Problems 2-4, an already paid original or final grid commitment may become unused during causal execution; it is recorded as non-revenue disposal and receives no sale credit."
)

# Preserve raw and corrected totals at full ledger precision.
text = text.replace("CNY 13,772,880.06", "CNY 13,772,880.061223")
text = text.replace("CNY 13,726,733.57", "CNY 13,726,733.574968")
text = text.replace("CNY 14,534,062.64", "CNY 14,534,062.642403")
text = text.replace("CNY 14,492,279.55", "CNY 14,492,279.546435")

# Add complete requested-date tables from the designated corrected ledgers.
q2_tables = representative_tables("results/q2/selected", 5, q2=True)
q3_tables = representative_tables("results/robustness/fixed_w28", 9)
q42_tables = representative_tables("results/q4/q42_ols", 13)
q43_tables = representative_tables("results/robustness/variable_w28", 16)
text = text.replace("### 5.3.6 Model Verification and Sensitivity Analysis", q2_tables + "\n\n### 5.3.6 Model Verification and Sensitivity Analysis")
text = text.replace("**Table 5. Principal Problem 3 comparisons over 334 days**", "**Table 8. Principal Problem 3 comparisons over 334 days**")
text = text.replace("### 5.4.6 Model Verification and Sensitivity Analysis", q3_tables + "\n\n### 5.4.6 Model Verification and Sensitivity Analysis")
text = text.replace("**Table 6. Matched variable-price comparisons over 334 days**", "**Table 12. Matched variable-price comparisons over 334 days**")
text = text.replace("### 5.5.6 Model Verification and Sensitivity Analysis", q42_tables + "\n\n" + q43_tables + "\n\n### 5.5.6 Model Verification and Sensitivity Analysis")

# Clarify table/workbook semantics supplied by the template review.
workbook_note = (
    "The paper table numbers are editorial labels and are distinct from the original Attachment 5 template table names. "
    "In the review workbooks, each timestamp is explicitly labelled from 00:00-00:10 through 23:50-24:00 under the interval-end convention. "
    "EP is the sum of the 144 grid-energy entries. In a plan sheet, EQ is the original midnight scheduled fee and excludes emergency cost; "
    "in an adjusted sheet, EQ is the final rule-A contract fee, including the original charge and revision adjustments, and is not added a second time. "
    "All-in cost equals the applicable contract fee plus the emergency fee, with the components disclosed in the companion cost summary. "
    "These populated files remain internal review outputs pending approval of the assumptions."
)
text = text.replace("# 6 Verification, Sensitivity, and Scope Limits", workbook_note + "\n\n# 6 Verification, Sensitivity, and Scope Limits")

# State the continuous correction chronology and the observed win/loss count.
text = text.replace(
    "This CNY 46,146.49 cumulative gain includes 122 higher-cost days",
    "The continuous 334-day replay uses raw forecasts through March and the correction from April through December. Over those 275 corrected days it records 153 lower-cost days and 122 higher-cost days; July and December are loss months. The CNY 46,146.486255 cumulative gain"
)
text = text.replace(
    "Day-level paired savings are also summarized using consecutive-date block resampling.",
    "Day-level paired savings are also summarized using consecutive-date block resampling. This is a conditional resampling analysis of the observed historical path, not external validation; a full factorial interaction study was not performed."
)

# Number every display equation globally.
counter = 0
def tag_display(m):
    global counter
    counter += 1
    body = m.group(1).strip()
    if "\\tag{" not in body:
        body += f"\n\\tag{{{counter}}}"
    return "$$\n" + body + "\n$$"
text = re.sub(r"\$\$\s*(.*?)\s*\$\$", tag_display, text, flags=re.S)

PAPER.write_text(text, encoding="utf-8")
print(f"updated {PAPER}; numbered {counter} display equations")
