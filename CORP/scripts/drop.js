/**
 * drop.js — Drop the corp schema (destructive; local DB only).
 */
const { query, end, connString } = require('../lib/db');

async function main() {
  if (connString.includes('render.com')) {
    console.error('Refusing to drop on a render.com host. Local DB only.');
    process.exit(1);
  }
  console.log('Dropping schema corp CASCADE…');
  await query('DROP SCHEMA IF EXISTS corp CASCADE;');
  console.log('OK.');
  await end();
}

main().catch((err) => {
  console.error('Drop failed:', err.message);
  process.exit(1);
});
