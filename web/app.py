"""FastAPI chat server for the EV Charging Schedule Agent.

Serves the HTML chat UI at GET / and handles chat messages at POST /api/chat.
Runs the real Python agent (including CVXPY solver) inline.

Usage (from project root):
    uvicorn web.app:app --reload --port 8000
    # Then open http://localhost:8000

Requires OPENAI_API_KEY in .env or the environment.
"""

import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so agent imports work when the
# server is started from any directory.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, List

app = FastAPI(title="EV Charging Schedule Agent")

_HTML_PATH = Path(__file__).parent / "index.html"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the chat UI."""
    if not _HTML_PATH.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(content=_HTML_PATH.read_text(encoding="utf-8"))


@app.post("/api/chat")
async def chat(req: ChatRequest) -> JSONResponse:
    """Run the agent on the user's message and return a response.

    Accepts:
        message: The user's latest message.
        history: Prior turns (used for display only; agent is stateless per call).

    Returns:
        { "response": str, "needs_clarification": bool }
        or on error:
        { "error": str }
    """
    try:
        from agent.run import run_agent_from_text, ClarificationResult
    except ImportError as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Agent import failed: {exc}. Make sure you are running from the project root."},
        )

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JSONResponse(
            status_code=500,
            content={"error": "OPENAI_API_KEY is not set. Add it to .env or set it in your environment."},
        )

    try:
        result = run_agent_from_text(req.message, api_key=api_key)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Agent error: {exc}"},
        )

    if isinstance(result, ClarificationResult):
        return JSONResponse(content={
            "response": result.message,
            "needs_clarification": True,
        })

    return JSONResponse(content={
        "response": result.explanation,
        "needs_clarification": False,
    })


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    """Simple health check."""
    api_key_set = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    return {"status": "ok", "api_key_set": api_key_set}
