"""FastAPI routes."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from src.agent import run_question
from src.config import PROJECT_ROOT
from src import streaming


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
