/**
 * 01-migrate.js — Create the corp schema and tables.
 */
const fs = require('fs');
const path = require('path');
const { query, end } = require('../lib/db');

async function main() {
  const sqlPath = path.join(__dirname, '..', 'sql', '01-schema.sql');
  const sql = fs.readFileSync(sqlPath, 'utf8');
  console.log('Applying schema from', sqlPath);
  await query(sql);
  console.log('OK — corp schema created.');
  await end();
}

main().catch((err) => {
  console.error('Migration failed:', err.message);
  process.exit(1);
});
