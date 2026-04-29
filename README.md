# Zombie Recipients — AI For Accountability Hackathon submission

Our entry for the **AI For Accountability Hackathon** (Agency 2026, Ottawa, April 29 2026), targeting **Challenge 1 — Zombie Recipients**: companies and nonprofits that received large amounts of Canadian public funding and then ceased operations — went bankrupt, dissolved, stopped filing, or vanished — within months of cashing the cheque.

The deliverable is an **agentic system** built on the Claude Agent SDK that investigates the question end-to-end against the unified CRA + FED + AB Postgres we assembled, narrates its work to a live dashboard, paranoidly cross-checks every candidate with a verifier subagent, and emits a publishable briefing the audience can re-derive from SQL.

The agent lives in [`zombie-agent/`](zombie-agent/). The data backbone it queries lives in [`CRA/`](CRA/), [`FED/`](FED/), [`AB/`](AB/), and [`general/`](general/).

## What the demo does

A judge types a question like *"Find federal recipients that received over $1M and disappeared within a year"*. They watch:

1. The orchestrator load the `accountability-investigator`, `data-quirks`, and `zombie-detection` skills, then narrate each SQL step it runs against the read-only Postgres MCP.
2. A **universe panel** populate with the size of the search space and the count each gate dropped, so the methodology is auditable before any survivor is named.
3. **Pending finding cards** appear for each surviving candidate — entity name, BN root, primary claim.
4. A **verifier subagent** (a separately-prompted Claude Sonnet 4.6) take the full candidate list and return VERIFIED / REFUTED / AMBIGUOUS verdicts with its own independent SQL.
5. AMBIGUOUS verdicts trigger up to 3 follow-up queries from the orchestrator before it concedes or revises — the *pending → challenged → verified* cycle the rubric rewards.
6. A **per-candidate dossier** populate alongside each verified card with the templated headline, the full SQL trail, and links back to the underlying tables.
7. A **publishable briefing** ready to download once the run completes.

![zombie_agent_dashboard.png](zombie_agent_dashboard.png)

![zombie_agent_details.png](zombie_agent_details.png)

## Architecture

```
Browser ── ws ──▶ FastAPI (src.main)
                       │
                       ▼
                 ClaudeSDKClient (src.agent)
                       │
       ┌───────────────┼─────────────────────────────────┐
       ▼               ▼                                 ▼
  external stdio   in-process SDK MCP             AgentDefinition
  postgres MCP     (publish_universe,             (verifier subagent)
  (crystaldba/      publish_finding,              │ inherits parent mcp_servers
   postgres-mcp,    publish_dossier)              │ tools = [execute_sql]
   restricted)     (src.mcp_servers.ui_bridge)    ▼
                                              Postgres
```

Two streams reach the UI on purpose:
- **Activity events** (step start/complete, subagent stop) come from **hooks** that fire on tool lifecycle.
- **Structured findings** (universe, candidates, dossiers) come from a custom **in-process MCP** the agent calls deliberately — schema-enforced, visible in the activity log, never paraphrased.

Hooks → side-effecting telemetry. Custom tool → structured semantic outputs. The split is deliberate.

### Components

- **Orchestrator** — Claude Sonnet 4.6 via the Claude Agent SDK. System prompt in `src/system_prompt.py`. Runs labelled SQL, publishes findings, delegates to the verifier, defends or revises on challenge.
- **Verifier subagent** — `AgentDefinition` in `src/verifier.py`. Independent SQL access, returns VERIFIED / REFUTED / AMBIGUOUS per candidate plus a JSON verdict block. Refutes designation A / B foundations and entities whose T3010 filing window is still open — those rejections are correct, not failures.
- **Skills** in `src/workspace/.claude/skills/` — load on demand:
  - `accountability-investigator` — master playbook for any accountability question.
  - `data-quirks` — defects that silently fool naive queries (the FED `agreement_value` cumulative-snapshot trap, CRA filing-window math, AB BN absence, etc.).
  - `zombie-detection` — the Challenge 1 recipe with the $1M hard gate, dissolution death-signal CASE expression, govt-share-of-rev flag, and the templated headline format.
- **Hooks** in `src/hooks.py` — gate destructive SQL, auto-inject `LIMIT`, stream activity-panel events, announce subagent completions, and inject a self-correction message on `execute_sql` errors.
- **Dashboard UI** in `zombie-agent/dashboard/index.html` — single-page websocket client; chat input, activity log, universe panel, finding cards with status pills (pending=amber, challenged=violet, verified=green, refuted=grey), per-candidate dossiers, briefing download.
- **Reporting** in `src/reporting/` — durable run store + publishable report builder.

### Why local, not AgentCore

The Claude Agent SDK loop fits cleanly into AWS Bedrock AgentCore for multi-tenant SaaS, but for a single-laptop demo where the only consumer is one browser tab, the AgentCore container, session store, and AWS auth path are overhead with no benefit. We kept the same internal organization — FastAPI app, `agent.py`, `mcp_config`-style server builders, `skills/` workspace — so this could be lifted into AgentCore later without rework.

## The "explainability bar" — non-negotiable

Every numeric claim, percentage, date, name, dollar figure, and ratio that ends up on a card traces to a SQL query in the same session, surfaced three ways:

- The **universe panel** (one `publish_universe` call) shows search-space size and per-gate drop counts.
- The **per-candidate dossier** (one `publish_dossier` per finding) shows the full evidence trail.
- The **`sql_trail` field** on every `publish_finding` carries the labelled queries that produced the claim.

The headline string on each verified card is a templated format string defined in the `zombie-detection` skill — filled with already-queried integers and dates, never LLM-paraphrased. The audience is the federal Minister, deputies, and auditors; they can re-derive every number from the database.

## Quick start

```bash
cd zombie-agent
cp .env.example .env                    # then fill in ANTHROPIC_API_KEY + READONLY_DATABASE_URL
uv sync
docker pull crystaldba/postgres-mcp     # one time
uv run python scripts/smoke_test.py     # verify orchestrator + verifier both reach Postgres
uv run uvicorn src.main:app --host 127.0.0.1 --port 8080 --reload
# open http://127.0.0.1:8080
```

The smoke test runs two probes: the orchestrator listing tables in the `cra` schema, then delegating a one-line `SELECT COUNT(*)` task to the verifier. Both must pass before any of the demo logic matters.

`scripts/smoke_test.py` and `tests/` are not deleted between runs — they are the scaffolding that proves the spine is right when the live database is misbehaving.

## The data backbone the agent queries

The agent's read-only Postgres MCP points at a hackathon database that unifies four Canadian government open-data sources, each in its own schema, with a cross-dataset entity-resolution pipeline producing ~851K canonical golden records. None of the agent's findings would be possible without this groundwork.

| Module | Schema | Rows | What it owns |
|--------|--------|------|--------------|
| [`CRA/`](CRA/) | `cra` | ~8.76M | T3010 charity filings 2020–2024, plus pre-computed circular-gifting / SCC / overhead / risk-scoring tables. |
| [`FED/`](FED/) | `fed` | ~1.275M | Federal Grants & Contributions disclosures, with views that correctly handle the `agreement_value` cumulative-snapshot trap. |
| [`AB/`](AB/) | `ab` | ~2.61M | Alberta grants, contracts, sole-source, non-profit registry. |
| [`general/`](general/) | `general` | ~10.5M | Cross-dataset entity-resolution pipeline (deterministic + Splink + LLM verdict) producing `entity_golden_records`. |

Auxiliary modules also exist (`CHARSTAT/`, `CORP/`, `LOBBY/`, `PA/`) feeding the addendum signals described in `plans/zombie_agent_*_addendum.md` — corporate-registry status, lobbying-registry presence, and web-presence checks that further harden the death signal.

Each module is a self-contained Node project with its own `package.json`, `lib/db.js`, and `CLAUDE.md`. **Read the per-module `CLAUDE.md` before working in `CRA/`, `FED/`, or `AB/`** — they document the analytical methodology and the dataset-specific gotchas that the `data-quirks` skill encodes for the agent.

### Setting up the database

Two options, both documented in [`.local-db/README.md`](.local-db/):

```bash
# Option A — connect to the shared Render database (read-only, fast)
# Drop the .env.public files from the event-day info pack into each module dir.
cd CRA && npm install && npm run verify

# Option B — recreate locally
docker compose up -d                   # Postgres 18 on port 5434
createdb hackathon
cd .local-db && npm install
DB_CONNECTION_STRING=postgresql://user:pass@localhost/hackathon npm run import
```

The JSONL data bundle (~13 GB) ships out of band; schemas, manifest, and import/export scripts are committed. `pg_trgm` and `fuzzystrmatch` extensions are required.

## Plans and design notes

The build evolved across four design docs in [`plans/`](plans/), each captured before the corresponding implementation block:

- `zombie_agent_build_manual_v2.md` — the hour-by-hour build plan (validated against BIRD-INTERACT, CHESS, MAGIC).
- `zombie_agent_v3_correctness_and_polish.md` — explainability-bar additions, universe panel, dossier panels, templated headlines.
- `zombie_agent_corp_pa_addendum.md` — corporate-registry + Public Accounts signal additions.
- `zombie_agent_lobby_addendum.md` — lobbying-registry signal.
- `zombie_agent_web_presence_addendum.md` — web-presence death signal.

Read these before changing the orchestration, the skills, or the death-signal definitions — the rationale for each rule is in the plans, not always in the code.

## Repository layout

```
agency-26-hackathon/
├── zombie-agent/        # The hackathon submission — agentic Challenge 1 system
├── CRA/  FED/  AB/      # Per-source ingestion + analysis modules (cra/fed/ab schemas)
├── general/             # Cross-dataset entity resolution → entity_golden_records
├── CHARSTAT/ CORP/ LOBBY/ PA/  # Auxiliary signals feeding the addendum work
├── .local-db/           # Exporter / importer / DDL / manifest for local DB recreation
├── plans/               # Design docs for the zombie-agent build (read these)
├── evaluations/         # Run captures + scoring artefacts
├── docker/postgres/     # Docker init SQL (creates `hackathon` DB + extensions)
├── docker-compose.yml   # Postgres 18 on port 5434
├── tests/               # Cross-module integration tests
├── challenges.md        # Full ten-challenge brief from the organizers
├── analysis-toolbox.md  # Canonical OSS libraries per problem family
├── KNOWN-DATA-ISSUES.md # Data-quality issues catalogued before agent was built
├── ATTRIBUTIONS.md      # Data sources + third-party libraries
├── SECURITY.md          # Credential convention
├── LICENSE              # MIT (covers source code only — data uses original OGLs)
└── index.html           # Browsable static documentation of the database
```

## License

Source code: **MIT** — see [LICENSE](LICENSE).

Data: redistributed under the original publishers' licences — **[Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada)** (CRA + federal data) and **[Open Government Licence – Alberta](https://open.alberta.ca/licence)** (Alberta data). The MIT licence on this repository covers the source code only; it does not relicense the underlying data. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for full credits and [SECURITY.md](SECURITY.md) for the credential-handling convention.

## Framing rule — non-negotiable

The agent's output is **audit leads, not accusations**. Every card uses language like *"signals consistent with a dormant funded recipient"*, *"public-record gaps that warrant follow-up"*, *"pattern is consistent with…"*. Words like "fraud", "stole", "misappropriated", "criminal" never appear in user-facing text. The methodology produces investigative leads worth an auditor's time — not legal conclusions.
