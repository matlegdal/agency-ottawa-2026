---
challenge: 4
name: Sole Source and Amendment Creep
slug: sole-source-and-amendment-creep
score_data: 4
score_impl: 4
score_fit: 5
score_resilience: 4
score_narrative: 5
score_differentiation: 4
score_total: 26
verdict: Pursue
evaluated_on: 2026-04-28
---

# Challenge 4 — Sole Source and Amendment Creep

> Which contracts started small and competitive but grew large through sole-source amendments? Where are vendors winning a competition and then receiving ongoing sole-source work?

---

## Data — Score: 4

**Justification.** The amendment trail is *natively* present: `fed.grants_contributions.is_amendment` is populated, and the canonical aggregations are pre-built as `fed.vw_agreement_current` (latest) and `fed.vw_agreement_originals` (initial commitment), which mechanically prevents the F-3 cumulative-snapshot trap. AB ships an explicit `ab.ab_sole_source` table (15,533 rows) with `permitted_situations` letter codes (A-4) plus `ab.ab_contracts` for competitive Blue Book contracts. Existing scripts target both sides. Score 4 because (a) cross-jurisdiction split-below-threshold detection requires inferring TBS/Alberta competitive thresholds (not in the DB), and (b) AB sole-source ↔ AB contracts join is name-based — route through `general.entity_golden_records`.

- **Datasets needed:** `fed.grants_contributions` + `fed.vw_agreement_current` + `fed.vw_agreement_originals`, `ab.ab_sole_source`, `ab.ab_contracts`, `general.entity_golden_records`.
- **Completeness:** strong on FED with the views; AB has explicit sole-source rows. Gaps: TBS competitive thresholds (~$25K goods / $40K services historically) must be hard-coded; A-4 `permitted_situations` letter→number mapping is positional inference (not Alberta-confirmed).
- **External data that could help:** TBS proactive-disclosure contracts dataset (richer original-vs-amended trail), Alberta's published "permitted situations" list to confirm A-4 letter codes.

## Implementation Difficulty — Score: 4

**Justification.** Existing scripts cover both halves: `FED/scripts/advanced/03-amendment-creep.js` already produces the FED amendment-creep report; `AB/scripts/advanced/04-sole-source-deep-dive.js` already produces the AB sole-source slice. Day-of work is wrapping them as a per-vendor agent dossier and computing the cross-cut metrics (initial vs current ratio, sole-source-as-share-of-vendor-revenue, post-competition sole-source streak). All windowed SQL — no graphs, no probabilistic linkage. ~2–3 hours of SQL plus agent wrapping. Visual demo is a per-vendor amendment timeline (the natural unit), which is a horizontal bar / step chart, not bespoke graph viz.

- **Data manipulation cost:** ~2–3 hours. Window functions over `(ref_number, recipient)` for FED amendment trails; straightforward joins for AB.
- **Visual demo path:** per-vendor dossier with (a) amendment-trail timeline, (b) original-vs-current ratio chart, (c) sole-source-share-of-revenue bar, (d) split-below-threshold flag.
- **Hard time-cost flags:** never `SUM(agreement_value)` raw — always go through the views. Avoid trying to reconstruct the amendment trail from `agreement_number` (F-10: free text, reused as program code).

## Fit — Score: 5

**Justification.** Procurement is the cleanest accountability story in the building. "This $50K bid grew to $5M through 11 sole-source amendments to the same vendor" is a sentence a Minister grasps immediately. Per-vendor dossier is naturally dynamic — the user types a vendor or department, the agent re-runs the trail live. Two-minute story passes: *"Vendor X won a competitive $50K contract in 2019; through 11 sole-source amendments it now sits at $5.2M, and 87% of their federal revenue this year is sole-source from this same department."*

- **Accountability/transparency mapping:** procurement integrity is the canonical accountability question.
- **Dynamic vs one-shot:** dynamic. Per-vendor or per-contract trail is the natural unit; user input drives the agent.
- **Two-minute story:** yes — name, dollar, amendment count, sole-source share.

---

## Risks & gotchas

- **F-3 cumulative `agreement_value`**: never `SUM` raw. Use `fed.vw_agreement_current` and `fed.vw_agreement_originals`.
- **F-1 (`ref_number` collisions, 41,046 cases)**: when reconstructing the amendment trail, partition by `(ref_number, COALESCE(recipient_business_number, recipient_legal_name))` — never by `ref_number` alone. The TBS spec promised uniqueness; the publishers broke it.
- **F-2 (duplicate `(ref_number, amendment_number)`, 25,853 pairs)**: `_id` is the only true row PK. When picking "the latest amendment" pick by `amendment_number` then by `_id` as tiebreaker.
- **F-10 (`agreement_number` is free text, reused as program code)**: never a join key.
- **F-11 (amendments can decrease)**: 2,900 amendment rows reduce value. Don't assume monotonic growth in the trail.
- **F-4 / F-5 (negative and zero `agreement_value`)**: 4,633 negative rows used as termination markers; 11,510 zero rows. Handle explicitly.
- **A-4 `permitted_situations` letter codes**: positional inference only — flag "Alberta has not confirmed" in any UI that decodes the letter.
- **AB contracts have no BNs** — route through `general.entity_golden_records`.

## Existing assets

- `FED/scripts/advanced/03-amendment-creep.js` (`npm run analyze:amendments`) — amendment-creep core.
- `AB/scripts/advanced/04-sole-source-deep-dive.js` — AB sole-source analytics.
- `fed.vw_agreement_current` / `fed.vw_agreement_originals` — F-3 mitigation already in place.
- `ab.ab_sole_source` (15,533 rows) — explicit sole-source records with `permitted_situations` codes.
- `general.entity_golden_records` for cross-jurisdiction vendor identity.

## Recommended demo shape

Per-vendor procurement dossier. The user types or selects a vendor (or department). The agent retrieves the FED amendment trail (originals + current), the AB sole-source records and competitive contracts for the same canonical vendor (via `general.entity_golden_records`), and renders: (1) amendment-trail timeline with original vs each-amendment value, (2) original-to-current ratio with a peer-comparison line, (3) sole-source share of the vendor's annual revenue, (4) a "structural amendment" verdict — agent classifies the trail as *normal indexation / scope expansion / unjustified creep* using `permitted_situations` and the original program purpose. Reuses `entities:dossier` shell. Follow-up: *"show me other vendors with the same pattern in the same department"* re-queries `vw_agreement_current` filtered by department.

---

## Final score: 13/15 — Pursue

Procurement is the most legible accountability story for the audience, and both halves of the pipeline (FED amendments + AB sole-source) already ship as analyze scripts. The win is wrapping them in a per-vendor agent that classifies the trail rather than just ranking it.
