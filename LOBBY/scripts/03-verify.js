/**
 * 03-verify.js — Sanity-check row counts and run a few zombie-relevant queries.
 */
const { query, end } = require('../lib/db');

async function main() {
  console.log('=== Row counts ===');
  const counts = await query(`
    SELECT 'lobby_registrations' AS t, COUNT(*) AS n FROM lobby.lobby_registrations
    UNION ALL SELECT 'lobby_govt_funding', COUNT(*) FROM lobby.lobby_govt_funding
    UNION ALL SELECT 'lobby_communications', COUNT(*) FROM lobby.lobby_communications
    UNION ALL SELECT 'lobby_communication_dpoh', COUNT(*) FROM lobby.lobby_communication_dpoh
    ORDER BY t;
  `);
  console.table(counts.rows);

  console.log('\n=== Top 10 institutions targeted (DPOH) ===');
  const inst = await query(`
    SELECT institution, COUNT(*) AS communications
      FROM lobby.lobby_communication_dpoh
     WHERE institution IS NOT NULL
     GROUP BY 1
     ORDER BY 2 DESC
     LIMIT 10;
  `);
  console.table(inst.rows);

  console.log('\n=== Top 10 self-disclosed govt funding by institution ===');
  const fund = await query(`
    SELECT institution, COUNT(*) AS rows, SUM(amount)::bigint AS total_amount
      FROM lobby.lobby_govt_funding
     WHERE amount IS NOT NULL AND institution IS NOT NULL
     GROUP BY 1
     ORDER BY total_amount DESC NULLS LAST
     LIMIT 10;
  `);
  console.table(fund.rows);

  console.log('\n=== Sample govt-funded clients with most lobbying registrations ===');
  const heavy = await query(`
    SELECT client_name_en,
           COUNT(*)                              AS registrations,
           MIN(effective_date)                   AS first_reg,
           MAX(end_date)                         AS last_end
      FROM lobby.lobby_registrations
     WHERE govt_fund_ind = 'Y'
       AND client_name_en IS NOT NULL
     GROUP BY 1
     ORDER BY 2 DESC
     LIMIT 10;
  `);
  console.table(heavy.rows);

  await end();
}

main().catch((err) => {
  console.error('Verify failed:', err.message);
  process.exit(1);
});
