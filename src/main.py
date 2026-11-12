"""HTTP entry point: the PDP the gateways call, plus the operations and chat APIs.

    uvicorn src.main:app --host 0.0.0.0 --port 8080

| Method | Path                    | Caller                                  |
|--------|-------------------------|-----------------------------------------|
| POST   | /pdp/decide             | gateway-esp32 (its ``pdpUrl``)          |
| GET    | /pdp/decisions[/{id}]   | operators, dashboards                   |
| GET    | /pdp/integrity          | auditors                                |
| POST   | /ops/run                | operators: intent -> operations crew    |
| GET    | /v1/models              | Open WebUI (OpenAI-compatible)          |
| POST   | /v1/chat/completions    | Open WebUI: chat -> operations crew     |
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from src import __version__
from src.llm.crews import AccessReviewer, run_operations
from src.llm.decision import DecisionService
from src.mcp_server.runtime import get_runtime

log = logging.getLogger("llm_access")
OPS_MODEL_ID = "smartgate-ops"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime = get_runtime()
    reviewer = None
    if runtime.settings.agent_review != "off":
        try:
            reviewer = await asyncio.to_thread(AccessReviewer, runtime.settings)
        except Exception:  # noqa: BLE001 - the PDP still runs; failure mode decides
            log.exception("agent reviewer unavailable; failure mode %s applies",
                          runtime.settings.agent_failure_mode)
    app.state.runtime = runtime
    app.state.decisions = DecisionService(runtime, reviewer)
    try:
        yield
    finally:
        if reviewer is not None:
            reviewer.close()


app = FastAPI(title="LLM Access - Smart Gateway PDP", version=__version__, lifespan=lifespan)


# ----------------------------------------------------------------------- PDP ---

@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    runtime = request.app.state.runtime
    return {"status": "ok", "version": __version__,
            "agent_review": runtime.settings.agent_review,
            "reviewer_ready": request.app.state.decisions.reviewer is not None,
            "deploy_mode": runtime.settings.deploy_mode}


@app.post("/pdp/decide")
async def pdp_decide(request: Request, authorization: str | None = Header(default=None)
                     ) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        body = {}
    bearer = authorization.removeprefix("Bearer ").strip() if authorization else None
    return await request.app.state.decisions.decide_raw(body if isinstance(body, dict) else {},
                                                        bearer)


@app.get("/pdp/decisions")
async def list_decisions(request: Request, limit: int = 50, door: str | None = None,
                         uid: str | None = None) -> list[dict[str, Any]]:
    return request.app.state.runtime.decisions.recent(limit=limit, door=door, uid=uid)


@app.get("/pdp/decisions/{decision_id}")
async def get_decision(request: Request, decision_id: str) -> dict[str, Any]:
    record = request.app.state.runtime.decisions.get(decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail="no such decision in recent history")
    return record


@app.get("/pdp/integrity")
async def integrity(request: Request) -> dict[str, Any]:
    return request.app.state.runtime.decisions.verify()


# ---------------------------------------------------------------- operations ---

class OpsRequest(BaseModel):
    intent: str
    dry_run: bool = True


async def _run_ops(intent: str, dry_run: bool) -> dict[str, Any]:
    settings = get_runtime().settings
    report = await asyncio.to_thread(run_operations, settings, intent, dry_run=dry_run)
    return report.model_dump()


@app.post("/ops/run")
async def ops_run(body: OpsRequest) -> dict[str, Any]:
    if not body.intent.strip():
        raise HTTPException(status_code=400, detail="empty intent")
    return await _run_ops(body.intent, body.dry_run)


# ------------------------------------------------- OpenAI-compatible chat (UI) ---

class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]]


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str
    messages: list[ChatMessage]
    stream: bool = False


def _last_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            if isinstance(message.content, str):
                return message.content.strip()
            return " ".join(part.get("text", "") for part in message.content).strip()
    return ""


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": OPS_MODEL_ID, "object": "model",
                                        "created": int(time.time()), "owned_by": "local"}]}


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(req: ChatCompletionRequest) -> Any:
    if req.model != OPS_MODEL_ID:
        raise HTTPException(status_code=400, detail=f"unknown model {req.model!r}")
    intent = _last_user_text(req.messages)
    if not intent:
        raise HTTPException(status_code=400, detail="empty message")
    dry_run = get_runtime().settings.deploy_mode == "dry_run"
    report = await _run_ops(intent, dry_run)
    answer = _format_report(report, dry_run)
    completion_id, created = f"chatcmpl-{uuid.uuid4().hex}", int(time.time())

    if req.stream:
        async def events() -> AsyncIterator[str]:
            chunk = {"id": completion_id, "object": "chat.completion.chunk", "created": created,
                     "model": req.model, "choices": [{"index": 0, "finish_reason": None,
                                                      "delta": {"role": "assistant",
                                                                "content": answer}}]}
            yield f"data: {json.dumps(chunk)}\n\n"
            done = {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(events(), media_type="text/event-stream")

    return {"id": completion_id, "object": "chat.completion", "created": created,
            "model": req.model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": answer}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}


def _format_report(report: dict[str, Any], dry_run: bool) -> str:
    lines = [f"**Outcome:** {report['outcome']}{' (dry run)' if dry_run else ''}", "",
             report["summary"]]
    for title, key in (("Plans applied", "plans_applied"), ("Plans failed", "plans_failed"),
                       ("Findings", "findings"), ("Follow-up", "follow_up")):
        if report.get(key):
            lines += ["", f"**{title}**"] + [f"- {item}" for item in report[key]]
    return "\n".join(lines)
