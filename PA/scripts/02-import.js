/**
 * 02-import.js — Load Public Accounts transfer-payment CSVs into pa.transfer_payments.
 *
 * Older years (2020, 2021) have English-only column headers (12 cols).
 * 2022+ have bilingual headers (19 cols). We map both shapes to the same
 * 13-column target via header lookup.
 *
 * The recipient_name_location field is free text: usually "<NAME>" alone,
 * sometimes "<NAME> - <CITY>", and the city/province/country columns are
 * frequently blank. We extract a normalized name from the start of the
 * field (split on " - " or comma) and store both raw and normalized.
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { from: copyFrom } = require('pg-copy-streams');
const { pool, end } = require('../lib/db');

const RAW_DIR = path.join(__dirname, '..', 'data', 'raw');

// ---------------------------------------------------------------------------
// CSV parser (handles quoted fields with commas/quotes)
// ---------------------------------------------------------------------------

function parseCsvLine(line) {
  const fields = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') { cur += '"'; i++; }
        else inQuotes = false;
      } else cur += ch;
    } else {
      if (ch === '"') inQuotes = true;
      else if (ch === ',') { fields.push(cur); cur = ''; }
      else cur += ch;
    }
  }
  fields.push(cur);
  return fields;
}

function csvEscape(v) {
  if (v == null) return '';
  let s = String(v).replace(/\0/g, '').replace(/\r/g, '');
  if (s.includes('"') || s.includes(',') || s.includes('\n')) s = '"' + s.replace(/"/g, '""') + '"';
  return s;
}
function csvLine(values) { return values.map(csvEscape).join(',') + '\n'; }

function normName(s) {
  if (!s) return null;
  // Recipient line is sometimes "Name - City, Province" — peel off any trailing location.
  let core = s.split(' - ')[0];
  return core.toLowerCase()
    .replace(/^\s*the\s+/, '')
    .replace(/[^a-z0-9 ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim() || null;
}

function parseFiscalYear(s) {
  // "2023/2024" → 2024
  const m = String(s).match(/(\d{4})\s*\/\s*(\d{4})/);
  return m ? parseInt(m[2], 10) : null;
}

function parseAmount(s) {
  if (s == null || s === '') return null;
  const n = Number(String(s).replace(/[^\d.\-]/g, ''));
  return isNaN(n) ? null : n;
}

// ---------------------------------------------------------------------------
// Header → column mapping. Both file shapes share the same English column
// names (the only difference is whether _fra siblings exist).
// ---------------------------------------------------------------------------

const HEADER_MAP = {
  fiscal_year:             'Fscl-yr_Ex-fin',
  ministry_code:           'Min-code',
  ministry_portfolio:      'Min-portfolio_Portefeuille-min_eng',
  department_number:       'Dept-nbr_No-min',
  department_name:         'Dept-name_Nom-min_eng',
  recipient_class:         'Rcpt-class_Cat-bnfcrs_eng',
  recipient_name_location: 'Rcpt-nm-locn_Nm-lieu-bnfcrs_eng',
  city:                    'City_Ville_eng',
  province:                'Prov-Terr_eng',
  country:                 'Country_Pays_eng',
  expenditure_current_yr:  'Xpnd-current-yr_Dep-ex-courant',
  aggregate_payments:      'Aggregate-payments_Versements-totalisant',
};

function buildIndex(header) {
  // Strip BOM from the first cell if present.
  const cleaned = header.map((h) => h.replace(/^﻿/, '').trim());
  const idx = {};
  for (const [k, v] of Object.entries(HEADER_MAP)) {
    idx[k] = cleaned.indexOf(v);
  }
  return idx;
}

// ---------------------------------------------------------------------------
// Process one file: stream lines, map to target columns, write to pg-copy stream
// ---------------------------------------------------------------------------

async function processFile(client, csvPath) {
  const sourceFile = path.basename(csvPath);
  console.log(`→ ${sourceFile}…`);

  const stream = client.query(copyFrom(`
    COPY pa.transfer_payments (
      fiscal_year, fiscal_year_end,
      ministry_code, ministry_portfolio, department_number, department_name,
      recipient_class, recipient_name_location, recipient_name_norm,
      city, province, country,
      expenditure_current_yr, aggregate_payments,
      source_file
    ) FROM STDIN WITH (FORMAT csv, NULL '', QUOTE '"', ESCAPE '"')
  `));

  const rl = readline.createInterface({
    input: fs.createReadStream(csvPath),
    crlfDelay: Infinity,
  });

  let idx = null;
  let lineNo = 0;
  let written = 0;

  return new Promise((resolve, reject) => {
    stream.on('error', reject);

    rl.on('line', (line) => {
      lineNo++;
      if (lineNo === 1) {
        idx = buildIndex(parseCsvLine(line));
        const missing = Object.entries(idx).filter(([, v]) => v === -1).map(([k]) => k);
        if (missing.length) {
          reject(new Error(`${sourceFile}: missing columns ${missing.join(', ')}`));
        }
        return;
      }
      const f = parseCsvLine(line);
      const fy = f[idx.fiscal_year];
      const recipient = f[idx.recipient_name_location];
      const row = [
        fy,
        parseFiscalYear(fy),
        f[idx.ministry_code] || '',
        f[idx.ministry_portfolio] || '',
        f[idx.department_number] || '',
        f[idx.department_name] || '',
        f[idx.recipient_class] || '',
        recipient || '',
        normName(recipient) || '',
        f[idx.city] || '',
        f[idx.province] || '',
        f[idx.country] || '',
        parseAmount(f[idx.expenditure_current_yr]),
        parseAmount(f[idx.aggregate_payments]),
        sourceFile,
      ];
      const csv = csvLine(row);
      if (!stream.write(csv)) {
        rl.pause();
        stream.once('drain', () => rl.resume());
      }
      written++;
    });

    rl.on('close', () => {
      stream.end();
      stream.on('finish', () => {
        console.log(`  ✓ ${written.toLocaleString()} rows`);
        resolve(written);
      });
    });
    rl.on('error', reject);
  });
}

async function main() {
  const files = fs.readdirSync(RAW_DIR)
    .filter((f) => /^pt-tp-\d{4}\.csv$/.test(f))
    .sort();
  if (!files.length) {
    console.error('No pt-tp-*.csv files in', RAW_DIR);
    process.exit(1);
  }

  console.log(`→ Loading ${files.length} fiscal year files…`);

  const client = await pool.connect();
  let total = 0;
  try {
    for (const f of files) {
      total += await processFile(client, path.join(RAW_DIR, f));
    }
    console.log('\n→ ANALYZE…');
    await client.query('ANALYZE pa.transfer_payments;');
  } finally {
    client.release();
  }
  await end();
  console.log(`\nDone. ${total.toLocaleString()} total rows.`);
}

main().catch((err) => {
  console.error('Import failed:', err.message);
  console.error(err.stack);
  process.exit(1);
});
