# Zombie Recipients Agent

Agentic system that investigates publicly-funded "zombie recipients" — entities that received material federal/provincial money and then went silent. Built for the AI For Accountability Hackathon (Ottawa, 2026-04-29) using the Claude Agent SDK.

## What you get

- An **orchestrator** (Claude Sonnet 4.6 via the Claude Agent SDK) that decomposes an investigative question, runs labelled SQL queries against a read-only Postgres MCP, and publishes structured findings to a UI.
- A **paranoid verifier subagent** that independently cross-checks each candidate and returns VERIFIED / REFUTED / AMBIGUOUS.
- An **iterative-exploration loop**: AMBIGUOUS verdicts trigger up to 3 follow-up SQL queries before the orchestrator concedes or revises.
- Three **skills** (`accountability-investigator`, `data-quirks`, `zombie-detection`) that load on demand and encode the methodology + the data quirks that will silently fool a naive query.
- Four **hooks** that gate destructive SQL, auto-inject `LIMIT`, stream activity-panel events, and announce subagent completions.
- A **3-panel UI** (chat / activity / briefing) wired to the agent over a single websocket.

## Architecture

```
Browser <-- ws --> FastAPI (server.main)
                       │
                       ▼
                   ClaudeSDKClient (src.agent)
                       │
            ┌──────────┼─────────────────────────────┐
            ▼          ▼                             ▼
   external stdio   in-process SDK MCP        AgentDefinition
   postgres MCP     (publish_finding tool)    (verifier subagent)
   (crystaldba/     (src.mcp_servers.         │
    postgres-mcp,    ui_bridge)               │ inherits parent mcp_servers
    restricted)                               │ but tools=["mcp__postgres__execute_sql"]
                                              ▼
                                          Postgres
```

## Project layout

```
zombie-agent/
├── pyproject.toml
├── .env.example
├── README.md
├── ui/index.html               # 3-panel single page, websocket client
├── scripts/
│   └── smoke_test.py           # CLI verification of MCP access (orchestrator + subagent)
├── src/
│   ├── main.py                 # FastAPI app
│   ├── router.py               # /, /ws routes
│   ├── config.py               # Pydantic settings
│   ├── agent.py                # Claude Agent SDK orchestration
│   ├── system_prompt.py        # SYSTEM_PROMPT constant
│   ├── verifier.py             # AgentDefinition for the verifier subagent
│   ├── hooks.py                # 4 hooks (safe_sql, post_sql, inject_context, subagent_stop)
│   ├── streaming.py            # websocket-sender abstraction shared by hooks + tools
│   ├── mcp_servers/
│   │   ├── postgres.py         # external stdio MCP config (crystaldba/postgres-mcp)
│   │   └── ui_bridge.py        # in-process SDK MCP server with publish_finding tool
│   └── workspace/              # cwd handed to the SDK; skills live here
│       ├── CLAUDE.md
│       └── .claude/skills/
│           ├── accountability-investigator/SKILL.md
│           ├── data-quirks/SKILL.md
│           └── zombie-detection/SKILL.md
└── tests/
```

## Quick start

```bash
cd zombie-agent
cp .env.example .env            # then fill in ANTHROPIC_API_KEY

# install dependencies
uv sync

# pull the postgres MCP image (one time)
docker pull crystaldba/postgres-mcp

# verify the agent + subagent can both reach the postgres MCP
uv run python scripts/smoke_test.py

# launch the demo
uv run uvicorn src.main:app --host 127.0.0.1 --port 8080 --reload
# open http://127.0.0.1:8080
```

## Why local, not AgentCore

Both `deskcore` and `qacore` reference repos package the same Claude Agent SDK loop into a container deployed to AWS Bedrock AgentCore. That is the right shape for a multi-tenant SaaS backend. For a single-laptop hackathon demo where the only consumer is one browser tab, the AgentCore container, the Postgres-backed session store, and the AWS auth path are all overhead with no benefit. We keep the same internal organization (FastAPI app, `agent.py`, `mcp_config`-style server builders, `skills/` workspace) so the code could be lifted into AgentCore later, but ship it as a plain `uvicorn` process for the demo.

## Verifying postgres MCP access

`scripts/smoke_test.py` runs two probes back-to-back:

1. **Orchestrator probe** — asks the agent to list tables in the `cra` schema. Expects to see at least one `mcp__postgres__list_objects` tool use and a non-empty result.
2. **Subagent probe** — asks the orchestrator to delegate a one-line task to the verifier (`SELECT COUNT(*) FROM fed.vw_agreement_current`). Expects the verifier subagent to call `mcp__postgres__execute_sql` and return a number.

Both probes must pass before any of the demo logic matters.
