---
name: zombie-detection
description: Recipe for finding federally-funded recipients that ceased operations shortly after receiving public money (Challenge 1 — Zombie Recipients). Use when investigating zombie/dissolution/disappearance questions.
---

# Filters applied before any candidate enters consideration

EXCLUDE entities where `cra.cra_identification.designation = 'A'`.
  Designation A means private foundation. Private foundations are
  STRUCTURALLY allowed to have low or zero operating revenue — they exist
  to distribute funds, not to run programs. They are not zombies.

EXCLUDE entities whose most recent observed `fiscal_year_end + 6 months`
  is AFTER the CRA scrape effective date. Their T3010 filing window is
  still open, so "missing recent filing" is not yet a real signal. See
  the `data-quirks` skill for the math.

# What counts as a zombie

An entity that received material federal or provincial public funding and
shows no operating signs of life afterwards. Operationalized:

1. Cumulative federal funding ≥ $500K.
2. No CRA T3010 filing in any year after the last grant.
3. No appearance in subsequent FED grants or AB grants in 2024+.
4. (Optional) AB corporate registry shows dissolution or status indicating
   inactive.
5. (Optional) Funding dependency: grants ÷ last-known total revenue >
   70%, indicating they likely could not survive without public money.

A finding is strong when 1–3 hold; (4) and (5) make it visceral.

# Investigation steps

## Step A — top federal recipients with material funding

`fed.grants_contributions.agreement_value` is cumulative across amendments
(see `data-quirks` F-3). Use the inline CTE pattern, NOT a naive SUM of
the base table:

```sql
-- Step A: top federal recipients ≥ $1M, current commitment, 2018-2022
WITH agreement_current AS (
  SELECT DISTINCT ON (ref_number) *
  FROM fed.grants_contributions
  WHERE ref_number IS NOT NULL
    AND agreement_end_date BETWEEN '2018-01-01' AND '2022-12-31'
  ORDER BY ref_number,
           amendment_date DESC NULLS LAST,
           CASE WHEN amendment_number ~ '^[0-9]+$'
                THEN amendment_number::int ELSE -1 END DESC,
           _id DESC
)
SELECT
  LEFT(NULLIF(recipient_business_number,''), 9) AS bn_root,
  recipient_legal_name,
  SUM(agreement_value)               AS total_committed_cad,
  MIN(agreement_start_date)          AS first_grant,
  MAX(agreement_end_date)            AS last_grant,
  COUNT(DISTINCT ref_number)         AS num_agreements
FROM agreement_current
GROUP BY 1, 2
HAVING SUM(agreement_value) >= 1000000
ORDER BY total_committed_cad DESC
LIMIT 50;
```

A simpler, almost-as-correct approximation when you don't need the
absolute peak number is to filter `WHERE is_amendment = false` (originals
only). That gives initial-commitment dollars.

## Step B — which of those still file T3010 in 2023 or 2024?

Per-org join on the 9-digit BN root:

```sql
-- Step B: drop candidates with any 2023+ CRA filing
SELECT c.bn_root, c.recipient_legal_name, c.total_committed_cad
FROM <step_a_candidates> c
LEFT JOIN cra.cra_identification ci
  ON LEFT(ci.bn, 9) = c.bn_root
 AND ci.fiscal_year IN (2023, 2024)
WHERE ci.bn IS NULL;
```

For candidates without a BN, resolve through
`general.entity_golden_records.aliases` instead.

## Step C — also check no FED or AB grants in 2024+

```sql
-- Step C: any further FED grants in 2024+?
SELECT COUNT(*) FROM fed.grants_contributions
WHERE LEFT(NULLIF(recipient_business_number,''), 9) = $1
  AND agreement_start_date >= '2024-01-01';
```

```sql
-- Step C': any further AB payments in FY 2024-25 / 2025-26?
SELECT COUNT(*) AS n_payments,
       COALESCE(SUM(amount),0) AS total_amount
FROM ab.ab_grants ag
JOIN general.entity_source_links esl
  ON esl.source_schema = 'ab'
 AND esl.source_table  = 'ab_grants'
 AND (esl.source_pk->>'id')::int = ag.id
WHERE esl.entity_id = $1
  AND ag.display_fiscal_year IN ('2024 - 2025', '2025 - 2026');
```

## Step D — resolve to canonical entity

Look each surviving candidate up in `general.vw_entity_funding` so you
have one canonical name, every alias, and a single rolled-up funding
total across schemas.

## Step E — funding dependency

For BN-bearing candidates with at least one CRA filing year, compute
govt-share-of-revenue:
```sql
SELECT bn, fpe,
       (COALESCE(field_4540,0) + COALESCE(field_4570,0)) AS govt_revenue,
       field_4700                                        AS total_revenue,
       CASE WHEN field_4700 > 0
            THEN (COALESCE(field_4540,0) + COALESCE(field_4570,0))::float
                 / field_4700
       END AS govt_share
FROM cra.cra_financial_details fd
WHERE LEFT(bn, 9) = $1
  AND NOT EXISTS (
    SELECT 1 FROM cra.t3010_impossibilities ti
    WHERE ti.bn = fd.bn AND ti.fpe = fd.fpe
  )
ORDER BY fpe DESC LIMIT 1;
```

A `govt_share > 0.7` is an unsubtle dependency signal.

## Step F — publish (pending)

For each of your top 3-5 candidates, call
`mcp__ui_bridge__publish_finding` with:
- `entity_name`, `bn` (9-digit root), `total_funding_cad`,
  `last_known_year`, `govt_dependency_pct` (0.0 if unknown),
  `evidence_summary` (audit-lead language),
  `verifier_status="pending"`,
  `sql_trail` (the labels of the queries that produced it).

## Step G — handle challenges

Spawn the verifier subagent with the candidate list. It returns
VERIFIED / REFUTED / AMBIGUOUS per candidate. Update via
`publish_finding`:
- VERIFIED   → `verifier_status="verified"`
- REFUTED    → `verifier_status="refuted"`
- AMBIGUOUS  → `verifier_status="challenged"`, then run up to 3 follow-up
               SQL queries to defend or revise, then publish a final
               `"verified"` or `"refuted"`.

# Pitfalls

- Do not naïvely `SUM(agreement_value)` over `fed.grants_contributions` —
  use the inline CTE or `WHERE is_amendment = false`. (F-3)
- Do not assume `recipient_business_number` is a clean 9-digit string;
  trim and use `LEFT(NULLIF(...,''),9)`.
- Do not skip `cra.t3010_impossibilities` filtering when computing
  `govt_share`.
- An entity that received funding in 2022 and last filed T3010 with
  `fpe = 2023-12-31` is NOT a zombie — that's normal.
- Designation A foundations are excluded by default (top of skill).
- Filing window must be closed before "no recent filing" counts (see
  `data-quirks`).
