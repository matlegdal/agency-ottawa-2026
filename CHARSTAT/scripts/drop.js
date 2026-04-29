/**
 * drop.js — Drop the charstat schema (destructive; local DB only).
 */
const { query, end, connString } = require('../lib/db');

async function main() {
  if (connString.includes('render.com')) {
    console.error('Refusing to drop on a render.com host. Local DB only.');
    process.exit(1);
  }
  console.log('Dropping schema charstat CASCADE…');
  await query('DROP SCHEMA IF EXISTS charstat CASCADE;');
  console.log('OK.');
  await end();
}

main().catch((err) => {
  console.error('Drop failed:', err.message);
  process.exit(1);
});
