# Dynamic vs One-Shot — Heuristics for the Fit Score

The hackathon explicitly prefers **applied, agentic, autonomous** systems (`challenges.md` line 65). A challenge that produces a static report — however polished — fits worse than one where the user can interact with an agent that re-runs analysis live.

This file gives the heuristics used in the **Fit** dimension to distinguish dynamic problems from one-shot ones.

---

## Definition

**Dynamic problem:** the analysis is parameterized by something a user might supply at demo time — an entity name, a category, a date range, a department, a follow-up question. The agent re-runs the relevant pipeline on the new input within seconds and returns a fresh, evidence-backed answer.

**One-shot problem:** the analysis runs once on the full dataset, produces a ranked list or report, and the demo consists of showing that list. There is nothing for the user to *do* mid-demo other than scroll.

The distinction is not about how long the data work takes — it is about whether the *user's input changes the output*.

---

## Signals that a challenge is dynamic

- The natural unit of output is **per-entity** (per recipient, per vendor, per department) rather than aggregate-only.
- The user could plausibly say *"now do that for [entity X]"* and want a fresh answer.
- The analysis decomposes cleanly: a global pre-compute (once, offline) plus a per-entity re-rank or drill-down (live, fast).
- A follow-up question (*"why is this entity flagged?"*) has a substantive answer the agent can construct from the underlying data.
- An LLM judgment step is part of the pipeline (e.g. classifying severity, summarizing evidence) and benefits from being agentic rather than batched.

## Signals that a challenge is one-shot

- The output is fundamentally a **single ranked table or chart** of the whole dataset.
- Re-running on a subset would not change the conclusion in an interesting way.
- The interesting work is the offline computation; the demo is the result.
- "What if the user types in X" has no good answer because the analysis is global.

---

## Per-challenge tendency (starting point — verify in the actual evaluation)

| # | Challenge | Tendency | Why |
|---|-----------|----------|-----|
| 1 | Zombie Recipients | **Dynamic** | Per-recipient dossier. User asks about any funded entity, agent computes ceased-operations score live. |
| 2 | Ghost Capacity | **Dynamic** | Per-recipient. Same dossier shape as Zombie. |
| 3 | Funding Loops | **Mostly one-shot** | Cycle enumeration is global. Per-charity drill-down (*"what loops is this charity in?"*) gives a partial dynamic angle. |
| 4 | Sole Source / Amendment Creep | **Dynamic** | Per-vendor or per-contract trail. *"Show me amendment history for vendor X"* is a fresh agent run. |
| 5 | Vendor Concentration | **Mostly one-shot** | Concentration metrics are aggregate. Dynamic angle: *"concentration in [department X] over the last 3 years"* — re-runs slice by slice. |
| 6 | Related Parties | **Dynamic** | Per-person traversal. User picks a director, agent walks the network. |
| 7 | Policy Misalignment | **One-shot** unless reframed | Policy-vs-spending diff is a global comparison. Could be made dynamic by *"alignment score for [department X]"*. |
| 8 | Duplicative Funding | **Dynamic** | Per-recipient. *"Is this organization receiving from multiple levels for the same purpose?"* re-runs cleanly. |
| 9 | Contract Intelligence | **Mostly one-shot** | Cost-growth decomposition is aggregate. Per-category drill-down adds a dynamic angle. |
| 10 | Adverse Media | **Dynamic** | Per-recipient lookup against a media corpus is intrinsically a query, not a report. (Implementation cost is the issue, not fit.) |

---

## How to score Fit using this

- If the challenge is **naturally dynamic** and the team plans to expose it as an agent the user can converse with: Fit ≥ 4.
- If the challenge is **one-shot by nature** but the team is reframing it as a parameterized drill-down: Fit can still be 4, provided the reframing is honest (the dynamic angle is real, not cosmetic).
- If the demo is a static dashboard with no user input: Fit ≤ 3 regardless of how good the underlying analysis is.

The two-minute story-test from `rubric.md` applies: if the team's demo can end on a named entity and a dollar amount the user just asked about, the dynamic angle is real.
