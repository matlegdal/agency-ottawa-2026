---
challenge: 8
name: Duplicative Funding
slug: duplicative-funding
score_data: 4
score_impl: 3
score_fit: 4
score_resilience: 4
score_narrative: 4
score_differentiation: 4
score_total: 23
verdict: Pursue
evaluated_on: 2026-04-28
---

# Challenge 8 — Duplicative Funding (and Funding Gaps)

> Which organizations are being funded by multiple levels of government for the same purpose, potentially without those governments knowing about each other? And — the flip side — where do all levels claim to prioritize something, but none are actually funding it?

---

## Data — Score: 4

**Justification.** The duplication side has everything needed: `fed.grants_contributions` + `fed.vw_agreement_current` (federal) joined to `ab.ab_grants` (provincial) through `general.entity_golden_records` (cross-dataset key, BN-aware). For any recipient with both federal and Alberta funding in the same fiscal year, the join is trivial and authoritative. The "same purpose" half is fuzzier — `fed.prog_name_en` / `fed.prog_purpose_en` are free text, AB's `program` is free text, and there is no canonical category code shared across jurisdictions — so program-purpose matching needs LLM categorization or fuzzy matching for the comparison to be defensible. The **gap side** is where the score is capped: detecting *absence* of funding for a stated priority requires the policy-commitments corpus that does not exist in the DB (same gap as Challenge 7). Score 4 because the duplication half (the more interesting demo half) is fully supported.

- **Datasets needed:** `fed.grants_contributions` + `fed.vw_agreement_current`, `ab.ab_grants`, `general.entity_golden_records`. For the gap side: external policy commitments (see Challenge 7).
- **Completeness:** strong for duplication (federal + AB join); weak for "all levels of government" because only AB is in the repo (no BC / ON / QC / municipal datasets); weak for the gap side without policy commitments.
- **External data that could help:** provincial spending datasets beyond AB (BC, ON, QC) for fuller "multiple levels of government" coverage; OpenSanctions / OCCRP Aleph for related-party detection; policy-commitments corpus for the gap side.

## Implementation Difficulty — Score: 3

**Justification.** Custom multi-step pipeline, but every step is well-known. Step 1 — recipient match via `general.entity_golden_records` (already done). Step 2 — same-fiscal-year join between FED and AB (windowed aggregation, ~30 minutes). Step 3 — the hard step: program-purpose similarity for *"same purpose"* claim. Doing this with LLM categorization is the right answer but costs 1–2 hours of prompt design + offline classification at scale. Step 4 — UI: per-recipient "duplicate funding flags" panel, reusing `entities:dossier`. The visual demo is naturally a per-recipient ranked table plus a small duplicate-flags widget — no graphs, no probabilistic linkage to stand up. The gap-side analysis would push the score to 2 because of the missing commitment corpus; **scope to the duplication half** for v1.

- **Data manipulation cost:** ~3–4 hours: SQL joins are fast, program-purpose matching is the slow step (offline LLM classification at concurrency ~50, batch over distinct program purpose strings, not per-row).
- **Visual demo path:** per-recipient dossier with a "funded by federal + provincial in same year" panel; ranked leaderboard of recipients with the highest duplicate-flag scores.
- **Hard time-cost flags:** **don't classify program purposes at the row level** (millions of rows; classify the few thousand distinct program-purpose strings instead); avoid the gap-side analysis for v1; AB has no BNs — must route through `general.entity_golden_records`.

## Fit — Score: 4

**Justification.** Strong accountability story — *"this organization received $X from Ottawa and $Y from Edmonton in the same year for what looks like the same program"* is exactly the kind of inter-jurisdictional waste the audience cares about, and the multi-level audience composition (federal + provincial DMs in the room) makes it especially resonant. Naturally per-recipient and naturally agentic — user types a recipient, agent re-runs the duplicate detection live. Two-minute story passes: *"This recipient received $1.2M from Health Canada and $800K from Alberta Health in 2023 for what both call 'mental health programming' — neither funding letter references the other."* Score 4 (not 5) because the *gap* half of the question — the more politically resonant story — is out of scope for v1, and because the "same purpose" claim is LLM-classified and therefore needs to be hedged in the UI.

- **Accountability/transparency mapping:** very strong, especially given the multi-level audience.
- **Dynamic vs one-shot:** dynamic. Per-recipient query is the natural unit.
- **Two-minute story:** yes — name + dollar from each level + matched purpose.

---

## Risks & gotchas

- **F-3 cumulative `agreement_value`**: use `fed.vw_agreement_current`.
- **F-1 (`ref_number` collisions)**: per-agreement grouping needs `(ref_number, recipient_business_number_or_name)`.
- **AB has no BNs** — must route through `general.entity_golden_records`. Naive name joins will under-match by ~30%.
- **A-13 (AB exact duplicates / reversal pairs)**: 5,557 excess rows + 951 reversal pairs across FY 2024-25 + 2025-26 — dedup before counting.
- **A-10 (AB roll-up rows)**: 616 publisher roll-ups (`recipient IS NULL`) totalling $24.95B in the two newest years — exclude from per-recipient duplication detection.
- **Free-text program purposes**: LLM classification needs to be hedged ("looks like the same purpose") and pre-curated for the showcase entities.
- **Only AB is in the repo for "provincial"** — frame the demo as "federal + Alberta" rather than "all levels of government" until BC/ON/QC datasets are added.

## Existing assets

- `general.entity_golden_records` — the cross-dataset key that makes this challenge tractable.
- `fed.vw_agreement_current` — F-3 mitigation.
- `general.norm_name()` — name canonicalizer.
- No challenge-specific scripts. (The work is mostly join + classify + present.)

## Recommended demo shape

Per-recipient duplicate-funding dossier. The user types or selects a recipient. The agent queries both `fed.vw_agreement_current` (federal) and `ab.ab_grants` (provincial), pulls all funding events in a configurable window (default: same fiscal year), classifies the program purposes against a pre-built embedding/LLM map, and renders: (1) a side-by-side timeline of federal vs Alberta funding, (2) flagged "same purpose" pairs with a confidence score, (3) the per-program purpose drill-down. Agent answers follow-ups like *"are there other recipients with the same overlap pattern in this department?"* by re-querying the pre-computed map. Skip the gap analysis — frame it explicitly as out of scope for v1 ("the gap side requires policy commitments not yet ingested"). Reuses `entities:dossier`.

---

## Final score: 11/15 — Pursue with caveats

Genuinely interesting cross-jurisdictional story with a multi-level audience that will respond to it, and the duplication half is fully supported by existing data through `general.entity_golden_records`. The caveats are (a) "same purpose" is LLM-classified and must be hedged in the UI, (b) the gap half of the challenge needs to be scoped out, and (c) framing must be honest — *"federal + Alberta"* not *"all levels of government"*. Pursue with the duplication side only.
