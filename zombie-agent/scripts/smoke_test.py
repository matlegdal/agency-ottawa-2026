"""End-to-end MCP smoke test.

Verifies — without involving the FastAPI / browser layer — that:

  Probe 1 (orchestrator): the main agent can list objects in the `cra`
    schema via `mcp__postgres__list_objects`.

  Probe 2 (subagent): the orchestrator can delegate via the `Task` tool to
    the `verifier` subagent, and the verifier can independently call
    `mcp__postgres__execute_sql` and return a real number.

Run from the project root:

    cd zombie-agent
    uv run python scripts/smoke_test.py

A non-zero exit means the agent infrastructure is broken; fix it before
working on demo logic.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Make `from src.X` work when invoked as `python scripts/smoke_test.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk.types import HookMatcher

from src.config import WORKSPACE_DIR, config
from src.hooks import (
    inject_context_hook,
    safe_sql_hook,
    subagent_stop_hook,
)
from src.mcp_servers import build_postgres_mcp, ui_bridge_mcp
from src.system_prompt import SYSTEM_PROMPT
from src.verifier import verifier_agent


def _build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        cwd=str(WORKSPACE_DIR),
        setting_sources=["project"],
        model="claude-sonnet-4-6",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=[
            "Skill",
            "Task",
            "Agent",
            "mcp__postgres__execute_sql",
            "mcp__postgres__explain_query",
            "mcp__postgres__list_schemas",
            "mcp__postgres__list_objects",
            "mcp__postgres__get_object_details",
            "mcp__ui_bridge__publish_finding",
        ],
        mcp_servers={
            "postgres": build_postgres_mcp(config.READONLY_DATABASE_URL),
            "ui_bridge": ui_bridge_mcp,
        },
        agents={"verifier": verifier_agent},
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="mcp__postgres__execute_sql",
                    hooks=[safe_sql_hook],
                )
            ],
            "UserPromptSubmit": [HookMatcher(hooks=[inject_context_hook])],
            "SubagentStop": [HookMatcher(hooks=[subagent_stop_hook])],
        },
        permission_mode="bypassPermissions",
        max_turns=20,
        env={"ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY},
    )


async def _run_probe(label: str, prompt: str) -> dict:
    """Run a single probe and collect tool-use evidence."""
    print(f"\n{'=' * 70}\nPROBE: {label}\n{'=' * 70}")
    print(f"PROMPT: {prompt}\n")

    state = {
        "main_tool_uses": [],          # tools used by the orchestrator
        "subagent_tool_uses": [],      # tools used inside a subagent context
        "subagent_stops": [],
        "tool_results": [],
        "assistant_text": [],
        "final": None,
    }

    options = _build_options()
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                # parent_tool_use_id is set when the message is being produced
                # inside a subagent context (the subagent was launched by a
                # Task tool call whose tool_use_id is referenced here).
                parent_tool_use_id = getattr(msg, "parent_tool_use_id", None)
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        record = {
                            "name": block.name,
                            "input_keys": (
                                list(block.input.keys())
                                if isinstance(block.input, dict)
                                else None
                            ),
                            "parent_tool_use_id": parent_tool_use_id,
                        }
                        if parent_tool_use_id:
                            state["subagent_tool_uses"].append(record)
                        else:
                            state["main_tool_uses"].append(record)
                        print(
                            f"  → {('subagent' if parent_tool_use_id else 'main'):>8s} "
                            f"tool_use: {block.name}"
                        )
                    elif isinstance(block, TextBlock):
                        if block.text.strip():
                            state["assistant_text"].append(block.text)
                            preview = block.text.strip().replace("\n", " ")[:140]
                            print(f"  · text: {preview}")
            elif isinstance(msg, UserMessage):
                # The SDK surfaces tool results as UserMessage(ToolResultBlock).
                content = msg.content if isinstance(msg.content, list) else []
                for block in content:
                    if isinstance(block, ToolResultBlock):
                        snippet = ""
                        if isinstance(block.content, list):
                            for c in block.content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    snippet = (c.get("text") or "")[:200]
                                    break
                        state["tool_results"].append(snippet)
            elif isinstance(msg, ResultMessage):
                state["final"] = {
                    "duration_ms": getattr(msg, "duration_ms", None),
                    "total_cost_usd": getattr(msg, "total_cost_usd", None),
                    "num_turns": getattr(msg, "num_turns", None),
                    "is_error": getattr(msg, "is_error", None),
                }
                print(f"\n  [result] {state['final']}")

    return state


def _evaluate_probe1(state: dict) -> bool:
    used_postgres = [
        u for u in state["main_tool_uses"] if u["name"].startswith("mcp__postgres__")
    ]
    if not used_postgres:
        print("  ✗ FAIL: orchestrator never called any mcp__postgres__* tool.")
        return False
    print(
        "  ✓ PASS: orchestrator called "
        f"{len(used_postgres)} postgres MCP tool(s): "
        f"{[u['name'] for u in used_postgres]}"
    )
    return True


def _evaluate_probe2(state: dict) -> bool:
    spawn_calls = [
        u for u in state["main_tool_uses"] if u["name"] in ("Task", "Agent")
    ]
    if not spawn_calls:
        print("  ✗ FAIL: orchestrator never invoked Task/Agent to spawn the verifier.")
        return False
    print(
        f"  ✓ orchestrator spawned subagent via {len(spawn_calls)} "
        f"{spawn_calls[0]['name']} call(s)"
    )

    sub_postgres = [
        u
        for u in state["subagent_tool_uses"]
        if u["name"] == "mcp__postgres__execute_sql"
    ]
    if not sub_postgres:
        print(
            "  ✗ FAIL: subagent did not call mcp__postgres__execute_sql. "
            "Subagent tool uses observed: "
            f"{[u['name'] for u in state['subagent_tool_uses']]}"
        )
        return False
    print(
        f"  ✓ verifier subagent independently ran "
        f"{len(sub_postgres)} mcp__postgres__execute_sql call(s)"
    )
    return True


async def main() -> int:
    print(f"WORKSPACE_DIR = {WORKSPACE_DIR}")
    print(f"DATABASE_URI  = {config.READONLY_DATABASE_URL}")

    p1 = await _run_probe(
        "Orchestrator can reach the postgres MCP",
        (
            "Use the postgres MCP to LIST OBJECTS in the `cra` schema. "
            "Specifically, call mcp__postgres__list_objects with "
            "schema_name='cra'. Then in plain text reply with the names of "
            "the first three tables you see, separated by commas. "
            "Do NOT call publish_finding, do NOT spawn the verifier, do NOT "
            "run any other queries. This is a connectivity test."
        ),
    )
    p1_ok = _evaluate_probe1(p1)

    p2 = await _run_probe(
        "Verifier subagent can independently call execute_sql",
        (
            "This is a connectivity test for the verifier subagent. "
            "Use the `Task` tool with `subagent_type='verifier'` and pass it "
            "the following prompt verbatim: \n\n"
            "  CONNECTIVITY TEST. Call mcp__postgres__execute_sql with "
            "  sql='SELECT COUNT(*) AS n FROM cra.cra_identification' and "
            "  return the integer COUNT in your final response, in the form "
            "  'count = <N>'. Do NOT do any of your usual VERIFIED/REFUTED "
            "  reasoning — just run that one query and report the number.\n\n"
            "When the subagent returns, reply to me with the count it "
            "reported, in the form: 'verifier reported count = <N>'. Do "
            "not call publish_finding."
        ),
    )
    p2_ok = _evaluate_probe2(p2)

    print("\n" + "=" * 70)
    print(f"PROBE 1 (orchestrator)        : {'PASS' if p1_ok else 'FAIL'}")
    print(f"PROBE 2 (subagent)            : {'PASS' if p2_ok else 'FAIL'}")
    print("=" * 70)
    return 0 if (p1_ok and p2_ok) else 1


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Put it in zombie-agent/.env")
        sys.exit(2)
    sys.exit(asyncio.run(main()))
