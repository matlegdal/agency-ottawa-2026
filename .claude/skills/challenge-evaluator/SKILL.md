---
name: challenge-evaluator
description: This skill should be used when the user wants to evaluate, score, rank, rate, compare, or pick among the ten challenges listed in `challenges.md` for the Agency 2026 / AI for Accountability hackathon. Triggers on phrases like "evaluate challenge 1", "score the zombie recipients challenge", "is Vendor Concentration a good fit", "compare challenges 1 and 5", "which challenge should we pick", "should we do X", "assess feasibility of X", or any reference by name (Zombie Recipients, Ghost Capacity, Funding Loops, Sole Source / Amendment Creep, Vendor Concentration, Related Parties, Policy Misalignment, Duplicative Funding, Contract Intelligence, Adverse Media) or number that asks whether to pursue. Produces a 3–15 score across Data, Implementation Difficulty, and Fit with a Pursue / Pursue-with-caveats / Avoid verdict. Does not trigger for general data-exploration questions or implementation work on a challenge that has already been chosen.
version: 0.1.0
---

# Challenge Evaluator

Evaluate any of the ten Agency 2026 hackathon challenges from `challenges.md` against three dimensions: **Data**, **Implementation Difficulty**, and **Fit**. Each evaluation is written to its own markdown file under `evaluations/` at the repo root. The skill also runs in a **batch mode** that evaluates all ten challenges and produces a summary comparison table at `evaluations/summary.md`.

## When to use

Trigger when the user asks to evaluate, score, compare, or pick among the ten challenges in `challenges.md`. Also trigger when the user names a specific challenge (e.g. "is Vendor Concentration a good fit?", "how hard would Zombie Recipients be?", "what data do we need for Adverse Media?"), or asks to "run this on every challenge", "evaluate all challenges", or "build the summary table".

Do not trigger for:
- General data-exploration questions ("how many charities filed in 2023?")
- Implementation work on a challenge that has already been picked (use the relevant analyze scripts and per-module CLAUDE.md instead)

## Output location

All evaluations are written to `/Users/mathieu/code/qohash/agency-26-hackathon/evaluations/` at the repo root. Create the directory if it does not exist.

| File | When written |
|------|--------------|
| `evaluations/01-zombie-recipients.md` … `evaluations/10-adverse-media.md` | One per challenge — written when that challenge is evaluated |
| `evaluations/summary.md` | Comparison table across all challenges — written or refreshed whenever ≥2 challenges have evaluation files on disk |

**Filename convention:** `{NN}-{kebab-case-name}.md` where `NN` is the two-digit challenge number (`01`–`10`) and the slug is the kebab-case challenge name from `challenges.md`. Use exactly these slugs:

| # | Slug |
|---|------|
| 01 | `zombie-recipients` |
| 02 | `ghost-capacity` |
| 03 | `funding-loops` |
| 04 | `sole-source-and-amendment-creep` |
| 05 | `vendor-concentration` |
| 06 | `related-parties-and-governance-networks` |
| 07 | `policy-misalignment` |
| 08 | `duplicative-funding` |
| 09 | `contract-intelligence` |
| 10 | `adverse-media` |

If an evaluation file already exists, **overwrite it** with the new evaluation rather than appending. Do not create alternative filenames or directories.

## Workflow

Follow these steps in order. Skip a step only when the user has explicitly answered it already.

### Step 1 — Identify the challenge(s) and the mode

Decide which mode the request maps to:

- **Single mode** — evaluate exactly one challenge. Map the user's request to a challenge number 1–10 from `/Users/mathieu/code/qohash/agency-26-hackathon/challenges.md`. If ambiguous, ask once which challenge to evaluate.
- **Batch mode** — evaluate all ten challenges in sequence. Triggered by phrases like "run this on every challenge", "evaluate all", "score every challenge", "build the summary".
- **Comparison mode** — evaluate a specific subset (e.g. "compare 1 and 5"). Treat as Single mode applied N times.

In Batch mode, evaluate challenges in numerical order (1 → 10). After each individual evaluation file is written, refresh `evaluations/summary.md` (Step 5).

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

### Step 4 — Produce the report and write it to disk

Use the report template in `examples/evaluation-template.md`. **The output must be a frontmatter-tagged markdown file written to `evaluations/{NN}-{slug}.md`** (see the filename convention above). The frontmatter is required — `evaluations/summary.md` is generated by parsing it.

Frontmatter format (place at the very top of the file):

```yaml
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
```

Field rules:
- `verdict` is one of `Pursue`, `Pursue with caveats`, `Avoid` (exact strings).
- `score_total` must equal `score_data + score_impl + score_fit`. Do not write a derived total that disagrees with the parts.
- `evaluated_on` is today's date in ISO format (`YYYY-MM-DD`).

After the frontmatter, the report body must include:

1. **Header** — challenge number, name, one-sentence summary
2. **Three dimension blocks** with score, justification, and the sub-question answers
3. **Risks & gotchas** — pulled from KNOWN-DATA-ISSUES.md and the per-module CLAUDE.md
4. **Existing assets** — list scripts/tables/views already in the repo that materially reduce work
5. **Recommended demo shape** — one paragraph: what the user sees, what the agent does live
6. **Final score** — sum of the three dimensions (3–15) with a one-line verdict (Pursue / Pursue with caveats / Avoid)

Keep the total report under ~800 words. The audience is a hackathon team trying to choose; verbosity hurts.

Write the file with the `Write` tool. Do not print the full report inline in the response — instead, summarize in 2–3 sentences and link to the file path.

### Step 5 — Refresh the summary table

After every individual evaluation is written (Single, Comparison, or Batch mode), regenerate `evaluations/summary.md`. Steps:

1. List `evaluations/*.md` (excluding `summary.md`) using `Bash` (e.g. `ls evaluations/`).
2. For each file, parse the YAML frontmatter to extract: `challenge`, `name`, `score_data`, `score_impl`, `score_fit`, `score_total`, `verdict`. Use a tiny `awk` / `sed` snippet or read each file's first ~15 lines — do not pull the whole body into context.
3. Sort the rows by `score_total` descending, then by `challenge` ascending as tiebreaker.
4. Write `evaluations/summary.md` using the structure shown in `examples/summary-template.md`. Always overwrite — never append.

Summary table format:

```markdown
# Challenge Comparison Summary

_Last updated: {YYYY-MM-DD}. Sourced from `evaluations/*.md` frontmatter._

| Rank | # | Challenge | Data | Impl | Fit | Total | Verdict |
|------|---|-----------|------|------|-----|-------|---------|
| 1 | 1 | Zombie Recipients | 4 | 4 | 5 | 13 | Pursue |
| … | … | … | … | … | … | … | … |
```

Below the table, include:
- A **"Top picks"** section listing every `Pursue` challenge with a one-line rationale (pulled from each file's verdict line).
- A **"Coverage"** line stating `N / 10` challenges evaluated, and naming any that are missing.

If only one evaluation exists on disk, still produce a `summary.md` — but note explicitly that only one is evaluated and skip the ranking framing.

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

- **`examples/evaluation-template.md`** — Frontmatter + markdown template for a single-challenge evaluation report
- **`examples/summary-template.md`** — Template for `evaluations/summary.md` (the cross-challenge comparison table)
- **`examples/zombie-recipients-evaluation.md`** — Worked example evaluating Challenge 1 end-to-end (high score: 13/15 Pursue)
- **`examples/adverse-media-evaluation.md`** — Worked example evaluating Challenge 10 (low score: 7/15 Avoid, demonstrates the precedence-rule veto)
