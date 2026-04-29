/**
 * 02-import.js — Bulk-load the four key OCL CSVs into the lobby schema.
 *
 * Strategy:
 *   1. Stream each CSV through a transform that rewrites the literal string
 *      "null" to empty, normalizes dates, and quotes fields safely.
 *   2. Pipe into Postgres via COPY FROM STDIN (CSV format).
 *   3. After loading, run a SQL pass that populates client_name_norm and
 *      client_org_corp_num_int.
 *
 * Source CSVs (under LOBBY/data/csv/):
 *   - Registration_PrimaryExport.csv          → lobby_registrations
 *   - Registration_GovtFundingExport.csv      → lobby_govt_funding
 *   - Communication_PrimaryExport.csv         → lobby_communications
 *   - Communication_DpohExport.csv            → lobby_communication_dpoh
 */

const fs = require('fs');
const path = require('path');
const { from: copyFrom } = require('pg-copy-streams');
const { pool, end } = require('../lib/db');

const CSV_DIR = path.join(__dirname, '..', 'data', 'csv');

// Column order MUST match the schema column order for the COPY target.
const TABLES = [
  {
    table: 'lobby.lobby_registrations',
    csv: 'Registration_PrimaryExport.csv',
    // The CSV has 38 columns. Our table has 38 source columns + 2 derived
    // (client_name_norm, client_org_corp_num_int) which we leave NULL here
    // and populate in the post-load pass. So we COPY into the 38 source cols.
    columns: [
      'reg_id', 'reg_type', 'reg_num', 'version_code',
      'firm_name_en', 'firm_name_fr', 'registrant_position', 'firm_address', 'firm_tel', 'firm_fax',
      'registrant_num', 'registrant_last_nm', 'registrant_first_nm', 'ro_position',
      'registrant_address', 'registrant_tel', 'registrant_fax',
      'client_org_corp_profile_id', 'client_org_corp_num',
      'client_name_en', 'client_name_fr',
      'client_address', 'client_tel', 'client_fax',
      'rep_last_nm', 'rep_first_nm', 'rep_position',
      'effective_date', 'end_date',
      'parent_ind', 'coalition_ind', 'subsidiary_ind', 'direct_int_ind', 'govt_fund_ind',
      'fy_end_date', 'contg_fee_ind', 'prev_reg_id', 'posted_date',
    ],
  },
  {
    table: 'lobby.lobby_govt_funding',
    csv: 'Registration_GovtFundingExport.csv',
    columns: [
      'reg_id', 'institution', 'amount', 'funds_expected', 'text_description', 'amend_sub_date',
    ],
  },
  {
    table: 'lobby.lobby_communications',
    csv: 'Communication_PrimaryExport.csv',
    columns: [
      'comlog_id', 'client_org_corp_num', 'client_name_en', 'client_name_fr',
      'registrant_num', 'registrant_last_nm', 'registrant_first_nm',
      'comm_date', 'reg_type', 'submission_date', 'posted_date', 'prev_comlog_id',
    ],
  },
  {
    table: 'lobby.lobby_communication_dpoh',
    csv: 'Communication_DpohExport.csv',
    columns: [
      'comlog_id', 'dpoh_last_nm', 'dpoh_first_nm', 'dpoh_title',
      'branch_unit', 'other_institution', 'institution',
    ],
  },
];

/**
 * Stream-rewrite a CSV so:
 *   - the literal field "null" (after CSV-quote stripping) becomes empty
 *   - the header row is dropped (we use COPY ... HEADER, but that fails if
 *     the source had quoted columns and pg has different column order, so
 *     we strip header here and use COPY without HEADER)
 *
 * Postgres COPY ... CSV NULL '' should treat empty fields as NULL.
 */
function transformCsv(srcPath, destStream) {
  return new Promise((resolve, reject) => {
    const reader = require('readline').createInterface({
      input: fs.createReadStream(srcPath),
      crlfDelay: Infinity,
    });

    let isHeader = true;
    let lineCount = 0;
    let writeCount = 0;

    reader.on('line', (line) => {
      if (isHeader) { isHeader = false; return; }
      lineCount++;
      // Replace the OCL convention "null" (literal quoted four-character
      // string) with an UNQUOTED empty so Postgres COPY ... NULL '' reads
      // it as SQL NULL. A quoted "" would coerce to '' (empty string), which
      // breaks date columns.
      const cleaned = line.replace(/"null"/g, '');
      if (!destStream.write(cleaned + '\n')) {
        reader.pause();
        destStream.once('drain', () => reader.resume());
      }
      writeCount++;
    });

    reader.on('close', () => {
      destStream.end();
    });
    reader.on('error', reject);
    destStream.on('finish', () => resolve({ lineCount, writeCount }));
    destStream.on('error', reject);
  });
}

async function copyTable(client, { table, csv, columns }) {
  const srcPath = path.join(CSV_DIR, csv);
  if (!fs.existsSync(srcPath)) {
    throw new Error(`Missing CSV: ${srcPath}`);
  }
  const stat = fs.statSync(srcPath);
  console.log(`\n→ ${table}  (source: ${csv}, ${(stat.size / 1024 / 1024).toFixed(1)} MB)`);

  const sql = `COPY ${table} (${columns.join(', ')}) FROM STDIN WITH (FORMAT csv, NULL '', QUOTE '"', ESCAPE '"')`;
  const stream = client.query(copyFrom(sql));

  const start = Date.now();
  const { lineCount } = await transformCsv(srcPath, stream);
  const ms = Date.now() - start;
  console.log(`  loaded ${lineCount.toLocaleString()} rows in ${(ms / 1000).toFixed(1)}s`);
}

async function postLoad(client) {
  console.log('\n→ Populating derived columns…');

  // Postgres helper: lower + strip leading "THE ", strip trailing punctuation,
  // collapse whitespace. Lighter than general.norm_name() but compatible.
  const normSql = `
    UPDATE lobby.lobby_registrations
       SET client_name_norm = NULLIF(
             regexp_replace(
               regexp_replace(
                 lower(coalesce(client_name_en, client_name_fr, '')),
                 '^the\\s+', '', 'i'
               ),
               '[^a-z0-9 ]+', ' ', 'g'
             ),
             ''
           ),
           client_org_corp_num_int = NULLIF(client_org_corp_num, '')::BIGINT;
  `;
  await client.query(normSql);
  console.log('  ✓ lobby_registrations client_name_norm populated');

  await client.query(`
    UPDATE lobby.lobby_communications
       SET client_name_norm = NULLIF(
             regexp_replace(
               regexp_replace(
                 lower(coalesce(client_name_en, client_name_fr, '')),
                 '^the\\s+', '', 'i'
               ),
               '[^a-z0-9 ]+', ' ', 'g'
             ),
             ''
           ),
           client_org_corp_num_int = NULLIF(client_org_corp_num, '')::BIGINT;
  `);
  console.log('  ✓ lobby_communications client_name_norm populated');

  await client.query('ANALYZE lobby.lobby_registrations;');
  await client.query('ANALYZE lobby.lobby_govt_funding;');
  await client.query('ANALYZE lobby.lobby_communications;');
  await client.query('ANALYZE lobby.lobby_communication_dpoh;');
  console.log('  ✓ ANALYZE complete');
}

async function main() {
  const client = await pool.connect();
  try {
    for (const t of TABLES) {
      await copyTable(client, t);
    }
    await postLoad(client);
  } finally {
    client.release();
  }
  await end();
  console.log('\nDone.');
}

main().catch((err) => {
  console.error('Import failed:', err.message);
  console.error(err.stack);
  process.exit(1);
});
