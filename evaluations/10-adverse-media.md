---
challenge: 10
name: Adverse Media
slug: adverse-media
score_data: 1
score_impl: 2
score_fit: 4
score_resilience: 1
score_narrative: 4
score_differentiation: 5
score_total: 17
verdict: Avoid
evaluated_on: 2026-04-28
---

# Challenge 10 — Adverse Media

> Which organizations receiving public funding are the subject of serious adverse media coverage — regulatory enforcement, fraud allegations, safety incidents, criminal investigations, sanctions — distinguished from political controversy and op-eds?

---

## Data — Score: 1

**Justification.** The repo contains the recipient side (`general.entity_golden_records`) but **no media corpus and no enforcement-registry feed**. The entire ingestion + classification pipeline must be built from scratch: source acquisition, source-quality filtering, entity matching at scale, and severity classification. None of the four core modules ship anything in this direction. This is the lowest possible Data score per the rubric: core data does not exist in the repo and cannot be reasonably approximated from what is present.

- **Datasets needed:** `general.entity_golden_records` (recipient anchor); external — GDELT, OpenSanctions, regulatory enforcement registries (CRA charity sanctions, Competition Bureau, OSFI), news APIs, OCCRP Aleph.
- **Completeness:** ~zero. The recipient side is fine; the media side is entirely external.
- **External data that could help (essential, not optional):** OpenSanctions flat-file dump (`data.opensanctions.org/datasets/latest/*/targets.simple.csv`, no API key needed), GDELT events feed, CRA Charities Listings registry-actions endpoint, Competition Bureau enforcement decisions, news API of choice.

## Implementation Difficulty — Score: 2

**Justification.** Two expensive steps stack: (1) media ingestion + entity matching at scale (every story must be matched to recipients by fuzzy name, with the F-1 / no-AB-BNs caveats already documented for the recipient side), and (2) severity classification distinguishing genuine red-flag reporting from political noise — research-grade LLM-judgment-at-scale that is hard to make demo-stable in one day. The visual demo is conceptually simple (a per-recipient dossier with a "media flags" panel), but populating it with stable, defensible flags during a live demo is the actual cost. Score 2 (not 1) only because OpenSanctions provides a ready-made, low-cost first pass that can stand in for the full pipeline at demo time.

- **Data manipulation cost:** 6–10+ hours: media ingestion + entity matching + classification prompt design + evaluation. Multiplies if the team wants more than a single source.
- **Visual demo path:** per-recipient dossier with a media-flags panel. Reuses `entities:dossier` UI scaffolding.
- **Hard time-cost flags:** large external API pulls at demo time (cache aggressively); LLM classification at scale (batch and pre-compute, do not call live for every recipient); fuzzy entity matching against media mentions (precision/recall tradeoff is a research question, not a one-day deliverable).

## Fit — Score: 4

**Justification.** Strong accountability mapping — pairing public funding with regulatory or criminal red flags is exactly the "did the public know who they were funding" story the audience cares about. Naturally dynamic and per-entity: the user types or selects a recipient, the agent looks up flags live. Two-minute story passes: *"This recipient received $X and is the subject of Y enforcement action."* Score 4 (not 5) because the *demo* fit is weakened by the implementation risk above — false positives during a live demo to Ministers would undermine the story the challenge is meant to tell.

- **Accountability/transparency mapping:** very strong, directly addresses funder due-diligence.
- **Dynamic vs one-shot:** dynamic. Per-recipient lookup against a media corpus is intrinsically a query, not a report.
- **Two-minute story:** yes — but only if classification precision is high enough not to embarrass the demo.

---

## Risks & gotchas

- **Repo carries no media corpus.** Treat external-data ingestion as the critical path, not as an optional enrichment step.
- **Recipient-side caveats still apply** when matching media to funded entities: F-1 `ref_number` collisions, no AB BNs (route through `general.entity_golden_records`), partial 2024 CRA data.
- **OpenSanctions match rate on Canadian organizations is low** by default (per `analysis-toolbox.md`). Canadian PEP coverage is better than org coverage — plan for organization-side recall to be the bottleneck.
- **LLM severity classification is the demo failure mode.** A single false-positive on a Minister-relevant entity sinks the demo. Pre-curate the classified set; do not rely on live LLM calls for the showcase entities.

## Existing assets

- `general.entity_golden_records` — recipient anchor.
- `general.norm_name()` — name canonicalizer for matching media mentions to canonical names.
- `analysis-toolbox.md` — explicit pointers to OpenSanctions and OCCRP Aleph as the canonical first-check tools.

No existing scripts target this challenge.

## Recommended demo shape

Pre-compute aggressively and cache. Build a per-recipient dossier with a "media flags" panel populated from a curated bundle of (a) OpenSanctions flat-file matches against `general.entity_golden_records`, (b) any CRA charity sanctions / Competition Bureau decisions ingested as a one-time CSV, and (c) optionally a small batch-classified GDELT subset. Live demo: user picks or types a recipient, the agent reads from the pre-computed bundle and renders flags with source links. Avoid live LLM classification during the showcase. The team should explicitly scope down to a single source for the showcase entities and frame the demo as "this is what end-to-end coverage would look like" rather than overpromising recall.

---

## Final score: 7/15 — Avoid

Strongest fit story of any challenge that lacks core data, but Data = 1 is a hard veto under the rubric's precedence rule. Pursue only if the team has both (a) a member with prior experience shipping news-ingestion + entity-matching pipelines, and (b) willingness to scope the showcase to a curated, pre-classified entity set rather than a live agent.
