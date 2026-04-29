/**
 * 02-import.js — Two-phase loader for the Federal Corporations Registry.
 *
 * Phase 1: stream-parse the 103 OPEN_DATA_*.xml files and write three CSV
 *          files to data/staging/. SAX is used for O(1)-memory parsing.
 *
 * Phase 2: drop indexes on the history tables (they kill COPY throughput),
 *          run COPY FROM STDIN for each CSV, then recreate the indexes.
 *
 * The two-phase approach is much faster than streaming directly into Postgres
 * because (a) all three target tables can be loaded sequentially without
 * juggling multiplexed streams, (b) Postgres COPY from a complete file is
 * close to disk-I/O-bound, and (c) bulk index creation on a populated table
 * is faster than per-row btree maintenance.
 */

const fs = require('fs');
const path = require('path');
const sax = require('sax');
const { from: copyFrom } = require('pg-copy-streams');
const { pool, end } = require('../lib/db');

const XML_DIR = path.join(__dirname, '..', 'data', 'xml');
const STAGING_DIR = path.join(__dirname, '..', 'data', 'staging');
const CODES_PATH = path.join(XML_DIR, 'codes.xml');

const STAGING_FILES = {
  corporations: path.join(STAGING_DIR, 'corporations.csv'),
  statusHistory: path.join(STAGING_DIR, 'status_history.csv'),
  nameHistory:   path.join(STAGING_DIR, 'name_history.csv'),
};

// ---------------------------------------------------------------------------
// Codes (status / act labels)
// ---------------------------------------------------------------------------

function loadCodes() {
  const xml = fs.readFileSync(CODES_PATH, 'utf8');
  const parser = sax.parser(true);
  const codes = { status: {}, act: {}, activity: {} };
  let currentCodeName = null;
  let currentKey = null;
  let currentLang = null;
  let inFull = false;
  let textBuf = '';

  parser.onopentag = (node) => {
    if (node.name === 'code') currentCodeName = node.attributes.name;
    else if (node.name === 'key' && currentCodeName) currentKey = parseInt(node.attributes.value, 10);
    else if (node.name === 'full' && currentKey != null) {
      currentLang = node.attributes['xml:lang'] || node.attributes.lang;
      inFull = true; textBuf = '';
    }
  };
  parser.ontext = (text) => { if (inFull) textBuf += text; };
  parser.onclosetag = (name) => {
    if (name === 'full' && inFull) {
      if (currentLang === 'en' && codes[currentCodeName]) {
        codes[currentCodeName][currentKey] = textBuf.trim();
      }
      inFull = false;
    } else if (name === 'key') currentKey = null;
    else if (name === 'code') currentCodeName = null;
  };
  parser.write(xml).close();
  return codes;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function csvEscape(v) {
  if (v == null) return '';
  let s = String(v).replace(/\0/g, '').replace(/\r/g, '');
  if (s.includes('"') || s.includes(',') || s.includes('\n')) s = '"' + s.replace(/"/g, '""') + '"';
  return s;
}
function csvLine(values) { return values.map(csvEscape).join(',') + '\n'; }
function normName(s) {
  if (!s) return null;
  return s.toLowerCase().replace(/^\s*the\s+/, '').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim() || null;
}
function parseDate(ts) { return ts ? ts.slice(0, 10) : null; }

// ---------------------------------------------------------------------------
// Phase 1 — XML → CSV
// ---------------------------------------------------------------------------

function processFile(xmlPath, codes, sinks, counters) {
  return new Promise((resolve, reject) => {
    const parser = sax.createStream(true, { trim: false });

    let corp = null;
    let textBuf = '';
    let currentName = null;
    let currentAddress = null;
    let directorLimit = null;

    parser.on('opentag', (node) => {
      const a = node.attributes;
      switch (node.name) {
        case 'corporation':
          corp = {
            corporation_id: parseInt(a.corporationId, 10),
            current_name: null, current_name_norm: null,
            current_status_code: null, current_status_label: null, current_status_date: null,
            current_act_code: null, current_act_label: null,
            incorporation_date: null, dissolution_date: null, intent_to_dissolve_date: null,
            last_annual_return_year: null, last_annual_return_date: null,
            current_address_line: null, current_city: null, current_province: null,
            current_country: null, current_postal_code: null,
            business_number: null, director_min: null, director_max: null,
            _names: [],
            _earliestActivity1: null, _latestActivity101: null, _latestActivity14: null,
            _earliestAnnualMeeting: null, _latestAnnualReturn: null,
          };
          break;
        case 'annualReturn': {
          if (!corp) break;
          const year = a.yearOfFiling ? parseInt(a.yearOfFiling, 10) : null;
          const dateStr = parseDate(a.annualMeetingDate);
          if (year != null && (corp._latestAnnualReturn == null || year > corp._latestAnnualReturn.year)) {
            corp._latestAnnualReturn = { year, date: dateStr };
          }
          if (dateStr && (corp._earliestAnnualMeeting == null || dateStr < corp._earliestAnnualMeeting)) {
            corp._earliestAnnualMeeting = dateStr;
          }
          break;
        }
        case 'act':
          if (corp && a.current === 'true') {
            corp.current_act_code = parseInt(a.code, 10);
            corp.current_act_label = codes.act[corp.current_act_code] || null;
          }
          break;
        case 'status': {
          if (!corp) break;
          const code = parseInt(a.code, 10);
          const label = codes.status[code] || null;
          const eff = a.effectiveDate || '';
          const isCurrent = a.current === 'true';
          if (isCurrent) {
            corp.current_status_code = code;
            corp.current_status_label = label;
            corp.current_status_date = parseDate(a.effectiveDate);
          }
          sinks.statusHistory.write(csvLine([corp.corporation_id, code, label, eff, isCurrent ? 't' : 'f']));
          counters.statusHistory++;
          break;
        }
        case 'activity': {
          if (!corp) break;
          const code = parseInt(a.code, 10);
          const dateStr = parseDate(a.date);
          if (!dateStr) break;
          if (code === 1) {
            if (corp._earliestActivity1 == null || dateStr < corp._earliestActivity1) corp._earliestActivity1 = dateStr;
          } else if (code === 101) {
            if (corp._latestActivity101 == null || dateStr > corp._latestActivity101) corp._latestActivity101 = dateStr;
          } else if (code === 14) {
            if (corp._latestActivity14 == null || dateStr > corp._latestActivity14) corp._latestActivity14 = dateStr;
          }
          break;
        }
        case 'name':
          if (!corp) break;
          currentName = {
            text: '',
            effective_date: a.effectiveDate || null,
            expiry_date: a.expiryDate || null,
            is_current: a.current === 'true',
          };
          textBuf = '';
          break;
        case 'address':
          if (!corp) break;
          currentAddress = { isCurrent: a.current === 'true', lines: [], city: null, province: null, country: null, postal: null };
          break;
        case 'addressLine':
        case 'city':
        case 'postalCode':
        case 'businessNumber':
        case 'minimum':
        case 'maximum':
          textBuf = '';
          break;
        case 'province':
          if (currentAddress) currentAddress.province = a.code || null;
          break;
        case 'country':
          if (currentAddress) currentAddress.country = a.code || null;
          break;
        case 'directorLimit':
          if (a.current === 'true') directorLimit = { min: null, max: null };
          break;
      }
    });

    parser.on('text', (t) => { textBuf += t; });
    parser.on('cdata', (t) => { textBuf += t; });

    parser.on('closetag', (name) => {
      const trimmed = textBuf.trim();
      switch (name) {
        case 'name':
          if (corp && currentName) {
            currentName.text = trimmed;
            corp._names.push(currentName);
            if (currentName.is_current) {
              corp.current_name = currentName.text;
              corp.current_name_norm = normName(currentName.text);
            }
            sinks.nameHistory.write(csvLine([
              corp.corporation_id,
              currentName.text,
              normName(currentName.text) || '',
              currentName.effective_date || '',
              currentName.expiry_date || '',
              currentName.is_current ? 't' : 'f',
            ]));
            counters.nameHistory++;
            currentName = null;
          }
          break;
        case 'addressLine': if (currentAddress) currentAddress.lines.push(trimmed); break;
        case 'city':        if (currentAddress) currentAddress.city = trimmed || null; break;
        case 'postalCode':  if (currentAddress) currentAddress.postal = trimmed || null; break;
        case 'address':
          if (corp && currentAddress) {
            if (currentAddress.isCurrent) {
              corp.current_address_line = currentAddress.lines.join(', ') || null;
              corp.current_city = currentAddress.city;
              corp.current_province = currentAddress.province;
              corp.current_country = currentAddress.country;
              corp.current_postal_code = currentAddress.postal;
            }
            currentAddress = null;
          }
          break;
        case 'businessNumber':
          if (corp && !corp.business_number && trimmed) corp.business_number = trimmed;
          break;
        case 'minimum': if (directorLimit) directorLimit.min = parseInt(trimmed, 10); break;
        case 'maximum': if (directorLimit) directorLimit.max = parseInt(trimmed, 10); break;
        case 'directorLimit':
          if (corp && directorLimit) {
            corp.director_min = directorLimit.min;
            corp.director_max = directorLimit.max;
            directorLimit = null;
          }
          break;
        case 'corporation': {
          if (!corp) break;
          if (!corp.current_name && corp._names.length) {
            corp._names.sort((a, b) => (a.effective_date || '').localeCompare(b.effective_date || ''));
            const last = corp._names[corp._names.length - 1];
            corp.current_name = last.text;
            corp.current_name_norm = normName(last.text);
          }
          corp.incorporation_date = corp._earliestActivity1 || corp._earliestAnnualMeeting || null;
          corp.dissolution_date = corp._latestActivity101 || null;
          corp.intent_to_dissolve_date = corp._latestActivity14 || null;
          if (corp._latestAnnualReturn) {
            corp.last_annual_return_year = corp._latestAnnualReturn.year;
            corp.last_annual_return_date = corp._latestAnnualReturn.date;
          }
          sinks.corporations.write(csvLine([
            corp.corporation_id,
            corp.current_name || '',
            corp.current_name_norm || '',
            corp.current_status_code ?? '',
            corp.current_status_label || '',
            corp.current_status_date || '',
            corp.current_act_code ?? '',
            corp.current_act_label || '',
            corp.incorporation_date || '',
            corp.dissolution_date || '',
            corp.intent_to_dissolve_date || '',
            corp.last_annual_return_year ?? '',
            corp.last_annual_return_date || '',
            corp.current_address_line || '',
            corp.current_city || '',
            corp.current_province || '',
            corp.current_country || '',
            corp.current_postal_code || '',
            corp.business_number || '',
            corp.director_min ?? '',
            corp.director_max ?? '',
          ]));
          counters.corporations++;
          corp = null;
          break;
        }
      }
      textBuf = '';
    });

    parser.on('error', reject);
    parser.on('end', resolve);
    fs.createReadStream(xmlPath).pipe(parser);
  });
}

async function phase1WriteCsvs() {
  fs.mkdirSync(STAGING_DIR, { recursive: true });

  const sinks = {
    corporations: fs.createWriteStream(STAGING_FILES.corporations),
    statusHistory: fs.createWriteStream(STAGING_FILES.statusHistory),
    nameHistory:   fs.createWriteStream(STAGING_FILES.nameHistory),
  };

  const codes = loadCodes();
  console.log(`→ Codes loaded (status: ${Object.keys(codes.status).length}, act: ${Object.keys(codes.act).length}).`);

  const files = fs.readdirSync(XML_DIR)
    .filter((f) => /^OPEN_DATA_\d+\.xml$/.test(f))
    .sort((a, b) => parseInt(a.match(/\d+/)[0], 10) - parseInt(b.match(/\d+/)[0], 10));
  console.log(`→ Phase 1: parsing ${files.length} XML chunks → CSV staging files…`);

  const counters = { corporations: 0, statusHistory: 0, nameHistory: 0 };
  const startedAt = Date.now();
  let lastReport = startedAt;

  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    await processFile(path.join(XML_DIR, f), codes, sinks, counters);
    if (Date.now() - lastReport > 3000 || i === files.length - 1) {
      const elapsed = ((Date.now() - startedAt) / 1000).toFixed(1);
      console.log(`  [${i + 1}/${files.length}] ${f}  · corps=${counters.corporations.toLocaleString()}  status=${counters.statusHistory.toLocaleString()}  names=${counters.nameHistory.toLocaleString()}  · elapsed=${elapsed}s`);
      lastReport = Date.now();
    }
  }

  await Promise.all(Object.values(sinks).map((s) => new Promise((res, rej) => {
    s.end(() => res());
    s.on('error', rej);
  })));

  console.log('  ✓ CSVs written:');
  for (const [k, p] of Object.entries(STAGING_FILES)) {
    const sz = fs.statSync(p).size;
    console.log(`    ${k.padEnd(15)}  ${(sz / 1024 / 1024).toFixed(1)} MB  → ${p}`);
  }
  return counters;
}

// ---------------------------------------------------------------------------
// Phase 2 — CSV → Postgres COPY
// ---------------------------------------------------------------------------

const HISTORY_INDEXES_DROP = `
  DROP INDEX IF EXISTS corp.idx_corp_sh_corp_id;
  DROP INDEX IF EXISTS corp.idx_corp_sh_status;
  DROP INDEX IF EXISTS corp.idx_corp_nh_corp_id;
  DROP INDEX IF EXISTS corp.idx_corp_nh_name_norm;
`;

const HISTORY_INDEXES_CREATE = `
  CREATE INDEX idx_corp_sh_corp_id   ON corp.corp_status_history (corporation_id);
  CREATE INDEX idx_corp_sh_status    ON corp.corp_status_history (status_code);
  CREATE INDEX idx_corp_nh_corp_id   ON corp.corp_name_history (corporation_id);
  CREATE INDEX idx_corp_nh_name_norm ON corp.corp_name_history (name_norm);
`;

async function copyCsvToTable(client, csvPath, sql, label) {
  console.log(`→ COPY ${label} (${(fs.statSync(csvPath).size / 1024 / 1024).toFixed(1)} MB)…`);
  const t0 = Date.now();
  const stream = client.query(copyFrom(sql));
  await new Promise((res, rej) => {
    fs.createReadStream(csvPath).pipe(stream).on('finish', res).on('error', rej);
    stream.on('error', rej);
  });
  console.log(`  ✓ ${label} loaded in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}

async function phase2LoadDb() {
  const client = await pool.connect();
  try {
    console.log('\n→ Phase 2a: dropping history-table indexes for fast bulk load…');
    await client.query(HISTORY_INDEXES_DROP);
    console.log('  ✓ done');

    console.log('\n→ Phase 2b: COPY into Postgres…');
    await copyCsvToTable(client, STAGING_FILES.corporations, `
      COPY corp.corp_corporations (
        corporation_id, current_name, current_name_norm,
        current_status_code, current_status_label, current_status_date,
        current_act_code, current_act_label,
        incorporation_date, dissolution_date, intent_to_dissolve_date,
        last_annual_return_year, last_annual_return_date,
        current_address_line, current_city, current_province, current_country, current_postal_code,
        business_number, director_min, director_max
      ) FROM STDIN WITH (FORMAT csv, NULL '', QUOTE '"', ESCAPE '"')
    `, 'corp_corporations');

    await copyCsvToTable(client, STAGING_FILES.statusHistory, `
      COPY corp.corp_status_history (corporation_id, status_code, status_label, effective_date, is_current)
      FROM STDIN WITH (FORMAT csv, NULL '', QUOTE '"', ESCAPE '"')
    `, 'corp_status_history');

    await copyCsvToTable(client, STAGING_FILES.nameHistory, `
      COPY corp.corp_name_history (corporation_id, name, name_norm, effective_date, expiry_date, is_current)
      FROM STDIN WITH (FORMAT csv, NULL '', QUOTE '"', ESCAPE '"')
    `, 'corp_name_history');

    console.log('\n→ Phase 2c: rebuilding history indexes…');
    const t0 = Date.now();
    await client.query(HISTORY_INDEXES_CREATE);
    console.log(`  ✓ done in ${((Date.now() - t0) / 1000).toFixed(1)}s`);

    console.log('\n→ Phase 2d: ANALYZE…');
    await client.query('ANALYZE corp.corp_corporations;');
    await client.query('ANALYZE corp.corp_status_history;');
    await client.query('ANALYZE corp.corp_name_history;');
    console.log('  ✓ done');
  } finally {
    client.release();
  }
}

// ---------------------------------------------------------------------------
// Driver
// ---------------------------------------------------------------------------

async function main() {
  const startedAt = Date.now();

  // If staging CSVs already exist and are non-empty, skip Phase 1 (resume mode).
  const skipPhase1 = Object.values(STAGING_FILES).every((p) => {
    try { return fs.statSync(p).size > 0; } catch { return false; }
  });
  if (skipPhase1) {
    console.log('→ Phase 1: SKIPPED (staging CSVs already exist; delete data/staging/ to force re-parse).');
  } else {
    await phase1WriteCsvs();
  }

  await phase2LoadDb();
  await end();

  console.log(`\nDone in ${((Date.now() - startedAt) / 1000).toFixed(1)}s.`);
}

main().catch((err) => {
  console.error('Import failed:', err.message);
  console.error(err.stack);
  process.exit(1);
});
