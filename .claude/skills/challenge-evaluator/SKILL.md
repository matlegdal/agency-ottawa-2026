---
name: challenge-evaluator
description: This skill should be used when the user wants to evaluate, score, rank, rate, compare, or pick among the ten challenges listed in `challenges.md` for the Agency 2026 / AI for Accountability hackathon. Triggers on phrases like "evaluate challenge 1", "score the zombie recipients challenge", "is Vendor Concentration a good fit", "compare challenges 1 and 5", "which challenge should we pick", "should we do X", "assess feasibility of X", or any reference by name (Zombie Recipients, Ghost Capacity, Funding Loops, Sole Source / Amendment Creep, Vendor Concentration, Related Parties, Policy Misalignment, Duplicative Funding, Contract Intelligence, Adverse Media) or number that asks whether to pursue. Produces a 3–15 score across Data, Implementation Difficulty, and Fit with a Pursue / Pursue-with-caveats / Avoid verdict. Does not trigger for general data-exploration questions or implementation work on a challenge that has already been chosen.
version: 0.1.0
---

# Challenge Evaluator

Evaluate any of the ten Agency 2026 hackathon challenges from `challenges.md` against three dimensions: **Data**, **Implementation Difficulty**, and **Fit**. Produce a single structured report the user can compare across challenges to pick what to build.

## When to use

Trigger when the user asks to evaluate, score, compare, or pick among the ten challenges in `challenges.md`. Also trigger when the user names a specific challenge (e.g. "is Vendor Concentration a good fit?", "how hard would Zombie Recipients be?", "what data do we need for Adverse Media?").

Do not trigger for:
- General data-exploration questions ("how many charities filed in 2023?")
- Implementation work on a challenge that has already been picked (use the relevant analyze scripts and per-module CLAUDE.md instead)

## Workflow

Follow these steps in order. Skip a step only when the user has explicitly answered it already.

### Step 1 — Identify the challenge

Map the user's request to one of the ten challenges in `/Users/mathieu/code/qohash/agency-26-hackathon/challenges.md` (numbered 1–10). If ambiguous, ask once which challenge to evaluate. If the user wants a comparison, evaluate each in turn and produce a final ranking table at the end.

### Step 2 — Ground the evaluation in actual repo state

Before scoring, verify the data situation against the repo. Do not score from memory — datasets and scripts evolve. For each challenge:

1. **Read the per-module CLAUDE.md** for any module the challenge touches (`CRA/CLAUDE.md`, `FED/CLAUDE.md`, `AB/CLAUDE.md`). The root `CLAUDE.md` already lists which tables and scripts map to each challenge — use that table as the starting point.
2. **Check `KNOWN-DATA-ISSUES.md`** for caveats relevant to the tables involved (e.g. F-1 ref_number collisions, the `agreement_value` cumulative-snapshot trap, missing BNs in AB, partial 2024 CRA data).
3. **Check `plans/`** for any in-progress design doc on this challenge (e.g. `plans/zombie_agent_build_manual_v2.md` for Challenge 1).
4. **Check existing analysis scripts** under `<module>/scripts/advanced/` to see what is already built. Existing scripts dramatically reduce implementation cost.

If a per-module CLAUDE.md mentions a gotcha relevant to the challenge (e.g. designation A vs B vs C for circular flows, or `agreement_value` triple-counting), surface it explicitly in the report — it will affect difficulty.

### Step 3 — Score across three dimensions

Use the rubric in `references/rubric.md` to score each dimension on a 1–5 scale with a one-paragraph justification. The three dimensions and their sub-questions:

**Data (1–5, higher = better data situation)**
- Which datasets are needed? (Name the schemas and tables; see `references/data-map.md` for the per-challenge map.)
- How complete is the existing data to answer the question? (Coverage gaps, BN-join issues, partial years, NULLs introduced by form revisions.)
- What other data could be interesting to add? (External enrichment: OpenSanctions, news APIs, corporate registries, OCCRP Aleph, provincial registries beyond AB.)

**Implementation Difficulty (1–5, higher = easier to ship in one day)**
- How long could the data manipulation take? Be especially careful of:
  - Multi-hop graph algorithms (Johnson cycles in CRA already take ~2hr full run)
  - Probabilistic linkage on already-linked entities (use `general.entity_golden_records`; do not re-run Splink unless ingesting new data)
  - Time-series with sparse data (CRA T3010 is annual; FED contributions are quarterly snapshots)
- How easy is it to build a *visual* demo? Score higher when:
  - Output is naturally a list, ranked table, or per-entity dossier (zombie list, vendor concentration leaderboard)
  - Output reuses an existing UI scaffold (`general/scripts/tools/dashboard.js`, `entities:dossier`)
  - Score lower when output requires bespoke graph viz, geographic maps, or interactive timelines built from scratch

**Fit (1–5, higher = better fit)**
- How well does it map to the hackathon's stated goals: **accountability, transparency, government spending**? (See the intro and "Expectations for Demos" sections of `challenges.md`.)
- How **dynamic** is the problem? A skill that an agent can re-run on new data, new entities, or follow-up questions scores high. A one-shot data analysis that produces a static report scores low. Agentic / interactive demos are explicitly preferred. **Use the per-challenge tendency table in `references/dynamic-vs-oneshot.md`** — it pre-classifies each challenge and gives the heuristic for borderline cases.
- Bonus signal: does it tell a story a Minister or Deputy Minister can grasp in 2 minutes? (The audience is named in the "Audience" section of `challenges.md`.)

### Step 4 — Produce the report

Use the report template in `examples/evaluation-template.md`. The output must include:

1. **Header** — challenge number, name, one-sentence summary
2. **Three dimension blocks** with score, justification, and the sub-question answers
3. **Risks & gotchas** — pulled from KNOWN-DATA-ISSUES.md and the per-module CLAUDE.md
4. **Existing assets** — list scripts/tables/views already in the repo that materially reduce work
5. **Recommended demo shape** — one paragraph: what the user sees, what the agent does live
6. **Final score** — sum of the three dimensions (3–15) with a one-line verdict (Pursue / Pursue with caveats / Avoid)

Keep the total report under ~800 words. The audience is a hackathon team trying to choose; verbosity hurts.

### Step 5 — Compare (only if multiple challenges)

If evaluating more than one challenge, end with a comparison table sorted by final score:

| # | Challenge | Data | Impl | Fit | Total | Verdict |
|---|-----------|------|------|-----|-------|---------|
| 1 | Zombie Recipients | 4 | 4 | 5 | 13 | Pursue |

## Anti-patterns

- **Do not score from the challenge text alone.** The text is a prompt; the repo state is the ground truth. A challenge can look easy in prose and be expensive in practice (Funding Loops 6-hop cycles), or look hard and have most of the work already done (Zombie Recipients has `analyze:zombies` + a plan).
- **Do not invent table names.** Verify table existence via the per-module CLAUDE.md or by listing files in `<module>/scripts/`. Hallucinated columns mislead the team.
- **Do not recommend re-running entity resolution.** `general.entity_golden_records` is already produced. For any cross-dataset join, route through it.
- **Do not propose `SUM(fed.agreement_value)` over the raw table.** `agreement_value` is a cumulative snapshot per amendment — naive sums triple-count amended agreements (~$921B vs the correct ~$816B). Use `fed.vw_agreement_current` for committed values, `fed.vw_agreement_originals` for initial commitments.
- **Do not assume schema continuity across CRA years.** The 2024 T3010 form revision means some fields are NULL for 2024 (removed) and others NULL for 2020–2023 (added in 2024). Any dependence-ratio or year-over-year comparison must handle both NULL patterns.
- **Do not optimize for novelty over fit.** The hackathon judges on accountability/transparency outcomes for a government audience, not on technical sophistication. A slick D3 visualization with no accountability narrative is not a 5 on Fit.
- **Do not ignore the "dynamic vs one-shot" distinction.** A one-shot dashboard is less compelling than an agent that re-runs on new entities the user types in.

## Additional Resources

### Reference Files

- **`references/rubric.md`** — Full 1–5 scoring rubric per dimension with anchor examples
- **`references/data-map.md`** — Per-challenge table of which schemas, tables, views, and existing scripts apply
- **`references/dynamic-vs-oneshot.md`** — Heuristics for distinguishing a dynamic agentic problem from a static analysis

### Examples

- **`examples/evaluation-template.md`** — Markdown template for a single-challenge evaluation report
- **`examples/zombie-recipients-evaluation.md`** — Worked example evaluating Challenge 1 end-to-end (high score: 13/15 Pursue)
- **`examples/adverse-media-evaluation.md`** — Worked example evaluating Challenge 10 (low score: 7/15 Avoid, demonstrates the precedence-rule veto)
