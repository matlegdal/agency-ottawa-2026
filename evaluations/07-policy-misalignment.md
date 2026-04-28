---
challenge: 7
name: Policy Misalignment
slug: policy-misalignment
score_data: 2
score_impl: 2
score_fit: 4
score_total: 8
verdict: Avoid
evaluated_on: 2026-04-28
---

# Challenge 7 — Policy Misalignment

> Is the money going where the government says its priorities are? Pick measurable policy commitments (emissions targets, housing starts, reconciliation spending, healthcare capacity) and compare them to the actual flow of funds.

---

## Data — Score: 2

**Justification.** The spending side of the equation is solid: `fed.grants_contributions` + `fed.vw_agreement_current`, `ab.ab_grants`, `ab.ab_contracts` carry program/department-tagged spending. **The policy-commitments side does not exist in the DB.** Mandate Letters, Budget tables, Speech from the Throne, departmental plans, GC InfoBase priorities — none of them are loaded. The team must ingest stated commitments mid-hackathon, normalize them against department/program codes, and decide what counts as a "match" between rhetoric and dollars. This is the single biggest missing-data gap of any challenge in the set short of Adverse Media: *the comparison cannot be made until the rhetoric side is built from scratch*. Score 2 (not 1) because the rhetoric side is at least *available externally* (Budget CSVs, Mandate Letter texts) — unlike Adverse Media, no licensed feed is required.

- **Datasets needed:** `fed.grants_contributions` + `fed.vw_agreement_current`, `ab.ab_grants` (spending side); **external (essential):** Budget tables from Finance Canada, Mandate Letter texts, GC InfoBase departmental plans, Treasury Board planned-spending tables.
- **Completeness:** spending side strong; commitments side ~0%. Without the commitments side, the question cannot be answered.
- **External data that could help (essential, not optional):** GC InfoBase, Budget CSV tables, departmental plans, Mandate Letter corpus.

## Implementation Difficulty — Score: 2

**Justification.** Three compounding hard problems, each of which alone would push this challenge into "scope down or skip" territory. (1) **Ingestion of policy commitments** — Mandate Letters and departmental plans are PDFs/HTML; turning them into measurable, comparable line items requires LLM extraction with human verification, which is hard to make demo-stable in one day. (2) **Policy-to-spending semantic alignment** — matching "emissions targets" to the actual emissions-related grants is a fuzzy LLM-judgment problem at scale; the rubric explicitly anchors this kind of work at 1. (3) **The comparison metric is ill-defined** — "is the money going where the government says its priorities are" admits no canonical answer; the team must define *what counts as misalignment* and defend it to a Minister live. Score 2, not 1, because if the team picks a single, narrow policy (e.g. "reconciliation" with a Mandate Letter dollar target and a TBS function code), they can ship a one-policy slice. The full ambition is research-grade.

- **Data manipulation cost:** 6–10+ hours just to ingest and normalize a small commitment corpus, plus the LLM alignment loop, plus defensible metric definition. Scoping down to a single policy area is the only realistic v1.
- **Visual demo path:** narrow scope → a side-by-side bar chart for one policy area (committed vs spent) plus a per-program drill-down table. Avoid pretending to show "the whole portfolio".
- **Hard time-cost flags:** **LLM judgment at scale** (don't run live during the showcase); **PDF/HTML policy ingestion** (treat as critical path, not enrichment); **bespoke geographic / time-series viz** (don't).

## Fit — Score: 4

**Justification.** The accountability mapping is excellent — *"the government promised X and spent on Y"* is the most ministerial story imaginable, and the audience (Ministers and DMs) responds to it instantly. Naturally one-shot for the global comparison, but reframable as *"alignment score for [department X]"* — the dynamic angle is real if the team picks a concrete policy area. Two-minute story passes *if* the policy area is well-chosen: *"The Mandate Letter committed $X to reconciliation; departmental program codes Y total $Z, a 38% gap concentrated in these three programs."* Score 4 (not 5) because the demo is brittle: a single contested attribution (*"we did fund that — it just shows up under a different program code"*) ends the credibility of the chart in front of a DM who knows their portfolio.

- **Accountability/transparency mapping:** the canonical political accountability question.
- **Dynamic vs one-shot:** one-shot at the headline; dynamic if reframed as per-department.
- **Two-minute story:** yes — but only if the policy is narrow and the attribution is bulletproof.

---

## Risks & gotchas

- **F-3 cumulative `agreement_value`**: any "X went to category Y" claim must use `fed.vw_agreement_current`, not raw sums.
- **F-10 (`agreement_number` is reused as program code)**: don't infer policy categories from `agreement_number`.
- **A-1 (resolved) / A-11 (Alberta cabinet-rename drift)**: longitudinal AB ministry comparisons must use `general/data/ministries-history.json` as the predecessor/successor crosswalk.
- **A-10 (AB roll-up rows hold ~$25B)**: any policy-share of AB spending must decide how to treat `recipient IS NULL` rows.
- **Attribution hazard**: a contested attribution in front of a DM — *"that's accounted for under a different program code"* — ends the demo's credibility. Pre-validate every claim against the department's own annual report before showing it live.
- **No commitment corpus** — treat ingestion as the critical path.

## Existing assets

- `fed.vw_agreement_current` / `fed.vw_agreement_originals` — F-3 mitigations.
- Department / program code coverage on `fed.grants_contributions` (`owner_org`, `prog_name_en`, `prog_purpose_en`) and on `ab.ab_grants` (`ministry`, `program`).
- `general.entity_golden_records` for cross-dataset recipient identity.
- `general/data/ministries-history.json` for AB ministry-rename history.

No challenge-specific scripts. No commitment corpus.

## Recommended demo shape

**Pick one policy area and one jurisdiction.** Don't attempt the portfolio. The team chooses (e.g.) reconciliation funding at the federal level, ingests the Mandate Letter excerpts and the relevant Budget table line(s), normalizes against TBS function codes / department codes / program purposes, and produces a single-page report: committed vs current-committed-value vs spent over time. Add a per-department drill-down ("alignment score" by department for that one policy area). Pre-validate every line against the department's annual report before showing it. Skip live LLM alignment — pre-classify the program inventory offline and let the agent re-run only the slicing. The demo's two-minute story has to be airtight: the team should rehearse with someone who knows the portfolio. Even at maximum scope reduction, this is the riskiest demo in the set.

---

## Final score: 8/15 — Avoid

Strong accountability story but the data isn't there and the alignment problem is research-grade. The rubric verdict is Avoid (total < 9). Pursue *only if* a team member has prior experience with policy-corpus ingestion + alignment, and is willing to scope down to a single, narrow policy area with pre-validated attribution. Otherwise, the slick D3 dashboard a team is tempted to build will be one DM-question away from collapsing.
