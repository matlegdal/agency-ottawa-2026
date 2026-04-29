---
challenge: 1
name: Zombie Recipients
slug: zombie-recipients
score_data: 4
score_impl: 4
score_fit: 5
score_resilience: 4
score_narrative: 5
score_differentiation: 5
score_total: 27
verdict: Pursue
evaluated_on: 2026-04-28
plan_evaluated: plans/zombie_agent_build_manual_v2.md
---

# Challenge 1 — Zombie Recipients (Plan v2 Evaluation)

> Did public funding go to entities that ceased operations within 12 months — or to entities so dependent on public money that they could not survive without it? **This evaluation grades `plans/zombie_agent_build_manual_v2.md` specifically, not the raw challenge.** Special weight on Differentiation: what will stand out among 900+ participants?

---

## Data — Score: 4

**Justification.** Plan grounds every claim in the existing schemas: `fed.vw_agreement_current` (avoiding the cumulative-snapshot trap), `cra.cra_identification` for revocations, `ab.ab_non_profit` for dissolutions, all routed through `general.entity_golden_records` for canonical entity keying. The `data-quirks` skill is loaded before the first SQL query — the plan explicitly enforces this through the methodology skill. The remaining 4-not-5 gap is unchanged: FED-only commercial recipients with no CRA registration and no AB record have no first-class "ceased operations" signal, only an inference from absence. Plan does not pretend to solve this; it leans on the verifier subagent + iterative-exploration loop to surface ambiguity rather than hide it.

- **Datasets needed:** `fed.vw_agreement_current`, `cra.cra_identification`, `cra.cra_financial_details`, `ab.ab_non_profit`, `ab.ab_grants`, `general.entity_golden_records`, `general.vw_entity_funding`, `general.entity_source_links`.
- **Completeness:** strong for charities and AB nonprofits; the plan correctly flags partial 2024 CRA filings and the T3010 form revision as quirks the verifier must respect.
- **External data that could help:** OpenSanctions (already mentioned as §16 extension), Corporations Canada bulk dissolutions, and `charitydata.ca` for the manual hand-verification step in H11–12.

## Implementation Difficulty — Score: 4

**Justification.** The plan is a 16-hour two-day build with realistic hour-by-hour blocks, ~1100 LOC across nine Python files. Core SQL leans on existing assets (`FED/scripts/advanced/05-zombie-and-ghost.js`, the views, the golden records) — no Splink re-run, no Johnson cycles, no bespoke graph viz. The risky integration work (Postgres MCP container in restricted mode, in-process MCP for the UI bridge, three hooks, an `AgentDefinition` for the verifier) is well-scoped and the SDK primitives (`ClaudeSDKClient`, `HookMatcher`, `@tool`, `create_sdk_mcp_server`, `AgentDefinition`) are all named correctly. The warm-path cache (§12) is a load-bearing demo-resilience play. Score 4 not 5 because the iterative-exploration loop adds real moving parts — bounded rebuttal budget, AMBIGUOUS verdict pathway, three-state UI animation — and these need rehearsal, not just code.

- **Data manipulation cost:** ~2 hours; the heavy lifting is delegated to existing scripts and views.
- **Visual demo path:** custom three-panel HTML page (chat + activity log + briefing). Not reusing `entities:dossier`. Plan justifies this — the activity panel *is* the differentiator and `entities:dossier` doesn't show agent reasoning.
- **Hard time-cost flags:** none in the build itself. The risk is in the **rehearsal** block (H14): 5 end-to-end runs to pin question phrasing and confirm the challenged → verified animation fires reliably. If the iterative-exploration loop is flaky, the demo loses its moneyshot.

## Fit — Score: 5

**Justification.** Maximally agentic by design. The user types a natural-language question; the orchestrator decomposes, queries, publishes pending findings, delegates to a verifier subagent, **iterates on challenges with up to 3 follow-up queries per candidate**, and converges on verified/refuted verdicts. This is not a chatbot over a dashboard — it is a structured investigation surfaced live. The two-minute story test passes cleanly: the pitch script (§14) ends on *"$4.2M to <Entity>, no filings since 2022, 87% government dependency"*. Per `dynamic-vs-oneshot.md`, Zombie Recipients is naturally Dynamic, and this plan exposes that nature directly — the user can ask a fresh question and get a fresh investigation, not a pre-rendered report.

- **Accountability/transparency mapping:** as direct as it gets — *did the public get anything for this money?* answered per named entity with a SQL trail.
- **Dynamic vs one-shot:** dynamic, with a global pre-compute (warm path Step A) plus per-question agent re-run.
- **Two-minute story:** yes — the pitch script demonstrates it landing in 50s.

## Demo Resilience — Score: 4

**Justification.** This is the dimension where the plan's architecture earns its keep. Five mechanisms reduce stage risk: (1) **PreToolUse hook** denies destructive SQL — eliminates the "Minister types DROP TABLE" failure. (2) **PostToolUse hook with self-correction** — SQL errors trigger a retry-with-context turn rather than a stalled agent. (3) **Warm-path cache** — Render DB latency does not kill the demo; Step A falls back to pre-computed JSON. (4) **Iterative-exploration loop** — when the verifier challenges a candidate, "ambiguous on stage" becomes a feature, not a bug; the orchestrator follows up. (5) **Hand-verified showcase set** (H11–12) — three demo zombies validated against `charitydata.ca` and provincial registries. The 4-not-5 cap stays because the demo is still inferential on FED-only recipients, and a Minister typing in a famous entity from their portfolio could still produce an empty result. The plan mitigates with the "Try this question" suggestion bar (H14) — pre-vetted prompts that always land — but a freeform user input is still not bulletproof.

- **Determinism:** mostly direct registry signals (CRA revocation, AB dissolution); LLM judgment is bounded to the verifier's verdict (VERIFIED/REFUTED/AMBIGUOUS) and never invents numbers.
- **Failure mode:** "empty result on rare entity" rather than "wrong-looking result on famous entity" — the hand-verified showcase set sets the floor.
- **Curated showcase set required?** Yes — three zombies from H11–12, plus 2–3 pinned prompts in the suggestion bar.

## Narrative Specificity — Score: 5

**Justification.** Pitch is engineered around a single named-entity headline with a specific dollar amount and a specific outcome — the slide-test schema verbatim. Slide 2 ("Insight") is *"<Entity> received $4.2M from <departments> 2019–2021. No filings since 2022. Government revenue dependency 87% in their last filing year."* — this is exactly the *"$X to {named entity}, who {verb phrase}"* schema. Three demo zombies in different sectors (H11–12) gives the team three shots at landing this. The briefing panel reinforces — entity name big, BN small, $ as headline, verifier verdict as colored pill. There is no aggregate framing anywhere in the user-facing pitch.

- **Slide test:** passes — *"$4.2M to <Entity>, dissolved 9 months later, last filing showed 87% government revenue dependency."*
- **Setup required:** none — the audience hears the entity name and the dollar amount in the same sentence.

## Differentiation — Score: 5

**Justification — and this is where the plan really stands apart from 900+ teams.**

The challenge itself already scores 5 on Differentiation (the cross-jurisdictional join — federal funding events × CRA revocation × AB dissolution × charity financials — does not exist in any public tool). But that's the floor. The *plan* layers four additional differentiators that other teams will not bring:

1. **Adversarial verifier subagent** (CHESS, ICML 2025). Most teams will build a single agent that queries data and presents findings. This plan runs a *second agent* whose only job is to disprove the first. On stage, the audience watches the verifier challenge a candidate and the orchestrator defend or revise — that is a visible reasoning loop no chatbot demo will match.

2. **Iterative-exploration loop with bounded rebuttal budget** (BIRD-INTERACT, ICLR 2026 Oral). The pending → challenged → verified animation is the demo's moneyshot. Three things make this rare: (a) most hackathon agents do not have a verifier at all, (b) those that do treat REFUTED as a failure, (c) almost none implement a bounded follow-up budget. This plan does all three and rehearses the animation explicitly (H13, H14, H10 test).

3. **Persistent failure-catalogue skill** (MAGIC, AAAI 2025). The `data-quirks` skill loads *before* the first SQL query, codifying the F-/C-/A- gotchas (cumulative-snapshot trap, T3010 form revision, missing AB BNs). Other teams will hit the $921B-vs-$816B trap live on stage. This team will not, and the architecture diagram on slide 3 will footnote *why* it doesn't — citing the published research the design tracks.

4. **Architecture transparency on stage**. The activity panel is itself a differentiator. Most teams will demo a chatbot answer; this team demos *the agent doing the work* — every SQL query labeled, every step timed, every error recovered, every verifier verdict animated. The audience sees the investigation, not just the conclusion. This is the visceral difference between "AI gave us an answer" and "AI ran an investigation we could audit."

The slide-3 footnote — *"Adversarial verifier subagent (CHESS, ICML 2025), persistent failure-catalogue skill (MAGIC, AAAI 2025), iterative-exploration loop (BIRD-INTERACT, ICLR 2026 Oral)"* — is the single most underrated move in the plan. It converts "clever hackathon project" into "research-aligned production-shape" in one line judges will read without the team needing to explain it. Among 900 participants, the median submission is a chatbot wrapped around a query interface. This plan is visibly not that.

- **What can't you get from existing tools?** *"You can't get this today from `open.canada.ca` or `charitydata.ca` because no public tool composes federal funding events with CRA revocation timelines, AB dissolutions, and dependence ratios on a per-recipient basis — and no public tool surfaces an auditable agent reasoning trail with adversarial verification."*
- **Source of the novelty:** the cross-dataset join (data-level), the adversarial verifier (architecture-level), the iterative-exploration loop (interaction-level), the SOTA-citation framing (presentation-level). Four layers, not one.

---

## What will catch judges' attention — ranked

1. **The challenged → verified animation.** When the verifier raises an objection mid-demo and the orchestrator runs follow-up queries to defend, judges see *reasoning happen*, not just output. This is the single most differentiated moment in the demo. Make sure at least one of the three demo zombies takes the challenged path (per H13 note). If the animation doesn't fire on every run, fake-pin one with deterministic setup.
2. **The named-entity headline with a SQL trail.** Slide 2 names a real organization with a real dollar amount, and every claim in the briefing panel has a clickable SQL query. This is what a Deputy Minister would actually consume. Most teams will show charts; this team shows a one-page briefing.
3. **The architecture footnote on slide 3.** Three SOTA citations in one line, mapped 1:1 to three architectural choices (verifier / skill / loop). Judges with research backgrounds will notice. Judges without will register *"these people read papers."*
4. **Stage-resilience invisibles.** Hooks denying destructive SQL, warm-path cache surviving DB latency, error-retry self-correction. The audience won't see these as features — they'll just notice the demo doesn't break. Compounds across the 4-minute pitch.
5. **The agentic surface on a Canadian gov dataset.** Most agent demos at this hackathon will be on synthetic or trivial data. This one runs against the real curated CRA + FED + AB DB and produces auditable findings. The story *"five minutes of agent time → one-page briefing a Minister can act on"* lands because the data is real.

## Risks & gotchas (specific to executing this plan)

- **`fed.agreement_value` cumulative trap (F-3).** Plan correctly routes through `vw_agreement_current` — verify the verifier subagent also uses the view, not the raw column.
- **`fed.ref_number` collisions (F-1, 41,046 cases).** Plan does not explicitly call out the `(ref_number, COALESCE(...))` grouping rule — add to `data-quirks` skill if not already there.
- **AB has no BNs.** Verifier's step 3 correctly uses `entity_source_links` resolution rather than BN-join.
- **Partial 2024 CRA data.** Verifier's step 1 should restrict the "no 2024 filing" check to entities with fiscal year-end before 2024-06-30 to avoid premature zombie-flagging.
- **2024 T3010 form revision.** Dependence-ratio computation must handle both NULL patterns (fields removed in 2024, fields added in 2024).
- **Iterative-exploration loop runs away.** Plan caps at 3 follow-ups per candidate via system prompt. Consider a hook-level counter as belt-and-braces — system-prompt-only enforcement can be ignored under pressure.
- **Verifier returns AMBIGUOUS on all candidates.** Plan calls this a feature; it is, *if* the orchestrator's rebuttal is convincing. If it's not, the demo looks indecisive. Rehearse this case (H14).

## Existing assets the plan correctly leverages

- `FED/scripts/advanced/05-zombie-and-ghost.js` — analytical core.
- `general.entity_golden_records`, `general.norm_name()`, `general.extract_bn_root()` — cross-dataset keying.
- `fed.vw_agreement_current`, `fed.vw_agreement_originals` — pre-built views avoiding the cumulative trap.
- Postgres extensions `pg_trgm`, `fuzzystrmatch` — already enabled.
- Hackathon `.env.public` files — distributed event-day credentials.

## Recommended demo shape (what this plan ships)

A web page with three panels — chat input, agent activity log, briefing panel. Judge types *"Find federal recipients that received over $1M and disappeared within a year."* They watch the activity log fill with labeled SQL steps as the orchestrator investigates the live Render DB. They watch the verifier subagent challenge a candidate, then watch the orchestrator run three follow-up queries to defend. They see 3–5 named entities populate the briefing panel — entity name, BN, dollar figure, dependency percentage, verifier verdict as a colored pill — with at least one card animating pending → challenged → verified. Total runtime 75–120 seconds. The architecture diagram on slide 3 cites CHESS, MAGIC, BIRD-INTERACT in a footnote.

---

## Final score: 27/30 — Pursue

The plan executes the highest-scoring challenge with the strongest differentiation strategy in the field. The four-layer differentiation stack (cross-dataset join + adversarial verifier + iterative-exploration loop + SOTA-cited architecture) is the answer to *"why this team, not the other 899."*
