import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

import httpx
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from jsonschema import ValidationError, validate
from livekit import api as livekit_api
from pydantic import ValidationError as PydanticValidationError

from .auth import Principal, internal_token, principal
from .config import get_settings
from .knowledge import Embeddings, chunk_text, extract_bytes, extract_url, get_embeddings
from .live import EventBus, encode_sse, get_event_bus
from .livekit_sessions import LiveKitSessions, get_livekit_sessions
from .native_integrations import NativeIntegrations, get_native_integrations
from .postprocessing import Postprocessor, get_postprocessor
from .repository import Repository, get_repository
from .schemas import (
    AgentCreate,
    AgentDraftPatch,
    AgentPatch,
    AgentRollback,
    AgentToolsSet,
    ApiKeyCreate,
    CallEventBatch,
    CallPatch,
    CallToolCallCreate,
    CallTurnBatch,
    DocumentCreate,
    InternalCallCreate,
    InternalRagQuery,
    InternalToolExecute,
    KnowledgeBaseCreate,
    KnowledgeBasePatch,
    KnowledgeQuery,
    MemberCreate,
    MemberPatch,
    SecretCreate,
    SessionCreate,
    ToolCreate,
    ToolPatch,
    ToolTestRequest,
)
from .secrets import SecretCipher, get_secret_cipher
from .tool_execution import ToolExecutor, get_tool_executor

v1 = APIRouter(prefix="/v1")
internal = APIRouter(prefix="/internal", dependencies=[Depends(internal_token)])
webhooks = APIRouter(prefix="/webhooks")
Auth = Annotated[Principal, Depends(principal)]
Repo = Annotated[Repository, Depends(get_repository)]
Bus = Annotated[EventBus, Depends(get_event_bus)]
Executor = Annotated[ToolExecutor, Depends(get_tool_executor)]
Embedder = Annotated[Embeddings, Depends(get_embeddings)]
Cipher = Annotated[SecretCipher, Depends(get_secret_cipher)]
Native = Annotated[NativeIntegrations, Depends(get_native_integrations)]
Processor = Annotated[Postprocessor, Depends(get_postprocessor)]
Rtc = Annotated[LiveKitSessions, Depends(get_livekit_sessions)]


def _require_admin(auth: Principal) -> None:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})


def _egress_recording(event: livekit_api.WebhookEvent) -> tuple[UUID, dict[str, Any]] | None:
    info = event.egress_info
    if not info:
        return None
    file_info = info.file_results[0] if info.file_results else None
    candidate = file_info.filename if file_info else ""
    if not candidate and info.room_composite.file_outputs:
        candidate = info.room_composite.file_outputs[0].filepath
    try:
        call_id = UUID(candidate.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    except (ValueError, IndexError):
        return None
    status = "ready" if event.event == "egress_ended" and not info.error else "failed" if info.error else "processing"
    return call_id, {
        "s3_key": candidate,
        "format": candidate.rsplit(".", 1)[-1] if "." in candidate else "ogg",
        "duration_s": round(file_info.duration / 1_000_000_000) if file_info and file_info.duration else None,
        "size_bytes": file_info.size if file_info else None,
        "status": status,
        "metadata": {"egress_id": info.egress_id, "location": file_info.location if file_info else None, "error": info.error or None},
    }


@webhooks.post("/livekit")
async def livekit_webhook(request: Request, repo: Repo) -> dict[str, bool]:
    raw = (await request.body()).decode()
    authorization = request.headers.get("Authorization", "")
    settings = get_settings()
    try:
        event = livekit_api.WebhookReceiver(
            livekit_api.TokenVerifier(settings.livekit_api_key, settings.livekit_api_secret)
        ).receive(raw, authorization)
    except Exception as exc:
        raise HTTPException(401, detail={"code": "invalid_livekit_signature", "message": "Invalid LiveKit signature"}) from exc
    if event.event in {"egress_started", "egress_updated", "egress_ended"} and (recording := _egress_recording(event)):
        await repo.upsert_call_recording(*recording)
    return {"ok": True}


async def _resolve_tool_secret(repo: Repository, cipher: SecretCipher, tenant_id: UUID, tool: dict[str, Any]) -> str | None:
    auth = (tool.get("webhook") or {}).get("auth") or {}
    secret_id = auth.get("secret_id")
    if not secret_id:
        return None
    try:
        secret = await repo.get_secret(tenant_id, UUID(str(secret_id)))
    except ValueError:
        return None
    return await cipher.decrypt(secret["ciphertext"], secret["kms_key_id"]) if secret else None


async def _ingest_document(repo: Repository, embeddings: Embeddings, tenant_id: UUID, document: dict[str, Any], kb: dict[str, Any], content: str | None, upload: bytes | None = None) -> None:
    try:
        extracted = await extract_url(document["source_uri"]) if document["source_type"] == "url" else extract_bytes(upload, document.get("mime"), document["name"]) if upload is not None else content or ""
        texts = chunk_text(extracted, kb["chunk_size"], kb["chunk_overlap"])
        if not texts:
            raise ValueError("document has no extractable text")
        vectors = await embeddings.create(texts, kb["embedding_model"])
        await repo.complete_document(tenant_id, document["id"], [{"content": text, "embedding": vector, "metadata": {"url": document.get("source_uri")}, "token_count": max(1, len(text) // 4)} for text, vector in zip(texts, vectors, strict=True)])
    except Exception as exc:
        await repo.fail_document(tenant_id, document["id"], str(exc))


@v1.get("/me")
async def me(auth: Auth) -> dict[str, Any]:
    return {"id": auth.user_id, "tenant_id": auth.tenant_id, "role": auth.role}


@v1.get("/tenants/{tenant_id}/members")
async def list_members(tenant_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    if tenant_id != auth.tenant_id:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    return {"data": await repo.list_members(auth.tenant_id), "next_cursor": None}


@v1.post("/tenants/{tenant_id}/members", status_code=201)
async def create_member(tenant_id: UUID, body: MemberCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    if tenant_id != auth.tenant_id:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    return await repo.create_member(auth.tenant_id, body.email, body.role)


@v1.patch("/tenants/{tenant_id}/members/{user_id}")
async def update_member(tenant_id: UUID, user_id: UUID, body: MemberPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    if tenant_id != auth.tenant_id or not (member := await repo.update_member(auth.tenant_id, user_id, body.role)):
        raise HTTPException(404, detail={"code": "member_not_found", "message": "Member not found"})
    return member


@v1.delete("/tenants/{tenant_id}/members/{user_id}", status_code=204)
async def delete_member(tenant_id: UUID, user_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if tenant_id != auth.tenant_id or not await repo.delete_member(auth.tenant_id, user_id):
        raise HTTPException(404, detail={"code": "member_not_found", "message": "Member not found"})


@v1.get("/api-keys")
async def list_api_keys(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    return {"data": await repo.list_api_keys(auth.tenant_id), "next_cursor": None}


@v1.post("/api-keys", status_code=201)
async def create_api_key(body: ApiKeyCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    raw = f"vos_{'pk' if body.scope == 'public' else 'sk'}_{secrets.token_urlsafe(32)}"
    prefix = raw[:14]
    item = await repo.create_api_key(auth.tenant_id, {"name": body.name, "prefix": prefix, "hash": hashlib.sha256(raw.encode()).hexdigest(), "scope": body.scope, "allowed_origins": body.allowed_origins})
    return {**item, "key": raw}


@v1.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(key_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if not await repo.revoke_api_key(auth.tenant_id, key_id):
        raise HTTPException(404, detail={"code": "api_key_not_found", "message": "API key not found"})


@v1.get("/agents")
async def list_agents(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_agents(auth.tenant_id), "next_cursor": None}


@v1.post("/agents", status_code=201)
async def create_agent(body: AgentCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    return await repo.create_agent(auth.tenant_id, body.name, auth.user_id)


@v1.get("/agents/{agent_id}")
async def get_agent(agent_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    agent = await repo.get_agent_detail(auth.tenant_id, agent_id)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return agent


@v1.patch("/agents/{agent_id}")
async def update_agent(agent_id: UUID, body: AgentPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    agent = await repo.update_agent(auth.tenant_id, agent_id, body.model_dump(exclude_unset=True))
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return agent


@v1.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: UUID, auth: Auth, repo: Repo) -> None:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    if not await repo.delete_agent(auth.tenant_id, agent_id):
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})


@v1.get("/agents/{agent_id}/versions")
async def list_versions(agent_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    if not await repo.get_agent(auth.tenant_id, agent_id):
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return {"data": await repo.list_versions(auth.tenant_id, agent_id), "next_cursor": None}


@v1.get("/agents/{agent_id}/versions/{version_id}")
async def get_version(agent_id: UUID, version_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    version = await repo.get_version(auth.tenant_id, agent_id, version_id)
    if not version:
        raise HTTPException(404, detail={"code": "version_not_found", "message": "Version not found"})
    return version


@v1.patch("/agents/{agent_id}/draft")
async def update_draft(agent_id: UUID, body: AgentDraftPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    draft = await repo.update_draft(auth.tenant_id, agent_id, body.model_dump(exclude_unset=True))
    if not draft:
        raise HTTPException(404, detail={"code": "draft_not_found", "message": "Draft not found"})
    return draft


@v1.post("/agents/{agent_id}/publish")
async def publish_agent(agent_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    existing = await repo.get_agent(auth.tenant_id, agent_id)
    draft = await repo.get_runtime(agent_id, "draft") if existing else None
    if not draft:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    errors: list[str] = []
    if not str(draft.get("system_prompt", "")).strip():
        errors.append("system_prompt is required")
    if not draft.get("tts"):
        errors.append("tts voice configuration is required")
    for tool in draft["tools"]:
        if tool["type"] == "webhook" and not tool.get("last_test_ok_at"):
            errors.append(f"webhook tool '{tool['name']}' must pass a test")
        if tool.get("native_kind") == "transfer_call" and not draft.get("behavior", {}).get("transfer_number"):
            errors.append("transfer_number is required when transfer_call is enabled")
    if draft.get("knowledge_base_id"):
        documents = await repo.list_documents(auth.tenant_id, draft["knowledge_base_id"])
        if not any(document["status"] == "ready" for document in documents):
            errors.append("selected knowledge base requires at least one ready document")
    if errors:
        raise HTTPException(422, detail={"code": "publish_validation_failed", "message": "Agent draft is not publishable", "details": {"errors": errors}})
    agent = await repo.publish_agent(auth.tenant_id, agent_id)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return agent


@v1.post("/agents/{agent_id}/rollback")
async def rollback_agent(agent_id: UUID, body: AgentRollback, auth: Auth, repo: Repo) -> dict[str, Any]:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    agent = await repo.rollback_agent(auth.tenant_id, agent_id, body.version_id)
    if not agent:
        raise HTTPException(404, detail={"code": "version_not_found", "message": "Published version not found"})
    return agent


@v1.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, auth: Auth, repo: Repo, rtc: Rtc) -> dict[str, Any]:
    agent = await repo.get_agent(auth.tenant_id, body.agent_id)
    if not agent or agent["status"] != "active":
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Active agent not found"})
    end_user = None
    if body.end_user:
        try:
            end_user = await repo.upsert_end_user(auth.tenant_id, body.end_user)
        except ValueError as exc:
            raise HTTPException(422, detail={"code": "invalid_end_user", "message": str(exc)}) from exc
    call = await repo.create_call(auth.tenant_id, body.agent_id, body.variables, body.metadata, agent_version_id=agent["current_version_id"], end_user_id=end_user["id"] if end_user else None)
    call_id = call["id"]
    session = await rtc.provision(call_id=call_id, agent_id=body.agent_id, version="current", variables=body.variables, end_user=body.end_user)
    await repo.update_call(auth.tenant_id, call_id, {"livekit_room": session["room_name"]})
    return {"session_id": call_id, "call_id": call_id, "livekit_url": get_settings().livekit_url, "token": session["token"], "expires_at": datetime.now(UTC) + timedelta(hours=1)}


@v1.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: UUID, auth: Auth, repo: Repo) -> None:
    call = await repo.update_call(auth.tenant_id, session_id, {"status": "cancelled", "end_reason": "user_hangup", "ended_at": datetime.now(UTC)})
    if not call:
        raise HTTPException(404, detail={"code": "session_not_found", "message": "Session not found"})


@v1.post("/agents/{agent_id}/test-session", status_code=201)
async def create_test_session(agent_id: UUID, body: SessionCreate, auth: Auth, repo: Repo, rtc: Rtc) -> dict[str, Any]:
    if body.agent_id != agent_id:
        raise HTTPException(422, detail={"code": "agent_mismatch", "message": "Path and body agent_id must match"})
    agent = await repo.get_agent(auth.tenant_id, agent_id)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    end_user = await repo.upsert_end_user(auth.tenant_id, body.end_user) if body.end_user else None
    metadata = {**body.metadata, "test_session": True}
    call = await repo.create_call(auth.tenant_id, agent_id, body.variables, metadata, agent_version_id=agent["draft_version_id"], end_user_id=end_user["id"] if end_user else None)
    call_id = call["id"]
    session = await rtc.provision(call_id=call_id, agent_id=agent_id, version="draft", variables=body.variables, end_user=body.end_user)
    await repo.update_call(auth.tenant_id, call_id, {"livekit_room": session["room_name"]})
    return {"session_id": call_id, "call_id": call_id, "livekit_url": get_settings().livekit_url, "token": session["token"], "expires_at": datetime.now(UTC) + timedelta(hours=1)}


@v1.get("/calls")
async def calls(
    auth: Auth,
    repo: Repo,
    agent_id: UUID | None = None,
    channel: str | None = None,
    status: str | None = None,
    end_user_id: UUID | None = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    q: str | None = None,
) -> dict[str, Any]:
    filters = {"agent_id": agent_id, "channel": channel, "status": status, "end_user_id": end_user_id, "from": from_date, "to": to_date, "q": q}
    return {"data": await repo.list_calls(auth.tenant_id, filters), "next_cursor": None}


@v1.get("/calls/{call_id}")
async def get_call(call_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    call = await repo.get_call_detail(auth.tenant_id, call_id)
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    return call


@v1.get("/calls/{call_id}/live")
async def live_call(call_id: UUID, request: Request, auth: Auth, repo: Repo, bus: Bus) -> StreamingResponse:
    if not await repo.get_call(auth.tenant_id, call_id):
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})

    async def stream() -> Any:
        yield encode_sse({"type": "connected", "call_id": call_id})
        async for event in bus.subscribe(auth.tenant_id, call_id):
            if await request.is_disconnected():
                break
            yield encode_sse(event)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@v1.post("/calls/{call_id}/hangup")
async def hangup_call(call_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    call = await repo.update_call(auth.tenant_id, call_id, {"status": "completed", "end_reason": "agent_hangup", "ended_at": datetime.now(UTC)})
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    return call


@v1.post("/tools", status_code=201)
async def create_tool(body: ToolCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    return await repo.create_tool(auth.tenant_id, body.model_dump(by_alias=True))


@v1.get("/tools")
async def list_tools(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_tools(auth.tenant_id), "next_cursor": None}


@v1.get("/tools/{tool_id}")
async def get_tool(tool_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    tool = await repo.get_tool(auth.tenant_id, tool_id)
    if not tool:
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})
    return tool


@v1.patch("/tools/{tool_id}")
async def update_tool(tool_id: UUID, body: ToolPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    tool = await repo.update_tool(auth.tenant_id, tool_id, body.model_dump(exclude_unset=True, by_alias=True))
    if not tool:
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})
    return tool


@v1.delete("/tools/{tool_id}", status_code=204)
async def delete_tool(tool_id: UUID, auth: Auth, repo: Repo) -> None:
    if not await repo.delete_tool(auth.tenant_id, tool_id):
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})


@v1.post("/tools/{tool_id}/test")
async def test_tool(tool_id: UUID, body: ToolTestRequest, auth: Auth, repo: Repo, executor: Executor, cipher: Cipher) -> dict[str, Any]:
    tool = await repo.get_tool(auth.tenant_id, tool_id)
    if not tool:
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})
    secret = await _resolve_tool_secret(repo, cipher, auth.tenant_id, tool)
    result = await executor.execute(tool, body.arguments, {"tenant_id": auth.tenant_id, "session_variables": body.session_variables, "end_user": body.end_user, "call": {}, "secret": secret})
    if "error" not in result and result.get("status", 500) < 300:
        await repo.update_tool(auth.tenant_id, tool_id, {"last_test_ok_at": datetime.now(UTC)})
    return result


@v1.get("/secrets")
async def list_secrets(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_secrets(auth.tenant_id), "next_cursor": None}


@v1.post("/secrets", status_code=201)
async def create_secret(body: SecretCreate, auth: Auth, repo: Repo, cipher: Cipher) -> dict[str, Any]:
    ciphertext, key_id = await cipher.encrypt(body.value)
    return await repo.create_secret(auth.tenant_id, body.name, ciphertext, key_id)


@v1.delete("/secrets/{secret_id}", status_code=204)
async def delete_secret(secret_id: UUID, auth: Auth, repo: Repo) -> None:
    if not await repo.delete_secret(auth.tenant_id, secret_id):
        raise HTTPException(404, detail={"code": "secret_not_found", "message": "Secret not found"})


@v1.get("/integrations/google/connect")
async def google_connect(auth: Auth, native: Native) -> dict[str, str]:
    try:
        return {"url": native.google_connect_url(auth.tenant_id, auth.user_id)}
    except RuntimeError as exc:
        raise HTTPException(503, detail={"code": "integration_unavailable", "message": str(exc)}) from exc


@v1.get("/integrations/google/callback")
async def google_callback(code: str, state: str, repo: Repo, cipher: Cipher, native: Native) -> dict[str, Any]:
    try:
        integration = await native.google_callback(code, state, repo, cipher)
    except (ValueError, jwt.PyJWTError, httpx.HTTPError) as exc:
        raise HTTPException(400, detail={"code": "oauth_failed", "message": str(exc)}) from exc
    return {key: value for key, value in integration.items() if key != "refresh_token_secret_id"}


@v1.get("/integrations")
async def list_integrations(auth: Auth, repo: Repo) -> dict[str, Any]:
    google = await repo.get_integration(auth.tenant_id, "google")
    sanitized = {key: value for key, value in google.items() if key != "refresh_token_secret_id"} if google else None
    return {"data": [sanitized] if sanitized else []}


@v1.put("/agents/{agent_id}/draft/tools")
async def set_draft_tools(agent_id: UUID, body: AgentToolsSet, auth: Auth, repo: Repo) -> dict[str, Any]:
    try:
        tools = await repo.set_draft_tools(auth.tenant_id, agent_id, body.tool_ids)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_tools", "message": str(exc)}) from exc
    if tools is None:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return {"data": tools}


@v1.get("/knowledge-bases")
async def list_knowledge_bases(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_knowledge_bases(auth.tenant_id), "next_cursor": None}


@v1.post("/knowledge-bases", status_code=201)
async def create_knowledge_base(body: KnowledgeBaseCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    return await repo.create_knowledge_base(auth.tenant_id, body.model_dump())


@v1.get("/knowledge-bases/{kb_id}")
async def get_knowledge_base(kb_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    item = await repo.get_knowledge_base(auth.tenant_id, kb_id)
    if not item:
        raise HTTPException(404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"})
    return item


@v1.patch("/knowledge-bases/{kb_id}")
async def update_knowledge_base(kb_id: UUID, body: KnowledgeBasePatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    item = await repo.update_knowledge_base(auth.tenant_id, kb_id, body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"})
    return item


@v1.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_knowledge_base(kb_id: UUID, auth: Auth, repo: Repo) -> None:
    if not await repo.delete_knowledge_base(auth.tenant_id, kb_id):
        raise HTTPException(404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"})


@v1.get("/knowledge-bases/{kb_id}/documents")
async def list_documents(kb_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    if not await repo.get_knowledge_base(auth.tenant_id, kb_id):
        raise HTTPException(404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"})
    return {"data": await repo.list_documents(auth.tenant_id, kb_id), "next_cursor": None}


@v1.post("/knowledge-bases/{kb_id}/documents", status_code=202)
async def create_document(kb_id: UUID, request: Request, background: BackgroundTasks, auth: Auth, repo: Repo, embeddings: Embedder) -> dict[str, Any]:
    upload_bytes: bytes | None = None
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        uploaded = form.get("file")
        if not hasattr(uploaded, "read"):
            raise HTTPException(422, detail={"code": "file_required", "message": "Multipart field 'file' is required"})
        upload_bytes = await uploaded.read()  # type: ignore[union-attr]
        body = DocumentCreate(name=getattr(uploaded, "filename", None) or "documento", text="uploaded")
        source_type, mime = "upload", getattr(uploaded, "content_type", None)
    else:
        try:
            body = DocumentCreate.model_validate(await request.json())
        except PydanticValidationError as exc:
            raise HTTPException(422, detail={"code": "invalid_document", "message": "Document requires text or URL"}) from exc
        source_type, mime = ("url" if body.url else "text"), None
    item = await repo.create_document(auth.tenant_id, kb_id, {"name": body.name, "source_type": source_type, "source_uri": body.url, "mime": mime, "size_bytes": len(upload_bytes) if upload_bytes is not None else None})
    if not item:
        raise HTTPException(404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"})
    kb = await repo.get_knowledge_base(auth.tenant_id, kb_id)
    assert kb is not None
    background.add_task(_ingest_document, repo, embeddings, auth.tenant_id, item, kb, None if source_type == "upload" else body.text, upload_bytes)
    return item


@v1.delete("/knowledge-bases/{kb_id}/documents/{document_id}", status_code=204)
async def delete_document(kb_id: UUID, document_id: UUID, auth: Auth, repo: Repo) -> None:
    if not await repo.delete_document(auth.tenant_id, kb_id, document_id):
        raise HTTPException(404, detail={"code": "document_not_found", "message": "Document not found"})


@v1.post("/knowledge-bases/{kb_id}/query")
async def query_knowledge_base(kb_id: UUID, body: KnowledgeQuery, auth: Auth, repo: Repo, embeddings: Embedder) -> dict[str, Any]:
    kb = await repo.get_knowledge_base(auth.tenant_id, kb_id)
    if not kb:
        raise HTTPException(404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"})
    vector = (await embeddings.create([body.query], kb["embedding_model"]))[0]
    return {"data": await repo.query_chunks(auth.tenant_id, kb_id, vector, body.top_k, body.min_score)}


@internal.get("/agents/{agent_id}/runtime")
async def runtime(agent_id: UUID, repo: Repo, version: str = "current") -> dict[str, Any]:
    agent = await repo.get_runtime(agent_id, version)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return {"tenant_id": agent["tenant_id"], "tenant_settings": agent.get("tenant_settings") or {}, "agent_id": agent_id, "version_id": agent["version_id"], "system_prompt": agent["system_prompt"], "greeting": agent["greeting"], "language": agent["language"], "llm": agent["llm"], "stt": agent["stt"], "tts": agent["tts"], "turn": agent["turn_config"], "behavior": agent["behavior"], "knowledge_base_id": agent["knowledge_base_id"], "rag": agent["rag"], "variables": agent["variables"], "tools": agent["tools"]}


@internal.post("/calls", status_code=201)
async def create_internal_call(body: InternalCallCreate, repo: Repo) -> dict[str, Any]:
    return await repo.create_internal_call(body.model_dump())


@internal.patch("/calls/{call_id}")
async def update_internal_call(call_id: UUID, body: CallPatch, repo: Repo) -> dict[str, Any]:
    call = await repo.update_internal_call(call_id, body.model_dump(exclude_unset=True))
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    return call


async def _postprocess_call(call_id: UUID, call: dict[str, Any], repo: Repository, processor: Postprocessor) -> None:
    try:
        result = await processor.process(call)
        await repo.update_internal_call(call_id, result)
        await repo.append_call_events(call_id, [{"type": "call.postprocessed", "payload": {"model": get_settings().anthropic_postprocess_model}, "at": datetime.now(UTC)}])
    except Exception as exc:
        await repo.append_call_events(call_id, [{"type": "call.postprocess_failed", "payload": {"error": type(exc).__name__}, "at": datetime.now(UTC)}])


@internal.post("/calls/{call_id}/postprocess", status_code=202)
async def postprocess_call(call_id: UUID, background: BackgroundTasks, repo: Repo, processor: Processor) -> dict[str, bool]:
    tenant_id = await repo.get_call_tenant(call_id)
    call = await repo.get_call_detail(tenant_id, call_id) if tenant_id else None
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    background.add_task(_postprocess_call, call_id, call, repo, processor)
    return {"queued": True}


@internal.post("/calls/{call_id}/events")
async def append_call_events(call_id: UUID, body: CallEventBatch, repo: Repo, bus: Bus) -> dict[str, int]:
    events = [event.model_dump() for event in body.events]
    count = await repo.append_call_events(call_id, events)
    if not count:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    tenant_id = await repo.get_call_tenant(call_id)
    if tenant_id:
        for event in events:
            await bus.publish(tenant_id, call_id, event)
    return {"accepted": count}


@internal.post("/calls/{call_id}/turns")
async def append_call_turns(call_id: UUID, body: CallTurnBatch, repo: Repo, bus: Bus) -> dict[str, int]:
    turns = [turn.model_dump() for turn in body.turns]
    count = await repo.append_call_turns(call_id, turns)
    if not count:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    tenant_id = await repo.get_call_tenant(call_id)
    if tenant_id:
        for turn in turns:
            await bus.publish(tenant_id, call_id, {"type": f"turn.{turn['role']}", "turn": turn})
    return {"accepted": count}


@internal.post("/calls/{call_id}/tool-calls", status_code=201)
async def append_call_tool_call(call_id: UUID, body: CallToolCallCreate, repo: Repo, bus: Bus) -> dict[str, Any]:
    item = await repo.append_call_tool_call(call_id, body.model_dump())
    if not item:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    tenant_id = await repo.get_call_tenant(call_id)
    if tenant_id:
        await bus.publish(tenant_id, call_id, {"type": "tool.called", "tool_call": item})
    return item


@internal.post("/tools/execute")
async def execute_tool(body: InternalToolExecute, repo: Repo, executor: Executor, cipher: Cipher, native: Native) -> dict[str, Any]:
    tenant_id = await repo.get_call_tenant(body.call_id)
    if not tenant_id:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    tool = await repo.get_tool(tenant_id, body.tool_id)
    call = await repo.get_call(tenant_id, body.call_id)
    if not tool or not call:
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})
    try:
        validate(body.arguments, tool["parameters_schema"])
    except ValidationError as exc:
        raw_result: Any = {"error": "invalid_arguments", "details": exc.message}
        result: dict[str, Any] = raw_result
    else:
        if tool["type"] == "native":
            try:
                raw_result = await native.execute(tool.get("native_kind") or tool["name"], body.arguments, tenant_id, repo, cipher)
            except (httpx.HTTPError, RuntimeError, KeyError, ValueError) as exc:
                raw_result = {"error": "integration_failed", "message": str(exc)}
            result = raw_result
        else:
            secret = await _resolve_tool_secret(repo, cipher, tenant_id, tool)
            result = await executor.execute(tool, body.arguments, {"tenant_id": tenant_id, "session_variables": body.session_variables, "end_user": body.end_user, "call": call, "secret": secret})
            raw_result = result.get("result", result)
    llm_result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {"value": raw_result}
    await repo.append_call_tool_call(body.call_id, {"id": None, "turn_id": None, "tool_id": body.tool_id, "name": tool["name"], "arguments": body.arguments, "result": llm_result, "status": "error" if "error" in llm_result else "ok", "duration_ms": result.get("latency_ms"), "started_at": datetime.now(UTC)})
    return llm_result


@internal.post("/rag/query")
async def internal_rag_query(body: InternalRagQuery, repo: Repo, embeddings: Embedder) -> dict[str, Any]:
    tenant_id = await repo.get_knowledge_base_tenant(body.knowledge_base_id)
    if not tenant_id:
        raise HTTPException(404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"})
    kb = await repo.get_knowledge_base(tenant_id, body.knowledge_base_id)
    assert kb is not None
    vector = (await embeddings.create([body.query], kb["embedding_model"]))[0]
    return {"data": await repo.query_chunks(tenant_id, body.knowledge_base_id, vector, body.top_k, body.min_score)}
