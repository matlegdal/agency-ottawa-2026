---
challenge: 5
name: Vendor Concentration
slug: vendor-concentration
score_data: 5
score_impl: 5
score_fit: 3
score_resilience: 5
score_narrative: 2
score_differentiation: 2
score_total: 22
verdict: Pursue
evaluated_on: 2026-04-28
---

# Challenge 5 — Vendor Concentration

> In any given category of government spending, how many vendors actually compete? Where has incumbency replaced competition?

---

## Data — Score: 5

**Justification.** All required tables exist, are complete for the relevant period, and have authoritative joins. `fed.grants_contributions` carries the federal side (with the F-3-mitigating views); `ab.ab_contracts` (67,079 rows) and `ab.ab_sole_source` (15,533 rows) carry Alberta procurement. `general.entity_golden_records` is already built so AB's no-BN problem is solved through the canonical entity layer. HHI / top-N / per-category concentration are well-defined metrics on this exact data — no inference, no fuzzy joins, no missing dimensions. External GSIN/UNSPSC normalization would help cross-jurisdiction category alignment but is not on the critical path for v1.

- **Datasets needed:** `fed.grants_contributions` + `fed.vw_agreement_current`, `ab.ab_contracts`, `ab.ab_sole_source`, `general.entity_golden_records`.
- **Completeness:** very strong. The metrics map cleanly to the columns.
- **External data that could help:** GSIN/UNSPSC code mappings to align FED `prog_name_en` and AB `ministry`/program categories; provincial procurement datasets beyond AB for fuller "concentration in this category nationally" coverage.

## Implementation Difficulty — Score: 5

**Justification.** This is the cheapest 5 in the set. The core script already exists (`FED/scripts/advanced/04-recipient-concentration.js`, `npm run analyze:concentration`) and produces the canonical concentration report. The metrics — HHI, top-N share, top-1 share, count of distinct vendors — are pure SQL aggregations that take seconds, not hours. Visual demo is a leaderboard plus a per-category drill-down chart, both reusing the dashboard primitives at `general/scripts/tools/`. Day-of work is mostly category normalization across FED and AB, plus agent wrapping. No graphs, no probabilistic linkage, no multi-hop algorithms.

- **Data manipulation cost:** ~1–2 hours. SQL aggregations only; the script already runs.
- **Visual demo path:** ranked leaderboard of (department, category) → HHI + top-1 share + vendor count, with per-row drill-down to the contributing contracts.
- **Hard time-cost flags:** never `SUM(agreement_value)` raw (F-3); use `fed.vw_agreement_current`. Avoid building any bespoke viz beyond ordered tables and small bar charts.

## Fit — Score: 3

**Justification.** The accountability mapping is solid — concentration is exactly the question of *"where has government become dependent on a vendor it can no longer walk away from?"* But the demo is mostly **one-shot by nature**: HHI for the whole portfolio is a global statistic. The dynamic angle exists (*"concentration in this department over the last 3 years"*) and is real, not cosmetic — re-running the slice live is fast. But the headline output is a static leaderboard, and the two-minute story (*"these 5 vendors take 78% of [department X] IT contracts"*) is aggregate, not per-named-bad-actor. It scores well above the floor because the audience is clearly Ministerial — DMs care about vendor lock-in — but it does not score 4 or 5 because the demo lacks a per-recipient *drill-down to a single accountability story*. Pair this with Challenge 4 if you want a fit boost.

- **Accountability/transparency mapping:** strong topic.
- **Dynamic vs one-shot:** mostly one-shot. Re-slicing by department/period/region is real but cosmetic compared to a per-entity dossier.
- **Two-minute story:** yes, but ends on an aggregate ("these 5 vendors take 78%"), not a single-named story.

---

## Risks & gotchas

- **F-3 cumulative `agreement_value`**: HHI computed on raw `SUM(agreement_value)` will inflate dominant amended vendors. Use `fed.vw_agreement_current`.
- **F-1 / F-2 (ref_number collisions, dup pairs)**: aggregate by canonical recipient (`recipient_business_number` normalized + `recipient_legal_name`) routed through `general.entity_golden_records`, not by raw recipient string.
- **AB has no BNs** — must route through `general.entity_golden_records` to avoid splitting the same vendor across spelling variants.
- **A-13 (AB exact duplicates / reversal pairs)**: 5,557 excess duplicate rows + 951 reversal pairs across FY 2024-25 + 2025-26. Don't compute "vendor count by row count" on AB without dedup.
- **A-10 (AB roll-up rows)**: 616 publisher roll-up rows where `recipient IS NULL` total $24.95B across FY 2024-25/26 — exclude from per-vendor concentration metrics or treat as a separate "undisclosed-individuals" bucket.
- **GSIN/UNSPSC normalization is not in the DB.** Cross-jurisdiction "same category" claims should be qualified.

## Existing assets

- `FED/scripts/advanced/04-recipient-concentration.js` — `npm run analyze:concentration` produces the canonical leaderboard.
- `fed.vw_agreement_current` — F-3 mitigation already in place.
- `general.entity_golden_records` — cross-jurisdiction vendor identity.
- `general/scripts/tools/dashboard.js` — UI scaffold for ranked tables.

## Recommended demo shape

A two-pane concentration explorer. Left pane: leaderboard of (department × category) bins ranked by HHI, with top-1 share and vendor count. Right pane: drill-down chart for the selected bin showing the per-vendor share over time (small multiples by year). Agent layer: user types a department or category in natural language (*"IT contracts in Health Canada"*), agent re-queries `fed.vw_agreement_current` + `ab.ab_contracts` filtered through `general.entity_golden_records`, classifies the bin as *competitive / consolidating / dominated / monopoly*, and surfaces the top vendors with their amendment trails (links into the Challenge 4 demo if both are built). Two-minute story: *"In [category X] inside [department Y], one vendor took $Z (HHI = 0.84) — they have won every renewal since 2019."*

---

## Final score: 13/15 — Pursue

The cleanest data + simplest implementation in the ten challenges. Fit is capped at 3 because concentration is fundamentally an aggregate story rather than a per-entity dossier, but the score still clears the Pursue threshold and pairs naturally with Challenge 4 to add a per-vendor narrative on top of the per-category metric.
