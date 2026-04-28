# Scoring Rubric

Score each of the three dimensions on a 1–5 scale. Sum to a final score (3–15). Verdicts:

- **Pursue** — total ≥ 12 and no dimension below 3
- **Pursue with caveats** — total 9–11, or any dimension at 2
- **Avoid** — total < 9, or any dimension at 1

**Precedence:** apply the most cautious verdict that any rule triggers. A single dimension at 1 is a hard veto regardless of total — a 5+5+1 = 11 still resolves to **Avoid**, not "Pursue with caveats". A single dimension at 2 caps the verdict at "Pursue with caveats" even when the total is ≥ 12.

Justify each score in one paragraph. Anchor to the examples below — do not float scores.

---

## Dimension 1 — Data (1–5, higher = better data situation)

Combines three sub-questions:
- Which datasets are needed?
- How complete is the existing data to answer the question?
- What other data could be interesting to add?

| Score | Anchor |
|-------|--------|
| **5** | All required tables exist in the local DB, are complete for the relevant period, and have authoritative joins (BN root or already linked through `general.entity_golden_records`). External enrichment is optional, not required. *Example: Vendor Concentration — `fed.grants_contributions` + `ab.ab_contracts` cover the question on their own.* |
| **4** | All required tables exist with one well-understood gap (partial 2024, AB has no BNs, designation A/B/C nuance). Workable through documented mitigations (`fed.vw_agreement_current`, `general.norm_name`). External data would strengthen but is not required for a v1. |
| **3** | Required data partially exists. One core join must go through fuzzy/name-based matching, or a key signal is derivable but indirect (e.g. inferring "ceased operations" from absence of CRA filings). Demo viable but with caveats the team must call out. |
| **2** | Major data gap. The question demands a dataset not in the repo (corporate registries beyond AB, employee counts, stated policy commitments) and the proxy in current data is weak. External data ingestion is on the critical path. |
| **1** | Core data does not exist in the repo and cannot be reasonably approximated. *Example: Adverse Media — requires news/regulatory feeds the repo does not contain.* |

**Always answer all three sub-questions explicitly in the report**, even when the score is high.

---

## Dimension 2 — Implementation Difficulty (1–5, higher = easier to ship in one day)

Combines:
- How long could the data manipulation take?
- How easy is it to build a *working and visual* demo?

| Score | Anchor |
|-------|--------|
| **5** | Existing scripts already produce the core artifact (`npm run analyze:zombies`, `npm run analyze:concentration`). Visual demo reuses `entities:dashboard` or `entities:dossier`. Day-of work is mostly agent wrapping + UX polish. |
| **4** | Some core SQL/queries need to be written but the algorithms are simple aggregations / ranks / windowed metrics. Visual demo is a ranked list, leaderboard, or per-entity dossier. <2 hours of data crunching expected. |
| **3** | Custom multi-step pipeline required, but each step is well-known (graph build → component analysis → ranking). Visual demo needs a custom view but reuses common primitives (table, sortable list). 2–4 hours of data work plus 2–4 hours of UI. |
| **2** | At least one expensive step: probabilistic linkage on new data, multi-hop graph algorithms, or change-point detection on sparse series. *Example: Funding Loops Johnson cycles take ~2hr full run; need to scope to a subset.* Visual demo requires bespoke graph or geo viz. |
| **1** | Core algorithm is not well-defined or is research-grade (LLM judgment at scale on adverse media, policy-to-spending semantic alignment). Demo cannot be made interactive in one day. |

**Hard time-cost flags to call out explicitly in the report:**
- Re-running Splink (do not — `general.entity_golden_records` is pre-built)
- Multi-hop CRA cycle analysis at full depth
- Any pipeline that re-fetches >100K rows from external APIs at demo time
- Bespoke graph viz from scratch (use NetworkX → static PNG, not interactive D3, unless someone on the team has shipped one before)

---

## Dimension 3 — Fit (1–5, higher = better fit)

Combines:
- How well does it map to the hackathon's stated goals (accountability, transparency, government spending)?
- How dynamic / agentic is the problem?

| Score | Anchor |
|-------|--------|
| **5** | Directly about public-money accountability, output is a list of named entities a Minister could read in 2 minutes, and the demo shape is **agentic and interactive** — user types an entity or category, agent re-runs analysis live, surfaces evidence, drills down on follow-ups. *Example: Zombie Recipients dossier where the user asks about any recipient and gets a fresh ceased-operations score.* |
| **4** | Strong accountability fit. The agentic angle is present but slightly forced — e.g. the analysis is a one-shot batch but the user can re-run on a different filter or sub-population live. Output is named-entity-level. |
| **3** | Solid public-spending topic but the demo is largely a **static dashboard** rather than agentic. Re-running on new data would help but is not the core interaction. |
| **2** | Tangential to spending accountability (e.g. pure governance-network mapping with no link to dollar flows), or output is aggregate-only (no named entities for the audience to point at). |
| **1** | Off-topic for the hackathon (technical-merit demo without an accountability narrative), or output is so abstract a Minister cannot consume it. |

**Story-test:** can the team's two-minute demo end with the sentence *"…and that is why $X went to entity Y who [did Z]"*? If yes, fit is ≥ 4. If no, fit is ≤ 3.

---

## Final score

Sum the three dimensions (3–15). Apply the verdict thresholds at the top of this file. The verdict is a heuristic — the team can override with reason — but the score forces an apples-to-apples comparison across challenges.
