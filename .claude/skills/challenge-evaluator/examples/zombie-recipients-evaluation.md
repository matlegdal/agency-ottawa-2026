---
challenge: 1
name: Zombie Recipients
slug: zombie-recipients
score_data: 4
score_impl: 4
score_fit: 5
score_total: 13
verdict: Pursue
evaluated_on: 2026-04-28
---

# Challenge 1 — Zombie Recipients

> Did public funding go to entities that ceased operations within 12 months — or to entities so dependent on public money (>70–80% of revenue) that they could not survive without it?

---

## Data — Score: 4

**Justification.** All required tables exist in the local DB and the cross-dataset key (`general.entity_golden_records`) is pre-built. Revocation/dissolution signals are direct: `cra.cra_identification` carries CRA revocations, `ab.ab_non_profit` carries dissolution/struck-off status. Revenue-dependence is computable from `cra.cra_financial_details` for the charity subset. The remaining gap is meaningful but bounded: FED-only recipients with no CRA registration and no AB record have no first-class "ceased operations" signal — the team must infer ceased status from absence of subsequent activity. Score capped at 4 (not 5) because of this inference gap.

- **Datasets needed:** `fed.grants_contributions` + `fed.vw_agreement_current`; `cra.cra_identification`, `cra.cra_financial_details`; `ab.ab_non_profit`; `general.entity_golden_records`.
- **Completeness:** strong for charities and AB nonprofits; weaker for FED-only commercial recipients. 2024 CRA data is partial — recent funding events should not be compared against the same fiscal year's CRA filings.
- **External data that could help:** Corporations Canada bulk download (federal corporate dissolutions), provincial corporate registries beyond AB, OpenSanctions PEPs to detect ex-public-servant principals on the recipient side.

## Implementation Difficulty — Score: 4

**Justification.** Most of the work is already shipping: `FED/scripts/advanced/05-zombie-and-ghost.js` runs today via `npm run analyze:zombies`, and `plans/zombie_agent_build_manual_v2.md` documents an agent build on top of it. Core SQL is windowed aggregation (funding events → next-12-months activity check), no graph algorithms or probabilistic linkage. Visual demo reuses the per-entity dossier shape (`general/scripts/tools/dashboard.js`, `entities:dossier`) — a recipient-keyed page showing the funding event, the dependence ratio, and the post-funding status. Day-of work is agent wrapping, evidence-snippet retrieval, and UX polish. Score 4 (not 5) because the dependence-ratio computation across multi-year financials still needs careful handling of partial 2024 data and the T3010 form revision.

- **Data manipulation cost:** ~2 hours to extend the existing zombie script with the dependence-ratio dimension; near-zero for the dossier query path.
- **Visual demo path:** per-entity dossier with three panels — funding events, dependence ratio time-series, status-after-funding banner.
- **Hard time-cost flags:** none. No Johnson cycles, no Splink re-run, no bespoke graph viz.

## Fit — Score: 5

**Justification.** Direct mapping to the hackathon's accountability/transparency/spending mandate. The demo is naturally agentic: the user types or selects a recipient, the agent computes the zombie/dependence score live and explains the evidence. Output is per-entity at named-entity granularity — exactly what a Minister can absorb in two minutes. The two-minute story test passes: *"This $4.2M went to entity Y, which dissolved 9 months later and where federal grants made up 86% of revenue."*

- **Accountability/transparency mapping:** as direct as it gets — did the public get anything for its money?
- **Dynamic vs one-shot:** dynamic. Per-recipient query is the natural unit. Global pre-compute exists; per-entity drill-down is fast.
- **Two-minute story:** yes, ends on a named recipient, a dollar amount, and a status outcome.

---

## Risks & gotchas

- **`fed.agreement_value` is cumulative per amendment.** Use `fed.vw_agreement_current` (committed) and `fed.vw_agreement_originals` (initial) — never `SUM` raw `agreement_value`. Triple-counting risk: ~$921B vs correct ~$816B.
- **`fed.ref_number` is not unique** (KNOWN-DATA-ISSUES F-1). Use `(ref_number, COALESCE(recipient_business_number, recipient_legal_name))` for grouping.
- **AB has almost no BNs** — must route through `general.entity_golden_records` for AB-recipient lookup, not BN-join.
- **2024 CRA data is partial** (6-month filing window). Do not infer "stopped filing" within 6 months of fiscal year-end 2024.
- **2024 T3010 form revision** — some financial fields are NULL for 2024 (removed) and others NULL for 2020–2023 (added 2024). Handle both NULL patterns when computing dependence ratio.

## Existing assets

- `FED/scripts/advanced/05-zombie-and-ghost.js` — analytical core (`npm run analyze:zombies`).
- `plans/zombie_agent_build_manual_v2.md` — in-progress agent design.
- `general.entity_golden_records` + `general.norm_name()` + `general.extract_bn_root()` — cross-dataset keying done.
- Dossier scaffolding at `general/scripts/tools/dashboard.js` and `npm run entities:dossier` (port 3801).

## Recommended demo shape

A live recipient dossier. The user types or selects a funded entity (or asks the agent in natural language). The agent retrieves the funding history from `fed`/`ab`, the CRA registration trajectory, the AB non-profit status, computes the dependence ratio from `cra.cra_financial_details`, and renders a single page with: top-line verdict (Active / Zombie / At-risk), funding-events timeline, dependence-ratio sparkline, and a status-change banner. The agent also accepts follow-ups (*"who were the directors at the time of dissolution?"*) by joining `cra.cra_directors`. Reuses the existing dossier UI on port 3801 with new panels.

---

## Final score: 13/15 — Pursue

Strongest fit-to-shippability ratio of the ten challenges: highest fit score, lowest implementation risk, and most existing assets to build on.
