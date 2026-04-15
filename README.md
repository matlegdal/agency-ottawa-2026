# AI For Accountability Hackathon

A multi-dataset analysis platform for government transparency and accountability research, built for the **AI For Accountability Hackathon** (April 29, 2026).

## Overview

This repository brings together four major Canadian government open data sources into a shared PostgreSQL database, with separate schemas to prevent collisions. Each dataset has its own pipeline for downloading, cleansing, importing, verifying, and analyzing data.

A shared `general` module provides cross-dataset tools including a universal fuzzy matching engine for entity resolution across all datasets, with AI-assisted review via Claude.

## Architecture

```
hackathon/
├── CRA/        # CRA T3010 Charity Data (cra schema)
├── FED/        # Federal Grants & Contributions (fed schema)
├── AB/         # Alberta Open Data (ab schema)
├── general/    # Shared tools & reference data (general schema)
├── LICENSE     # MIT
└── README.md   # This file
```

All four modules share the same PostgreSQL database on Render. Each uses its own schema (`cra`, `fed`, `ab`, `general`) so tables never collide. Every module follows the same conventions:

- **`.env.public`** - Shared credentials (committed, primary)
- **`.env`** - Personal overrides (gitignored, fallback)
- **`.env.public` takes precedence** over `.env` for consistent hackathon defaults

## Datasets

### CRA - Canada Revenue Agency T3010 Charity Data
**Schema:** `cra` | **Records:** ~7.3M | **Years:** 2020-2024

Annual filings from ~85,000 registered Canadian charities including financial statements, board directors, gift flows between charities, and program descriptions. All 5 years loaded via the Government of Canada Open Data API.

```bash
cd CRA && npm install && npm run setup
```

Key features:
- 35 tables (6 lookup + 19 data + 10 analysis) + 3 views
- Deterministic circular gifting detection (2-6 hop cycles, 5,808 cycles found)
- 0-30 risk scoring across temporal, financial, and circular dimensions
- SCC decomposition, Johnson's algorithm, and matrix power cross-validation
- Interactive charity lookup and risk profiling

### FED - Federal Grants & Contributions
**Schema:** `fed` | **Records:** ~1.275M | **Years:** Multiple fiscal years

All federal government grants, contributions, and transfer payments from 51+ departments to 422K+ recipients.

```bash
cd FED && npm install && npm run setup
```

Key features:
- Single 40-column table with 12 indexes and 3 views
- 7-dimension risk scoring (0-35 scale)
- Provincial equity, amendment creep, vendor concentration analysis
- Cross-reference with CRA charity data

### AB - Alberta Open Data
**Schema:** `ab` | **Records:** ~2.36M | **Years:** 2014-2025

Four Alberta government datasets: grants, Blue Book contracts, sole-source contracts, and the non-profit registry.

```bash
cd AB && npm install && npm run setup
```

| Dataset | Table | Records |
|---------|-------|---------|
| Alberta Grants | `ab_grants` | 1,772,874 |
| Blue Book Contracts | `ab_contracts` | 67,079 |
| Sole-Source Contracts | `ab_sole_source` | 15,533 |
| Non-Profit Registry | `ab_non_profit` | 69,271 |

Key features:
- 9 tables + 3 views + status lookup
- Sole-source deep dive (repeat vendors, contract splitting, geographic concentration)
- Grant/contract ratio analysis, recipient concentration (HHI)
- Non-profit lifecycle trends (survival analysis, sector health scoring)
- 6 advanced analysis scripts producing JSON + TXT reports

### general - Shared Tools & Reference Data
**Schema:** `general` | Cross-dataset utilities

Shared reference data and tools that work across all datasets.

```bash
cd general && npm install && npm run setup
```

Key features:
- **27 Alberta ministries** with codes, ministers, deputy ministers
- **Universal fuzzy matching engine** with multi-layer entity resolution
- **AI-assisted entity review** via Claude (Anthropic direct + Vertex AI fallback)
- Cross-dataset matching (CRA charities vs FED recipients vs AB grants/contracts/non-profits)

## Entity Resolution

The defining challenge across these datasets is fuzzy matching - the same organization can appear under dozens of name variations across CRA, FED, and AB. The `general` module provides a multi-layer resolution engine:

```bash
cd general

# Deterministic resolution (no API key needed)
node scripts/resolve-entity.js --name "Boyle Street Service" --bn 118814391

# With AI second pass (needs ANTHROPIC_API_KEY or VERTEX credentials)
node scripts/resolve-entity.js --name "Homeward Trust" --bn 834173627 --llm

# Force a specific AI provider
node scripts/resolve-entity.js --name "mustard seed society" --llm --provider vertex
```

Resolution layers:
1. **BN Anchor** - Business number root (first 9 digits) as gold standard
2. **BN Negative Filter** - Reject candidates with different BN roots
3. **Core Token Gate** - Require discriminating words to match
4. **Trigram Similarity** - pg_trgm fuzzy matching with configurable threshold
5. **Trade-Name Expansion** - Parse "TRADE NAME OF" and bilingual "|" patterns
6. **AI Review** - Claude contextual judgment for ambiguous cases (Anthropic or Vertex)

## Environment Configuration

Each module loads environment variables in this order:

1. **`.env.public`** loaded first (shared defaults for hackathon participants, committed)
2. **`.env`** loaded second with `override: true` (personal overrides, gitignored)

Participants without a `.env` file get the shared read-only credentials from `.env.public`. Developers with a `.env` file (containing admin credentials) automatically override for write operations like migrations and imports.

## Quick Start

```bash
# Clone and install all modules
git clone <repo-url> && cd hackathon
for dir in CRA FED AB general; do (cd $dir && npm install); done

# Each module's data is already loaded in the shared database.
# To verify or reload:
cd CRA && npm run verify
cd ../FED && npm run verify
cd ../AB && npm run verify

# Run analysis
cd ../AB && npm run analyze:all
cd ../general && node scripts/resolve-entity.js --name "Your Entity" --llm
```

## Database Access

**Read-only** (for querying, no data modification):
```
postgresql://hackathon_readonly:...@render.com:5432/database_database_w2a1
```
Credentials are in each module's `.env.public`.

**Schemas:** `cra`, `fed`, `ab`, `general` (set via `search_path` in each module's `lib/db.js`)

## License

MIT - see [LICENSE](LICENSE)
