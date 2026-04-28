---
challenge: 6
name: Related Parties and Governance Networks
slug: related-parties-and-governance-networks
score_data: 3
score_impl: 2
score_fit: 4
score_resilience: 2
score_narrative: 4
score_differentiation: 4
score_total: 19
verdict: Pursue with caveats
evaluated_on: 2026-04-28
---

# Challenge 6 — Related Parties and Governance Networks

> Who controls the entities that receive public money — and do they also control each other? Cross-reference CRA T3010 directors with corporate registries and contract data to find the people behind the funding.

---

## Data — Score: 3

**Justification.** The director side exists — `cra.cra_directors` carries 2,873,624 rows of director-name-by-filing-year. Organization-level entity resolution is solved (`general.entity_golden_records`). But **person-level entity resolution is not done**: `general` resolves organizations, not people, and no person-keyed table exists in the repo. Director names alone are insufficient ("John Smith" is an obvious case); disambiguation must come from co-occurring orgs, time, role — i.e. the team must build it. Director NULL rates are documented (C-6: 0.11% NULL `first_name`, 5% NULL `at_arms_length`, 10% NULL `start_date`) — small but enough to silently drop matches. **Corporate-side directors** (companies receiving FED contracts) are not in the DB at all and require an external corporate-registry feed that the team would have to ingest mid-hackathon.

- **Datasets needed:** `cra.cra_directors`, `cra.cra_identification`, `general.entity_golden_records`, `fed.grants_contributions`, `ab.ab_contracts` / `ab.ab_sole_source`, `ab.ab_non_profit`. **External (essential for corporate side):** Corporations Canada bulk download or provincial corporate registries.
- **Completeness:** medium. Charity-side directors are present and rich; corporate-side directors are absent. Disambiguation is a research-grade subproblem with no scaffolding in the repo.
- **External data that could help:** Corporations Canada bulk download (federal corporate directors), OpenSanctions PEP list (former-public-servant detection), provincial corporate registries beyond AB, OCCRP Aleph for cross-jurisdictional governance graphs.

## Implementation Difficulty — Score: 2

**Justification.** Two expensive pieces stack and neither is shipped. First: **person-level disambiguation** (`John Smith` on charity A's 2021 filing vs `John Smith` on charity B's 2023 filing — same person?) is a Splink-on-people problem that the repo does not solve, and standing up another probabilistic-linkage pipeline against ~3M director rows in one day is exactly the kind of "expensive step" the rubric anchors at 2. Second: building a network-traversal viz from director→orgs→funding edges requires a bespoke graph render — even a static one is harder than a table, and an interactive force-directed graph from scratch is a multi-day project. Score 2, not 1, because the team can scope down to *"directors who appear on ≥3 charity boards in the same year that those charities exchange gifts"* and ship a leaderboard rather than a graph — that path is doable. The full ambition is not.

- **Data manipulation cost:** 4–6+ hours minimum if the team scopes hard to a leaderboard; substantially more if person-disambiguation or corporate-side ingestion is in scope.
- **Visual demo path:** scope down to a leaderboard ("directors with the most overlapping board seats among funded charities"); avoid the network graph for v1. A small static cycle diagram per cluster is acceptable.
- **Hard time-cost flags:** **bespoke graph viz** (don't); **person-level Splink** (don't — scope to exact-string co-occurrence on `(last_name, first_name)`); **corporate-registry ingestion** (cut from scope unless already in hand).

## Fit — Score: 4

**Justification.** Strong accountability narrative — *"these three directors sit on every charity in this funding loop"* is exactly the kind of story the audience cares about, and there's a real per-person dynamic angle (user types a director name, agent traverses to their orgs and the orgs' funding). Two-minute story passes if the team scopes down: *"This director sits on 4 boards; charities A and B exchanged $X in 2023, and they share 3 directors including this person."* The challenge text explicitly names "former public servants connected to entities funded by their former departments" — which is one of the highest-impact stories in the building, *if* the team has a PEP list to anchor it. Score 4 (not 5) because the *demo* is at risk of producing ambiguous people ("John Smith" on a Minister-relevant charity) — false-attribution to a real living person is the failure mode that ends the demo.

- **Accountability/transparency mapping:** very strong.
- **Dynamic vs one-shot:** dynamic. Per-person traversal is the natural unit.
- **Two-minute story:** yes — but the false-attribution risk is real. Pre-curate the showcase entities.

---

## Risks & gotchas

- **C-6 (`cra_directors` NULL rates)**: 3,193 NULL `first_name`, 670 NULL `last_name`, 142,682 NULL `at_arms_length`, 288,822 NULL `start_date`. Even small NULL rates silently drop overlap counts.
- **C-7 (historical legal names not preserved)**: only 1.4% of CRA BNs show name variation across 2020–2024 — rebrands are mostly erased, so director→org joins should normalize via BN, not legal name.
- **Common-name footgun**: `John Smith`, `Jean Tremblay`, etc. False positives on a Minister-relevant entity end the demo. Filter to last-name uniqueness ≥ some threshold or to last-name + first-name + year-overlap before showing anything live.
- **No person-level ER in `general`** — `general.entity_golden_records` is org-level only.
- **Corporate directors are absent from the DB.** Don't promise them in the demo unless an external feed is ingested.
- **Audit any "former public servant" claim** — without a PEP list, this is conjecture. Use OpenSanctions PEPs or scope it out.

## Existing assets

- `cra.cra_directors` — 2.87M director rows, 5 fiscal years.
- `general.entity_golden_records` for org-level identity (use as the *org* end of director→org joins).
- `cra.cra_identification` — designation, category, BN root via `general.extract_bn_root()`.
- `cra.loop_participants` (3,431 cycles + 30,003 participant rows) — a director-overlap layer on top of the existing loop universe is a natural and *much cheaper* scope than person-level disambiguation across the whole director table.

## Recommended demo shape

**Scoped, not ambitious.** Run director-overlap *only inside the charities that already participate in `cra.loop_universe`* — that's 1,501 entities, not all of CRA. Pre-compute the overlap layer offline: pairs of charities in the same cycle that share ≥2 directors by last_name + first_name + year. Demo surface: (a) leaderboard of director-clusters ranked by total funding flowing through the orgs they jointly sit on, (b) per-director dossier showing the orgs they appear on + the cycles those orgs are in. The agent answers *"is [name] on multiple boards that exchange funding?"* by querying the pre-computed overlap. Avoid the full directed graph — render each cluster as a small static diagram (orgs as nodes, directors as edge labels). Pre-curate the showcase entities to avoid common-name false positives. Reuses `entities:dossier`. Cuts corporate-side directors from v1 unless an external feed is in hand on day one.

---

## Final score: 9/15 — Pursue with caveats

High-fit story but expensive in implementation, and the failure mode (mis-attributing a name to a real Minister-relevant person) is a demo-killer. The score lands at 9 by the rubric (Implementation = 2 caps the verdict at "Pursue with caveats" regardless of total). Pursue only if the team scopes hard: director overlap inside the existing `cra.loop_universe`, pre-curated showcase entities, no corporate-registry ingestion, no full graph viz.
