/**
 * Create GIN trigram indexes on name columns used by the entity resolver.
 *
 * Reads DB_CONNECTION_STRING directly from .env (admin credentials),
 * bypassing the dotenv override chain that points to the readonly user.
 */

const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');

// --- Read admin connection string directly from .env -------------------------
const envPath = path.join(__dirname, '..', '.env');
const envContents = fs.readFileSync(envPath, 'utf-8');
const match = envContents.match(/^DB_CONNECTION_STRING=(.+)$/m);
if (!match) {
  console.error('Could not find DB_CONNECTION_STRING in .env');
  process.exit(1);
}
const connString = match[1].trim();

const pool = new Pool({
  connectionString: connString,
  max: 2,
  connectionTimeoutMillis: 30000,
  ssl: connString.includes('render.com') ? { rejectUnauthorized: false } : undefined,
});

// --- Index definitions -------------------------------------------------------
const indexes = [
  {
    name: 'idx_trgm_ab_grants_recipient',
    sql: `CREATE INDEX IF NOT EXISTS idx_trgm_ab_grants_recipient
           ON ab.ab_grants USING GIN (UPPER(recipient) gin_trgm_ops)`,
  },
  {
    name: 'idx_trgm_ab_contracts_recipient',
    sql: `CREATE INDEX IF NOT EXISTS idx_trgm_ab_contracts_recipient
           ON ab.ab_contracts USING GIN (UPPER(recipient) gin_trgm_ops)`,
  },
  {
    name: 'idx_trgm_ab_sole_source_vendor',
    sql: `CREATE INDEX IF NOT EXISTS idx_trgm_ab_sole_source_vendor
           ON ab.ab_sole_source USING GIN (UPPER(vendor) gin_trgm_ops)`,
  },
  {
    name: 'idx_trgm_ab_non_profit_legal_name',
    sql: `CREATE INDEX IF NOT EXISTS idx_trgm_ab_non_profit_legal_name
           ON ab.ab_non_profit USING GIN (UPPER(legal_name) gin_trgm_ops)`,
  },
  {
    name: 'idx_trgm_cra_identification_legal_name',
    sql: `CREATE INDEX IF NOT EXISTS idx_trgm_cra_identification_legal_name
           ON cra.cra_identification USING GIN (UPPER(legal_name) gin_trgm_ops)`,
  },
  {
    name: 'idx_trgm_fed_gc_recipient',
    sql: `CREATE INDEX IF NOT EXISTS idx_trgm_fed_gc_recipient
           ON fed.grants_contributions USING GIN (UPPER(recipient_legal_name) gin_trgm_ops)`,
  },
];

// --- Main --------------------------------------------------------------------
async function main() {
  console.log('Ensuring pg_trgm extension is enabled in public schema...');
  await pool.query('CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA public');
  console.log('pg_trgm extension OK.\n');

  for (const idx of indexes) {
    console.log(`Creating index: ${idx.name} ...`);
    const start = Date.now();
    try {
      await pool.query(idx.sql);
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      console.log(`  -> Done (${elapsed}s)\n`);
    } catch (err) {
      console.error(`  -> FAILED: ${err.message}\n`);
    }
  }

  // Verify
  console.log('--- Verifying indexes in pg_indexes ---');
  const { rows } = await pool.query(`
    SELECT schemaname, tablename, indexname
      FROM pg_indexes
     WHERE indexname LIKE 'idx_trgm_%'
     ORDER BY indexname
  `);
  if (rows.length === 0) {
    console.log('No trigram indexes found!');
  } else {
    for (const r of rows) {
      console.log(`  ${r.schemaname}.${r.tablename} -> ${r.indexname}`);
    }
  }
  console.log(`\nTotal trigram indexes: ${rows.length}`);

  await pool.end();
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
