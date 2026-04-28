---
name: data-quirks
description: Catalogue of known data defects in the CRA + FED + AB hackathon dataset that will silently fool naive queries. Load this before writing any SQL that aggregates or joins across schemas.
---

# Defects you must compensate for

These are the issues that turn a $4M finding into a $400M one if you miss
them.

## CRA T3010 filing window — CRITICAL

Charities have **6 months** after their fiscal-year-end to file the T3010
information return (Income Tax Act). Before treating a "missing T3010 for
FY2024" as a positive zombie signal, you must verify the filing window has
actually closed.

Practical rule:
- Find the entity's fiscal-year-end pattern from prior
  `cra.cra_identification` filings (most charities have a stable year-end
  month).
- For "missing FY2024 filing" to be a real signal:
  `fiscal_year_end + 6 months  <=  CRA_scrape_effective_date`
- Use the CRA scrape date as your "today" for filing-window math, NOT the
  literal current date.

Example: a charity with `fiscal_year_end` of 2024-12-31 has until
2025-06-30 to file. If the CRA scrape is from 2025-03-01, "missing FY2024
filing" is NOT a zombie signal — the window is still open.

Failure mode if you skip this: a verified-looking candidate that any
auditor can shoot down by pointing at the calendar.

## FED — federal grants & contributions

**F-3 (CRITICAL): `agreement_value` is cumulative across amendments, not
delta.** Each amendment row publishes the cumulative running total for the
whole agreement. Naive `SUM(agreement_value)` over the base table
triple-counts.

The base table has a precomputed boolean `is_amendment` (default false on
the original). Use it directly — there are no `vw_agreement_current` /
`vw_agreement_originals` views in this database.

**Initial commitment** (originals only — the bottom of the build manual's
"$533B" reference number):
```sql
SELECT SUM(agreement_value) FROM fed.grants_contributions
WHERE is_amendment = false;
```

**Current commitment** (latest amendment per agreement — the cumulative
running total at the most recent amendment for each agreement). Use this
inline CTE wherever you'd otherwise reference `vw_agreement_current`:
```sql
WITH agreement_current AS (
  SELECT DISTINCT ON (ref_number) *
  FROM fed.grants_contributions
  WHERE ref_number IS NOT NULL
  ORDER BY
    ref_number,
    amendment_date  DESC NULLS LAST,
    CASE WHEN amendment_number ~ '^[0-9]+$'
         THEN amendment_number::int
         ELSE -1 END DESC,
    _id DESC
)
SELECT ... FROM agreement_current ...;
```

That CTE returns the most-recently-amended row per `ref_number`; its
`agreement_value` IS the current cumulative committed dollar value.

A simpler approximation when joining to other tables and you don't need
the latest: `WHERE is_amendment = false` (originals only) is fine for
"what was the initial commitment".

**F-7: BN missing on ~16% of N (not-for-profit) recipients.** Use
name-based matching via `general.entity_golden_records` for these, not a
BN join.

**F-1: ref_number collisions.** Same `ref_number` can cover unrelated
grants. Don't use `ref_number` alone as a join key — use `_id` (the only
truly unique row PK).

## CRA — T3010 charity filings

**C-1: arithmetic-impossibility violations** persisted in
`cra.t3010_impossibilities`. Always filter when summing CRA financials:
```sql
WHERE NOT EXISTS (
  SELECT 1 FROM cra.t3010_impossibilities ti
  WHERE ti.bn = fd.bn AND ti.fpe = fd.fpe
)
```

**C-7: Historical legal names are NOT preserved.**
`cra_identification.legal_name` is backfilled to current name on all
historical years. Old name → new name rebrands (e.g. Ryerson → TMU) are
erased. To find a 2021 gift addressed to the old name, search
`cra.cra_qualified_donees.donee_name` (the donor's free-text record) plus
`general.entity_golden_records.aliases`.

**Aggregate per organization by 9-digit BN root, not the 15-char BN.**
```sql
SELECT LEFT(bn, 9) AS bn_root, SUM(...) FROM cra.cra_qualified_donees
GROUP BY 1
```

## AB — Alberta open data

**A-9: CSV-sourced rows (FY 2024-25 + 2025-26) have NULL lottery,
lottery_fund, version, created_at, updated_at.** `lottery` is unusable as
a filter for FY ≥ 2023-24.

**A-10: $24.95B of "publisher rollup" rows have `recipient IS NULL`** in
FY 2024-25 + 2025-26. These are AISH beneficiaries, per-physician FFS
billings, etc. Decide explicitly whether to filter them out.

**Always use `display_fiscal_year`, never bare `fiscal_year`.** Format:
`'2024 - 2025'` with literal spaces.

**A-6: 50,381 negative grant rows totalling -$13.11B are reversals
/corrections, not errors.** Documented; don't double-count.

## general — entity resolution

**Cross-dataset funding always goes through `general.vw_entity_funding`.**
Join paths:
- CRA → entity: `LEFT(cra.*.bn, 9) = entities.bn_root`
- FED → entity:
  `general.entity_source_links.source_pk->>'_id' = fed.grants_contributions._id::text`
- AB → entity:
  `general.entity_source_links.source_pk->>'id' = ab.*.id::text`

# Pre-computed accountability tables — DO NOT re-derive

These took the maintainers many hours; you have minutes:
- `cra.loops`, `cra.johnson_cycles`, `cra.partitioned_cycles`,
  `cra.loop_universe` — cycle detection done
- `cra.t3010_impossibilities`, `cra.t3010_plausibility_flags`
- `cra.donee_name_quality`
- `cra.overhead_by_charity`, `cra.govt_funding_by_charity`
- `general.entity_golden_records` (851K rows) — entity resolution done

Trust these tables. Re-deriving any of them on the fly is a demo-killer.
