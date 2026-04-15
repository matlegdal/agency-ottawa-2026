# General - Shared Tools & Reference Data

Part of the **AI For Accountability Hackathon** suite, alongside [CRA](../CRA/), [FED](../FED/), and [AB](../AB/).

## Overview

This module provides cross-dataset reference data and tools that work across all hackathon datasets. It includes Alberta ministry reference data, a universal fuzzy matching engine for entity resolution, and AI-assisted review via Claude (with Anthropic direct and Vertex AI fallback).

## Quick Start

```bash
npm install
npm run setup     # Create general schema + load 27 Alberta ministries
```

## Database

- **Schema:** `general` (search path set automatically by `lib/db.js`)
- **Table:** `general.ministries` - 27 current Alberta ministries with codes, ministers, deputy ministers

## Ministry Reference Data

27 ministries loaded from `scripts/02-seed-ministries.js` with current cabinet appointments:

| Code | Ministry | Minister |
|------|----------|----------|
| AE | Advanced Education | Myles McDougall |
| TI | Technology and Innovation | Nate Glubish |
| TBF | Treasury Board and Finance | Nate Horner |
| EC | Executive Council | Danielle Smith |
| ... | *(24 more)* | |

```bash
npm run seed:ministries    # Reload/update ministry data
```

## Entity Resolution

The core cross-dataset tool. Resolves entity names across CRA, FED, and AB using multi-layer matching.

### Deterministic Resolution (no API key needed)

```bash
# Basic fuzzy search
node scripts/fuzzy-search.js --name "University of Alberta"

# Smart resolution with BN anchor + core token gate + BN negative filter
node scripts/resolve-entity.js --name "Boyle Street Service" --bn 118814391

# Cross-dataset batch matching
node scripts/cross-match.js --threshold 0.6 --limit 200
```

### AI-Assisted Resolution

Adds a Claude second pass to judge ambiguous matches. Tries Anthropic direct API first, falls back to Vertex AI automatically.

```bash
# Auto provider selection (Anthropic -> Vertex fallback)
node scripts/resolve-entity.js --name "Homeward Trust" --bn 834173627 --llm

# Force Vertex AI
node scripts/resolve-entity.js --name "mustard seed society" --llm --provider vertex

# Force Anthropic direct
node scripts/resolve-entity.js --name "mustard seed society" --llm --provider anthropic

# Standalone AI review from saved results
node scripts/llm-review.js --input results.json --output reviewed.json
```

### Resolution Layers

| Layer | Method | Confidence | Description |
|-------|--------|-----------|-------------|
| 1 | BN Anchor | 99% | Match on root 9-digit business number (gold standard) |
| 1b | BN Negative | reject | Different BN root = confirmed different entity |
| 2 | Exact Normalized | 95% | Exact match after stripping punctuation, "THE", legal suffixes |
| 3 | Core Token Gate | 70-90% | All discriminating words must be present |
| 4 | Trigram + Gate | 60-85% | pg_trgm similarity filtered by core tokens |
| 5 | Trade-Name Expansion | varies | Parse "TRADE NAME OF" and bilingual "\|" patterns |
| 6 | AI Review | varies | Claude contextual judgment (SAME/RELATED/DIFFERENT/UNCERTAIN) |

### How BN Matching Works

Canadian Business Numbers: `118814391RR0001`
- First 9 digits (`118814391`) = organization identifier (root)
- 2-letter suffix (`RR`) = program type (RR=charity, RP=pension, RC=corporate, RT=GST)
- 4-digit account (`0001`) = program account number

**Same root = same organization**, regardless of suffix. The resolver extracts the root and matches with `LIKE '118814391%'`.

## AI Provider Configuration

The LLM review supports two providers with automatic fallback:

### Anthropic Direct API
Set `ANTHROPIC_API_KEY` in `.env.public` or `.env`.

### Vertex AI (Google Cloud)
Set these in `.env.public` or `.env`:
```
VERTEX_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
VERTEX_CLAUDE_SONNET_MODEL=claude-sonnet-4-6
VERTEX_PROJECT_ID=your-project-id
VERTEX_ENDPOINT=aiplatform.googleapis.com
VERTEX_LOCATION_ID=global
VERTEX_METHOD=rawPredict
```

Authentication uses Google OAuth2 JWT bearer flow with the service account's private key. Tokens are cached for 1 hour.

## Environment Configuration

```
.env.public    loaded first   (shared defaults for hackathon participants)
.env           loaded second  (override: true - personal overrides win)
```

Participants without a `.env` get read-only defaults. Developers with a `.env` containing admin credentials automatically override for write operations.

## File Structure

```
general/
├── .env.public              # Shared credentials (DB + Anthropic + Vertex)
├── .env                     # Personal overrides (gitignored)
├── .env.example             # Template
├── package.json
├── README.md                # This file
├── lib/
│   ├── db.js                # PostgreSQL connection (search_path=general)
│   ├── fuzzy-match.js       # Fuzzy matching engine (trigram, Levenshtein, tokens)
│   ├── entity-resolver.js   # Multi-layer entity resolution with BN anchoring
│   └── llm-review.js        # AI review (Anthropic + Vertex dual provider)
├── scripts/
│   ├── 01-migrate.js        # Create general schema + ministries table
│   ├── 02-seed-ministries.js # Load 27 Alberta ministries
│   ├── drop-tables.js       # Drop general schema
│   ├── fuzzy-search.js      # Interactive fuzzy entity search
│   ├── cross-match.js       # Batch cross-dataset matching
│   ├── resolve-entity.js    # Smart entity resolution (deterministic + AI)
│   └── llm-review.js        # Standalone AI review
└── reports/                 # Cross-match output files
```

## Scripts

```bash
npm run migrate          # Create schema and tables
npm run seed:ministries  # Load/update ministry data
npm run setup            # migrate + seed
npm run drop             # Drop all general tables
npm run reset            # drop + setup
npm run create-indexes   # Create pg_trgm indexes for fuzzy matching
```

## License

MIT - see [../LICENSE](../LICENSE)
