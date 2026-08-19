from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from .auth import Principal, internal_token, principal
from .config import get_settings
from .repository import Repository, get_repository
from .schemas import (
    AgentCreate,
    AgentDraftPatch,
    AgentPatch,
    AgentRollback,
    SessionCreate,
    ToolCreate,
)

v1 = APIRouter(prefix="/v1")
internal = APIRouter(prefix="/internal", dependencies=[Depends(internal_token)])
Auth = Annotated[Principal, Depends(principal)]
Repo = Annotated[Repository, Depends(get_repository)]


@v1.get("/me")
async def me(auth: Auth) -> dict[str, Any]:
    return {"id": auth.user_id, "tenant_id": auth.tenant_id, "role": auth.role}


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
async def create_session(body: SessionCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    agent = await repo.get_agent(auth.tenant_id, body.agent_id)
    if not agent or agent["status"] != "active":
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Active agent not found"})
    session_id = uuid4()
    call = await repo.create_call(auth.tenant_id, body.agent_id, body.variables, body.metadata)
    call_id = call["id"]
    return {"session_id": session_id, "call_id": call_id, "livekit_url": get_settings().livekit_url, "token": f"dev_{session_id}", "expires_at": datetime.now(UTC) + timedelta(hours=1)}


@v1.get("/calls")
async def calls(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_calls(auth.tenant_id), "next_cursor": None}


@v1.post("/tools", status_code=201)
async def create_tool(body: ToolCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    return await repo.create_tool(auth.tenant_id, body.model_dump(by_alias=True))


@internal.get("/agents/{agent_id}/runtime")
async def runtime(agent_id: UUID, repo: Repo) -> dict[str, Any]:
    agent = await repo.get_runtime(agent_id)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return {"tenant_id": agent["tenant_id"], "agent_id": agent_id, "version_id": agent["version_id"], "system_prompt": agent["system_prompt"], "greeting": agent["greeting"], "language": agent["language"], "llm": agent["llm"], "stt": agent["stt"], "tts": agent["tts"], "turn": agent["turn_config"], "behavior": agent["behavior"], "rag": agent["rag"], "tools": []}
