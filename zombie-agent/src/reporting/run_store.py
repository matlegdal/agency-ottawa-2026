"""Singleton that accumulates agent events for the /report endpoint.

Registered as a sync hook into streaming.emit via set_event_hook() in
main.py. Handles three event types:
- universe  — the methodology funnel counts (emitted once, after Step A)
- finding   — per-candidate verdict (may be emitted multiple times per BN
               as status progresses; last write wins)
- dossier   — rich per-verified-candidate evidence panels (emitted once
               per verified BN after the verdict settles)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RunState:
    question: str = ""
    run_date: str = ""
    universe: dict = field(default_factory=dict)
    findings: dict = field(default_factory=dict)   # bn → latest finding payload
    dossiers: dict = field(default_factory=dict)   # bn → dossier payload
    run_meta: dict = field(default_factory=dict)   # duration_ms, total_cost_usd, num_turns
    is_complete: bool = False


class RunStore:
    def __init__(self) -> None:
        self.state = RunState()

    def handle_event(self, payload: dict) -> None:
        t = payload.get("type")
        if t == "run_start":
            self.state = RunState(
                question=payload.get("question", ""),
                run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
        elif t == "universe":
            self.state.universe = payload
        elif t == "finding":
            bn = payload.get("bn") or "__unknown__"
            self.state.findings[bn] = payload
        elif t == "dossier":
            bn = payload.get("bn") or "__unknown__"
            self.state.dossiers[bn] = payload
        elif t == "result":
            self.state.run_meta = {
                k: payload.get(k)
                for k in ("duration_ms", "total_cost_usd", "num_turns")
            }
        elif t == "run_complete":
            self.state.is_complete = True


run_store = RunStore()
