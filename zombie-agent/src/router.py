"""FastAPI routes."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from src.agent import run_question
from src.config import PROJECT_ROOT
from src import streaming, run_manager
from src.reporting.run_store import run_store
from src.reporting.report import generate_html


logger = logging.getLogger(__name__)
router = APIRouter()

_INDEX_HTML_PATH = Path(PROJECT_ROOT) / "ui" / "index.html"
_DASHBOARD_HTML_PATH = Path(PROJECT_ROOT) / "dashboard" / "index.html"


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    if not _INDEX_HTML_PATH.exists():
        return HTMLResponse(
            "<h1>UI not built yet</h1>", status_code=503
        )
    return HTMLResponse(_INDEX_HTML_PATH.read_text(encoding="utf-8"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    if not _DASHBOARD_HTML_PATH.exists():
        return HTMLResponse(
            "<h1>Dashboard not built yet</h1>", status_code=503
        )
    return HTMLResponse(_DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))


@router.get("/report", response_class=HTMLResponse)
async def report() -> HTMLResponse:
    return HTMLResponse(generate_html(run_store.state, is_running=run_manager.is_running()))


@router.post("/api/run")
async def api_run() -> dict:
    """Start the canonical zombie investigation in the background.

    No-op if a run is already in progress. Called by the dashboard on page load.
    """
    started = await run_manager.trigger_run()
    return {"started": started}


@router.post("/api/stop")
async def api_stop() -> dict:
    """Cancel the current run and broadcast a run_cancelled event."""
    await streaming.emit({"type": "run_cancelled"})
    stopped = await run_manager.stop_run()
    return {"stopped": stopped}


@router.get("/api/status")
async def api_status() -> dict:
    """Return whether an investigation is currently running."""
    return {"running": run_manager.is_running()}


@router.get("/ping")
async def ping(request: Request) -> dict[str, str]:
    return {"status": "ok"}


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    """Subscribe-only broadcast channel for dashboard clients."""
    await websocket.accept()

    async def send(payload: dict) -> None:
        await websocket.send_text(json.dumps(payload))

    streaming.subscribe_broadcast(send)
    try:
        while True:
            # Keep the connection alive; we don't process inbound messages.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws/live connection error")
    finally:
        streaming.unsubscribe_broadcast(send)
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()

    async def send(payload: dict) -> None:
        await websocket.send_text(json.dumps(payload))

    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                await send({"type": "error", "error": "invalid JSON"})
                continue

            if data.get("type") != "ask" or not data.get("question"):
                await send(
                    {
                        "type": "error",
                        "error": "expected {'type':'ask','question':...}",
                    }
                )
                continue

            await run_question(data["question"], send)
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("Websocket loop crashed")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
