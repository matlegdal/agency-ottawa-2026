/**
 * 03-verify.js — Sanity checks + zombie cross-join preview.
 */
const { query, end } = require('../lib/db');

async function main() {
  console.log('=== Row counts ===');
  const counts = await query(`
    SELECT 'corp_corporations'    AS t, COUNT(*) AS n FROM corp.corp_corporations
    UNION ALL SELECT 'corp_status_history', COUNT(*) FROM corp.corp_status_history
    UNION ALL SELECT 'corp_name_history',   COUNT(*) FROM corp.corp_name_history
    ORDER BY t;
  `);
  console.table(counts.rows);

  console.log('\n=== Status distribution ===');
  const status = await query(`
    SELECT current_status_code, current_status_label, COUNT(*) AS n
      FROM corp.corp_corporations
     GROUP BY 1, 2
     ORDER BY 1;
  `);
  console.table(status.rows);

  console.log('\n=== BN coverage ===');
  const bn = await query(`
    SELECT
      COUNT(*) AS total,
      COUNT(business_number) AS with_bn,
      ROUND(100.0 * COUNT(business_number) / COUNT(*), 1) AS pct_with_bn
    FROM corp.corp_corporations;
  `);
  console.table(bn.rows);

  console.log('\n=== Zombie preview: corps with FED grants AND non-active status ===');
  const zombies = await query(`
    WITH bn_corps AS (
      SELECT business_number,
             current_name,
             current_status_label,
             current_status_date,
             dissolution_date,
             last_annual_return_year
        FROM corp.corp_corporations
       WHERE business_number IS NOT NULL
         AND current_status_code IN (2, 3, 11, 19, 10)
    ),
    fed_recipients AS (
      SELECT
        LEFT(recipient_business_number, 9) AS bn9,
        recipient_legal_name,
        SUM(agreement_value) FILTER (WHERE NOT is_amendment)::bigint AS originals,
        MAX(agreement_end_date) AS last_grant_end
      FROM fed.grants_contributions
      WHERE recipient_business_number IS NOT NULL
        AND recipient_business_number ~ '^[0-9]'
      GROUP BY 1, 2
      HAVING SUM(agreement_value) FILTER (WHERE NOT is_amendment) >= 500000
    )
    SELECT
      f.recipient_legal_name,
      c.current_name      AS corp_registry_name,
      c.current_status_label,
      c.dissolution_date,
      c.last_annual_return_year,
      f.originals,
      f.last_grant_end
    FROM fed_recipients f
    JOIN bn_corps c ON c.business_number = f.bn9
    ORDER BY f.originals DESC
    LIMIT 15;
  `);
  console.table(zombies.rows);

  await end();
}

main().catch((err) => {
  console.error('Verify failed:', err.message);
  process.exit(1);
});
