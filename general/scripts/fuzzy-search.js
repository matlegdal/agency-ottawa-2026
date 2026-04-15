/**
 * fuzzy-search.js - Interactive fuzzy entity search across all datasets.
 *
 * Usage:
 *   node scripts/fuzzy-search.js --name "University of Alberta"
 *   node scripts/fuzzy-search.js --name "Calgary" --sources ab_grants,cra,fed
 *   node scripts/fuzzy-search.js --name "AHS" --limit 20
 */
const { pool } = require('../lib/db');
const { FuzzyMatcher } = require('../lib/fuzzy-match');

function parseArgs() {
  const args = {};
  for (let i = 2; i < process.argv.length; i++) {
    if (process.argv[i] === '--name' && process.argv[i + 1]) {
      args.name = process.argv[++i];
    } else if (process.argv[i] === '--sources' && process.argv[i + 1]) {
      args.sources = process.argv[++i].split(',');
    } else if (process.argv[i] === '--limit' && process.argv[i + 1]) {
      args.limit = parseInt(process.argv[++i]);
    }
  }
  return args;
}

async function run() {
  const args = parseArgs();
  if (!args.name) {
    console.log('Usage: node scripts/fuzzy-search.js --name "Entity Name" [--sources ab_grants,cra,fed] [--limit 20]');
    process.exit(0);
  }

  const matcher = new FuzzyMatcher(pool);
  await matcher.initialize();

  console.log(`\nSearching for: "${args.name}"`);
  console.log('='.repeat(70));

  const results = await matcher.findMatches(args.name, {
    searchIn: args.sources || ['ab_grants', 'ab_contracts', 'ab_sole_source', 'ab_non_profit', 'cra', 'fed'],
    limit: args.limit || 10,
  });

  if (results.length === 0) {
    console.log('No matches found.');
  } else {
    console.log(`\nFound ${results.length} matches:\n`);
    console.log(`${'Conf'.padStart(6)} ${'Method'.padEnd(12)} ${'Source'.padEnd(18)} Name`);
    console.log('-'.repeat(80));
    for (const r of results) {
      const conf = (r.confidence * 100).toFixed(0) + '%';
      console.log(`${conf.padStart(6)} ${r.method.padEnd(12)} ${r.source.padEnd(18)} ${r.matched_name}`);
    }
  }

  await pool.end();
}

run().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
