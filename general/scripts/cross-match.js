/**
 * cross-match.js - Batch fuzzy cross-matching between datasets.
 *
 * Finds entities that appear across multiple Alberta datasets (and optionally
 * CRA/FED) using trigram similarity.
 *
 * Usage:
 *   node scripts/cross-match.js                          # Default: non-profit vs grants
 *   node scripts/cross-match.js --threshold 0.7 --limit 50
 *
 * Outputs: reports/cross-match-results.json and .txt
 */
const fs = require('fs');
const path = require('path');
const { pool } = require('../lib/db');
const { FuzzyMatcher } = require('../lib/fuzzy-match');

const REPORTS_DIR = path.join(__dirname, '..', 'reports');

function parseArgs() {
  const args = { threshold: 0.6, limit: 200 };
  for (let i = 2; i < process.argv.length; i++) {
    if (process.argv[i] === '--threshold' && process.argv[i + 1]) {
      args.threshold = parseFloat(process.argv[++i]);
    } else if (process.argv[i] === '--limit' && process.argv[i + 1]) {
      args.limit = parseInt(process.argv[++i]);
    }
  }
  return args;
}

async function run() {
  const args = parseArgs();
  const matcher = new FuzzyMatcher(pool);
  await matcher.initialize();

  const report = { generated: new Date().toISOString(), threshold: args.threshold, matches: {} };
  const lines = ['CROSS-DATASET FUZZY MATCHING REPORT', '='.repeat(70), ''];

  console.log('Cross-dataset fuzzy matching...');
  console.log(`Threshold: ${args.threshold}, Limit: ${args.limit}\n`);

  // Match 1: AB Non-profits vs AB Grants recipients
  console.log('1. Non-profits vs Grant recipients (fuzzy)...');
  const npGrants = await matcher.batchCrossMatch(
    'ab.ab_non_profit', 'legal_name',
    'ab.ab_grants', 'recipient',
    { threshold: args.threshold, limit: args.limit }
  );
  report.matches.non_profit_vs_grants = npGrants;
  lines.push(`1. NON-PROFITS vs GRANT RECIPIENTS (threshold ${args.threshold})`, '-'.repeat(50));
  lines.push(`Found ${npGrants.length} fuzzy matches (not exact):\n`);
  for (const r of npGrants.slice(0, 50)) {
    lines.push(`  [${(parseFloat(r.sim) * 100).toFixed(0)}%] "${r.source_name}" <-> "${r.target_name}"`);
  }

  // Match 2: AB Sole-source vendors vs AB Contract recipients
  console.log('2. Sole-source vendors vs Contract recipients (fuzzy)...');
  const ssContracts = await matcher.batchCrossMatch(
    'ab.ab_sole_source', 'vendor',
    'ab.ab_contracts', 'recipient',
    { threshold: args.threshold, limit: args.limit }
  );
  report.matches.sole_source_vs_contracts = ssContracts;
  lines.push(`\n\n2. SOLE-SOURCE VENDORS vs CONTRACT RECIPIENTS (threshold ${args.threshold})`, '-'.repeat(50));
  lines.push(`Found ${ssContracts.length} fuzzy matches:\n`);
  for (const r of ssContracts.slice(0, 50)) {
    lines.push(`  [${(parseFloat(r.sim) * 100).toFixed(0)}%] "${r.source_name}" <-> "${r.target_name}"`);
  }

  // Match 3: AB Grant recipients vs CRA charities (if available)
  console.log('3. Grant recipients vs CRA charities (fuzzy)...');
  try {
    const grantsCRA = await matcher.batchCrossMatch(
      'ab.ab_grants', 'recipient',
      'cra.cra_identification', 'legal_name',
      { threshold: args.threshold, limit: args.limit }
    );
    report.matches.grants_vs_cra = grantsCRA;
    lines.push(`\n\n3. GRANT RECIPIENTS vs CRA CHARITIES (threshold ${args.threshold})`, '-'.repeat(50));
    lines.push(`Found ${grantsCRA.length} fuzzy matches:\n`);
    for (const r of grantsCRA.slice(0, 50)) {
      lines.push(`  [${(parseFloat(r.sim) * 100).toFixed(0)}%] "${r.source_name}" <-> "${r.target_name}"`);
    }
  } catch (err) {
    console.log('  CRA schema not available - skipping');
    lines.push('\n\n3. GRANT RECIPIENTS vs CRA CHARITIES - SKIPPED (CRA schema not available)');
  }

  // Match 4: AB Non-profits vs FED grant recipients (if available)
  console.log('4. Non-profits vs FED grant recipients (fuzzy)...');
  try {
    const npFED = await matcher.batchCrossMatch(
      'ab.ab_non_profit', 'legal_name',
      'fed.grants_contributions', 'recipient_legal_name',
      { threshold: args.threshold, limit: args.limit }
    );
    report.matches.non_profit_vs_fed = npFED;
    lines.push(`\n\n4. NON-PROFITS vs FED GRANT RECIPIENTS (threshold ${args.threshold})`, '-'.repeat(50));
    lines.push(`Found ${npFED.length} fuzzy matches:\n`);
    for (const r of npFED.slice(0, 50)) {
      lines.push(`  [${(parseFloat(r.sim) * 100).toFixed(0)}%] "${r.source_name}" <-> "${r.target_name}"`);
    }
  } catch (err) {
    console.log('  FED schema not available - skipping');
    lines.push('\n\n4. NON-PROFITS vs FED GRANT RECIPIENTS - SKIPPED (FED schema not available)');
  }

  // Write reports
  fs.mkdirSync(REPORTS_DIR, { recursive: true });
  fs.writeFileSync(path.join(REPORTS_DIR, 'cross-match-results.json'), JSON.stringify(report, null, 2));
  fs.writeFileSync(path.join(REPORTS_DIR, 'cross-match-results.txt'), lines.join('\n'));

  console.log(`\nReports written to ${REPORTS_DIR}/`);
  console.log(lines.join('\n'));

  await pool.end();
}

run().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
