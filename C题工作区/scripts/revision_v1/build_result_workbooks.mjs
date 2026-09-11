import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const work = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const out = path.join(work, 'outputs/revision_v1');
const review = path.join(work, 'reports/revision_v1/workbook_previews');
await fs.mkdir(review, {recursive: true});
const items = JSON.parse(await fs.readFile(path.join(work, 'data/interim/revision_v1/workbook_payload.json'), 'utf8'));
const inspectOnly = process.argv.includes('--inspect-templates');
const inspectSaved = process.argv.includes('--inspect-saved');
const logs = [];
for (const item of items) {
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(inspectSaved ? path.join(out, item.name + '.xlsx') : item.template));
  if (inspectSaved) {
    if (item.name !== 'result1') {
      const blob = await wb.render({sheetName: '计划购电量', range:'EM331:EQ335', scale:1.5, format:'png'});
      await fs.writeFile(path.join(review, `${item.name}_saved_totals.png`), new Uint8Array(await blob.arrayBuffer()));
      const battery = await wb.render({sheetName: '充放电量', range:'A1999:F2005', scale:1.5, format:'png'});
      await fs.writeFile(path.join(review, `${item.name}_saved_last_day.png`), new Uint8Array(await battery.arrayBuffer()));
    }
    continue;
  }
  if (inspectOnly) {
    for (const name of Object.keys(item.sheets)) {
      const region = name === '计划购电量' || name === '调整购电量' ? (item.name === 'result1' ? 'A1:B10' : 'A1:F7') : name === '充放电量' ? (item.name === 'result1' ? 'A1:E7' : 'A1:F8') : 'A1:C8';
      const blob = await wb.render({sheetName: name, range: region, scale: 1.5, format: 'png'});
      await fs.writeFile(path.join(review, `${item.name}_${name}_before.png`), new Uint8Array(await blob.arrayBuffer()));
    }
    continue;
  }
  for (const [name, originalRows] of Object.entries(item.sheets)) {
    const sh = wb.worksheets.getItem(name);
    const rows = originalRows.map(r => [...r]);
    if (item.name !== 'result1') {
      for (const r of rows) r[0] = new Date(r[0] + 'T00:00:00Z');
    }
    const cols = rows[0].length;
    const last = rows.length + 1;
    if (name === '充放电量' && item.name !== 'result1') {
      for (let offset = 7; offset < last; offset += 6) {
        sh.getRangeByIndexes(offset, 0, 6, 6).copyFrom(sh.getRange('A2:F7'), 'all');
      }
    } else if (name === '紧急购电量') {
      for (let offset = 2; offset < last; offset++) {
        sh.getRangeByIndexes(offset, 0, 1, 3).copyFrom(sh.getRange('A2:C2'), 'all');
      }
    }
    // Expand the official example tables, retaining all original sheet names/order.
    sh.getUsedRange().offset(1, 0).clear({applyTo: 'contents'});
    sh.getRangeByIndexes(1, 0, rows.length, cols).values = rows;
    const isGrid = name === '计划购电量' || name === '调整购电量';
    if (item.name !== 'result1') {
      sh.getRange(`A2:A${last}`).setNumberFormat('yyyy-mm-dd');
      sh.getRange(`A1:A${last}`).format.columnWidth = 14;
      sh.getRange(`A2:A${last}`).format.horizontalAlignment = 'center';
    }
    if (isGrid && item.name !== 'result1') {
      sh.getRange('B1:EO1').values = [item.labels];
      sh.getRange('EP2').formulas = [['=SUM(B2:EO2)']];
      sh.getRange(`EP2:EP${last}`).fillDown();
      sh.getRange(`B2:EQ${last}`).setNumberFormat('0.000000');
      sh.getRange(`B1:EO${last}`).format.columnWidth = 15;
      sh.getRange(`EP1:EQ${last}`).format.columnWidth = 20;
    } else if (isGrid) {
      sh.getRange('B2:B145').setNumberFormat('0.000000');
      sh.getRange('A1:B145').format.columnWidth = 20;
    } else {
      const firstNumeric = item.name === 'result1' ? 1 : 2;
      sh.getRangeByIndexes(1, firstNumeric, rows.length, cols - firstNumeric).setNumberFormat('0.000000');
      const timeCol = item.name === 'result1' ? 'D' : 'E';
      if (name === '充放电量') sh.getRange(`${timeCol}2:${timeCol}${last}`).setNumberFormat('@');
      if (name === '充放电量') sh.getRange(`${timeCol}2:${timeCol}${last}`).format.horizontalAlignment = 'center';
      sh.getRangeByIndexes(1, item.name === 'result1' ? 0 : 1, rows.length, 1).format.horizontalAlignment = 'center';
      sh.getRangeByIndexes(0, item.name === 'result1' ? 0 : 1, last, cols - (item.name === 'result1' ? 0 : 1)).format.columnWidth = 18;
    }
    sh.getRangeByIndexes(0, 0, last, cols).format.rowHeight = 22;
    sh.freezePanes.freezeRows(1);
    if (item.name !== 'result1') sh.freezePanes.freezeColumns(1);
  }
  wb.recalculate();
  logs.push({file: item.name, inspection: (await wb.inspect({kind:'table', range: '计划购电量!A1:F4', tableMaxRows:4, tableMaxCols:6, maxChars:1400})).ndjson});
  logs.push({file: item.name, errorScan: (await wb.inspect({kind:'match', searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options:{useRegex:true,maxResults:20}, maxChars:2000})).ndjson});
  for (const name of Object.keys(item.sheets)) {
    const region = name === '计划购电量' || name === '调整购电量' ? (item.name === 'result1' ? 'A1:B10' : 'A1:F7') : name === '充放电量' ? (item.name === 'result1' ? 'A1:E7' : 'A1:F8') : 'A1:C8';
    const blob = await wb.render({sheetName:name, range:region, scale:1.5, format:'png'});
    await fs.writeFile(path.join(review, `${item.name}_${name}_after.png`), new Uint8Array(await blob.arrayBuffer()));
  }
  const xlsx = await SpreadsheetFile.exportXlsx(wb);
  await xlsx.save(path.join(out, item.name + '.xlsx'));
  console.log(`Exported ${item.name}.xlsx`);
}
if (!inspectOnly && !inspectSaved) await fs.writeFile(path.join(review, 'artifact_checks.json'), JSON.stringify(logs, null, 2));
