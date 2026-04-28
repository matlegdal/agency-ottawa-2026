---
challenge: 9
name: Contract Intelligence
slug: contract-intelligence
score_data: 3
score_impl: 3
score_fit: 3
score_resilience: 3
score_narrative: 2
score_differentiation: 3
score_total: 17
verdict: Pursue with caveats
evaluated_on: 2026-04-28
---

# Challenge 9 — Contract Intelligence

> What is Canada actually buying, and is it paying more over time? Which categories of procurement have seen the fastest cost growth, and is that growth from volume, unit cost, or vendor concentration?

---

## Data — Score: 3

**Justification.** Year-over-year cost growth is computable directly from `fed.grants_contributions` + `fed.vw_agreement_current` plus `ab.ab_contracts`. Aggregate spend by department × category × year is straightforward windowed SQL. **Unit cost is the hard piece** — it is not directly recorded in either dataset. To decompose growth into volume × unit cost × concentration, the team must infer category-level units from `prog_name_en` / contract descriptions / sole-source `contract_services` text, which is sparse and inconsistent. GSIN/UNSPSC code mappings are not in the repo and would have to be ingested. Concentration as the third factor is solved (Challenge 5 already produces it). Score 3 because two of the three decomposition components (volume, concentration) are supported but unit cost is derived rather than measured, which weakens any "we are paying more for the same thing" claim.

- **Datasets needed:** `fed.grants_contributions` + `fed.vw_agreement_current`, `ab.ab_contracts`, `ab.ab_sole_source` (descriptions for category inference), `general.entity_golden_records`.
- **Completeness:** medium. Volume + spend + concentration are clean; unit cost is inferential.
- **External data that could help:** GSIN catalog (category normalization across FED and AB), historical TBS price benchmarks if obtainable, UNSPSC mappings.

## Implementation Difficulty — Score: 3

**Justification.** Custom multi-step pipeline but every step is well-known. (1) Year-over-year aggregation by department × category is fast SQL. (2) Concentration borrows from Challenge 5's `analyze:concentration`. (3) Volume vs unit-cost decomposition is the hard step — needs a category-normalization layer (LLM classification of program/contract descriptions into shared categories) plus a "typical unit" inference per category that the team must defend. Visual demo is a per-category time series plus a small decomposition stack — both are common chart primitives, not bespoke graph viz. ~3–5 hours of work, of which most is the category-normalization layer.

- **Data manipulation cost:** ~3–5 hours: aggregations are fast, category-normalization at scale is the slow step (classify distinct program/contract descriptions offline, not per-row).
- **Visual demo path:** ranked leaderboard of (category, growth rate), per-category drill-down with a stacked decomposition (volume / unit cost proxy / concentration), per-vendor table for the top contributors.
- **Hard time-cost flags:** **don't classify per row** (classify distinct strings); never `SUM(agreement_value)` raw (F-3); avoid bespoke time-series viz beyond stacked-area charts.

## Fit — Score: 3

**Justification.** Strong topic mapping — "is Canada paying more for the same thing?" is exactly the accountability question Ministers and DMs respond to. But the demo shape is **mostly one-shot by nature**: cost-growth decomposition is an aggregate analysis, and the audience-relevant story is the leaderboard, not a per-entity dossier. The dynamic angle exists (*"cost growth in [department X] for [category Y] over the last 5 years"*) and is real, but it's slicing a static report rather than re-running a live agent on a fresh entity. Two-minute story passes at the aggregate level (*"the IT category in Health Canada grew 47% from 2019–2024 — 60% from concentration, 30% from unit cost, 10% from volume"*) but doesn't end on a single named accountability target. Compared to Challenge 5 (also one-shot but cleaner data), this challenge has the same fit shape but with weaker data, so it scores no higher.

- **Accountability/transparency mapping:** strong topic.
- **Dynamic vs one-shot:** mostly one-shot; per-category re-slicing is real but cosmetic vs a per-entity dossier.
- **Two-minute story:** yes, at aggregate level; doesn't end on a single named entity.

---

## Risks & gotchas

- **F-3 cumulative `agreement_value`**: cost-growth claims computed on raw `SUM(agreement_value)` are inflated by amendments. Always use `fed.vw_agreement_current`.
- **F-1 / F-2 (ref_number collisions, dup pairs)**: aggregate by canonical recipient + canonical agreement key, not by `ref_number` alone.
- **F-10 (`agreement_number` is reused as program code)**: useful as a *signal* for category, but not as a join key.
- **AB has no BNs** — vendor-side identity routes through `general.entity_golden_records`.
- **A-13 (AB duplicates / reversal pairs)**: dedup before computing volume metrics.
- **No category code in the data** — any "category" claim is the team's classification, not the publisher's. Hedge in the UI.
- **2024 partial / form revision (C-8)** — applies to CRA only here, but worth noting if any cross-cuts with charity-side spending are added.

## Existing assets

- `fed.vw_agreement_current` / `fed.vw_agreement_originals` — F-3 mitigations.
- `FED/scripts/advanced/04-recipient-concentration.js` — provides the concentration component of the decomposition.
- `general.entity_golden_records` — vendor identity across FED/AB.
- No challenge-specific scripts. The category-normalization layer is greenfield.

## Recommended demo shape

A two-pane category explorer. Left pane: leaderboard of (department × category) bins ranked by year-over-year growth rate, with the volume / unit-cost-proxy / concentration decomposition shown as a stacked bar. Right pane: drill-down for the selected bin showing the time series of total spend, the top vendors that drove the growth, and the amendment trail (links into Challenge 4 if both are built). Agent layer: user types a department or category, agent re-aggregates `fed.vw_agreement_current` + `ab.ab_contracts` for that slice and recomputes the decomposition. Be explicit in the UI about which decomposition components are measured (volume, concentration) vs inferred (unit cost). Reuses `general/scripts/tools/dashboard.js` for the table primitives. Pair naturally with Challenge 5 — same shape, different metric.

---

## Final score: 9/15 — Pursue with caveats

Strong topic and reuses Challenge 5's concentration plumbing, but unit cost is inferential rather than measured and the demo is fundamentally aggregate. Pursue only if (a) the team is willing to ship the category-normalization layer cleanly (offline LLM on distinct program-description strings, not per row), (b) the UI hedges on inferred-vs-measured components, and (c) the demo is paired with Challenge 5 to recover a per-vendor narrative. Standalone, this is a less compelling pick than Challenges 1, 2, 3, 4, or 5.
