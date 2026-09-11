import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const out = path.join(root, 'outputs/unified_direct_v5');
const previewDir = path.join(root, 'reports/unified_direct_v5/workbook_previews');
const payloadPath = path.join(out, 'workbook_payload.json');
const inspectTemplates = process.argv.includes('--inspect-templates');
const inspectSaved = process.argv.includes('--inspect-saved');

await fs.mkdir(previewDir, {recursive: true});
const items = JSON.parse(await fs.readFile(payloadPath, 'utf8'));
const checks = [];

function reviewRange(itemName, sheetName) {
  if (itemName === 'result1') return sheetName === '计划购电量' ? 'A1:B12' : 'A1:E7';
  if (sheetName === '计划购电量' || sheetName === '调整购电量') return 'A1:F7';
  if (sheetName === '充放电量') return 'A1:F8';
  return 'A1:C10';
}

async function savePreview(workbook, itemName, sheetName, suffix, range) {
  const blob = await workbook.render({sheetName, range, scale: 1.5, format: 'png'});
  const safe = sheetName.replaceAll('/', '_');
  await fs.writeFile(path.join(previewDir, `${itemName}_${safe}_${suffix}.png`), new Uint8Array(await blob.arrayBuffer()));
}

for (const item of items) {
  const source = inspectSaved ? path.join(out, `${item.name}.xlsx`) : item.template;
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
  if (inspectTemplates) {
    for (const sheetName of Object.keys(item.sheets)) {
      await savePreview(workbook, item.name, sheetName, 'before', reviewRange(item.name, sheetName));
    }
    continue;
  }
  if (inspectSaved) {
    for (const sheetName of Object.keys(item.sheets)) {
      await savePreview(workbook, item.name, sheetName, 'saved', reviewRange(item.name, sheetName));
      if (item.name !== 'result1' && (sheetName === '计划购电量' || sheetName === '调整购电量')) {
        await savePreview(workbook, item.name, sheetName, 'saved_totals', 'EM1:EQ7');
        await savePreview(workbook, item.name, sheetName, 'saved_tail', 'EM330:EQ335');
      }
      if (item.name !== 'result1' && sheetName === '充放电量') {
        await savePreview(workbook, item.name, sheetName, 'saved_tail', 'A1998:F2005');
      }
    }
    continue;
  }

  for (const [sheetName, originalRows] of Object.entries(item.sheets)) {
    const sheet = workbook.worksheets.getItem(sheetName);
    const rows = originalRows.map(row => [...row]);
    if (item.name !== 'result1') {
      for (const row of rows) row[0] = new Date(`${row[0]}T00:00:00Z`);
    }
    const columns = rows[0].length;
    const lastRow = rows.length + 1;
    if (sheetName === '充放电量' && item.name !== 'result1') {
      for (let start = 7; start < lastRow; start += 6) {
        sheet.getRangeByIndexes(start, 0, Math.min(6, lastRow - start), 6).copyFrom(
          sheet.getRangeByIndexes(1, 0, Math.min(6, lastRow - start), 6), 'all'
        );
      }
    } else if (sheetName === '紧急购电量') {
      for (let start = 2; start < lastRow; start += 1) {
        sheet.getRangeByIndexes(start, 0, 1, 3).copyFrom(sheet.getRange('A2:C2'), 'all');
      }
    }
    sheet.getUsedRange().offset(1, 0).clear({applyTo: 'contents'});
    sheet.getRangeByIndexes(1, 0, rows.length, columns).values = rows;
    const isGrid = sheetName === '计划购电量' || sheetName === '调整购电量';
    if (item.name !== 'result1') {
      sheet.getRange(`A2:A${lastRow}`).setNumberFormat('yyyy-mm-dd');
      sheet.getRange(`A1:A${lastRow}`).format.columnWidth = 14;
      sheet.getRange(`A2:A${lastRow}`).format.horizontalAlignment = 'center';
    }
    if (isGrid && item.name !== 'result1') {
      sheet.getRange('B1:EO1').values = [item.labels];
      sheet.getRange('EP2').formulas = [['=SUM(B2:EO2)']];
      sheet.getRange(`EP2:EP${lastRow}`).fillDown();
      sheet.getRange(`B2:EQ${lastRow}`).setNumberFormat('0.000000');
      sheet.getRange(`B1:EO${lastRow}`).format.columnWidth = 15;
      sheet.getRange(`EP1:EQ${lastRow}`).format.columnWidth = 20;
      sheet.freezePanes.freezeRows(1);
      sheet.freezePanes.freezeColumns(1);
    } else if (isGrid) {
      sheet.getRange('B2:B145').setNumberFormat('0.000000');
      sheet.getRange('A1:B145').format.columnWidth = 20;
      sheet.freezePanes.freezeRows(1);
    } else {
      const firstNumeric = item.name === 'result1' ? 1 : 2;
      sheet.getRangeByIndexes(1, firstNumeric, rows.length, columns - firstNumeric).setNumberFormat('0.000000');
      if (sheetName === '充放电量') {
        const timeColumn = item.name === 'result1' ? 'D' : 'E';
        sheet.getRange(`${timeColumn}2:${timeColumn}${lastRow}`).setNumberFormat('@');
        sheet.getRange(`${timeColumn}2:${timeColumn}${lastRow}`).format.horizontalAlignment = 'center';
      }
      const labelColumn = item.name === 'result1' ? 0 : 1;
      sheet.getRangeByIndexes(1, labelColumn, rows.length, 1).format.horizontalAlignment = 'center';
      sheet.getRangeByIndexes(0, labelColumn, lastRow, columns - labelColumn).format.columnWidth = 18;
      sheet.freezePanes.freezeRows(1);
      if (item.name !== 'result1') sheet.freezePanes.freezeColumns(1);
    }
    sheet.getRangeByIndexes(0, 0, lastRow, columns).format.rowHeight = 22;
  }

  workbook.recalculate();
  checks.push({
    file: `${item.name}.xlsx`,
    plan: (await workbook.inspect({kind: 'table', range: '计划购电量!A1:F4', include: 'values,formulas', tableMaxRows: 4, tableMaxCols: 6, maxChars: 1800})).ndjson,
    formulas: (await workbook.inspect({kind: 'formula', sheetId: '计划购电量', range: item.name === 'result1' ? 'A1:B145' : 'EP1:EQ335', options: {maxResults: 340}, maxChars: 6000})).ndjson,
    errors: (await workbook.inspect({kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: {useRegex: true, maxResults: 100}, maxChars: 5000})).ndjson,
  });
  for (const sheetName of Object.keys(item.sheets)) {
    await savePreview(workbook, item.name, sheetName, 'after', reviewRange(item.name, sheetName));
    if (item.name !== 'result1' && (sheetName === '计划购电量' || sheetName === '调整购电量')) {
      await savePreview(workbook, item.name, sheetName, 'after_totals', 'EM1:EQ7');
    }
  }
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(path.join(out, `${item.name}.xlsx`));
  console.log(`exported ${item.name}.xlsx (${item.strategy})`);
}

if (!inspectTemplates && !inspectSaved) {
  await fs.writeFile(path.join(previewDir, 'artifact_checks.json'), JSON.stringify(checks, null, 2));
}
