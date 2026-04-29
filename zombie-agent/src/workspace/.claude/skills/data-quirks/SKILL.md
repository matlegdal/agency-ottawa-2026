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

Two canonical views ship with the schema (per `FED/CLAUDE.md` and
`FED/scripts/01-migrate.js`); use them directly:

- `fed.vw_agreement_current` — one row per agreement, the latest-amendment
  snapshot. Internally disambiguates `(ref_number, recipient)` to neutralize
  the F-1 ref_number-collision problem, so it is the safer-by-default choice.
- `fed.vw_agreement_originals` — `is_amendment = false` only. Use when you
  want the initial commitment.

```sql
-- Initial commitment (originals)
SELECT SUM(agreement_value) FROM fed.vw_agreement_originals;
-- Current commitment (latest amendment, F-1-disambiguated)
SELECT SUM(agreement_value) FROM fed.vw_agreement_current;
```

If for some reason a view is unavailable in your environment, the F-1-safe
inline equivalent is:

```sql
WITH agreement_current AS (
  SELECT DISTINCT ON (
    ref_number,
    COALESCE(recipient_business_number, recipient_legal_name, _id::text)
  ) *
  FROM fed.grants_contributions
  WHERE ref_number IS NOT NULL
  ORDER BY
    ref_number,
    COALESCE(recipient_business_number, recipient_legal_name, _id::text),
    amendment_date  DESC NULLS LAST,
    CASE WHEN amendment_number ~ '^[0-9]+$'
         THEN amendment_number::int
         ELSE -1 END DESC,
    _id DESC
)
SELECT ... FROM agreement_current ...;
```

NOTE: a `DISTINCT ON (ref_number)` *only* CTE silently mis-attributes 41,046
ref_numbers that collide across distinct recipients (KDI F-1) — always
include the recipient disambiguator above, or use the view.

**F-7: BN missing on ~16% of N (not-for-profit) recipients.** Use
name-based matching via `general.entity_golden_records` for these, not a
BN join. (Note: a single deterministic SQL gate that requires a clean
9-digit BN will silently exclude this slice.)

**F-1: ref_number collisions.** Same `ref_number` can cover unrelated
grants. Don't use `ref_number` alone as a join key — use `_id` (the only
truly unique row PK). 41,046 ref_numbers collide. The two FED views
above neutralize this for aggregations.

**F-9: 947 rows have `agreement_end_date < agreement_start_date`.** When
using `agreement_end_date` to assert a "live agreement" or any temporal
filter, add `AND (agreement_end_date IS NULL OR agreement_end_date >=
agreement_start_date)` to drop these publisher-defect rows.

## CRA — T3010 charity filings

**C-1: arithmetic-impossibility violations** persisted in
`cra.t3010_impossibilities`. Always filter when summing CRA financials:
```sql
WHERE NOT EXISTS (
  SELECT 1 FROM cra.t3010_impossibilities ti
  WHERE ti.bn = fd.bn AND ti.fpe = fd.fpe
)
```

**Reserved-but-always-NULL columns** in `cra_identification` (per
`CRA/docs/DATA_DICTIONARY.md` §3.1): `registration_date`, `language`,
`contact_phone`, `contact_email`. Not populated by the CRA Open Data
T3010 feed. Do not rely on them for liveness or any other check.
Consequence: `general.entity_golden_records.cra_profile.registration_date`
is also always NULL (the build script reads from this same source).

**`field_1570` (T3010 self-reported dissolution).**
`cra_financial_general.field_1570 = TRUE` is the T3010 form's own line
A2: *"Has the charity wound-up, dissolved, or terminated operations?"*
This is FIRST-PARTY CHL "dissolved" evidence — the strongest single
death signal available, since the charity itself reported it. Most
ceased charities just stop filing without ever returning a final
`field_1570 = TRUE` form, so absence is not refutation, but presence
is decisive.

**Doc drift in CRA/docs/DATA_DICTIONARY.md §4a.** It lists
`t3010_arithmetic_violations`, `t3010_sanity_violations`,
`t3010_impossibility_violations` as the data-quality tables. Those
names are out of date — the actual tables are
`cra.t3010_impossibilities`, `cra.t3010_plausibility_flags`,
`cra.t3010_completeness_issues`. KDI uses the correct names; trust KDI.

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

**Canadian government fiscal year runs April 1 → March 31.** Alberta's
`display_fiscal_year` is the canonical "YYYY - YYYY" label
(e.g. `'2024 - 2025'` covers payments from 2024-04-01 to 2025-03-31,
confirmed against MIN/MAX(payment_date) in the source). Use it directly
for fiscal filters; do NOT try to compute Apr–Mar boundaries by hand.

The federal fiscal year uses the same April 1 → March 31 boundary, but
`fed.grants_contributions` does not carry a `display_fiscal_year`-style
column — agreement dates are calendar dates. For "no further federal
grants since FY2024-25", filter by `agreement_start_date >= '2024-04-01'`
if you want strict FY alignment, or `>= '2024-01-01'` for a slightly
looser calendar-year cutoff. The zombie-detection skill uses calendar-
year cutoffs because they match how the user phrases their question.

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

**A-13: 5,557 exact-duplicate rows + 951 perfect-reversal pairs in the
two CSV-sourced fiscal years (FY 2024-25 + 2025-26).** A `COUNT(*)` over
`ab.ab_grants` for those years inflates payment counts. When using
"any AB payment in 2024+" as a liveness signal, prefer
`COUNT(*) FILTER (WHERE amount > 0)` and `SUM(amount) FILTER (WHERE
amount > 0)` over raw `COUNT(*)` / `SUM(amount)` so reversal pairs net
out cleanly.

## general — entity resolution

`general.entity_golden_records` carries three JSON profile columns
(`cra_profile`, `fed_profile`, `ab_profile`) populated by
`general/scripts/09-build-golden-records.js`:

- `cra_profile` — designation, category, registration_date, address,
  contact. **Does NOT contain `last_fy` or financial summaries** — query
  `cra.cra_identification` and `cra.cra_financial_details` for those.
- `fed_profile` — `total_grants` is computed as raw
  `SUM(gc.agreement_value)` over `entity_source_links`, which
  **re-introduces F-3 (cumulative-amendment double-count) AND aggregates
  across predecessor entities and pre-BN aliases**. Do NOT use for
  candidate exposure totals; use `fed.vw_agreement_current` filtered to
  the BN root instead.
- `ab_profile` — has `total_grants` and `ministries` from `ab_grants`
  only. **Does NOT contain `non_profit_status`** — query
  `ab.ab_non_profit` (or the `ab.vw_non_profit_decoded` view) directly
  for dissolution status.

`general.vw_entity_funding` is also defined (in `03-migrate-entities.js`)
and aggregates CRA + FED + AB per entity. Same F-3 problem on the FED
side: `total_grants = SUM(gc.agreement_value)` over the raw base table.
Useful for cross-dataset coverage / existence checks; **not safe for
dollar-exposure totals.**

Join paths when going table-to-entity manually:
- CRA → entity: `LEFT(cra.*.bn, 9) = entities.bn_root`
- FED → entity:
  `general.entity_source_links.source_pk->>'_id' = fed.grants_contributions._id::text`
- AB → entity:
  `general.entity_source_links.source_pk->>'id' = ab.*.id::text`

## What is NOT available via SQL

- **FED risk-register** (`FED/data/reports/risk-register.json`) is a
  Node-side artifact produced by `FED/scripts/advanced/07-risk-register.js`,
  not a SQL table. The agent has only MCP postgres — do not try to
  `SELECT` from a "risk_register" table; it does not exist. If a 0–35
  composite score would be useful, derive it inline from the underlying
  fields (or accept the loss for the demo).
- **Reference zombie implementation** (`FED/scripts/advanced/05-zombie-and-ghost.js`):
  uses a $500K threshold (we use $1M), groups by name (we group by BN
  root), and sums `is_amendment = false` rows (originals only — we use
  `vw_agreement_current` which gives current commitment). The two
  numbers will not match by design; if a stakeholder cites
  `npm run analyze:zombies` output, document the divergence rather than
  forcing alignment.

# Pre-computed accountability tables — DO NOT re-derive

These took the maintainers many hours; you have minutes:
- `cra.loops`, `cra.johnson_cycles`, `cra.partitioned_cycles`,
  `cra.loop_universe` — cycle detection done
- `cra.t3010_impossibilities`, `cra.t3010_plausibility_flags`
- `cra.donee_name_quality`
- `cra.overhead_by_charity` — per-BN × year overhead (admin + fundraising
  ÷ programs)
- `cra.govt_funding_by_charity` — per-BN × year govt revenue with
  `govt_share_of_rev` already in percentage units. Canonical source for
  CHL's "70-80% of total revenue" check; do not re-derive from raw
  `field_4540 + field_4570 / field_4700`. **Caveat:** the build script
  does NOT pre-filter `t3010_impossibilities`, so add a `NOT EXISTS`
  subquery joined on `(bn, EXTRACT(YEAR FROM fpe))` when querying. Also
  consider excluding `cra.t3010_plausibility_flags` rows where
  `rule_code = 'PLAUS_MAGNITUDE_OUTLIER'` for extra safety.
- `general.entity_golden_records` (851K rows) — entity resolution done

Trust these tables. Re-deriving any of them on the fly is a demo-killer.
