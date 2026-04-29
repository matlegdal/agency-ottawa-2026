"""Background investigation manager.

The dashboard calls POST /api/run on page load to start the canonical
zombie investigation automatically. Only one run is active at a time;
a second call while a run is live is a silent no-op.

POST /api/stop emits run_cancelled (so all /ws/live subscribers see it)
then cancels the asyncio task.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Same canonical query as the UI — kept in sync manually.
ZOMBIE_QUESTION = (
    "Find me 3 federal grant recipients that look operationally dormant on the"
    " public record. Criteria: cumulative federal commitment of at least $1 million"
    " between 2018 and 2022 (use the agreement_current CTE pattern from the"
    " data-quirks skill, NOT a naive SUM of fed.grants_contributions); no CRA T3010"
    " filing in any year after their last grant when matched on the 9-digit BN root;"
    " no further federal grants since 2024-01-01; no Alberta grant payments in"
    " fiscal years 2024-2025 or 2025-2026.\n\n"
    "For each surviving candidate, quantify total federal exposure (CAD), last-known"
    " year of activity, and government-share of operating revenue from the most"
    " recent CRA filing (filtered through cra.t3010_impossibilities so a stray"
    " five-billion-dollar typo does not pollute the ratio). Resolve every candidate"
    " through general.vw_entity_funding so the briefing names canonical entities,"
    " not aliases.\n\n"
    "Publish your top 3-5 candidates with verifier_status=\"pending\" first, then"
    " delegate to the verifier subagent. Expect the verifier to REFUTE candidates"
    " that turn out to be designation A private foundations or whose T3010 filing"
    " window is still open — those refutations are the methodology working, not"
    " failing. For any candidate the verifier marks AMBIGUOUS, use the"
    " iterative-exploration loop (up to 3 follow-up SQL queries) to defend or"
    " revise before publishing the final verdict.\n\n"
    "Frame all output as audit leads worth a closer look — never as accusations."
)

_current_task: Optional[asyncio.Task] = None


def is_running() -> bool:
    return _current_task is not None and not _current_task.done()


async def _noop_sender(payload: dict) -> None:
    pass


async def trigger_run(question: str = ZOMBIE_QUESTION) -> bool:
    """Start a background investigation.

    Returns True if a new run was started, False if one was already running.
    """
    global _current_task
    if is_running():
        logger.info("trigger_run: already running, ignoring")
        return False
    from src.agent import run_question

    logger.info("trigger_run: starting background investigation")
    _current_task = asyncio.create_task(run_question(question, _noop_sender))
    return True


async def stop_run() -> bool:
    """Cancel the current run.

    Returns True if a task was cancelled, False if nothing was running.
    The caller is responsible for emitting run_cancelled before calling this
    so /ws/live subscribers see the event.
    """
    global _current_task
    if not is_running():
        return False
    _current_task.cancel()
    return True
