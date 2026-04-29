const { query, end, connString } = require('../lib/db');

async function main() {
  if (connString.includes('render.com')) {
    console.error('Refusing to drop on a render.com host. Local DB only.');
    process.exit(1);
  }
  console.log('Dropping schema pa CASCADE…');
  await query('DROP SCHEMA IF EXISTS pa CASCADE;');
  console.log('OK.');
  await end();
}

main().catch((err) => {
  console.error('Drop failed:', err.message);
  process.exit(1);
});
