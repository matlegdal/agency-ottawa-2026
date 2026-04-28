---
challenge: {N}
name: {Challenge Name}
slug: {kebab-case-slug}
score_data: {1-5}
score_impl: {1-5}
score_fit: {1-5}
score_resilience: {1-5}
score_narrative: {1-5}
score_differentiation: {1-5}
score_total: {sum, must equal sum of all six scores, range 6-30}
verdict: {Pursue | Pursue with caveats | Avoid}
evaluated_on: {YYYY-MM-DD}
---

# Challenge {N} — {Name}

> {One-sentence summary of the challenge, paraphrased from `challenges.md`.}

---

## Data — Score: {1–5}

**Justification.** {One paragraph anchored to the rubric.}

- **Datasets needed:** {schemas + tables/views}
- **Completeness:** {what is covered, what is missing, which `KNOWN-DATA-ISSUES.md` entries apply}
- **External data that could help:** {OpenSanctions, GDELT, corporate registries, policy commitments — only what is genuinely additive}

## Implementation Difficulty — Score: {1–5}

**Justification.** {One paragraph. Call out any expensive step explicitly.}

- **Data manipulation cost:** {fast SQL / multi-step pipeline / multi-hop graph / probabilistic linkage. Estimate hours.}
- **Visual demo path:** {existing dashboard / per-entity dossier / ranked leaderboard / bespoke graph viz}
- **Hard time-cost flags:** {list any of: full Johnson cycles, re-running Splink, bespoke graph viz from scratch, large external API pulls at demo time}

## Fit — Score: {1–5}

**Justification.** {One paragraph anchored to the rubric.}

- **Accountability/transparency mapping:** {how directly does this answer "where did public money go and was it well-spent?"}
- **Dynamic vs one-shot:** {use `references/dynamic-vs-oneshot.md`}
- **Two-minute story:** {can the demo end on "…and that is why $X went to entity Y who [did Z]"? Yes/No.}

## Demo Resilience — Score: {1–5}

**Justification.** {One paragraph. What happens when a Minister types in a famous entity from their portfolio? Is the output deterministic or inferential? Wrong-looking results on famous entities are worse than empty results.}

- **Determinism:** {pure aggregation / set membership / direct registry signal vs ratio with NULLs / fuzzy match / LLM judgment}
- **Failure mode:** {empty result on rare entity / wrong-looking result on famous entity / inconsistent between runs}
- **Curated showcase set required?** {yes/no — and which entities the team should pre-validate}

## Narrative Specificity — Score: {1–5}

**Justification.** {One paragraph. How vivid is the headline finding?}

- **Slide test:** {can the punchline fit the schema "$X to {named entity}, who {verb phrase}"? Write the actual punchline.}
- **Setup required:** {no setup / one sentence of context / multi-entity cluster the audience must track}

## Differentiation — Score: {1–5}

**Justification.** {One paragraph. With ~900 hackathon participants, why does this stand out?}

- **What can't you get from existing tools?** {finish the sentence: "You can't get this today from {GC InfoBase / Open.Canada.ca / charitydata.ca / buyandsell.gc.ca / etc.} because {structural reason}."}
- **Source of the novelty:** {new join / new signal / new framing / mostly UI wrapping}

---

## Risks & gotchas

- {Pull from `KNOWN-DATA-ISSUES.md`: F-/C-/A- entries that touch the cited tables}
- {Pull from per-module `CLAUDE.md`: designation A/B/C, cumulative-snapshot trap, missing AB BNs, partial 2024 CRA, 2024 T3010 form revision}

## Existing assets

- {Scripts under `<module>/scripts/advanced/` already shipping the core artifact}
- {Pre-computed tables / views the challenge can build on}
- {Plans under `plans/` if any}

## Recommended demo shape

{One paragraph. What the user sees on screen. What the agent does live in response to user input. Which existing UI scaffold (`general/scripts/tools/dashboard.js`, `entities:dossier`) is reused.}

---

## Final score: {sum}/30 — {Pursue / Pursue with caveats / Avoid}

{One-line verdict.}
