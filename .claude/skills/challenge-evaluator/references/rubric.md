# Scoring Rubric

Score each of the **six** dimensions on a 1–5 scale. Sum to a final score (6–30). Verdicts:

- **Pursue** — total ≥ 22 and no dimension below 3
- **Pursue with caveats** — total 16–21, or any dimension at 2
- **Avoid** — total < 16, or any dimension at 1

**Precedence:** apply the most cautious verdict that any rule triggers. A single dimension at 1 is a hard veto regardless of total. A single dimension at 2 caps the verdict at "Pursue with caveats" even when the total is ≥ 22.

**Why six dimensions, not three:** the original three (Data, Implementation, Fit) all collapsed five top-tier challenges to the same total. With ~900 hackathon participants, the deciding question is not *"is this doable?"* but *"is this doable, robust on stage, vivid in the slide, and visibly different from existing public dashboards?"* The three added dimensions — **Demo Resilience**, **Narrative Specificity**, **Differentiation** — measure on-the-day performance and novelty, which the original three do not.

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

## Dimension 4 — Demo Resilience (1–5, higher = lower risk of embarrassing the team on stage)

Will the demo survive being driven live by a Minister or a curious audience member typing in their riding's largest charity, their own department's vendor, or a high-profile public entity? Tests the failure modes the existing Implementation dimension does not measure: false-positive risk, empty-result risk, judgment instability, and recipient-match brittleness.

| Score | Anchor |
|-------|--------|
| **5** | Output is fully deterministic. Same input always returns the same answer. The signal is direct (registry status, contract dollars, cycle membership), not inferred. False positives are structurally impossible because the rule is mechanical. *Example: Vendor concentration HHI — pure aggregation; Funding Loops cycle membership — set membership.* |
| **4** | Output is mostly deterministic but depends on a derived field that has well-understood NULLs or partial-year gaps. The team can curate a known-good showcase set and confidently demo any entity in it. *Example: Zombie Recipients — revocation/dissolution is direct, but the "ceased operations" inference for FED-only recipients needs care.* |
| **3** | Output depends on inference from indirect signals (absence of filings, ratio thresholds, fuzzy name matches). False positives on famous entities are plausible. The demo works only on a curated showcase list, and freeform user input may produce nonsense. *Example: Ghost Capacity — dependence ratio is sensitive to T3010 form revision and partial 2024 filings.* |
| **2** | Output requires probabilistic matching, LLM judgment, or graph traversal where ranking can shift between runs. A single bad result on a famous entity in front of the audience sinks the demo. *Example: Related Parties — name-based director matching has both false positives (common names) and false negatives (variants).* |
| **1** | Demo is one false-positive away from disaster. LLM judgment at scale on subjective categories (adverse media severity, policy alignment) where a misclassification on a politically sensitive entity is plausible. |

**Hard demo-resilience flags to call out explicitly:**
- Live LLM classification on user input (pre-classify and cache; do not call live)
- Fuzzy match against AB recipients without a curated showcase set
- Any analysis whose answer changes between runs on the same input
- Any output where the obvious test case (a Minister's own department, a famous charity) returns nothing or returns wrong-looking results

---

## Dimension 5 — Narrative Specificity (1–5, higher = more vivid, named-entity-concrete headline finding)

Existing Fit asks if there is a story. Narrative Specificity asks how *vivid* it is. A demo that ends on *"Charity X dissolved 9 months after $4.2M of federal grants"* lands harder on stage than *"vendor concentration in IT services rose 18%."* This is the dimension that decides which Pursue actually wins.

| Score | Anchor |
|-------|--------|
| **5** | Headline finding is a single named entity, a specific dollar amount, and a single concrete outcome. The slide writes itself: *"$X to [Y], who [Z]."* No setup required for the audience to feel the story. *Example: Zombie Recipients — "$4.2M to Charity X, dissolved 9 months later"; Amendment Creep — "$200K initial bid, $14M after 7 amendments to the same vendor".* |
| **4** | Headline is named-entity-level but requires one sentence of setup (designation, program, jurisdiction). The story is still concrete, but the audience has to be primed. *Example: Ghost Capacity — "$3M to Charity Y, which reports zero employees and 92% of expenses going to compensation for 2 directors."* |
| **3** | Headline is a named entity *cluster* or pattern rather than a single entity — *"these 12 charities form a cycle returning $50M to the same five donors."* Memorable but the audience needs to track multiple entities. |
| **2** | Headline is aggregate or ratio-shaped — *"top 5 vendors took 80% of IT spend in this department."* Punchy but requires the audience to translate from a number to an implication. |
| **1** | Headline is structural or methodological — *"funding patterns deviate from policy commitments by 14% averaged across 23 commitments."* The audience has to do work to feel why it matters. |

**Slide test:** can the team write the demo's punchline as a single sentence following the schema *"\${amount} to {named entity}, who {verb phrase}"*? If yes, Narrative Specificity ≥ 4. If the punchline is *"\${aggregate} of {category}, which {trend}"*, score ≤ 3.

---

## Dimension 6 — Differentiation (1–5, higher = more visibly novel vs. existing public tools)

With ~900 participants, the demo competes against existing public-sector data tools (GC InfoBase, Open.Canada.ca proactive disclosure, charitydata.ca, buyandsell.gc.ca, provincial open-data portals) as much as against other teams. A demo that wraps a chatbot around an existing dashboard does not stand out. A demo that composes data the public cannot get today does.

| Score | Anchor |
|-------|--------|
| **5** | The output is data the public cannot get from any existing public tool — and the underlying join is the reason. Cross-jurisdictional, cross-temporal, or cross-dataset combinations the source publishers do not produce themselves. *Example: Zombie Recipients (joins federal funding events to CRA revocation/AB dissolution timelines — no public tool does this); Funding Loops at scale (Johnson cycle enumeration on T3010 Schedule 5 — no public tool ranks circular flows).* |
| **4** | Output is *available* somewhere in fragments but no single tool composes it. The team's contribution is the agentic surface and the join, not the underlying numbers. *Example: Sole Source / Amendment Creep — TBS proactive disclosure shows individual amendments, but no public tool surfaces the original-vs-amended creep narrative as a per-vendor trail.* |
| **3** | Output is comparable to an existing public dashboard, but the agentic / per-entity-on-demand framing is new. *Example: Duplicative Funding — federal × provincial spending overlap exists in fragments; assembling it as a per-recipient query is the value-add.* |
| **2** | Output substantially overlaps an existing public tool. The differentiation is mostly UI / chatbot wrapping, not new information. *Example: Vendor Concentration — buyandsell.gc.ca and others publish concentration views by category and department; the team's contribution is mostly the conversational interface.* |
| **1** | Output is essentially a re-skin of an existing public dashboard. No new join, no new signal, no new framing — a Minister could already get this from `open.canada.ca` in three clicks. |

**Differentiation test:** finish this sentence — *"You can't get this today from {existing tool} because {reason}."* If you can name a specific tool and a specific structural reason, score ≥ 4. If the sentence becomes *"…because no one made a chatbot for it,"* score ≤ 2.

---

## Final score

Sum the six dimensions (6–30). Apply the verdict thresholds at the top of this file. The verdict is a heuristic — the team can override with reason — but the score forces an apples-to-apples comparison across challenges, and the three new dimensions are designed to break ties between challenges that all looked equally pursuable on the original three.
