---
challenge: 2
name: Ghost Capacity
slug: ghost-capacity
score_data: 4
score_impl: 4
score_fit: 5
score_total: 13
verdict: Pursue
evaluated_on: 2026-04-28
---

# Challenge 2 — Ghost Capacity

> Which funded organizations show no evidence of actually being able to deliver — no employees, no physical presence, expenditures flowing to a few people or onward transfers — yet persist indefinitely?

---

## Data — Score: 4

**Justification.** The signal stack is unusually rich for CRA-registered recipients. `cra.cra_compensation` carries headcount and the 10-bracket compensation-by-bracket panel (T3010 Schedule 3); `cra.cra_financial_details` exposes the revenue mix (government-transfer line, gifts received, qualified-donee gifts disbursed) and the expenditure/compensation ratios. `fed.grants_contributions` + `general.entity_golden_records` close the loop on the funding side. Existing `FED/scripts/advanced/05-zombie-and-ghost.js` already implements the basic ghost heuristic. Score capped at 4 because **non-charity FED/AB recipients have no employee/revenue panel** — the team either scopes to charities (clean) or accepts that for-profit/sole-prop/individual recipients can only be partly characterized.

- **Datasets needed:** `cra.cra_compensation`, `cra.cra_financial_details`, `cra.cra_identification` (designation + ongoing status), `fed.grants_contributions` + `fed.vw_agreement_current`, `general.entity_golden_records`.
- **Completeness:** very strong for charities; partial for non-charity recipients (no compensation/headcount data exists in `fed` or `ab`). 2024 T3010 form revision (C-8) means several compensation fields are populated only for 2024 or only pre-2024.
- **External data that could help:** Statistics Canada Business Register (firm headcount), federal/provincial corporate registries for active-status confirmation, OpenCorporates/LinkedIn for evidence-of-operations on for-profit recipients.

## Implementation Difficulty — Score: 4

**Justification.** Same shape as Challenge 1 — windowed aggregation per recipient, no graph or probabilistic work. Existing `analyze:zombies` script already produces the ghost-capacity slice; the new work is wrapping it as an agent and adding the *narrative* dimensions (compensation-as-share-of-expenditure, onward-transfers ratio, headcount-vs-funding magnitude) into a dossier. Reuses the per-entity dossier UI scaffold. ~2–3 hours of SQL + agent wrapping. Score 4 because the comp-bracket math has T3010 form-revision edge cases (C-8) and the duplicate Schedule 6 vs Schedule 3 compensation reconciliation (C-1 `COMP_4880_EQ_390`, 13,504 violations) needs explicit handling.

- **Data manipulation cost:** ~2–3 hours. Aggregations only; no multi-hop traversal. Re-uses the zombie script's BN normalization + golden-records join.
- **Visual demo path:** per-recipient dossier — top-line "ghost score", headcount vs funding panel, compensation-as-%-of-expenditure bar, onward-transfers Sankey (small).
- **Hard time-cost flags:** none. Avoid bespoke graph viz; the onward-transfer Sankey is 2–4 nodes max per recipient.

## Fit — Score: 5

**Justification.** As direct as accountability gets — the audience instantly understands "this charity received $X, has 0 employees, and 95% of expenditures are compensation to two people." Naturally per-entity, naturally agentic. Two-minute story passes: *"This $2.1M went to recipient Y; they reported zero employees in 2023 and 2024, expenditures are 91% comp to three named directors, and the rest is onward transfers to two related charities."* This is exactly the story the hackathon framing names.

- **Accountability/transparency mapping:** very direct.
- **Dynamic vs one-shot:** dynamic. Per-recipient query, fresh evidence each time.
- **Two-minute story:** yes — name + dollar + ratio + outcome.

---

## Risks & gotchas

- **C-1 (T3010 arithmetic impossibilities)**: 54,010 violations across 30,856 BNs include `COMP_4880_EQ_390` (Schedule 6 comp ≠ Schedule 3 comp). When the two sides disagree, prefer Schedule 3 (line 390) for the per-bracket detail, but flag the discrepancy.
- **C-8 (2024 T3010 form revision)**: comp/expenditure fields shifted between v24 and v27 — `field_4180` is pre-2024 only; `field_4101`/`field_5045` are populated v27+. Handle both NULL patterns.
- **C-2 (plausibility flags)**: 234 filings where comp > total expenditures. These are the *prime* ghost candidates (or unit-error filings). Surface them explicitly rather than filtering them out.
- **Designation A/B/C interpretation** (CRA/CLAUDE.md): a public foundation (A) with low headcount and high onward-transfers is operating as designed. Filter to Designation C charitable orgs for the headline list.
- **F-3 cumulative `agreement_value`**: use `fed.vw_agreement_current` for funding totals.
- **AB has no BNs** — route AB-side via `general.entity_golden_records`.

## Existing assets

- `FED/scripts/advanced/05-zombie-and-ghost.js` — already produces the basic ghost slice.
- `cra.cra_compensation` + `cra.cra_financial_details` — the analytical raw material is fully populated for the charity subset.
- `general.entity_golden_records` — cross-dataset key.
- Dossier scaffolding at `general/scripts/tools/` and `npm run entities:dossier`.

## Recommended demo shape

Per-recipient ghost-capacity dossier sharing the dossier shell with Challenge 1. Top banner shows the verdict (Active / Ghost / Hollow). Three panels: (1) funding-vs-headcount (FED + AB committed dollars vs reported employees over the same fiscal years); (2) expenditure breakdown — compensation %, onward-transfers %, program % — with the few-named-recipients flag if compensation concentrates on ≤3 individuals; (3) related-party shadow showing onward-transfer recipients (joins to `cra.cra_qualified_donees` or `cra.cra_directors` overlap). The agent answers follow-ups like *"compare to peers in the same designation/category"* by re-querying with a category filter. Could share the same chat-driven entry surface as Challenge 1, framed as a second card alongside the Zombie verdict.

---

## Final score: 13/15 — Pursue

Same fit-to-shippability profile as Challenge 1 and shares 80% of its plumbing. Strong candidate to pair with Challenge 1 in a single agent surface that emits *both* a Zombie verdict and a Ghost-capacity verdict per recipient.
