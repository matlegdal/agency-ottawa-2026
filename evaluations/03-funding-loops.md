---
challenge: 3
name: Funding Loops
slug: funding-loops
score_data: 5
score_impl: 4
score_fit: 4
score_total: 13
verdict: Pursue
evaluated_on: 2026-04-28
---

# Challenge 3 — Funding Loops

> Where does money cycle between charities (CRA T3010 gifts), and which loops look structural (denominational, federated, foundation endowments) versus designed to inflate revenue, generate receipts, or absorb funds into overhead?

---

## Data — Score: 5

**Justification.** The challenge lives entirely inside the `cra` schema, and not only is the source data present, the heavy analytical artifacts are already pre-computed. `cra.cra_qualified_donees` (Schedule 5 gifts) is the raw signal. On top of it the repo ships `cra.loop_edges` (53,771 directed edges), `cra.loops` (3,431 cycles), `cra.loop_universe` (1,501 entities) with the 0–30 risk score baked in (`cra.loop_universe.score`), `cra.loop_participants` (30,003), `cra.johnson_cycles` (4,759), `cra.partitioned_cycles`, `cra.scc_components` / `scc_summary`, and `cra.loop_financials` (1:1 with `loops`). Designation, category, financials, compensation, and director tables sit alongside for context. No cross-dataset join is needed — `general` is irrelevant here.

- **Datasets needed:** `cra` only — `cra_qualified_donees`, `cra_identification` (designation, category, names), `cra_financial_details` / `cra_compensation` (overhead/comp lens), and the pre-computed `cra.loops*` / `cra.johnson_cycles` / `cra.scc_*` / `cra.loop_financials` tables.
- **Completeness:** Very high. 5 fiscal years (2020–2024) loaded; cycles already enumerated up to 6 hops. Two well-understood data-quality entries apply: **C-3** (donee BN↔name mismatches, ~$8.97B unjoinable in worst readings — donors literally write `'Toronto'` as the BN), and **C-4 / C-11** (109,996 NULL donee BNs, 47,338 malformed BNs, 20,192 well-formed donee BNs unregistered in `cra_identification`). These attenuate edges but do not block the demo — score the loops you *can* trust and show the unjoinable mass as a separate "shadow" tally.
- **External data that could help:** denominational hierarchy mappings (Catholic dioceses, United Church, Anglican networks) to whitelist structurally-normal flows; community-foundation registries (CFC) to mark category 0210 cycles as expected; press releases / sanction lists to corroborate flagged Designation-C orgs. None are required for v1.

## Implementation Difficulty — Score: 4

**Justification.** Despite the original Johnson-cycles run taking ~2 hours, **that run is already done and persisted**. New work is querying pre-computed tables, not recomputing them. The day-of pipeline is: rank `loop_universe` by score, filter by designation, attach `loop_financials` to expose the dollar volume vs program-spend ratio, and assemble a per-charity dossier. Demo UI reuses the existing `entities:dossier` shape. The only bespoke piece is a small loop-graph visualization (3–6 nodes per cycle, easy with a static SVG or a small d3-force snippet) — the cycles themselves are already enumerated in `cra.loops` + `cra.loop_participants`, no graph algorithm at demo time.

- **Data manipulation cost:** ~1–2 hours. SQL only: rank, filter, join `loop_universe → loops → loop_participants → cra_identification → loop_financials`. No multi-hop traversal needed at runtime.
- **Visual demo path:** ranked leaderboard of top-scoring Designation-C charities + per-entity dossier showing (a) its cycles with co-participants, (b) symmetry per year (same-year vs adjacent-year), (c) overhead vs program spend, (d) shared directors flag. The year-by-year symmetry SQL is in `CRA/CLAUDE.md` lines 233–253 — copy-paste.
- **Hard time-cost flags:** **Do not re-run `npm run analyze:all`** (~2 hr, dominated by 6-hop Johnson). Use the pre-computed tables. Avoid building an interactive force-directed graph from scratch — render each loop as a small static cycle diagram.

## Fit — Score: 4

**Justification.** Strong accountability narrative: "$X went around in a circle between charities A, B, C and never reached programs." The Designation-A/B/C lens turns a confusing topic into a crisp story — most loops are normal, *these* loops are not, and here is why. The challenge is naturally **mostly one-shot** (cycle enumeration is global), but the per-charity drill-down ("show me the loops this charity participates in, and how it compares to its denominational peers") is a real dynamic angle, not a cosmetic reframe. The agent's job is interpretation, not enumeration: given a flagged charity, classify the loop pattern (denominational hierarchy / federated / community foundation / private-foundation related-party / Designation-C anomaly), surface program-spend vs comp vs circular-flow ratios, and pull director overlap. That's a genuine LLM-judgment task on top of deterministic pre-compute.

- **Accountability/transparency mapping:** direct — circular flows that exist to game disbursement quotas or absorb funds into overhead are exactly the "did the money do anything?" question Ministers care about.
- **Dynamic vs one-shot:** mostly one-shot for enumeration, dynamic for interpretation. The user types a charity name; the agent re-classifies its loops live and explains why this one is structural vs not.
- **Two-minute story:** Yes — *"This Designation-C charity sent $X to charity B in FY2023, B sent $X back the same year (98% symmetry), neither reported joint programs, both share three directors, and 78% of their reported expenditures are compensation."*

---

## Risks & gotchas

- **Designation A/B/C drives interpretation** (`CRA/CLAUDE.md`). Public foundations *cycle by design* — flagging Mastercard Foundation or a community foundation as "circular" is a footgun. Filter to Designation C (or A/B with overhead-vs-grants anomaly) before showing anything to a Minister.
- **Same-year symmetric flows are the sharpest signal** (`CRA/CLAUDE.md` Section 3 of "What Drives the Most Insightful Analysis"). Multi-year aggregate symmetry that alternates direction is project collaboration, not gaming.
- **C-3 donee-BN mismatches** (~$8.97B unjoinable; the "Toronto"-as-BN case): cycles are silently undercounted where donors wrote garbage BNs. Show the shadow tally separately.
- **C-4 / C-11**: 109,996 NULL `donee_bn`, 47,338 malformed BNs, 20,192 unregistered donee BNs. These rows are dropped from cycle detection.
- **2024 is partial** and the **T3010 form was revised in 2024** — some fields NULL in 2024, others NULL pre-2024. Year-over-year comparisons must handle both.
- **`cra_political_activity_funding` is empty (C-10)** — irrelevant here but listed for completeness if the team strays.

## Existing assets

- Pre-computed: `cra.loops` (3,431), `cra.loop_universe` (1,501 with `score 0–30`), `cra.loop_participants` (30,003), `cra.loop_edges` (53,771), `cra.johnson_cycles` (4,759), `cra.partitioned_cycles`, `cra.scc_components` / `scc_summary`, `cra.loop_financials` (1:1 with `loops`), `cra.donee_name_quality`.
- Scripts: `CRA/scripts/advanced/01-detect-all-loops.js`, `02-score-universe.js`, `03-scc-decomposition.js`, `05-partitioned-cycles.js`, `06-johnson-cycles.js`, `07-loop-financial-analysis.js`, `09-overhead-analysis.js`, plus interactive `lookup-charity.js` and `risk-report.js` (`npm run lookup --bn ...`, `npm run risk --bn ...`).
- CRA skills already defined under `CRA/.claude/skills/` (profile-charity, detect-circular-patterns, analyze-network, temporal-flow-analysis).
- Year-by-year symmetry SQL template in `CRA/CLAUDE.md`.
- No `plans/` doc for this challenge yet (`plans/` only contains the zombie agent plan).

## Recommended demo shape

A two-pane agent: left pane is a leaderboard of `cra.loop_universe` filtered to Designation C with score ≥ ~12 and overhead-or-compensation anomalies from `loop_financials`; right pane is a per-charity dossier the user opens by clicking a row or typing a name. The dossier shows the charity's identity (designation, category, BN-prefix family), the cycles it participates in (rendered as small static cycle diagrams from `loop_participants`), year-by-year same-year symmetry per partner using the SQL in `CRA/CLAUDE.md`, the program-spend vs compensation vs circular-flow stack, and shared-director overlaps. The agent layer adds a classification verdict — *"structural (denominational hierarchy)" / "structural (community foundation)" / "anomaly (Designation C, no joint program, high same-year symmetry)"* — and answers follow-ups like *"compare to peers in the same category"* by re-querying `loop_universe` filtered to that category. Reuses the dossier scaffold pattern from `general/scripts/tools/` and CRA's `risk-report.js` output shape.

---

## Final score: 13/15 — Pursue

Strongest "data already done" challenge in the set: Johnson cycles, SCC, scoring, overhead, and financials are pre-computed in `cra.loops*` / `loop_universe` / `loop_financials`. The win is wrapping the existing artifacts in an agent that classifies loops by designation and tells the structural-vs-anomaly story; the risk is showing a Designation-A foundation as a "circular gifting" hit and getting corrected by anyone in the room who reads CRA filings.
