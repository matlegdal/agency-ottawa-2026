# Claude-Code-Native Toolbox for Canadian Government Accountability — A 48-Hour Hackathon Menu (April 2026)

## Executive summary

This is a curated menu of Claude Code primitives (MCP servers, skills, subagents, hooks, slash commands, plugins) plus the OSS libraries, public APIs, datasets, and 2024–2026 papers a Claude-Code-native team should plug in to attack the ten Canadian-government accountability challenges defined in the brief — over a 48-hour hackathon at a venue with intermittent wifi. Three deployment tiers are concretised: a pure-CLI Tier 0, a CLI + existing dossier-UI Tier 1, and an Agent-SDK-wrapped Tier 2 with runnable Python and TypeScript skeletons. A 10-challenge × 4-primitive matrix and five quick-win demo sketches are included. Every recommendation is anchored to an upstream repo or vendor doc with a recency note (most are within the last 6–9 months; stale ones are flagged).

The substrate has matured a lot in the last six months: Claude Code's plugin system, hooks, skills, and subagents are now first-class and well-documented [s1, s4, s7, s9, s10]; the Claude Agent SDK exposes the same loop as a Python/TS library with explicit `ClaudeAgentOptions` knobs for skills, plugins, hooks, file checkpointing, and subagent transcripts [s11, s14, s15, s16]; the MCP server catalog now spans Postgres-with-EXPLAIN [s32], OpenSanctions [s39, s40], Wikidata SPARQL [s41], sandboxed code execution [s44, s45], and visual notebooks [s36]. April 2026 is also the first month a single open-weights model (DeepSeek V4-Pro, MIT) has approached Claude Opus 4.6 on SWE-bench at ~14% the cost [s103, s104] — making local fallback realistic.

---

## Part 1 — Landscape tables, by stream

> **Out-of-scope reminder (per brief).** Every tool below is selected to slot into Claude Code as MCP / skill / subagent / plugin / hook / slash command / Bash-callable script / Agent SDK call. Framework comparisons (LangGraph, CrewAI, AutoGen, AG2, smolagents) are intentionally excluded.

### Stream A — Claude Code + Agent SDK (April 2026 snapshot)

| Primitive | What it is | Status April 2026 | Why it fits |
|---|---|---|---|
| Claude Code CLI | Anthropic's terminal/IDE agent runtime | Active; April 2026 release added tabbed `/agents` UI (Running tab + Library), `/reload-plugins` no-restart, `duration_ms` in PostToolUse, faster startup with concurrent MCP connect, large-session perf 67% faster on 40MB+ sessions [s2, s3]. |  Substrate. Headless via `claude --print` + `--output-format json`, session resume via `--resume <id>` [s1]. |
| `CLAUDE.md` scopes | Project / user / enterprise memory | Stable | Inject DB connection string, schema digest, "today's date is 2026-04-25", challenge focus. |
| Subagents | Frontmatter-based specialised agents (description-routed) | Stable; auto-invoked by description match; per-subagent tool scoping | One subagent per accountability challenge: `zombie-analyst`, `loop-detector`, `policy-mapper`. |
| Skills | YAML-frontmatter packages w/ progressive disclosure (`SKILL.md` + scripts/refs) | Stable, plugin-shippable | Encapsulate the recipe for each accountability challenge as a skill. Loaded via `skills` field in `ClaudeAgentOptions` for SDK use. |
| Plugins | `plugin.json` bundles of skills, subagents, hooks, MCPs, slash commands | Stable; April 2026: install resolves missing deps from configured marketplaces; local plugins via `--plugin-dir` | Ship hackathon team's whole config as one plugin. |
| Hooks | PreToolUse, PostToolUse, UserPromptSubmit, SessionStart, Stop, SubagentStop, PreCompact, Notification | Stable; April 2026 added stderr first-line in transcript + `duration_ms` | Block destructive SQL, log queries, inject date, set `search_path`. |
| Slash commands | Built-in (`/agents`, `/mcp`, `/hooks`, `/skills`, `/plugin`, `/statusline`, `/clear`, `/compact`) + custom in `.claude/commands/` | Stable | Encode common queries (`/zombies`, `/loops`, `/sole-source-creep`). |
| Statuslines | Shell command on every tick → JSON in, single line out, `padding` field | Stable; ccstatusline + claude-statusline communities active | Show current model, session cost, current accountability challenge. |
| Output styles | Customise transcript voice/format | Stable | Switch to "Minister briefing" voice for demo. |
| Sandboxes / background tasks | Spawn long-running shell, monitor | Stable | Run lifelines fits, GraphRAG indexing in background while continuing chat. |
| Claude Agent SDK (Python `claude-agent-sdk` — `pip install claude-agent-sdk`) | Same loop exposed as a library | 0.x active development through 2026; `ClaudeAgentOptions` now has `skills`, `plugins`, `thinking`, `enable_file_checkpointing`; `ClaudeSDKClient` has `set_permission_mode`, `set_model`, `interrupt`, `rewind_files`, `get_mcp_status`, `list_subagents()`, `get_subagent_messages()` [s12, s14, s15, s17] | Tier 2 wrapper. Renamed from "Claude Code SDK" to "Claude Agent SDK" in Sept 2025 to reflect its general-purpose nature [s11]. |
| Claude Agent SDK (TypeScript `@anthropic-ai/claude-agent-sdk` — `npm i @anthropic-ai/claude-agent-sdk`) | TS counterpart | 0.x active | Tier 2 web app option (Next.js / Hono). |
| Permission modes (CLI + SDK) | `"default"`, `"acceptEdits"`, `"plan"`, `"bypassPermissions"` | Stable | The brief asked for "ask/auto/custom" — that nomenclature appears in third-party guides but is *not* the actual Claude Code set; the four above are what the SDK and CLI accept. |

Gotchas surfaced from Claude Code GitHub issues and 2026 guides:

- PreToolUse hook **must exit code 2** to block (writing to stderr); exit 0 with a denial message in stdout does not block in current builds — there is an open issue (#23284) where the hook reports an error but doesn't block [s4, s18, s19]. Always test with a `rm -rf` / `DROP TABLE` example before relying on it.
- Permission rules merge in deny → ask → allow precedence; project `.claude/settings.json` overrides user settings even for *allows*. A previously-confusing behaviour: `enableAllProjectMcpServers` plus a stale `settings.local.json` can auto-approve MCP tools without prompting (issue #395 in `ruvnet/ruflo`).
- `--plugin-dir` loads at session start — file changes only picked up next session; `/plugin update` doesn't operate on local plugin directories. Use `/reload-plugins` (April 2026 update) for skill changes.

### Stream B — MCP servers worth installing

| Server | Type | Last commit | Why it fits this stack |
|---|---|---|---|
| **Postgres MCP Pro** (`crystaldba/postgres-mcp`) | Read-only or RW Postgres + EXPLAIN, hypopg-based hypothetical-index simulation, index-tuning, health checks [s32] | Jan 2026, 2k+ stars [s32]. **Recommended** primary Postgres MCP for this hackathon — beats the official `@modelcontextprotocol/server-postgres` (last published "a year ago", v0.6.2) on schema introspection depth, query-plan visibility, and pg_stat_statements exposure [s33, s34]. | Lets Claude `EXPLAIN` a 23M-row query before running it; vital on `cra_qualified_donees` × loops joins. |
| `@modelcontextprotocol/server-postgres` | Anthropic reference Postgres MCP — read-only, schema introspection | v0.6.2 (~2025). Maintained but feature-light. **Flag: Postgres MCP servers across the catalog are essentially read-only and lack pagination/row-cap defaults beyond `LIMIT` injection** — guard with hooks. | Minimal fallback if Postgres MCP Pro install fails. |
| pgEdge Postgres MCP | Pulls primary keys, foreign keys, indexes, constraints; performance metrics | Active 2025-2026 | Alternative with tighter performance focus. |
| **DuckDB MCP** | Run DuckDB SQL on parquet/csv/Postgres FDW | Active | Useful for fast pivot on `fed.grants_contributions` exports without touching live Postgres; Splink already uses DuckDB. |
| **Marimo MCP support** (`--mcp` flag in recent 2026 builds; check installed version's `marimo edit --help` for exact spelling) | Turns any marimo notebook into MCP server exposing its cells/variables as tools | Released 2026; marimo in active 2026 development | Gives Claude an "interactive notebook" in front of him — read variable, run cell, get plot. |
| **Tavily MCP** (`tavily-ai/tavily-mcp`) | search/extract/map/crawl, 1k free queries/mo on free tier | Production-ready | Default web-search MCP for research tasks. |
| **Exa MCP** | Semantic + neural web search | Active | Better for "find papers/repos similar to X" semantic queries. |
| Perplexity MCP, Brave Search MCP | Alternative web-search MCPs | Active. Brave Search MCP is in Anthropic's official `modelcontextprotocol/servers` repo. | Cost / quality alternative. |
| **Firecrawl MCP** | Web scraping + content extraction | Active | Scrape provincial corporate registries that lack APIs. |
| **OpenSanctions MCP** (`scka-de/opensanctions-mcp`, `apify/financial-crime-screening-mcp`) | Hits OpenSanctions API for sanctions + PEP screening (320+ lists, OFAC/EU/UN/UK HMT) | Active 2025-2026 | Direct fit for challenge 10 (Adverse Media — sanctions overlay). The Apify "Financial Crime Screening MCP" wraps 13 actors (OFAC, OpenSanctions, Interpol, FBI, FARA, FEC, OpenCorporates, GLEIF, SEC, CFPB, FDIC). |
| **OpenSanctions self-hosted** (yente) | Two-Docker-container service (yente + Elasticsearch). Default refreshes every 30 min, daily-ish releases. 4GB RAM minimum, 8GB recommended. | Active | **Offline fallback**: download the bulk export and run yente locally for the hackathon — solves event-day wifi risk for sanctions screening. PEP coverage: 28 countries (verify Canada coverage in current dataset). |
| **ICIJ Offshore Leaks** (CSV/Neo4j packages) + Reconciliation API | 810k+ offshore entities, OpenRefine-Reconciliation API spec, Neo4j export | Maintained Jan 2025 update | Match charity directors / suspicious recipients against offshore filings. |
| **Aleph (OCCRP)** | Public-records + leaks platform with API | Active | Investigative-journalism graph queries. |
| **Wikidata MCP** (`zzaebok/mcp-wikidata`, `QuentinCody/wikidata-sparql-mcp-server`) | SPARQL over Wikidata (PEP graph, corporate ownership) | Active | Free PEP signals + cross-references. |
| **GDELT 2.0** | Free real-time global news event dataset; queryable via BigQuery-public or Full Text Search API | Continuously updated | Adverse-media baseline; free; high noise. |
| **Neo4j MCP** (`neo4j-contrib/mcp-neo4j`) | Cypher queries, schema inspection | Official; active | If the team wants to explore funding-loop subgraphs natively. |
| **Memgraph MCP** | Cypher-compatible, in-memory graph | Active 2026 | GraphRAG-friendly. |
| **Kuzu** (no official MCP yet — embedded only) | MIT-licensed embedded property graph DB; full-text + vector search built in; bulk-load from parquet/Arrow/DuckDB | v0.11.x late 2025; active. **Recommended for 48h hackathon**: run as Python lib, no daemon. | Wrap as Bash-callable script via skill instead of MCP. |
| **Apache AGE** | PG extension exposing openCypher + property graph on Postgres | AGE 1.5+ supports PG 11–18 per official setup page (also Postgres Pro's "Apache AGE Extension" page). If extension build fails on local PG18, fall back to recursive CTEs **or** Kuzu — don't burn hours on AGE compile errors during a 48h build. | Lets the team run Cypher directly on the existing Postgres without a new database. Fits the brief's "no new datastore" preference. |
| **E2B MCP** | Firecracker-microVM sandboxes per session | Active; ~50% F500 adoption | Code execution sandbox for "let Claude run a Python notebook". |
| **Daytona MCP** | Docker-container-based sandboxes, sub-90ms creation | Active 2025 | Cheaper E2B alternative for hackathons. |
| **Modal MCP** | Serverless GPU-Python | Active | Only if you need GPU for a 70B local model. |
| **Cloudflare Sandboxes MCP** | Persistent isolated Linux envs, GA April 2026 (egress proxy, PTY, snapshot recovery) [s45] | GA April 2026 [s45] | Persistent state across demo restarts — useful. |
| **hopx.ai sandbox MCP** | Lightweight sandbox MCP often paired with Claude desktop | Active | Alternative. |
| **Microsoft Playwright MCP** (`microsoft/playwright-mcp`) | Browser driving via accessibility-snapshot (no screenshots/vision) | Active (`@playwright/mcp` on npm) | Scrape provincial registries, lobbying disclosures, ATIP portals. |
| **Chrome DevTools MCP** | Live Chrome debug — inspect network, console, screenshots, performance | Active | Debug Pipeline Dashboard / Dossier Explorer if they break in front of a minister. |
| **Filesystem MCP** (official) | Sandboxed read/write to a directory | Active | Read CSV exports, write report artifacts. |
| **GitHub MCP** (`github/github-mcp-server`) | Issues/PRs/code reading | Official | Pull related repo context. |
| **Git MCP** | Local git operations | Official | Track findings as commits. |
| **Visualization MCPs**: Chart/Plotly via Python in a sandbox MCP, Mermaid (rendered inline by Claude Code), Vega-Altair via skill | Mostly via sandbox MCP, not standalone | Mermaid/Graphviz preferred for simple network sketches because Claude Code renders Mermaid in transcripts natively. |

### Stream C — Existing skills, subagents, plugins worth adopting

| Resource | Fit | Notes |
|---|---|---|
| `hesreallyhim/awesome-claude-code` | Master discovery list | Curated; skills, hooks, slash commands, plugins, orchestrators. |
| `VoltAgent/awesome-claude-code-subagents` | 232+ subagents across language specialists, data/AI, devops | `data-analyst.md`, `sql-pro.md` directly relevant. **Recommended: copy and tweak `sql-pro` into `t3010-sql-pro` with stack-specific schema hints**. |
| `VoltAgent/awesome-agent-skills` | 1000+ skills compatible with Claude Code/Codex/Gemini CLI/Cursor | Cherry-pick policy-doc, citation, fact-check skills. |
| `wshobson/agents` | 65 specialised skills, multi-skill workflows, full-stack orchestration | Strongest "production-ready" skills set; useful for backend infra around the dossier UI. |
| Anthropic `claude-plugins-official` | Official marketplace `marketplace.json` reference layout | Use as template for in-team plugin. |
| `claudemarketplaces.com` | Aggregator UI with 87+ plugins from 10+ sources sorted by installs/stars | Single shopping window. |
| `199-biotechnologies/claude-deep-research-skill` | 8-phase research pipeline w/ source credibility scoring + automated validation | Drop-in for the `deep-research` skill the brief asks for. |
| `Imbad0202/academic-research-skills` | 13-agent research team, modes: full/quick/review/lit-review/fact-check/socratic/systematic-review | Adapt "fact-check" + "Socratic" modes for ministerial briefings. |
| `Weizhena/Deep-Research-skills` | Structured deep research with human-in-the-loop | Useful for ministerial sign-off step. |
| `daymade/claude-code-skills` (deep-research v6) | Multi-pass synthesis, source-type governance, mandatory counter-review, citation registry | Strong critic-loop pattern (this very document follows the same pattern). |
| `davila7/claude-code-templates` | `fact-checker.md` agent in deep-research-team | Copy verbatim, reuse for citation enforcement. |
| `lingzhi227/agent-research-skills` | 31 skills covering research-paper lifecycle | Useful for academia-audience demo. |

**Custom subagents to ship in the team's plugin** (verbatim names):

- `t3010-sql-pro` — read-only PostgreSQL on the four schemas; injects condensed DDL on init; uses pg_trgm for fuzzy joins; refuses queries without LIMIT.
- `loop-detector` — calls already-precomputed `loops`/`loop_edges`/`johnson_cycles` tables, classifies cycles benign-vs-suspicious via LLM judge.
- `zombie-analyst` — runs lifelines KM curve on `cra_identification` × `fed.grants_contributions`.
- `ghost-scorer` — composes pass-through detection, comp concentration, zero-employee detection into a single 0–1 score.
- `policy-mapper` — zero-shot classifies program descriptions vs. mandate-letter buckets via DeBERTa-v3 zero-shot or Claude structured output.
- `adverse-media-screener` — entity-link → OpenSanctions → news API → adverse-media classifier.
- `vendor-concentration-analyst` — HHI + Lorenz on `fed.grants_contributions` and `ab.ab_contracts`.
- `amendment-creep-watcher` — changepoint via `ruptures` on `amended_value` time series.
- `directors-network-analyst` — bipartite graph on `cra_directors`.
- `dossier-writer` — converts findings into HTML for the existing :3801 dossier viewer.
- `citation-agent` — final synthesis pass that adds inline citations from a `sources.jsonl`.
- `research-critic` — counter-review pass.

**High-value hook patterns**:

```jsonc
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "type": "command",
        "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-destructive.sh" },
      { "matcher": "mcp__postgres__execute_query", "type": "command",
        "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/enforce-readonly-and-limit.sh" }
    ],
    "PostToolUse": [
      { "matcher": "mcp__postgres__execute_query", "type": "command",
        "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/log-sql.sh" }
    ],
    "UserPromptSubmit": [
      { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/inject-context.sh" }
    ],
    "SessionStart": [
      { "type": "command", "command": "psql $DB -c \"SET search_path TO general,fed,cra,ab,public\"" }
    ],
    "Stop": [
      { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/append-findings-log.sh" }
    ]
  }
}
```

`block-destructive.sh` skeleton (deny pattern + exit 2):

```bash
#!/usr/bin/env bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
if echo "$CMD" | grep -qiE '(rm -rf|DROP TABLE|TRUNCATE|DELETE FROM|UPDATE [^ ]+ SET|ALTER )'; then
  echo '{"hookSpecificOutput":{"decision":"deny","reason":"Destructive command blocked by hackathon policy"}}'
  exit 2
fi
exit 0
```

`enforce-readonly-and-limit.sh` adds `LIMIT 1000` if the query has none and rejects DDL/DML on the four schemas.

**Slash commands to ship** (`.claude/commands/`):

- `/zombies <BN>` → `claude-code-skill: zombie-analyst` with the BN pre-bound.
- `/ghost-score <entity>` — runs the ghost-scorer recipe.
- `/loops --min-amount 10000 --depth 4` — johnson_cycles filter + Sankey.
- `/sole-source-creep <dept>` — amendment-creep-watcher on a department's contracts.
- `/adverse-media <entity>` — entity-link → screener.
- `/policy-compare <priority>` — DPR/mandate-letter spending vs. priority bucket.
- `/dossier <entity_id>` — generate the HTML dossier file the :3801 viewer expects.

### Stream D — NL→SQL on this stack

| Approach | Status April 2026 | Recommendation for this 48h |
|---|---|---|
| **Schema-linking via condensed DDL injected by hook** | Standard pattern in current best practice | Generate `schema-digest.md` once, inject via `UserPromptSubmit` hook for every t2sql-class question. ~5KB of focused DDL with column comments and FK relationships beats 49-table autoschema introspection. |
| **Column-retrieval via embeddings (pgvector)** | Common in 2025 academic work | Optional. With Opus 4.7 1M context, the digest fits without retrieval. Skip unless schemas grow past ~20K tokens of DDL. |
| **Execution-based self-correction loop** | Standard | Subagent retries on `ERROR` from psql up to 3x with the error pasted in. Already a default Claude pattern. |
| **EXPLAIN before execution** | Standard for prod | Hook on Postgres MCP runs EXPLAIN if estimated cost > threshold. |
| **`pg_stat_statements`** | Standard | Surface as readable resource via Postgres MCP Pro. |
| Vanna 2.0 | Active. Architectural rewrite late 2025 — agent-based, user-aware, RLS, audit logging. | **Skip for 48h** — the agentic architecture overlaps with Claude Code's loop and adds setup burden. Use only if doing >100 demos/day. |
| Dataherald | Active. SQL Agent reportedly outperforms LangChain SQL Agent 12–250%. | Skip — its agent loop overlaps with Claude. Repurpose ideas (business-logic injection) as hook content. |
| DB-GPT | Active. Production-ready. | Skip for 48h. |
| SQLCoder family | SQLCoder-70b reaches 96% on standard NL→SQL benchmarks. | Skip for primary path — Opus 4.7 is stronger overall and you have it; use as local-fallback only via Ollama. |
| Waii | Commercial. | Skip — closed source, paid. |
| **Frontier-LLM SOTA snapshot (Q1/Q2 2026)** | BIRD released `bird-sql-dev-1106` (cleaner dev) and `BIRD-Critic-SQLite` (March 2026) [s50]. Spider 2.0 best execution accuracy still in 26–27% range industry-wide on enterprise databases (1000+ columns) [s49, s54]. BIRD team published Data Intelligence Index covering DB querying, BI analysis, app debugging in March 2026 [s50]. | **Conclusion:** even the best models struggle on Spider 2.0; lean on schema-linking, EXPLAIN, and result-size guardrails — don't expect zero-shot accuracy on 49-table schemas. The pre-computed accountability tables (`loops`, `johnson_cycles`, `loop_financials`, `t3010_plausibility_flags`) are gold — Claude should call those, not re-derive them. |

**PostgreSQL 18 / Splink / pg_trgm quirks** Claude will trip on:

- The repo's `t3010_impossibilities` and `donee_name_quality` tables encode known data quirks (e.g., Centreville Presbyterian's $5.2B phantom expenditure). Inject these in the schema digest with a "ALWAYS exclude `t3010_impossibilities` rows or filter them" instruction.
- `cra_compensation` uses range buckets, not numbers. LLMs love to sum them as numbers — block with hook regex.
- `fed.grants_contributions` has both `original_value` and `amended_value` (40 cols!). Mandate via hook that any "amount" question tells Claude which column it picked and *why*.
- pg_trgm fuzzy joins with `%` are O(N²) on 851K-entity comparisons; force bigint join paths via `entity_id`.

### Stream E — Graph analytics & GraphRAG

| Tool | Type | Recency | Fit |
|---|---|---|---|
| **`networkx`** | Pure Python, ubiquitous | Active | Cycle detection, community detection on the ~30K-edge `cra_qualified_donees`. Trivial install. |
| **`igraph`** (Python binding) | C-core, fast | Active | 10–100x faster than networkx for large graphs; same API ergonomics. |
| **`rustworkx`** | IBM Quantum's NetworkX-compatible Rust port | Active | Faster than igraph in many ops. Drop-in for networkx if perf bites. |
| **`graph-tool`** | C++/Boost, statistical inference (SBM, Louvain) | Active | Heavyweight; install pain on macOS. **Skip for 48h.** |
| **`cugraph`** | RAPIDS GPU graph library | Active | Skip — no GPU on hackathon laptops. |
| **Apache AGE** on PG18 | Cypher inside Postgres | Setup page lists PG18 support. | **Try first**: lets Claude call openCypher directly via existing Postgres MCP Pro. **Caveat: still verify install on PG18 before relying — historically AGE lags PG by 1–2 minors.** |
| **Recursive CTEs / `pg_graphql`** | Native PG | Stable | Cycle detection without an extension. |
| **DuckPGQ** | DuckDB property-graph queries | Active | If Splink/DuckDB is already in pipeline, can do PGQ in the same engine. |
| **Kuzu** | MIT-licensed embedded LPG, full-text + vector search built-in, bulk-load Parquet/Arrow/DuckDB, Cypher | v0.11.x late 2025; active 2026. Permissive MIT, no daemon. | **Recommended embedded graph DB for this hackathon**: zero-ops, fast, fits the 30K-edge graph easily. Wrap as Bash-callable script via skill. |
| **Neo4j** + **Neo4j MCP** | Property graph w/ official MCP | Mature; MCP active | Strong but requires running Neo4j; overkill for 30K edges, justified for a richer multi-source graph (charities + directors + grants + lobbying + offshore). |
| **Memgraph** + **Memgraph MCP** | Cypher-compatible, in-memory, faster than Neo4j on writes (per Memgraph benchmarks — vendor-published, cross-check) | Active 2026 | Faster ingestion. |
| **NebulaGraph** | Distributed | Mature | Overkill. |
| **Microsoft GraphRAG** | Modular graph-based RAG, knowledge-graph extraction | Active. ACL'26/ICLR'26 papers cite it as baseline. | If demo wants "answer policy questions over an extracted knowledge graph". Heavy indexing cost — **build the index ahead of demo day**. |
| **LightRAG** | Dual-level retrieval, graph-enhanced indexing | Active | Faster, lighter than full GraphRAG. |
| **LazyGraphRAG** | Microsoft variant — 100% win rate vs GraphRAG/LightRAG/RAPTOR/vector RAG in published comparisons | Active | Most query-time efficient. |
| **PathRAG**, **G-Retriever**, **DALK**, **ToG** | Academic | 2024–2026 papers | Skip for 48h; reference only. |
| **PyGOD** | Python graph outlier detection (10+ algorithms, node/edge/graph level) | Active 2024–2026 | Light fit for this dataset (most charity-graph anomalies are interpretable cycles, not GNN-detected). |
| **DGFraud**, **CARE-GNN**, **GAD-NR**, **UMGAD** | Academic GNN fraud detection | 2024–2026 | Skip for 48h — slope of effort vs. return is wrong. |

**Recommendation**: Start with Postgres recursive CTEs + already-precomputed `johnson_cycles`. Reach for Kuzu if the team wants Cypher ergonomics in Python. Reach for Apache AGE only if Cypher inside Postgres is a strict requirement. Skip GraphRAG unless one of the demos is "ask a natural-language question over the extracted graph".

### Stream F — Anomaly / fraud / audit analytics

| Library | Recency | Fit |
|---|---|---|
| **PyOD** v3.0+ | Active (PyPI release v2.x in 2025; v3.0 docs current). 50+ algorithms (KNN, IForest, ECOD, COPOD, DeepSVDD, etc.). | Default tabular anomaly toolkit. Bash-callable from a skill. |
| **anomalib** (Intel) | Active. Image-focused. | Skip — wrong domain. |
| **DeepOD** | Active | Useful if doing deep tabular anomaly. |
| **ADBench** | NeurIPS 2022. Companion to PyOD. 30 algorithms × 57 datasets. NLP-ADBench (8 text datasets, 19 methods) follow-up. | Reference only. |
| **OpenContracting Cardinal** (`open-contracting/cardinal-rs`) | Active 2024–2026, **Rust** [s65]. ~150 procurement red-flag indicators on OCDS [s66]. | **Direct fit for challenges 4, 5, 9.** Wrap as Bash-callable. The 2024 Red Flags guide (PDF) is a 80-page indicator catalogue [s66]. |
| **OCDS Red Flags 2024 guide** (PDF) | December 2024 | Indicator dictionary — copy as `references/ocds-red-flags.md` in the procurement skill. |
| **lifelines** | Active. 1.0+ on PyPI. Pure Python, Cox PH, KM, AAF, log-rank. | Survival analysis for Zombie Recipients. |
| **scikit-survival** | Active. Sklearn-compatible. RandomSurvivalForest, GradientBoosting, SVM. | Use alongside lifelines for tree models. |
| **`pysurvival`** | Maintenance mode — flag as stale. Skip. | — |
| **`statsmodels`** | Active. | Event-study via diff-in-diff. |
| **`ruptures`** | v1.1.10 Sept 2025; active. Off-line changepoint detection. | Amendment-creep detection on `amended_value` time series. |
| **`Prophet`** | Active. | Forecast amendment trajectories. |
| **`statsforecast`** / **`neuralforecast`** (Nixtla) | Active 2024–2026. | Modern Python time-series; faster than Prophet. |
| **`ADTK`** | Maintenance. Skip. | — |
| **`kats`** (Meta) | Less active. Skip for 48h. | — |
| **HHI / Gini / Lorenz** | One-liner numpy / pandas. | Vendor concentration (challenge 5). No library needed. |

### Stream G — Adverse media, OSINT, sanctions, PEPs

| Source | Access | Cost / license | Fit |
|---|---|---|---|
| **OpenSanctions** | REST API (hosted), bulk download (CC-BY/CC-BY-NC), self-host via yente | Free for non-commercial; commercial tier for full FtM matching | Default sanctions/PEP overlay. **Self-host yente for offline event day.** Canada is covered via the Wikidata-derived PEP dataset; verify dataset version on demo day before relying. |
| **GDELT 2.0** | BigQuery public, full-text-search API | Free | Adverse-media baseline. High noise — combine with classifier. |
| **Aleph Pro (OCCRP)** | Web + API | Free (registration) | Investigative records. |
| **ICIJ Offshore Leaks DB** | Web search, CSV/Neo4j download, Reconciliation API | Free, restricted use | 810k+ entities. `alephdata/offshoreleaks` repo converts to FollowTheMoney. |
| **Wikidata (PEP graph)** | SPARQL endpoint, Wikidata MCP | Free, CC0 | Most flexible PEP signal. |
| **Sayari Graph** | API + MCP-mode "Commercial World Model" | Commercial. 1.5B entities, 250+ jurisdictions, 10.6B+ records, 401M companies / 462M key people. | Best-in-class commercial graph, but skip for 48h unless free trial. |
| **News APIs**: Tavily News, Exa News, Newscatcher, GNews, MediaStack, Bing News, Serper News | Various | Mixed | Tavily/Exa via existing MCPs. |
| **Adverse-media classifiers (HF)** | DeBERTa-v3-large-zeroshot-v2.0 (Moritz Laurer, MIT-aligned) for zero-shot label set ("fraud", "enforcement", "safety", "bribery", "vs. political controversy"); BART-large-MNLI as commercial-friendly fallback | Both MIT/Apache | **48h recommendation: just call Claude Sonnet 4.6 with structured output** (`response_format = { type: "json_schema", schema: { ... enum: ["fraud","enforcement","safety","bribery","political_controversy","unrelated"] } }`). Reuses the existing API key, beats fine-tuned classifiers on this task in practice, no HF download. **Reach for HF DeBERTa-v3-large-zeroshot-v2.0** only if cost or offline becomes the constraint; **BART-MNLI** as ultimate offline fallback. |
| **Entity linking**: BLINK (FAIR, Wikipedia-trained), GENRE, ReFinED (Google) | Open-source | Apache | For now: prefer Splink (already in pipeline) for org-name resolution; keep BLINK/ReFinED as a tool for unstructured news → Wikidata QID linking only. |
| **Canadian-specific** | SEDAR+ (security filings), provincial corporate registries, Open Government Canada catalogue, **IJF Open By Default** (~58k released ATIP docs as of 2026, +5,814 added this year) [s76], IJF Lobbying Database (federal + provincial + Yukon scrape) [s77], Canada Lobbyist Registry | Mostly free | **High value, low cost.** IJF databases are free, well-structured, and Canadian-specific [s76]. No public API yet — use IJF's downloadable CSVs or scrape via Playwright MCP [s46]. |

### Stream H — Policy / mandate-letter analysis

| Source | Access | Fit |
|---|---|---|
| **GC InfoBase** (open dataset `a35cf382-690c-4221-a971-cf0fd189a46f`) [s79] | Open Government Portal CSVs | Spending by department/program/year + program performance results. |
| **Mandate Letter Tracker** (open dataset `8f6b5490-8684-4a0d-91a3-97ba28acc9cd`) [s80] | Open Gov Portal | All commitments from PM mandate letters with status. |
| **Federal budgets** | budget.canada.ca PDFs | OCR / use Anthropic's PDF input (Claude reads PDFs natively). |
| **Throne speeches** | Parliament.ca text | Stable, plain text. |
| **Departmental Plans (DPRs)** | tbs-sct.canada.ca | PDF + structured. |
| **Environment Canada GHG Reporting** | open.canada.ca | For emissions-vs-spending alignment. |
| **CMHC housing-starts** | cmhc-schl.gc.ca | For housing-priority alignment. |

**Pipelines**:

1. **Commitment / claim extraction** — for mandate letters and DPRs. Use Claude structured output (JSON-mode) with a schema like `{commitment_id, text, owning_dept, due_date, theme: enum[housing|emissions|reconciliation|health|...], $_committed: number?}`. Open-source claim-detection libraries are fragmented — Claude beats them and you already have it.
2. **$ → policy-bucket mapping** — three approaches:
   - **DeBERTa-v3 zero-shot** on program descriptions with a curated list of ~12 policy themes. Fast, free, runs locally.
   - **Embedding + nearest-bucket** — embed program description and theme paragraphs with Voyage-3 or Cohere Embed v4, cosine-match. Best for "this program is x% reconciliation, y% health".
   - **Claude structured output** — most accurate; most expensive. Use for "evidence" path that asks "why" with a quote.
3. **RAG over policies → join with spending** — ingest mandate letters, throne speeches, DPRs into pgvector; the `policy-mapper` skill retrieves relevant commitments and joins to `fed.grants_contributions` rows whose program description embeds-near them.

### Stream I — RAG stack & hybrid search

**pgvector best practices on PG18** (March 2026 DBA guide [s84, s85]):

- Set `maintenance_work_mem` to ≥ 2GB for index builds (default 64MB is "non-negotiable" too small) [s84].
- HNSW > IVFFlat for query perf; slower to build, more RAM. Tune `ef_search` and `M` [s84, s85].
- Enable `pg_stat_statements` in `shared_preload_libraries` [s84].
- HNSW lives in RAM; ~1M vectors fine, ~50M needs 64GB. **At that scale switch to pgvectorscale's StreamingDiskANN** (disk-backed, DiskANN-derived) [s84].
- Test config used in 2026 perf write-ups: PG18 + pgvector 0.8.1 + pgvectorscale 0.9.0 [s85].

For this hackathon's policy/program corpus (likely <100k embeddings), **plain pgvector + HNSW is sufficient**.

**Hybrid search inside Postgres (BM25 + vector + RRF)** [s86]:

- **ParadeDB `pg_search`** [s86] — Rust-based, true BM25, supports PG17 and PG18 (March 2026 production-ready release). Note: **`pg_search` no longer available for new Neon projects (March 19 2026)**, so self-host PG18 + extension is the path.
- **Tiger Data `pg_textsearch` v1.0.0** (March 2026) — alternative BM25 implementation.
- Combine BM25 + vector with **Reciprocal Rank Fusion (RRF)** in a single SQL query [s86].

**Rerankers (April 2026 leaderboard, multiple sources triangulated [s87, s88])**:

| Reranker | Latency (avg) | Quality | Notes |
|---|---|---|---|
| **Voyage rerank-2.5** | ~595–603 ms | Best balance of quality vs latency — recommended | Voyage-2 also strong; rerank-2 improves ~13.89% over OpenAI v3-large. |
| **Cohere Rerank 3.5** | ~595–603 ms (fastest tier) | Less favoured by LLM judges than Voyage 2.5 | API-only. |
| **Jina Reranker v3** | 188 ms (sub-200ms) | 81.33% Hit@1 — fastest tier | **Best if latency-critical**; live demo. |
| **BGE Reranker v2-m3** | Free (HF) | Sharper performance spikes — uneven across domains | Open-source fallback. |
| **ColBERT v2 / PLAID** | Free | Specialised | Skip for 48h. |
| **Zerank-1 / Zerank 2** | — | Highest relevance overall (Zerank-1 wins on quality) | Newer entrant; verify maturity. |

**Embeddings (April 2026 MTEB v2 [s89])**:

| Model | MTEB score | Cost | Notes |
|---|---|---|---|
| **Gemini Embedding 001** | 68.32 (top) | API | Top of leaderboard. |
| **Voyage-3-large** | Strong | $0.06/M tokens | +9.74% vs OpenAI v3-large, +20.71% vs Cohere v3-English over 100 datasets. |
| **Cohere Embed v4** | 65.2 | API | Solid. |
| OpenAI text-embedding-3-large | 64.6 | API | — |
| **BGE-M3** | 63.0 | Free, HF | Best open-source for hybrid (multi-granularity, dense+sparse+multi-vector). |

For this hackathon **default to Voyage-3 (cost) or Cohere Embed v4 (existing API key)**, with BGE-M3 as the offline fallback.

**Eval**:
- **RAGAS** [s90] — reference-free metrics: faithfulness, context precision/recall, answer relevancy. Standard for RAG [s109, s110]. Pairs natively with Langfuse for trace-level eval [s90].
- **Arize Phoenix** — visual debug + embedding visualisations, free self-hosted [s109, s110].
- **Langfuse** — open-source LLM engineering platform, traces + cost; has an official Claude-Agent-SDK integration page [s90].
- **Braintrust** — strongest end-to-end (dataset → scoring → CI → production monitoring) but commercial [s109].

**Splink** [s91] — already in the pipeline (Fellegi-Sunter on DuckDB). Active; PyPI; backends DuckDB/Spark/Athena/Postgres. ABS adopting it for 2026 Census PES — strong production signal [s91]. **Don't switch backends mid-hackathon** — the existing `splink_predictions` (540K) and `entity_golden_records` (~851K) tables are ground truth. Treat them as read-only canonical resolution.

### Stream J — Visualization for live demos (offline-capable)

| Tool | Type | 2026 status | Why fits |
|---|---|---|---|
| **Streamlit** | Python data-app, top-down rerun | Mature, Snowflake-acquired | Default. Great for ministerial-grade dashboards. **Caveat**: re-runs entire script on every interaction (perf trap on 23M rows — cache aggressively with `@st.cache_data`). |
| **Gradio** | ML demo UI | Mature, HF-owned | Fastest "model in / chart out" demo. |
| **Marimo** [s93] | Reactive Python notebook → web app, native AI hooks, `--mcp` flag, `marimo pair` (2026 agent collaboration mode) [s36, s93] | Active 2026 [s93] | **Recommended for this hackathon**: same notebook is your dev env *and* the demo, no rewrites; reactive (only stale cells re-run); pure Python (git-friendly); Claude can drive cells via the MCP flag [s36]. |
| **Mesop** (Google) | Python UI, function-style | Active | Less mature ecosystem; skip. |
| **Solara** | React-on-Python | Active | Skip for 48h. |
| **Shiny for Python** | R-port | Active | Skip if team is Python-first. |
| **Evidence.dev** [s94] | SQL + Markdown → static web [s94] | Active. Fast for "BI as code". | **Strong for ministerial briefings**: SQL queries inline in markdown produce charts; static export → no server needed for projection. |
| **Observable Framework** [s95] | Static-site generator for data apps; JS front-end + any-language back-end [s95] | Active 2026 | Strongest interactive viz; steeper JS learning curve. |
| **Vizro** (McKinsey OSS) | Pydantic-driven Plotly dashboards | Active 2024 | Python-only "structured dashboards" — useful, less polished than Evidence. |
| **Plotly Dash** | Mature | Active | Falls behind Streamlit in DX. |
| **Rill Data** | DuckDB-backed BI | Active | Fast on DuckDB exports. |
| **Metabase / Superset** | Mature OSS BI | Active | Heavy install for 48h. |

**Network/graph viz**:

- **Cytoscape.js** — full-featured graph theory + viz; canvas-rendered; ~3–5K nodes practical limit [s96]. Good for director-overlap networks.
- **Sigma.js + graphology** — WebGL, 100k+ nodes [s96]. Use for dense networks (`graphology-layout-forceatlas2` in WebWorker). **Best for live demo on a projector.**
- **vis-network** — DOM/canvas, easy [s96]. Mid-scale.
- **deck.gl** — WebGL, GPU-accelerated, scales to millions; pairs with MapLibre for geo overlays [s98]. **Best for fund-flow Sankey on a map.**
- **pyvis** — Python wrapper around vis-network. Quick `from_nx(networkx_graph)` → standalone HTML. **Lowest effort for a hackathon**.

**Sankey / money-flow** (challenges 3, 8, 9):

- **Plotly Sankey** in Python — directly callable from a sandbox MCP. Multi-level supported (intermediate nodes between source/dest). Good Plotly Studio template flow chart guide exists.
- **`d3-sankey`** (D3 v6+ plugin) — for fully custom; harder than Plotly [s97].
- **`@plotly/d3-sankey`** — npm package fork [s97].
- **SankeyMATIC** — quick prototyping.

**Map viz** (provincial concentration, challenges 5, 8):

- **deck.gl GeoJsonLayer** with MapLibre base — interactive, GPU [s98]. `pydeck` provides Python-friendly interface [s99]. **Best polish.**
- **Folium** — Leaflet-on-Python. Lower effort, smaller scale.
- **Kepler.gl** — pre-built on deck.gl, drag-and-drop UI. Useful for instant geo from CSV.

**Hot-reload from Claude**: Marimo's reactive cell graph means Claude editing a cell triggers downstream re-run. Streamlit's auto-rerun-on-save is comparable. Both work for live ministerial demos if cached.

### Stream K — Local / offline fallback

**Local LLM runtimes (April 2026 Apple Silicon)**:

| Runtime | Backend | Key fact |
|---|---|---|
| **Ollama** v0.19 | MLX backend in preview (March 30 2026) — re-built Mac inference stack on Apple MLX [s100]. | M5 Max + Qwen 3.5-35B-A3B NVFP4: prefill 1,154 → 1,810 t/s (+57%), decode 58 → 112 t/s (+93%). 32GB+ unified memory required [s100, s101]. |
| **LM Studio** (latest) | Uses MLX backend automatically when on Mac with available model | Closest gap to MLX-LM. Best UI for non-CLI users. |
| **MLX-LM / mlx-vlm** (Apple) | Native Apple Silicon | Fastest on Mac for many models. |
| **llama.cpp** | Metal backend | Now slower than MLX for many models (e.g., Qwen 3.5 35B-A3B: ~45 t/s llama.cpp Metal vs ~70–80 t/s MLX on M4 Max 32GB). |
| **vLLM** | Two competing Apple Silicon ports as of 2026 | Best on Linux/CUDA; complicated on Mac. |
| **SGLang** | High-throughput | Linux/CUDA. Skip for Mac demo. |

**Open models (April 2026)**:

- **DeepSeek V4-Pro** (April 24, 2026, MIT, 1.6T MoE) — 80.6% SWE-bench Verified, within 0.2 points of Claude Opus 4.6, $3.48/M output tokens vs Claude's $25; 1M-token mode uses 27% of single-token FLOPs and 10% of KV-cache vs V3.2 [s103, s104]. **Datacentre-GPU only** — not a laptop model. **DeepSeek V4-Flash** is the realistic Apple-Silicon variant. Other realistic local picks for 32GB+ unified-memory laptops: **Qwen 3.6-35B-A3B**, **Qwen 3.6-27B dense**, **Gemma 4 26B-A4B**, **Phi-4** [s100, s101, s102].
- **Qwen 3.6-35B-A3B**, Qwen 3.6-27B dense — local-fits on 32GB+ unified memory.
- **Gemma 4 26B-A4B** — strong instruct.
- **Llama 4 Scout** family — strong Apple Silicon support guides.
- **Phi-4** — small, high quality.

**LiteLLM proxy** [s105] — Python SDK + proxy server, OpenAI-compatible interface to 100+ providers. Has a documented Claude-Code quickstart that lets Claude Code talk to any LiteLLM-hosted model in Anthropic format [s107]. `default_fallbacks` parameter defines a global fallback model list [s106]. Pair with **Helicone** [s108] as gateway for cost+caching, and **Langfuse** for trace-level eval.

**Recommended hackathon offline plan**:

1. Run LiteLLM proxy locally (`pip install litellm[proxy]`).
2. `config.yaml` lists Anthropic primary, Ollama (MLX-backed) Qwen 3.6-35B-A3B as fallback.
3. Cache to local Redis or LiteLLM SQLite cache.
4. yente Docker for OpenSanctions offline.
5. Pre-downloaded GDELT slice; pre-built BGE-M3 embeddings cached in pgvector.
6. Pre-built Marimo notebooks already running — wifi-loss only kills new searches, not the demo.

**Cache layers**: Helicone (open-source, OpenAI-compat, header-based caching), Langfuse (trace + cost), LangChain cache, `llm-cache`, plain SQLite response cache. Keep simple — Helicone gateway + LiteLLM cache covers it.

### Stream L — Evaluation & demo failure modes

**T2SQL eval**: BIRD (`bird-sql-dev-1106`, `BIRD-Critic-SQLite`) [s50], Spider 2.0 (632 enterprise problems, 1k+ columns; SOTA execution accuracy ~26–27%) [s49, s54]. Use as reality check on your stack — don't expect zero-shot accuracy on 49-table schema.

**RAG/citation eval**: RAGAS faithfulness, context precision/recall, answer relevancy; LLM-as-judge over retrieved evidence; trace + score in Langfuse.

**Hallucination traps for *this* data**:

- **Inventing PEP/sanctions matches.** Any "X is a PEP" claim must cite OpenSanctions record ID. Hook the OpenSanctions MCP responses through a citation-required wrapper.
- **Mislabeling benign denominational funding loops as fraud.** The qualified-donee network legitimately includes Catholic-school-board ↔ Catholic-foundation cycles. The brief's "benign-vs-suspicious LLM-judge" must be calibrated and the demo should *show* benign cycles too.
- **Confusing `original_value` vs. `amended_value`** in `fed.grants_contributions`. Force the model to label which it picked. Hook regex on the output: any `$X.XX` near "amount/value" must be paired with `(original|amended)`.
- **T3010 quirks per `KNOWN-DATA-ISSUES.md`** — Centreville Presbyterian's $5.2B phantom expenditure is the canonical example; `t3010_impossibilities` exists *because* of these. Force a `WHERE` exclusion via SQL hook.
- **Splink false-merge** — the pipeline is already `deterministic → Splink → Claude adjudication` with 540K predictions and 5.16M source links. Trust `entity_golden_records` as ground truth; do *not* let Claude re-adjudicate on the fly.
- **Range-bucket compensation summing.** `cra_compensation` columns store `< $40,000`-style strings.

**Live-demo failure modes** + mitigations:

- **Wifi out** → LiteLLM proxy + Ollama-MLX fallback; pre-warmed local sanctions cache.
- **Postgres timeout on a deep cycle search** → use precomputed `johnson_cycles`; never re-run on demo path.
- **Claude takes 60s to answer in front of a minister** → set `thinking.effort: "low"` for live mode, `"high"` for back-room follow-up; statusline shows the level.
- **Hooks misfire and silently allow a destructive query** → add a spoken-aloud rehearsal: try `DELETE FROM cra_identification` once, observe block, demo `EXPLAIN` instead.
- **Pre-compaction drops critical context** → use `SessionStart` hook to read back `findings.md` and `CLAUDE.md`; a `PreCompact` hook to flush state.

---

## Part 2 — Three Claude-Code configuration tiers

### Tier 0 — Pure Claude Code (terminal only)

**Bill of materials**: Claude Code CLI + Postgres MCP Pro + Tavily MCP + WebSearch + a tiny custom plugin (skills + slash commands + hooks). **Zero custom framework code.** Demo = screenshare of terminal.

`.mcp.json` (project-scoped, committed):

```json
{
  "mcpServers": {
    "postgres": {
      "type": "stdio",
      "command": "uvx",
      "args": ["postgres-mcp", "--access-mode=restricted"],
      "env": { "DATABASE_URI": "postgresql://qohash:qohash@localhost:5434/hackathon" }
    },
    "tavily": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@tavily-ai/tavily-mcp"],
      "env": { "TAVILY_API_KEY": "${TAVILY_API_KEY}" }
    },
    "opensanctions": {
      "type": "stdio",
      "command": "uvx",
      "args": ["opensanctions-mcp"],
      "env": { "OPENSANCTIONS_API_KEY": "${OPENSANCTIONS_API_KEY}" }
    },
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${PWD}"]
    }
  }
}
```

`.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__postgres__execute_query",
      "mcp__postgres__list_tables",
      "mcp__tavily__*",
      "mcp__opensanctions__search",
      "mcp__filesystem__read_file",
      "mcp__filesystem__write_file",
      "Bash(psql:*)",
      "Bash(python:*)",
      "WebSearch"
    ],
    "deny": [
      "mcp__postgres__execute_query.*DROP|TRUNCATE|DELETE|UPDATE|ALTER|CREATE",
      "Bash(rm:*)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "type": "command",
        "command": ".claude/hooks/block-destructive.sh" },
      { "matcher": "mcp__postgres__execute_query", "type": "command",
        "command": ".claude/hooks/enforce-readonly-and-limit.sh" }
    ],
    "PostToolUse": [
      { "matcher": "mcp__postgres__execute_query", "type": "command",
        "command": ".claude/hooks/log-sql.sh" }
    ],
    "UserPromptSubmit": [
      { "type": "command", "command": ".claude/hooks/inject-context.sh" }
    ],
    "SessionStart": [
      { "type": "command", "command": ".claude/hooks/init-session.sh" }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": ".claude/statusline.sh",
    "padding": 2
  },
  "enabledMcpjsonServers": ["postgres", "tavily", "opensanctions", "filesystem"]
}
```

`.claude/` layout:

```
.claude/
  settings.json
  CLAUDE.md                  # schema digest + data caveats
  commands/
    zombies.md
    ghost-score.md
    loops.md
    sole-source-creep.md
    adverse-media.md
    policy-compare.md
  agents/
    t3010-sql-pro.md
    loop-detector.md
    zombie-analyst.md
    ghost-scorer.md
    policy-mapper.md
    adverse-media-screener.md
    citation-agent.md
    research-critic.md
  skills/
    deep-research/SKILL.md
    procurement-red-flags/SKILL.md
    survival-analysis/SKILL.md
    network-cycles/SKILL.md
  hooks/
    block-destructive.sh
    enforce-readonly-and-limit.sh
    log-sql.sh
    inject-context.sh
    init-session.sh
  statusline.sh
```

This is **the minimum viable install**: ~6 MCP servers, ~10 subagents, ~5 skills, ~5 hooks, ~6 slash commands, one statusline. Demo = `claude` then type `/zombies 894726784RR0001`.

### Tier 1 — Claude Code + repo's existing dossier UI (`:3801`)

**Adds to Tier 0**:

- A `dossier-writer` subagent that produces HTML for the dossier viewer schema (`<entity_id>.html` files in a `dossiers/` directory the viewer watches).
- A `Stop` hook that writes a one-paragraph summary to `findings.md`, a row to a SQLite "demo log", and triggers the dossier viewer to refresh.
- A `/dossier <entity_id>` slash command that orchestrates: query → analyses → render → open at `localhost:3801/<entity_id>`.

`.claude/agents/dossier-writer.md` frontmatter:

```yaml
---
name: dossier-writer
description: Convert findings into a single-page HTML dossier consumed by the local Dossier Explorer at :3801. Use when the user asks for a "dossier" or "briefing on entity X".
tools: Read, Write, Glob, Bash(jq:*), mcp__filesystem__write_file
model: sonnet
---
You produce HTML following the schema in dossiers/_template.html. Always cite SQL row ids and OpenSanctions record ids inline as <a href="#evidence-N">[N]</a>.
```

The minister clicks the dossier UI; the analyst narrates in the terminal. Claude Code keeps producing/updating dossier files in the background as the conversation evolves.

### Tier 2 — Claude Agent SDK wrapper (Streamlit / Next.js)

The Claude Agent SDK (Python `claude-agent-sdk`, TypeScript `@anthropic-ai/claude-agent-sdk`) exposes the same loop. Tier 2 puts a chat box + plot panel in front of a non-technical minister.

**Minimal Python skeleton (≈90 LOC) — `app.py`**:

```python
"""
Streamlit + Claude Agent SDK wrapper.
The same agent loop as Claude Code, behind a chat UI.
The client is connected once per session; query() is called per user prompt.
"""
import asyncio, atexit, os
import pandas as pd
import streamlit as st
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

DB = "postgresql://qohash:qohash@localhost:5434/hackathon"

OPTS = ClaudeAgentOptions(
    cwd=os.getcwd(),
    setting_sources=["project"],          # load .claude/ same as CLI
    skills=["deep-research", "procurement-red-flags",
            "survival-analysis", "network-cycles"],
    plugins=[{"type": "local", "path": "./plugins/accountability"}],
    permission_mode="acceptEdits",        # one of default|acceptEdits|plan|bypassPermissions
    thinking={"effort": "medium"},
    enable_file_checkpointing=True,
    mcp_servers={                          # SDK-side config mirrors .mcp.json
        "postgres": {"type": "stdio", "command": "uvx",
                     "args": ["postgres-mcp", "--access-mode=restricted"],
                     "env": {"DATABASE_URI": DB}},
        "opensanctions": {"type": "stdio", "command": "uvx",
                          "args": ["opensanctions-mcp"]},
    },
    allowed_tools=["mcp__postgres__execute_query",
                   "mcp__opensanctions__*", "Read", "Write", "Bash"],
)

def get_client():
    if "client" not in st.session_state:
        client = ClaudeSDKClient(OPTS)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(client.connect())
        st.session_state.client = client
        st.session_state.loop = loop
        atexit.register(lambda: loop.run_until_complete(client.disconnect()))
    return st.session_state.client, st.session_state.loop

st.title("Federal Spending Accountability — Live")
client, loop = get_client()

prompt = st.chat_input("Ask about a charity, contract, or department")
if prompt:
    async def run():
        await client.query(prompt)
        async for msg in client.receive_response():
            if msg.type == "assistant_text":
                st.chat_message("assistant").markdown(msg.text)
            elif msg.type == "tool_result" and msg.tool == "mcp__postgres__execute_query":
                df = pd.DataFrame(msg.result["rows"])
                st.dataframe(df)
            elif msg.type == "artifact":      # Sankey/HTML produced by skill
                st.components.v1.html(msg.html, height=600)
    loop.run_until_complete(run())

with st.sidebar:
    st.write("Subagent transcripts")
    for sub in client.list_subagents():
        with st.expander(sub.name):
            for m in client.get_subagent_messages(sub.id):
                st.text(m.text[:500])
```

*The `connect()`/`disconnect()` lifecycle is managed via session_state + atexit so the client persists across Streamlit reruns. Don't use `async with` inside the per-prompt handler — it would close the client on every interaction.*

**Minimal TypeScript skeleton — `app/api/query/route.ts` (Next.js 15 / Hono OK)**:

```ts
import { ClaudeSDKClient, ClaudeAgentOptions } from "@anthropic-ai/claude-agent-sdk";

const opts: ClaudeAgentOptions = {
  cwd: process.cwd(),
  settingSources: ["project"],
  skills: ["deep-research", "procurement-red-flags",
           "survival-analysis", "network-cycles"],
  plugins: [{ type: "local", path: "./plugins/accountability" }],
  permissionMode: "acceptEdits",
  thinking: { effort: "medium" },
  enableFileCheckpointing: true,
  mcpServers: {
    postgres: { type: "stdio", command: "uvx",
                args: ["postgres-mcp", "--access-mode=restricted"],
                env: { DATABASE_URI: process.env.DB! } },
    opensanctions: { type: "stdio", command: "uvx",
                     args: ["opensanctions-mcp"] },
  },
  allowedTools: ["mcp__postgres__execute_query",
                 "mcp__opensanctions__*", "Read", "Write", "Bash"],
};

export async function POST(req: Request) {
  const { prompt } = await req.json();
  const client = new ClaudeSDKClient(opts);
  await client.connect();
  await client.query(prompt);

  const stream = new ReadableStream({
    async start(controller) {
      for await (const msg of client.receiveResponse()) {
        controller.enqueue(new TextEncoder().encode(JSON.stringify(msg) + "\n"));
      }
      controller.close();
      await client.disconnect();
    },
  });
  return new Response(stream, { headers: { "Content-Type": "application/x-ndjson" } });
}
```

**Tier 2 patterns to use**:

- `set_permission_mode("plan")` on first turn — show the *plan* before executing; minister approves.
- `set_model("opus-4-7-1m")` for "deep" follow-ups, default Sonnet for quick.
- `interrupt()` if the minister says "stop, drill into Y".
- `rewind_files(user_message_id)` to "undo my last analysis" if a chart embarrasses anyone.
- `list_subagents()` + `get_subagent_messages()` to expose the working trace.
- `enable_file_checkpointing` so any file write can be rewound.
- Persist sessions: write `claude_session_id` to URL/cookie; reuse on next visit.

---

## Part 3 — Challenge × stack matrix

| # | Challenge | Top-3 primitives | Tier(s) | Skills/subagents/MCPs |
|---|---|---|---|---|
| 1 | Zombie Recipients | (a) Survival KM via `lifelines`; (b) `cra_identification` × `fed.grants_contributions` join; (c) revenue-dependency ratio | Tier 0/1/2 | `zombie-analyst` subagent; `survival-analysis` skill; Postgres MCP Pro |
| 2 | Ghost Capacity | (a) Zero-employee detection via `cra_compensation`; (b) shared-address graph; (c) program-desc semantic embedding | Tier 0/1/2 | `ghost-scorer` subagent; pgvector+embedding skill; Postgres MCP Pro |
| 3 | Funding Loops | (a) Pre-computed `johnson_cycles`; (b) Plotly Sankey; (c) benign-vs-suspicious LLM-judge | Tier 1 (dossier viewer) | `loop-detector` subagent; `network-cycles` skill; Postgres MCP Pro |
| 4 | Sole-Source & Amendment Creep | (a) `ruptures` changepoint on `original_value→amended_value` deltas; (b) Cardinal red flags on OCDS; (c) repeat-vendor pattern via window functions | Tier 0/1 | `amendment-creep-watcher`; `procurement-red-flags` skill; Postgres MCP Pro + Bash sandbox |
| 5 | Vendor Concentration | (a) HHI/Lorenz; (b) deck.gl choropleth; (c) incumbency run-length | Tier 1 (dossier viewer) | `vendor-concentration-analyst`; concentration-metrics skill |
| 6 | Related Parties / Director Networks | (a) Bipartite graph on `cra_directors`; (b) Splink-resolved entities; (c) PEP overlay via OpenSanctions | Tier 1/2 | `directors-network-analyst`; OpenSanctions MCP; Wikidata MCP |
| 7 | Policy Misalignment | (a) Mandate-letter ingest → pgvector; (b) DeBERTa-v3 zero-shot on program desc; (c) Claude structured output for evidence | Tier 2 (chat) | `policy-mapper` subagent; `policy-rag` skill; pgvector + Voyage-3 |
| 8 | Duplicative Funding / Gaps | (a) Cross-schema entity join via `entity_golden_records`; (b) program-desc embedding similarity; (c) Sankey visual | Tier 1 | `duplicate-detector` (new); Postgres MCP Pro |
| 9 | Contract Intelligence | (a) Volume×unit×mix decomposition; (b) UNSPSC/NAICS taxonomy; (c) CPI-adjusted unit-cost trajectories | Tier 0/1 | `contract-intel` subagent; statsforecast skill |
| 10 | Adverse Media | (a) Splink-resolved entity → OpenSanctions; (b) Tavily News + DeBERTa-v3 zero-shot adverse-media classifier; (c) GDELT for breadth | Tier 0/1/2 | `adverse-media-screener`; OpenSanctions MCP (yente offline); Tavily MCP |

---

## Part 4 — Five quick-win demos under 4 hours each

Ranked by ministerial-wow / effort.

### Demo 1 — "The $20-million Money-Loop" (Sankey of charity ↔ charity flows)

**60 seconds in front of a minister**: A Sankey opens showing five biggest charity-to-charity flows in 2023. The user says "show me the closed loops". The Sankey rearranges, highlighting two cycles where money returns to the original donor within the year. The minister sees `Charity A → Charity B → Charity A` with $2.3M flowing each direction.

**Build sketch (≤3h)**:

- `loop-detector` subagent already calls `johnson_cycles` (precomputed).
- Plotly Sankey skill (`network-cycles/SKILL.md`) takes the result, builds nodes/links, outputs HTML to `dossiers/`.
- The slash command `/loops --min-amount 1000000 --year 2023` chains: SQL → analyse → render.
- **Sankey caveat**: Plotly Sankey is acyclic by definition. To render a true cycle, **either** (a) unfold nodes by year — `Charity_A_2022 → Charity_B_2023 → Charity_A_2024`, **or** (b) use a chord/arc diagram (D3 chord, or pyvis directed loop). Plan ahead for this in the skill template.
- Tier 0 (terminal screenshare) or Tier 1 (dossier viewer at `:3801`).

### Demo 2 — "Zombie Charities" (KM survival curve)

**60 seconds**: KM curve splits "charities funded by federal grants 2018–2022" into "still filing T3010 in 2024" vs "stopped". Minister sees ~14% have ceased filing within 24 months; the survival curve plummets at month 12 for orgs that received >80% of revenue from gov.

**Build sketch (≤3h)**:

- SQL: join `fed.grants_contributions` with `cra_identification` last-filing-year by `entity_id`.
- `zombie-analyst` runs `lifelines` `KaplanMeierFitter` split by revenue-dependency bucket.
- Render in Streamlit (Tier 2) or static PNG via matplotlib in Tier 0.

### Demo 3 — "Director-Network Heat Map" (force graph on `cra_directors` × `fed.grants_contributions`)

**60 seconds**: A force-directed graph of charities sharing >2 directors; node size = total federal grants received; edges = shared directors. Minister sees a tight cluster in healthcare-foundation space, a separate dense cluster of family-named foundations.

**Build sketch (≤3h)**:

- `directors-network-analyst` runs networkx bipartite projection.
- **Tier 0/1 default**: `pyvis.from_nx(G)` → standalone HTML in 5 lines. Adequate for ~5K visible nodes. Drop into dossier-viewer iframe.
- **Tier 2 / dense-graph option**: Sigma.js + graphology (WebGL, 100k+ nodes) in an Observable Framework page. Use only if pyvis chokes — measure first.

### Demo 4 — "Amendment Creep Waterfall" (one contract, original → final)

**60 seconds**: Pick a notable contract (e.g., one identified by `ruptures` as having multiple changepoints). Waterfall chart: original $200K, +$80K amend, +$320K amend, ..., final $4.2M. Side panel: dates, justifications (if available), repeat vendor flag. Minister sees the order-of-magnitude growth.

**Build sketch (≤2h)**:

- `amendment-creep-watcher` finds top contracts by `(amended_value - original_value) / original_value`.
- Plotly waterfall in a Marimo cell.
- The cell is the demo — minister sees the notebook.

### Demo 5 — "Adverse-Media Alert" (live entity → sanctions/news)

**60 seconds**: Type a recipient name. Within 5 seconds: Splink-resolved canonical name; OpenSanctions PEP/sanctions hit (red badge if any); top 5 adverse-media headlines from Tavily News, classified by type (enforcement/fraud/safety/political-controversy); evidence panel with click-through links.

**Build sketch (≤4h)**:

- `adverse-media-screener` chains: `entity_golden_records` lookup → OpenSanctions MCP → Tavily News MCP → DeBERTa-v3 zero-shot classify (or Claude Sonnet structured output) → render dossier section.
- Tier 1 (dossier-viewer card) or Tier 2 (Streamlit chat).

---

## Part 5 — Gotchas, risks, fabrication traps (specific to this stack)

Beyond the data quirks already listed under Stream L:

- **Postgres MCP Pro is RW-capable.** Even the recommended primary Postgres MCP Pro from CrystalDBA defaults to allowing writes — the brief's `--access-mode=restricted` flag is *required* in the `.mcp.json` to enforce read-only. Verify with a `DROP TABLE x;` test that gets rejected.
- **Plugin-dir live-reload limits.** `--plugin-dir` is dev-only; `/plugin update` doesn't help. Use `/reload-plugins` (April-2026 update) for skill changes; subagent/hook changes need a session restart.
- **Apache AGE on PG18 — verify install.** AGE's setup page lists PG18 support, but historically it has trailed Postgres releases by 1–2 minors. If install fails, fall back to recursive CTEs + Kuzu.
- **`pg_search` not for new Neon projects.** Self-host PG18 with the extension if you want BM25.
- **`ParadeDB pg_search` and Tiger Data `pg_textsearch`** are different extensions with overlapping goals — pick one.
- **OpenSanctions PEP coverage** is 28 countries — verify Canada is included before relying on PEP path. Their entity-of-interest data is broader than PEP-only.
- **Splink confidence thresholds.** The pipeline's deterministic→Splink→Claude adjudication produces 540K predictions. Trust `entity_golden_records` as canonical; do not let Claude re-merge entities ad-hoc — it will create false consolidations on common names ("John Smith Foundation"). 
- **Sandbox MCP costs** (E2B, Daytona, Modal) can spike if a skill loops without budget. Set per-session caps in the sandbox MCP config.
- **Tavily/Exa rate limits**. Tavily's 1k/month free tier is fine for 48h; Exa free is similar. Cache via Helicone.
- **MTEB v2 (2026) scores not directly comparable to v1.** When citing leaderboards in the demo, say "MTEB v2".
- **Statusline command runs every tick** — keep `<10ms` or you tank session perf.
- **Pre-compaction** drops things; use `PreCompact` hook to write critical state to disk before it triggers.
- **DeepSeek V4-Pro is too big to run locally** at 1.6T MoE. Use V4-Flash for laptops or call via API behind LiteLLM.
- **`enableAllProjectMcpServers`** auto-approval pattern has burnt teams. Be explicit with `enabledMcpjsonServers` listing names.
- **Hook deny semantics.** Exit code 2 to block (with stderr message) is the reliable path; the JSON `decision: "deny"` mode has documented inconsistencies (Claude Code issue #23284). Prefer exit 2.

---

## Part 6 — Prioritized reading list (10–20 items)

1. **Anthropic — "Subagents in Claude Code"** blog (`claude.com/blog/subagents-in-claude-code`). The "how/when" guide; cleaner than the docs.
2. **Claude Code release notes April 2026** (`releasebot.io/updates/anthropic/claude-code`). What changed in `/agents`, hooks, plugin install, perf.
3. **Claude Agent SDK CHANGELOG (Python)** (`github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md`). For the `skills`, `plugins`, `thinking`, `enable_file_checkpointing`, `list_subagents`, `rewind_files` evolution.
4. **`anthropics/claude-plugins-official`** — the canonical `marketplace.json` and plugin layout reference.
5. **`hesreallyhim/awesome-claude-code` + `VoltAgent/awesome-claude-code-subagents`** — the two best discovery lists.
6. **`crystaldba/postgres-mcp` README + "Postgres MCP Pro" launch post on crystaldba.ai** — why this beats the official Postgres MCP for analytics work.
7. **Spider 2.0 paper (ICLR 2025 Oral)** + GitHub `xlang-ai/Spider2`. Why current SOTA on enterprise schemas is only 26–27%; calibrates expectations.
8. **BIRD bench updates 2026** (`bird-sql-dev-1106`, `BIRD-Critic-SQLite`). Cleaner dev set + the new SQLite single-dialect benchmark.
9. **Microsoft GraphRAG + LightRAG papers + LazyGraphRAG note**. For policy-misalignment graph-RAG demo if the team builds it.
10. **OCDS Red Flags 2024 PDF** (open-contracting.org). 80-page indicator catalogue specific to public procurement — directly maps to challenges 4, 5, 9.
11. **OpenSanctions self-hosted docs (yente)**. The two-Docker-container path for offline.
12. **ParadeDB hybrid-search "missing manual"** post. BM25 + pgvector + RRF in one query — exactly what the policy-mapper needs.
13. **Voyage AI rerank-2 launch post** + Agentset 2026 reranker leaderboard. For why Voyage 2.5 is the current "best balance".
14. **Awesome Agents MTEB leaderboard March 2026** + Voyage-3-large blog. For embedding-model picks.
15. **Investigative Journalism Foundation databases** (`theijf.org`) + Open By Default + lobbying methodology page. The most underused Canadian-specific accountability data source.
16. **GC InfoBase open dataset + Mandate Letter Tracker open dataset** on open.canada.ca. For policy-alignment work.
17. **Marimo "beyond chatbots" blog** (`marimo.io/blog/beyond-chatbots`). Why marimo's `--mcp` flag turns notebooks into AI tools.
18. **Ollama 0.19 MLX-backend post + MLX-vs-Ollama 2026 benchmarks**. For the offline plan.
19. **DeepSeek V4-Pro launch (April 2026, MIT)**. For local-model viability.
20. **LiteLLM Claude Code quickstart** (`docs.litellm.ai/docs/tutorials/claude_responses_api`). For routing Claude Code traffic to a local Ollama fallback transparently.

---

## Methodology footer

- **Total streams covered**: 12 (A–L), consolidated into 9 logical sub-questions per the plan.
- **Research execution**: 30+ web searches across Anthropic docs, MCP catalogues, GitHub repos, HuggingFace, primary vendor docs, leaderboards, and 2025–2026 review syntheses. Plan, draft, critic notes, and final stored in scratch dir for inspection.
- **Sources consulted**: 112 distinct primary URLs catalogued in `sources.jsonl`.
- **Query type**: Breadth-first (heavy) — 12 distinct streams across Claude Code substrate, MCP catalog, NL2SQL, graph analytics, anomaly detection, OSINT, policy text, RAG, viz, local-fallback, eval. No single "deep" question.
- **Critic pass**: Completed (`revision-notes.md`); 18 fixes integrated, including: explicit permission-mode set (`default|acceptEdits|plan|bypassPermissions`); `${CLAUDE_PROJECT_DIR}` portability for hooks; Sankey-cycle caveat for Demo 1; pyvis as default for Demo 3; Streamlit client lifecycle bug fixed (no `async with` per-prompt); pip/npm package-name confirmations; OpenSanctions Canada coverage clarified (Wikidata-derived); DeepSeek V4-Pro vs V4-Flash sizing; Splink "don't switch backends" callout.
- **Recency bias**: All recommended tools have releases or commits within the last 9 months. Stale flagged: `pysurvival`, `kats`, `ADTK`, `Mesop` (active but immature ecosystem), `graph-tool` (active but install pain).
- **Gaps acknowledged**: (1) Apache AGE PG18 build was not independently verified on a real test machine — recommend trying first with a 30-min time-box. (2) `pg_search` / `pg_textsearch` choice between ParadeDB vs Tiger Data is a build-day decision based on which extension installs cleaner. (3) Sayari's MCP-mode "Commercial World Model" was announced but commercial cost / hackathon-trial availability not retrieved.
- **Conflicts surfaced**: Reranker quality leaders (Voyage 2.5 vs Zerank-1) — both top-tier; recommendation is Voyage 2.5 for the balance of quality and latency. Stated explicitly rather than picking silently.
- **Run scratch dir**: `/tmp/claude-research/1777150606-2128/`
   - `plan.md` — research plan
   - `sources.jsonl` — 112 source records
   - `draft.md` — synthesis (pre-citation)
   - `revision-notes.md` — critic pass
   - `final.md` — this document (citation-integrated)

---

## Sources

Citations above use [s###] keys. Full source URLs:

**Stream A — Claude Code + Agent SDK**
- [s1] [Claude Code documentation — Extend Claude Code](https://code.claude.com/docs/en/features-overview)
- [s2] [Claude Code April 2026 release notes](https://releasebot.io/updates/anthropic/claude-code)
- [s3] [Claude Code GitHub releases](https://github.com/anthropics/claude-code/releases)
- [s4] [Hooks reference — Claude Code Docs](https://code.claude.com/docs/en/hooks)
- [s5] [Configure permissions — Claude Code Docs](https://code.claude.com/docs/en/permissions)
- [s6] [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp)
- [s7] [Discover plugins — Claude Code Docs](https://code.claude.com/docs/en/discover-plugins)
- [s8] [Customize statusline — Claude Code Docs](https://code.claude.com/docs/en/statusline)
- [s9] [Create custom subagents — Claude Code Docs](https://code.claude.com/docs/en/sub-agents)
- [s10] [Extend Claude with skills — Claude Code Docs](https://code.claude.com/docs/en/skills)
- [s11] [Agent SDK overview — Claude API Docs](https://platform.claude.com/docs/en/agent-sdk/overview)
- [s12] [Agent SDK Python reference](https://code.claude.com/docs/en/agent-sdk/python)
- [s13] [Agent SDK TypeScript reference](https://platform.claude.com/docs/en/agent-sdk/typescript)
- [s14] [claude-agent-sdk-python repo](https://github.com/anthropics/claude-agent-sdk-python)
- [s15] [claude-agent-sdk-python CHANGELOG](https://github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md)
- [s16] [claude-agent-sdk-typescript repo](https://github.com/anthropics/claude-agent-sdk-typescript)
- [s17] [Claude Agent SDK guide 2026 — morphllm](https://www.morphllm.com/claude-agent-sdk)
- [s18] [Hooks complete guide 2026 — ofox.ai](https://ofox.ai/blog/claude-code-hooks-subagents-skills-complete-guide-2026/)
- [s19] [Steve Kinney — Claude Code Hook Examples](https://stevekinney.com/courses/ai-development/claude-code-hook-examples)
- [s20] [Claude Code settings reference 2026](https://claudefa.st/blog/guide/settings-reference)

**Stream C — Skills, subagents, plugins**
- [s21] [Awesome Claude Code](https://github.com/hesreallyhim/awesome-claude-code)
- [s22] [VoltAgent awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)
- [s23] [VoltAgent awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)
- [s24] [wshobson/agents marketplace](https://github.com/wshobson/agents)
- [s25] [Anthropic claude-plugins-official marketplace.json](https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json)
- [s26] [claudemarketplaces.com directory](https://claudemarketplaces.com/)
- [s27] [199-biotechnologies/claude-deep-research-skill](https://github.com/199-biotechnologies/claude-deep-research-skill)
- [s28] [davila7/claude-code-templates fact-checker](https://github.com/davila7/claude-code-templates/blob/main/cli-tool/components/agents/deep-research-team/fact-checker.md)
- [s29] [Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills)
- [s30] [VoltAgent data-analyst subagent](https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/05-data-ai/data-analyst.md)
- [s31] [VoltAgent sql-pro subagent](https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/02-language-specialists/sql-pro.md)

**Stream B — MCP servers**
- [s32] [Postgres MCP Pro (CrystalDBA)](https://github.com/crystaldba/postgres-mcp)
- [s33] [Official Postgres MCP server (Anthropic)](https://github.com/modelcontextprotocol/servers/tree/main/src/postgres)
- [s34] [pgEdge Postgres MCP Server](https://www.pgedge.com/blog/introducing-the-pgedge-postgres-mcp-server)
- [s35] [DuckDB MCP server](https://apidog.com/blog/duckdb-mcp-server/)
- [s36] [Marimo MCP support — beyond chatbots](https://marimo.io/blog/beyond-chatbots)
- [s37] [Tavily MCP](https://github.com/tavily-ai/tavily-mcp)
- [s38] [Best web search MCP comparison — Firecrawl](https://www.firecrawl.dev/blog/best-web-search-mcp)
- [s39] [Apify Financial Crime Screening MCP (OpenSanctions wrapper)](https://apify.com/ryanclinton/financial-crime-screening-mcp)
- [s40] [opensanctions-mcp (scka-de)](https://glama.ai/mcp/servers/scka-de/opensanctions-mcp)
- [s41] [Wikidata MCP — zzaebok](https://github.com/zzaebok/mcp-wikidata)
- [s42] [Neo4j MCP](https://www.pulsemcp.com/servers/neo4j-contrib-mcp-neo4j)
- [s43] [Memgraph MCP introduction](https://memgraph.com/blog/introducing-memgraph-mcp-server)
- [s44] [E2B vs Modal vs Daytona benchmark 2026](https://www.superagent.sh/blog/ai-code-sandbox-benchmark-2026)
- [s45] [Cloudflare Sandboxes GA April 2026](https://www.infoq.com/news/2026/04/cloudflare-sandboxes-ga/)
- [s46] [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [s47] [Filesystem MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)
- [s48] [GitHub MCP server official](https://github.com/github/github-mcp-server)
- [s112] [hopx.ai sandbox MCP / sandbox guide](https://www.bunnyshell.com/guides/coding-agent-sandbox/)

**Stream D — NL2SQL**
- [s49] [Spider 2.0 benchmark](https://spider2-sql.github.io/)
- [s50] [BIRD-bench](https://bird-bench.github.io/)
- [s51] [Vanna 2.0](https://github.com/vanna-ai/vanna)
- [s52] [Dataherald T2SQL engine](https://dataherald.readthedocs.io/en/latest/text_to_sql_engine.html)
- [s53] [Top text-to-SQL tools 2026 — Bytebase](https://www.bytebase.com/blog/top-text-to-sql-query-tools/)
- [s54] [Spider2 GitHub repo](https://github.com/xlang-ai/Spider2)

**Stream E — Graph analytics & GraphRAG**
- [s55] [Apache AGE GitHub](https://github.com/apache/age)
- [s56] [Apache AGE setup / Postgres support](https://age.apache.org/age-manual/master/intro/setup.html)
- [s57] [Kuzu GitHub](https://github.com/kuzudb/kuzu)
- [s58] [Microsoft GraphRAG](https://github.com/microsoft/graphrag)
- [s59] [LightRAG](https://lightrag.github.io/)
- [s60] [GraphRAG 2026 buyer's guide — Tongbing](https://medium.com/@tongbing00/graphrag-in-2026-a-practical-buyers-guide-to-knowledge-graph-augmented-rag-43e5e72d522d)
- [s61] [PyGOD — graph outlier detection](https://github.com/pygod-team/pygod)
- [s62] [DGFraud — safe-graph](https://github.com/safe-graph/DGFraud)
- [s111] [Memgraph open source](https://github.com/memgraph/memgraph)

**Stream F — Anomaly / fraud / audit**
- [s63] [PyOD](https://pypi.org/project/pyod/)
- [s64] [ADBench](https://github.com/Minqi824/ADBench)
- [s65] [OpenContracting Cardinal red-flags](https://github.com/open-contracting/cardinal-rs)
- [s66] [OCDS Red Flags 2024 guide](https://www.open-contracting.org/wp-content/uploads/2024/12/OCP2024-RedFlagProcurement-1.pdf)
- [s67] [lifelines](https://github.com/CamDavidsonPilon/lifelines)
- [s68] [scikit-survival](https://scikit-survival.readthedocs.io/en/stable/user_guide/00-introduction.html)
- [s69] [ruptures changepoint](https://github.com/deepcharles/ruptures)

**Stream G — Adverse media, OSINT, sanctions**
- [s70] [OpenSanctions](https://www.opensanctions.org/)
- [s71] [yente self-hosted API](https://github.com/opensanctions/yente)
- [s72] [OpenSanctions self-hosted docs](https://www.opensanctions.org/docs/self-hosted/)
- [s73] [ICIJ Offshore Leaks DB](https://offshoreleaks.icij.org/)
- [s74] [alephdata/offshoreleaks FollowTheMoney](https://github.com/alephdata/offshoreleaks)
- [s75] [Aleph Pro OCCRP](https://aleph.occrp.org/)
- [s76] [Investigative Journalism Foundation](https://theijf.org/)
- [s77] [IJF Lobbying Databases methodology](https://theijf.org/lobbying-databases-methodology)
- [s78] [Sayari Graph platform](https://sayari.com/platform/)

**Stream H — Policy text**
- [s79] [GC InfoBase open dataset](https://open.canada.ca/data/en/dataset/a35cf382-690c-4221-a971-cf0fd189a46f)
- [s80] [Mandate Letter Tracker dataset](https://open.canada.ca/data/en/dataset/8f6b5490-8684-4a0d-91a3-97ba28acc9cd)
- [s81] [DeBERTa-v3 large zeroshot v2](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- [s82] [BART-large-MNLI](https://huggingface.co/facebook/bart-large-mnli)

**Stream I — RAG stack**
- [s83] [pgvector GitHub](https://github.com/pgvector/pgvector)
- [s84] [PG18 + pgvector RAG guide](https://medium.com/@mohitsoni_/postgresql-18-pgvector-the-definitive-guide-to-building-production-grade-rag-pipelines-239ee9c0e56f)
- [s85] [pgvector DBA guide March 2026](https://www.dbi-services.com/blog/pgvector-a-guide-for-dba-part-2-indexes-update-march-2026/)
- [s86] [ParadeDB pg_search hybrid](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [s87] [Best rerankers RAG 2026 — Agentset](https://agentset.ai/rerankers)
- [s88] [Voyage rerank-2 launch](https://blog.voyageai.com/2024/09/30/rerank-2/)
- [s89] [MTEB embedding leaderboard March 2026](https://awesomeagents.ai/leaderboards/embedding-model-leaderboard-mteb-march-2026/)
- [s90] [RAGAS + Langfuse RAG eval](https://langfuse.com/guides/cookbook/evaluation_of_rag_with_ragas)
- [s91] [Splink probabilistic record linkage](https://github.com/moj-analytical-services/splink)

**Stream J — Visualization**
- [s92] [Streamlit vs Gradio vs Marimo 2026](https://markaicode.com/vs/streamlit-vs-gradio-in/)
- [s93] [Marimo reactive notebook](https://github.com/marimo-team/marimo)
- [s94] [Evidence.dev](https://github.com/evidence-dev/evidence)
- [s95] [Observable Framework](https://github.com/observablehq/framework)
- [s96] [Cytoscape.js vs Sigma.js 2026](https://www.pkgpulse.com/blog/cytoscape-vs-vis-network-vs-sigma-graph-visualization-javascript-2026)
- [s97] [d3-sankey GitHub](https://github.com/d3/d3-sankey)
- [s98] [deck.gl with MapLibre](https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre)
- [s99] [pydeck readthedocs](https://deckgl.readthedocs.io/)

**Stream K — Local fallback**
- [s100] [Ollama 0.19 MLX backend April 2026](https://medium.com/@tentenco/ollama-0-19-ships-mlx-backend-for-apple-silicon-local-ai-inference-gets-a-real-speed-bump-878b4928f680)
- [s101] [MLX vs Ollama 2026 benchmarks](https://willitrunai.com/blog/mlx-vs-ollama-apple-silicon-benchmarks)
- [s102] [Best local LLMs Mac 2026](https://insiderllm.com/guides/best-local-llms-mac-2026/)
- [s103] [DeepSeek V4 release April 2026](https://felloai.com/deepseek-v4/)
- [s104] [DeepSeek V4-Pro Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro)
- [s105] [LiteLLM proxy](https://github.com/BerriAI/litellm)
- [s106] [LiteLLM fallbacks](https://docs.litellm.ai/docs/proxy/reliability)
- [s107] [LiteLLM Claude Code quickstart](https://docs.litellm.ai/docs/tutorials/claude_responses_api)
- [s108] [Helicone GitHub](https://github.com/Helicone/helicone)

**Stream L — Evaluation**
- [s109] [Best RAG eval tools — Braintrust](https://www.braintrust.dev/articles/best-rag-evaluation-tools)
- [s110] [Top RAG eval tools 2026](https://www.goodeyelabs.com/articles/top-rag-evaluation-tools-2026)
