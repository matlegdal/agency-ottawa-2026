"""Singleton that accumulates agent events for the /report endpoint.

Registered as a sync hook into streaming.emit via set_event_hook() in
main.py. Handles three event types:
- universe  — the methodology funnel counts (emitted once, after Step A)
- finding   — per-candidate verdict (may be emitted multiple times per BN
               as status progresses; last write wins)
- dossier   — rich per-verified-candidate evidence panels (emitted once
               per verified BN after the verdict settles)

State is persisted to data/last_run.json after every event so a server
restart does not lose a completed run.
"""

import dataclasses
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

_PERSIST_PATH = Path(PROJECT_ROOT) / "data" / "last_run.json"


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
        self.state = self._load() or RunState()

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
        else:
            return  # nothing persisted for untracked event types
        self._save()

    def _save(self) -> None:
        try:
            _PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            _PERSIST_PATH.write_text(
                json.dumps(dataclasses.asdict(self.state), indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("run_store: failed to persist state", exc_info=True)

    def _load(self) -> RunState | None:
        try:
            if not _PERSIST_PATH.exists():
                return None
            data = json.loads(_PERSIST_PATH.read_text(encoding="utf-8"))
            return RunState(**data)
        except Exception:
            logger.warning("run_store: failed to load persisted state", exc_info=True)
            return None


run_store = RunStore()
