/**
 * 03-verify.js — Sanity checks + zombie-relevant queries.
 */
const { query, end } = require('../lib/db');

async function main() {
  console.log('=== Row counts by fiscal year ===');
  const counts = await query(`
    SELECT fiscal_year_end, COUNT(*) AS rows, SUM(expenditure_current_yr)::bigint AS total_paid
      FROM pa.transfer_payments GROUP BY 1 ORDER BY 1;
  `);
  console.table(counts.rows);

  console.log('\n=== Top 10 departments by total transfer payments (all years) ===');
  const dept = await query(`
    SELECT department_name, SUM(expenditure_current_yr)::bigint AS total
      FROM pa.transfer_payments GROUP BY 1
     ORDER BY 2 DESC NULLS LAST LIMIT 10;
  `);
  console.table(dept.rows);

  console.log('\n=== Top 10 individual transfer payments ===');
  const big = await query(`
    SELECT fiscal_year, department_name, recipient_name_location,
           expenditure_current_yr::bigint AS amount
      FROM pa.transfer_payments
     ORDER BY expenditure_current_yr DESC NULLS LAST LIMIT 10;
  `);
  console.table(big.rows);

  console.log('\n=== Zombie cross-check: FED-disclosed-but-not-paid (sample) ===');
  // Recipients with a FED grant in 2020-2023 but no PA row in any year.
  const missing = await query(`
    WITH fed_recipients AS (
      SELECT
        NULLIF(regexp_replace(regexp_replace(lower(coalesce(recipient_legal_name,'')),
          '^the\\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '') AS norm,
        recipient_legal_name,
        SUM(agreement_value) FILTER (WHERE NOT is_amendment)::bigint AS originals
      FROM fed.grants_contributions
      WHERE agreement_start_date BETWEEN '2020-01-01' AND '2023-12-31'
        AND recipient_legal_name IS NOT NULL
      GROUP BY 1, 2
      HAVING SUM(agreement_value) FILTER (WHERE NOT is_amendment) >= 1000000
    )
    SELECT f.recipient_legal_name, f.originals
    FROM fed_recipients f
    LEFT JOIN pa.transfer_payments p ON p.recipient_name_norm = f.norm
    WHERE p.recipient_name_norm IS NULL
    ORDER BY f.originals DESC LIMIT 15;
  `);
  console.table(missing.rows);

  await end();
}

main().catch((err) => {
  console.error('Verify failed:', err.message);
  process.exit(1);
});
