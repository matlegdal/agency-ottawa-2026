/**
 * 03-verify.js — Sanity checks + zombie cross-join previews.
 *
 * Prints:
 *  - Row count + status distribution
 *  - Effective-date range (so we know the snapshot is recent)
 *  - Charities NOT covered by T3010 filings (registry-only zombies)
 *  - FED grant recipients whose CRA charity status is Revoked/Annulled/Suspended
 */

const { query, end } = require('../lib/db');

async function main() {
  console.log('=== Row counts ===');
  const counts = await query(`
    SELECT
      COUNT(*)                         AS total,
      COUNT(DISTINCT bn_root)          AS unique_bn_roots,
      MIN(source_snapshot_date)        AS oldest_snapshot,
      MAX(source_snapshot_date)        AS newest_snapshot
    FROM charstat.charity_status;
  `);
  console.table(counts.rows);

  console.log('\n=== Status distribution ===');
  const status = await query(`
    SELECT status, COUNT(*) AS n
      FROM charstat.charity_status
     GROUP BY 1
     ORDER BY 2 DESC;
  `);
  console.table(status.rows);

  console.log('\n=== Effective-date histogram (year of status change) ===');
  const dates = await query(`
    SELECT
      EXTRACT(YEAR FROM status_effective_date)::int AS year,
      status,
      COUNT(*) AS n
    FROM charstat.charity_status
    WHERE status_effective_date IS NOT NULL
      AND status <> 'Registered'
    GROUP BY 1, 2
    ORDER BY 1 DESC, 2
    LIMIT 30;
  `);
  console.table(dates.rows);

  console.log('\n=== Sanity: registry vs T3010 coverage ===');
  // How many BNs in charstat have NO matching T3010 filing in the cra schema?
  // Those are registry-only entities — the gap that justifies this module.
  const coverage = await query(`
    WITH t3010_bn_roots AS (
      SELECT DISTINCT LEFT(bn, 9) AS bn_root
        FROM cra.cra_identification
    )
    SELECT
      COUNT(*) FILTER (WHERE t.bn_root IS NULL)                                 AS registry_only,
      COUNT(*) FILTER (WHERE t.bn_root IS NOT NULL)                             AS in_both,
      COUNT(*) FILTER (WHERE t.bn_root IS NULL AND cs.status <> 'Registered')   AS registry_only_dead,
      COUNT(*) FILTER (WHERE t.bn_root IS NULL AND cs.status = 'Revoked')       AS registry_only_revoked
    FROM charstat.charity_status cs
    LEFT JOIN t3010_bn_roots t ON t.bn_root = cs.bn_root;
  `);
  console.table(coverage.rows);

  console.log('\n=== Zombie preview: FED grant recipients with non-Registered CRA status ===');
  // Join FED grants to charstat by 9-digit BN root and surface entities
  // that received money while officially Revoked / Annulled / Suspended.
  const zombies = await query(`
    WITH dead_charities AS (
      SELECT bn_root, charity_name, status, status_effective_date, sanction
        FROM charstat.charity_status
       WHERE status IN ('Revoked', 'Annulled', 'Suspended')
    ),
    fed_recipients AS (
      SELECT
        LEFT(recipient_business_number, 9) AS bn9,
        recipient_legal_name,
        SUM(agreement_value) FILTER (WHERE NOT is_amendment)::bigint AS originals,
        MAX(agreement_end_date)            AS last_grant_end,
        MIN(agreement_start_date)          AS first_grant_start
      FROM fed.grants_contributions
      WHERE recipient_business_number IS NOT NULL
        AND recipient_business_number ~ '^[0-9]'
      GROUP BY 1, 2
      HAVING SUM(agreement_value) FILTER (WHERE NOT is_amendment) >= 100000
    )
    SELECT
      f.recipient_legal_name,
      d.charity_name AS cra_registry_name,
      d.status,
      d.status_effective_date,
      d.sanction,
      f.originals,
      f.last_grant_end,
      CASE
        WHEN d.status_effective_date IS NOT NULL
         AND f.last_grant_end IS NOT NULL
         AND f.last_grant_end > d.status_effective_date
        THEN (f.last_grant_end - d.status_effective_date)
      END AS days_funded_after_status_change
    FROM fed_recipients f
    JOIN dead_charities d ON d.bn_root = f.bn9
    ORDER BY f.originals DESC
    LIMIT 20;
  `);
  console.table(zombies.rows);

  await end();
}

main().catch((err) => {
  console.error('Verify failed:', err.message);
  process.exit(1);
});
