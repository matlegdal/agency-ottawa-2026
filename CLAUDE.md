# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A hackathon repo for the **AI For Accountability Hackathon (Agency 2026 — Ottawa, April 29 2026)**. It unifies four Canadian government open-data sources into a single PostgreSQL database, with each dataset in its own schema, plus a cross-dataset entity-resolution pipeline that produces ~851K canonical golden records.

The `challenges.md` file at the repo root lists ten investigation themes (Zombie Recipients, Ghost Capacity, Funding Loops, Sole-Source/Amendment Creep, Vendor Concentration, Related Parties, Policy Misalignment, Duplicative Funding, Contract Intelligence, Adverse Media). The end deliverable is a working, agentic AI demo for one of these — see `plans/zombie_agent_build_manual_v2.md` for an in-progress plan targeting Challenge #1.

`analysis-toolbox.md` lists the canonical open-source libraries the organizers point to per problem family (PyOD, Splink, NetworkX, Leiden, ruptures, mlxtend, OpenSanctions, DuckDB). Reach for those before custom implementations.

## Repository layout — the four modules

Each top-level module is a self-contained Node project with its own `package.json`, `lib/db.js`, scripts, and (per-module) `CLAUDE.md`. They all talk to the same Postgres database but write to different schemas.

| Dir | Schema | What it owns | Per-module CLAUDE.md |
|-----|--------|--------------|----------------------|
| `CRA/` | `cra` | CRA T3010 charity filings 2020–2024 (~8.76M rows, 49 tables + 3 views). Includes pre-computed circular-gifting / SCC / Johnson cycle / overhead / risk-scoring tables. | `CRA/CLAUDE.md` |
| `FED/` | `fed` | Federal Grants & Contributions (~1.275M rows, 6 tables + 3 views). | `FED/CLAUDE.md` |
| `AB/` | `ab` | Alberta grants/contracts/sole-source/non-profit registry (~2.61M rows, 9 tables + 3 views). | `AB/CLAUDE.md` |
| `general/` | `general` | Cross-dataset entity-resolution pipeline → `entity_golden_records` (~10.5M rows, 14 tables + 2 views). | (no CLAUDE.md — see `general/README.md`) |

Other top-level dirs:

- `.local-db/` — exporter/importer + JSONL data + DDL for spinning up a local copy of the full database. Auto-discovers tables via `information_schema`.
- `docker/postgres/create_db.sql` — initialization SQL (creates `hackathon` DB and enables `pg_trgm` + `fuzzystrmatch`); used by `docker-compose.yml` (Postgres 18 on port 5434).
- `tests/end-to-end.test.js` — cross-module integration tests (runs only with valid `.env.public` files).
- `plans/` — design docs for in-progress agent builds. Read these before starting related work.
- `index.html` — landing page / browsable documentation (~73KB single file).
- `KNOWN-DATA-ISSUES.md` — catalogued data-quality problems across all schemas. Consult before claiming a discrepancy is a bug.

**Always read the per-module `CLAUDE.md` before working in `CRA/`, `FED/`, or `AB/`.** They contain the analytical methodology and dataset-specific gotchas (e.g. the FED `agreement_value` cumulative-snapshot trap that triple-counts amended agreements; the CRA designation-A/B/C distinction that changes how a "circular flow" is interpreted).

## Database conventions (apply to every module)

- **Connection**: every module's `lib/db.js` reads `DB_CONNECTION_STRING` from env. It loads `.env.public` first, then `.env` with `override: true`. Both files are gitignored. The `.env.public` files are distributed in the hackathon info pack on event day; without them, a fresh clone cannot connect to the shared Render database.
- **Schema isolation via `search_path`**: each module's pool is configured with `options: '-c search_path=<schema>,public'`. So inside `CRA/` you can write `SELECT * FROM cra_identification` without prefixing `cra.`, but you should still qualify schema names when crossing modules (e.g. an analysis script that joins `cra.cra_identification` to `fed.grants_contributions` to `general.entity_golden_records`).
- **SSL**: Render-hosted DB requires `ssl: { rejectUnauthorized: false }`. The pool sets this only when the connection string contains `render.com` — do not generalize that pattern.
- **Required extensions**: `pg_trgm` (used heavily by entity-resolution and fuzzy-name matching) and `fuzzystrmatch`.
- **`bn` (Business Number) is the cross-dataset primary identifier.** The 9-digit *root* (first 9 chars of the 15-char CRA BN like `123456789RR0001`) is what `general.entity_golden_records` keys on. Always normalize via `general.extract_bn_root()` and validate with `general.is_valid_bn_root()` before joining — the raw column carries placeholders (`-`, all-zeros, `100000000`), 15-char CRA BNs, 9-digit BNs, and 17-char values with embedded spaces.
- **Read-only by default**: participants get a read-only Postgres user. Only the maintainer admin `.env` has write access. Never write a script that assumes write privileges without a clear migration/setup intent.

## Common commands

### Run from the repo root

```bash
# Spin up local Postgres (port 5434, user/pass qohash/qohash, db hackaton)
docker compose up -d

# Run cross-module integration tests (requires .env.public files in place)
node --test tests/end-to-end.test.js
```

### Per-module pipeline (same shape in CRA / FED / AB / general)

```bash
cd <module>
npm install
npm run setup       # full pipeline: migrate + seed + fetch + import + verify
npm run verify      # sanity-check schema and row counts
npm run drop        # destructive — drops the schema's tables
npm run reset       # drop + setup
npm run test:unit   # pure-function tests, no DB
npm run test:integration   # DB-dependent
```

### Module-specific analysis entry points

```bash
# CRA — circular-gifting analysis (deterministic, ~2 hr full run dominated by 6-hop cycles)
cd CRA
npm run analyze:all
npm run lookup -- --bn 123456789RR0001          # interactive network lookup
npm run risk -- --name "charity name"           # 0–30 risk report

# FED — 8 advanced risk dimensions
cd FED
npm run analyze:all
npm run analyze:zombies        # directly relevant to Challenge #1
npm run analyze:amendments     # Challenge #4
npm run analyze:concentration  # Challenge #5

# AB — 6 advanced analyses (sole-source deep dive, sector health, etc.)
cd AB
npm run analyze:all

# general — entity-resolution pipeline (7 stages, idempotent)
cd general
npm run pipeline:run                    # full pipeline
npm run entities:dashboard              # http://localhost:3800 (operator UI)
npm run entities:dossier                # http://localhost:3801 (per-entity dossier)
npm run entities:llm                    # LLM golden-record authoring (concurrency 100)
```

### Local-database recreation

```bash
createdb hackathon
cd .local-db && npm install
DB_CONNECTION_STRING=postgresql://user:pass@localhost/hackathon npm run import
```

The JSONL data files (~13 GB) are gitignored and ship out of band. Schemas, manifest, and import/export scripts are committed.

## Entity resolution (`general/`) — what to know before touching it

The pipeline produces one `entity_golden_records` row per real-world organization. Three techniques cascade:

1. **Deterministic** (Stage 2 / `04-resolve-entities.js`): BN-anchoring across six source tables in trust order (CRA → CRA donees → FED → AB), then dedup by BN root and by normalized name. The normalized-name dedup is BN-aware — two charities sharing a normalized name but different BNs (e.g. 115 distinct `ST. ANDREW'S PRESBYTERIAN CHURCH` registrations) are deliberately *not* merged.
2. **Probabilistic via Splink** (Stage 3 / `05-run-splink.js` + `splink/`): Fellegi-Sunter linkage with EM-learned weights. DuckDB backend. Produces match candidates only.
3. **LLM verdict + golden-record authoring** (Stage 7 / `08-llm-golden-records.js`): Claude Sonnet 4.6 via Anthropic API and/or Vertex AI in parallel (default concurrency 100+100). The LLM emits SAME / RELATED / DIFFERENT and, when SAME, *authors the canonical name + alias list in the same call*.

Key invariants:

- **Every stage is idempotent and resumable**. Interruptions pick up cleanly from the database state — no separate event log.
- **Every stage is observable via the dashboard**, which polls Postgres directly. If you add a stage, expose it through `general/scripts/tools/dashboard.js`.
- **`general.norm_name()` is the canonicalizer** used everywhere downstream. Strips `TRADE NAME OF`, `O/A`, `DBA`, `DOING BUSINESS AS`, `AKA`, `FORMERLY`, `F/K/A`, trailing `(THE)`, leading `THE`; handles bilingual EN|FR pipe/slash split. Use it; do not write a new one.
- **The Anthropic SDK is `@anthropic-ai/sdk` (Node)**. The pipeline can target Claude direct or Vertex AI; pick via `--provider` flag.

## Working on hackathon challenges

Each challenge maps to specific tables/scripts:

| Challenge | Primary data | Existing scripts |
|-----------|--------------|------------------|
| 1 Zombie Recipients | `fed.grants_contributions` + `cra.cra_identification` (revocations) + `ab.ab_non_profit` (status=dissolved/struck) | `FED/.../05-zombie-and-ghost.js` |
| 2 Ghost Capacity | `cra.cra_compensation` + `cra.cra_financial_details` + `fed.grants_contributions` | `FED/.../05-zombie-and-ghost.js` |
| 3 Funding Loops | `cra.cra_qualified_donees` | `CRA/scripts/advanced/01-detect-all-loops.js`, `03-scc-decomposition.js`, `06-johnson-cycles.js` |
| 4 Amendment Creep | `fed.grants_contributions` (`is_amendment` + `vw_agreement_*`), `ab.ab_sole_source` | `FED/.../03-amendment-creep.js`, `AB/.../04-sole-source-deep-dive.js` |
| 5 Vendor Concentration | `fed`, `ab.ab_contracts`, `ab.ab_sole_source` | `FED/.../04-recipient-concentration.js` |
| 6 Related Parties | `cra.cra_directors` + `general.entity_golden_records` | none yet |
| 9 Contract Intelligence | `fed`, `ab.ab_contracts` | none yet |
| 10 Adverse Media | external (OpenSanctions, news APIs) + golden records | none yet |

## Things that will trip you up

- **`fed.agreement_value` is a cumulative snapshot per amendment, not a delta.** Naive `SUM(agreement_value)` over the full table triple-counts amended agreements (~$921B vs the correct ~$816B). Use `fed.vw_agreement_current` for current committed values, `fed.vw_agreement_originals` for initial commitments. See `FED/CLAUDE.md` for the full set of FED publisher quirks.
- **CRA designation A vs B vs C completely changes how circular flows are interpreted.** A high circular-flow score for a Designation A public foundation is *expected* (that is its business model). The same score for a Designation C charitable organization is the actual signal. See `CRA/CLAUDE.md` for the full decision matrix.
- **2024 CRA data is partial** — charities have 6 months after fiscal year-end to file. Don't compare 2024 totals to 2023 totals as if the year is closed.
- **The T3010 form was revised in 2024** — some fields are NULL for 2024 (removed) and others are NULL for 2020–2023 (added in 2024). Do not assume schema continuity across years.
- **AB data has almost no BNs.** Cross-dataset matching for AB recipients is name-based and goes through `general` entity resolution. Do not try to BN-join to AB directly.
- **`fed.ref_number` is not unique** (publisher collisions across recipients). Only `_id` is. For per-agreement grouping, use `(ref_number, COALESCE(recipient_business_number, recipient_legal_name))`.
- **AB grant `amount` and FED `agreement_value` can be negative** — those are reversals/terminations, not data errors. Filter explicitly when summing.
- **Splink intermediate parquet files (~60 MB) live in `general/splink/data/`** and are gitignored. Regenerated each run.
