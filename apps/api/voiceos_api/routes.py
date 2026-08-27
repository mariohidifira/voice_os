import csv
import hashlib
import io
import json
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

import httpx
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from jsonschema import ValidationError, validate
from livekit import api as livekit_api
from pydantic import ValidationError as PydanticValidationError

from .agent_templates import get_agent_template, list_agent_templates
from .auth import Principal, internal_token, principal
from .billing import StripeGateway, get_stripe_gateway, stripe_event, stripe_signature_valid
from .campaigns import dialing_allowed, transition_status
from .config import get_settings
from .idempotency import IdempotencyStore, get_idempotency_store
from .knowledge import Embeddings, chunk_text, extract_bytes, extract_url, get_embeddings
from .live import EventBus, encode_sse, get_event_bus
from .livekit_sessions import LiveKitSessions, get_livekit_sessions
from .native_integrations import NativeIntegrations, get_native_integrations
from .outgoing_webhooks import OutgoingWebhookSender, delivery_result
from .postprocessing import Postprocessor, get_postprocessor
from .prompt_improvement import PromptImprover, get_prompt_improver
from .repository import LastOwnerError, Repository, get_repository
from .schemas import (
    AdminTenantPatch,
    AgentCreate,
    AgentDraftPatch,
    AgentPatch,
    AgentRollback,
    AgentToolsSet,
    ApiKeyCreate,
    BillingCheckoutRequest,
    CallEventBatch,
    CallPatch,
    CallQaPatch,
    CallTakeoverRequest,
    CallToolCallCreate,
    CallTurnBatch,
    CampaignContactCreate,
    CampaignContactsCreate,
    CampaignCreate,
    CampaignPatch,
    DocumentCreate,
    DoNotCallCreate,
    EndUserPatch,
    ExportCreate,
    InternalCallCreate,
    InternalRagQuery,
    InternalToolExecute,
    KnowledgeBaseCreate,
    KnowledgeBasePatch,
    KnowledgeQuery,
    MemberCreate,
    MemberPatch,
    OutboundCallCreate,
    PhoneNumberPatch,
    PhoneNumberPurchase,
    PromptImproveRequest,
    SecretCreate,
    SessionCreate,
    SimulationCreate,
    TenantPatch,
    ToolCreate,
    ToolPatch,
    ToolTestRequest,
    VoicePreviewRequest,
    WebhookCreate,
    WebhookPatch,
    WhatsAppConnect,
    WhatsAppHandoffMessage,
)
from .secrets import SecretCipher, get_secret_cipher
from .simulator import run_simulation, simulation_yaml
from .storage import (
    ExportStorage,
    RecordingStorage,
    RetentionStorage,
    get_export_storage,
    get_recording_storage,
    get_retention_storage,
)
from .telephony import Telephony, TelephonyProviderError, get_telephony
from .tool_execution import ToolExecutor, get_tool_executor
from .voice_preview import VoicePreview, get_voice_preview
from .whatsapp import WhatsAppGateway, incoming_messages, valid_meta_signature
from .whatsapp_runtime import (
    fallback_reply,
    generate_whatsapp_reply,
    synthesize_whatsapp_audio,
    transcribe_whatsapp_audio,
)

v1 = APIRouter(prefix="/v1")
admin = APIRouter(prefix="/admin")
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
Improver = Annotated[PromptImprover, Depends(get_prompt_improver)]
Rtc = Annotated[LiveKitSessions, Depends(get_livekit_sessions)]
Storage = Annotated[RecordingStorage, Depends(get_recording_storage)]
ExportStore = Annotated[ExportStorage, Depends(get_export_storage)]
RetentionStore = Annotated[RetentionStorage, Depends(get_retention_storage)]
Voice = Annotated[VoicePreview, Depends(get_voice_preview)]
Phone = Annotated[Telephony, Depends(get_telephony)]
Idempotency = Annotated[IdempotencyStore, Depends(get_idempotency_store)]
Stripe = Annotated[StripeGateway, Depends(get_stripe_gateway)]


def _require_admin(auth: Principal) -> None:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})


def _require_platform_admin(auth: Principal) -> None:
    if not auth.is_platform_admin:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Platform admin required"})


def _sanitize_integration(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    return {key: value for key, value in item.items() if key != "refresh_token_secret_id"}


def _whatsapp_handoff_requested(text: str) -> bool:
    lowered = text.casefold()
    return any(
        phrase in lowered
        for phrase in ("humano", "atendente", "pessoa", "suporte humano", "falar com alguem")
    )


def _build_whatsapp_reply(
    runtime: dict[str, Any] | None, user_text: str, inbound_type: str
) -> tuple[str, bool]:
    greeting = str((runtime or {}).get("greeting") or "Olá! Como posso ajudar?")
    cleaned = user_text.strip()
    if _whatsapp_handoff_requested(cleaned):
        return ("Vou encaminhar sua conversa para um atendente humano agora.", True)
    if not cleaned:
        if inbound_type == "audio":
            return (
                "Recebi sua mensagem de voz. Pode me dizer em texto ou áudio o que você precisa?",
                False,
            )
        return (greeting, False)
    if inbound_type == "audio":
        return (f"Recebi sua mensagem de voz. {cleaned}", False)
    return (f"Recebi sua mensagem: {cleaned}", False)


def _whatsapp_reply_mode(runtime: dict[str, Any] | None) -> str:
    behavior = dict((runtime or {}).get("behavior") or {})
    mode = str(behavior.get("whatsapp_reply_mode") or "text").lower()
    return mode if mode in {"text", "audio", "both"} else "text"


def _origin_allowed(origin: str | None, allowed_origins: list[str]) -> bool:
    if not origin:
        return False
    return origin in allowed_origins


async def _require_public_widget_api_key(
    repo: Repository,
    tenant_id: UUID,
    x_api_key: str | None,
    origin: str | None,
) -> dict[str, Any]:
    if not x_api_key or not x_api_key.startswith("vos_pk_"):
        raise HTTPException(
            401,
            detail={"code": "invalid_api_key", "message": "Valid public API key required"},
        )
    api_key = await repo.get_api_key_by_hash(
        tenant_id,
        x_api_key[:14],
        hashlib.sha256(x_api_key.encode()).hexdigest(),
    )
    if not api_key or api_key["scope"] != "public":
        raise HTTPException(
            401,
            detail={"code": "invalid_api_key", "message": "Valid public API key required"},
        )
    if not _origin_allowed(origin, list(api_key.get("allowed_origins") or [])):
        raise HTTPException(
            403,
            detail={"code": "origin_not_allowed", "message": "Origin is not allowed for this key"},
        )
    return api_key


@admin.get("/tenants")
async def admin_tenants(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_platform_admin(auth)
    return {"data": await repo.admin_list_tenants(), "next_cursor": None}


@admin.patch("/tenants/{tenant_id}")
async def admin_update_tenant(tenant_id: UUID, body: AdminTenantPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_platform_admin(auth)
    item = await repo.admin_update_tenant(tenant_id, body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    return item


@admin.post("/tenants/{tenant_id}/impersonate")
async def admin_impersonate(tenant_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_platform_admin(auth)
    if not any(item["id"] == tenant_id for item in await repo.admin_list_tenants()):
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode({"sub": auth.user_id, "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "iat": now, "exp": now + timedelta(minutes=15), "tenants": [{"id": str(tenant_id), "role": "owner"}], "impersonated_by": auth.user_id}, settings.auth_secret, algorithm="HS256")
    return {"access_token": token, "token_type": "Bearer", "expires_in": 900, "tenant_id": tenant_id}


@admin.get("/metrics")
async def admin_metrics(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_platform_admin(auth)
    return await repo.admin_metrics()


def _stripe_datetime(value: Any) -> datetime | None:
    return datetime.fromtimestamp(int(str(value)), UTC) if value else None


async def _enforce_call_limit(auth: Principal, repo: Repository, channel: str) -> None:
    plan = await repo.get_billing_plan(auth.tenant_id)
    if not plan:
        return
    if plan.get("tenant_status") == "suspended":
        raise HTTPException(
            402,
            detail={
                "code": "plan_limit",
                "message": "Tenant is suspended",
                "details": {"reason": "suspended"},
            },
        )
    features = dict(plan.get("features") or {})
    if channel.startswith("phone") and not (features.get("phone") or features.get("all")):
        raise HTTPException(
            402,
            detail={
                "code": "plan_limit",
                "message": "Phone channel is not included",
                "details": {"feature": "phone", "plan": plan["code"]},
            },
        )
    period = datetime.now(UTC).date().replace(day=1)
    usage = await repo.get_billing_usage(auth.tenant_id, period)
    if plan["code"] == "trial":
        created_at = plan.get("tenant_created_at")
        expired = bool(created_at and datetime.now(UTC) >= created_at + timedelta(days=14))
        if expired or int(usage["minutes"]) >= int(plan["included_minutes"]):
            raise HTTPException(
                402,
                detail={
                    "code": "plan_limit",
                    "message": "Trial is exhausted",
                    "details": {"reason": "trial_exhausted", "usage": usage},
                },
            )
    active = sum(
        call.get("status") in {"queued", "ringing", "in_progress"}
        for call in await repo.list_calls(auth.tenant_id)
    )
    maximum = plan.get("max_concurrent_calls")
    if maximum is not None and active >= int(maximum):
        raise HTTPException(
            402,
            detail={
                "code": "plan_limit",
                "message": "Concurrent call limit reached",
                "details": {"limit": maximum, "active": active},
            },
        )


async def _enforce_agent_limit(auth: Principal, repo: Repository) -> None:
    plan = await repo.get_billing_plan(auth.tenant_id)
    maximum = (plan or {}).get("max_agents")
    if maximum is not None and len(await repo.list_agents(auth.tenant_id)) >= int(maximum):
        raise HTTPException(
            402,
            detail={
                "code": "plan_limit",
                "message": "Agent limit reached",
                "details": {"limit": maximum},
            },
        )


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
    status = (
        "ready"
        if event.event == "egress_ended" and not info.error
        else "failed"
        if info.error
        else "processing"
    )
    return call_id, {
        "s3_key": candidate,
        "format": candidate.rsplit(".", 1)[-1] if "." in candidate else "ogg",
        "duration_s": round(file_info.duration / 1_000_000_000)
        if file_info and file_info.duration
        else None,
        "size_bytes": file_info.size if file_info else None,
        "status": status,
        "metadata": {
            "egress_id": info.egress_id,
            "location": file_info.location if file_info else None,
            "error": info.error or None,
        },
    }


@webhooks.post("/stripe")
async def stripe_webhook(
    request: Request,
    repo: Repo,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, bool]:
    payload = await request.body()
    settings = get_settings()
    if settings.stripe_webhook_secret and (
        not stripe_signature
        or not stripe_signature_valid(payload, stripe_signature, settings.stripe_webhook_secret)
    ):
        raise HTTPException(
            400, detail={"code": "invalid_signature", "message": "Invalid Stripe signature"}
        )
    event = stripe_event(payload)
    event_type = str(event.get("type", ""))
    obj = dict((event.get("data") or {}).get("object") or {})
    metadata = dict(obj.get("metadata") or {})
    if not metadata and obj.get("subscription_details"):
        metadata = dict((obj["subscription_details"] or {}).get("metadata") or {})
    tenant_raw = metadata.get("tenant_id") or obj.get("client_reference_id")
    if not tenant_raw:
        return {"received": True}
    try:
        tenant_id = UUID(str(tenant_raw))
    except ValueError as exc:
        raise HTTPException(
            422, detail={"code": "invalid_tenant", "message": "Invalid tenant metadata"}
        ) from exc
    plan_code = str(metadata.get("plan_code") or "starter")
    if event_type == "checkout.session.completed":
        await repo.update_billing_tenant(
            tenant_id, {"stripe_customer_id": obj.get("customer"), "status": "active"}
        )
        await repo.upsert_subscription(
            tenant_id,
            {
                "plan_code": plan_code,
                "stripe_subscription_id": obj.get("subscription"),
                "status": "active",
            },
        )
    elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
        status = "canceled" if event_type.endswith("deleted") else str(obj.get("status", "active"))
        target_plan = await repo.get_plan_by_code(plan_code)
        subscription_items = list((obj.get("items") or {}).get("data") or [])

        def item_for(price_id: Any) -> str | None:
            return next(
                (
                    str(item["id"])
                    for item in subscription_items
                    if str((item.get("price") or {}).get("id")) == str(price_id)
                ),
                None,
            )

        await repo.upsert_subscription(
            tenant_id,
            {
                "plan_code": plan_code,
                "stripe_subscription_id": obj.get("id"),
                "status": status,
                "current_period_start": _stripe_datetime(obj.get("current_period_start")),
                "current_period_end": _stripe_datetime(obj.get("current_period_end")),
                "cancel_at": _stripe_datetime(obj.get("cancel_at")),
                "stripe_overage_item_id": item_for(
                    (target_plan or {}).get("stripe_overage_price_id")
                ),
                "stripe_phone_item_id": item_for((target_plan or {}).get("stripe_phone_price_id")),
                "past_due_since": datetime.now(UTC) if status == "past_due" else None,
            },
        )
        tenant_status = (
            "active"
            if status == "active"
            else (
                "trial"
                if status == "trialing"
                else "past_due"
                if status == "past_due"
                else "suspended"
            )
        )
        await repo.update_billing_tenant(tenant_id, {"status": tenant_status})
    elif event_type in {"invoice.paid", "invoice.payment_failed"}:
        invoice_status = "paid" if event_type == "invoice.paid" else "past_due"
        await repo.upsert_invoice(
            tenant_id,
            {
                "stripe_invoice_id": obj.get("id"),
                "period_start": _stripe_datetime(obj.get("period_start")),
                "period_end": _stripe_datetime(obj.get("period_end")),
                "amount_cents": obj.get("amount_due", 0),
                "status": invoice_status,
                "pdf_url": obj.get("invoice_pdf"),
            },
        )
        await repo.update_billing_tenant(
            tenant_id, {"status": "active" if invoice_status == "paid" else "past_due"}
        )
    return {"received": True}


@webhooks.get("/whatsapp")
async def whatsapp_webhook_verify(
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> Response:
    settings = get_settings()
    if (
        hub_mode == "subscribe"
        and hub_challenge
        and hub_verify_token
        and hub_verify_token == settings.whatsapp_verify_token
    ):
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(
        403, detail={"code": "invalid_verify_token", "message": "Invalid WhatsApp verify token"}
    )


@webhooks.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    repo: Repo,
    meta_signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> dict[str, Any]:
    payload = await request.body()
    settings = get_settings()
    if settings.whatsapp_app_secret and (
        not meta_signature
        or not valid_meta_signature(payload, meta_signature, settings.whatsapp_app_secret)
    ):
        raise HTTPException(
            401, detail={"code": "invalid_signature", "message": "Invalid WhatsApp signature"}
        )
    body = json.loads(payload or b"{}")
    accepted = 0
    for item in incoming_messages(body):
        accepted += int(await repo.ingest_whatsapp_message(item))
    return {"received": True, "accepted": accepted}


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
        raise HTTPException(
            401,
            detail={"code": "invalid_livekit_signature", "message": "Invalid LiveKit signature"},
        ) from exc
    if event.event in {"egress_started", "egress_updated", "egress_ended"} and (
        recording := _egress_recording(event)
    ):
        await repo.upsert_call_recording(*recording)
    return {"ok": True}


async def _resolve_tool_secret(
    repo: Repository, cipher: SecretCipher, tenant_id: UUID, tool: dict[str, Any]
) -> str | None:
    auth = (tool.get("webhook") or {}).get("auth") or {}
    secret_id = auth.get("secret_id")
    if not secret_id:
        return None
    try:
        secret = await repo.get_secret(tenant_id, UUID(str(secret_id)))
    except ValueError:
        return None
    return await cipher.decrypt(secret["ciphertext"], secret["kms_key_id"]) if secret else None


async def _execute_runtime_tool(
    repo: Repository,
    executor: ToolExecutor,
    cipher: SecretCipher,
    native: NativeIntegrations,
    tenant_id: UUID,
    call: dict[str, Any],
    tool: dict[str, Any],
    arguments: dict[str, Any],
    *,
    session_variables: dict[str, Any] | None = None,
    end_user: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        validate(arguments, tool["parameters_schema"])
    except ValidationError as exc:
        raw_result = {"error": "invalid_arguments", "details": exc.message}
        return raw_result, raw_result
    if tool["type"] == "native":
        try:
            raw = await native.execute(
                tool.get("native_kind") or tool["name"],
                arguments,
                tenant_id,
                repo,
                cipher,
                call,
            )
        except (httpx.HTTPError, RuntimeError, KeyError, ValueError) as exc:
            raw = {"error": "integration_failed", "message": str(exc)}
        return (raw if isinstance(raw, dict) else {"value": raw}), (
            raw if isinstance(raw, dict) else {"value": raw}
        )
    secret = await _resolve_tool_secret(repo, cipher, tenant_id, tool)
    result = await executor.execute(
        tool,
        arguments,
        {
            "tenant_id": tenant_id,
            "session_variables": session_variables or {},
            "end_user": end_user or {},
            "call": call,
            "secret": secret,
        },
    )
    raw_result = result.get("result", result)
    llm_result = raw_result if isinstance(raw_result, dict) else {"value": raw_result}
    return llm_result, result


async def _ingest_document(
    repo: Repository,
    embeddings: Embeddings,
    tenant_id: UUID,
    document: dict[str, Any],
    kb: dict[str, Any],
    content: str | None,
    upload: bytes | None = None,
) -> None:
    try:
        extracted = (
            await extract_url(document["source_uri"])
            if document["source_type"] == "url"
            else extract_bytes(upload, document.get("mime"), document["name"])
            if upload is not None
            else content or ""
        )
        texts = chunk_text(extracted, kb["chunk_size"], kb["chunk_overlap"])
        if not texts:
            raise ValueError("document has no extractable text")
        vectors = await embeddings.create(texts, kb["embedding_model"])
        await repo.complete_document(
            tenant_id,
            document["id"],
            [
                {
                    "content": text,
                    "embedding": vector,
                    "metadata": {"url": document.get("source_uri")},
                    "token_count": max(1, len(text) // 4),
                }
                for text, vector in zip(texts, vectors, strict=True)
            ],
        )
    except Exception as exc:
        await repo.fail_document(tenant_id, document["id"], str(exc))


@v1.get("/me")
async def me(auth: Auth) -> dict[str, Any]:
    return {"id": auth.user_id, "tenant_id": auth.tenant_id, "role": auth.role}


@v1.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    if tenant_id != auth.tenant_id or not (tenant := await repo.get_tenant(auth.tenant_id)):
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    return tenant


@v1.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: UUID, body: TenantPatch, auth: Auth, repo: Repo
) -> dict[str, Any]:
    _require_admin(auth)
    if tenant_id != auth.tenant_id:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    data = body.model_dump(exclude_unset=True)
    if body.settings is not None:
        data["settings"] = body.settings.model_dump(exclude_unset=True)
    tenant = await repo.update_tenant(auth.tenant_id, data)
    if not tenant:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    return tenant


@v1.get("/tenants/{tenant_id}/members")
async def list_members(tenant_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    if tenant_id != auth.tenant_id:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    return {"data": await repo.list_members(auth.tenant_id), "next_cursor": None}


@v1.post("/tenants/{tenant_id}/members", status_code=201)
async def create_member(
    tenant_id: UUID, body: MemberCreate, auth: Auth, repo: Repo
) -> dict[str, Any]:
    _require_admin(auth)
    if tenant_id != auth.tenant_id:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Tenant not found"})
    return await repo.create_member(auth.tenant_id, body.email, body.role)


@v1.patch("/tenants/{tenant_id}/members/{user_id}")
async def update_member(
    tenant_id: UUID, user_id: UUID, body: MemberPatch, auth: Auth, repo: Repo
) -> dict[str, Any]:
    _require_admin(auth)
    if tenant_id != auth.tenant_id:
        raise HTTPException(404, detail={"code": "member_not_found", "message": "Member not found"})
    try:
        member = await repo.update_member(auth.tenant_id, user_id, body.role)
    except LastOwnerError:
        raise HTTPException(
            409,
            detail={
                "code": "last_owner_required",
                "message": "Promote another owner before changing the last owner",
            },
        ) from None
    if not member:
        raise HTTPException(404, detail={"code": "member_not_found", "message": "Member not found"})
    return member


@v1.delete("/tenants/{tenant_id}/members/{user_id}", status_code=204)
async def delete_member(tenant_id: UUID, user_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if tenant_id != auth.tenant_id:
        raise HTTPException(404, detail={"code": "member_not_found", "message": "Member not found"})
    try:
        deleted = await repo.delete_member(auth.tenant_id, user_id)
    except LastOwnerError:
        raise HTTPException(
            409,
            detail={
                "code": "last_owner_required",
                "message": "Promote another owner before removing the last owner",
            },
        ) from None
    if not deleted:
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
    item = await repo.create_api_key(
        auth.tenant_id,
        {
            "name": body.name,
            "prefix": prefix,
            "hash": hashlib.sha256(raw.encode()).hexdigest(),
            "scope": body.scope,
            "allowed_origins": body.allowed_origins,
        },
    )
    return {**item, "key": raw}


@v1.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(key_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if not await repo.revoke_api_key(auth.tenant_id, key_id):
        raise HTTPException(
            404, detail={"code": "api_key_not_found", "message": "API key not found"}
        )


@v1.get("/end-users")
async def list_end_users(auth: Auth, repo: Repo, q: str | None = None) -> dict[str, Any]:
    return {"data": await repo.list_end_users(auth.tenant_id, q), "next_cursor": None}


@v1.get("/analytics/overview")
async def analytics_overview(
    auth: Auth,
    repo: Repo,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    agent_id: UUID | None = None,
) -> dict[str, Any]:
    end = to or datetime.now(UTC).date()
    start = from_ or end - timedelta(days=29)
    if start > end or (end - start).days > 366:
        raise HTTPException(422, detail={"code": "invalid_period", "message": "Analytics period must be 0-366 days"})
    return await repo.analytics_overview(auth.tenant_id, start, end, agent_id)


@v1.get("/analytics/tools")
async def analytics_tools(
    auth: Auth,
    repo: Repo,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> dict[str, Any]:
    end = to or datetime.now(UTC).date()
    start = from_ or end - timedelta(days=29)
    if start > end or (end - start).days > 366:
        raise HTTPException(422, detail={"code": "invalid_period", "message": "Analytics period must be 0-366 days"})
    return {"data": await repo.analytics_tools(auth.tenant_id, start, end)}


@v1.get("/end-users/{end_user_id}")
async def get_end_user(end_user_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    item = await repo.get_end_user(auth.tenant_id, end_user_id)
    if not item:
        raise HTTPException(404, detail={"code": "end_user_not_found", "message": "End user not found"})
    return item


@v1.patch("/end-users/{end_user_id}")
async def update_end_user(end_user_id: UUID, body: EndUserPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    item = await repo.update_end_user(auth.tenant_id, end_user_id, body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(404, detail={"code": "end_user_not_found", "message": "End user not found"})
    return item


@v1.delete("/end-users/{end_user_id}", status_code=204)
async def delete_end_user(end_user_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if not await repo.anonymize_end_user(auth.tenant_id, end_user_id):
        raise HTTPException(404, detail={"code": "end_user_not_found", "message": "End user not found"})


@v1.get("/webhooks")
async def list_outgoing_webhooks(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    return {"data": await repo.list_webhooks(auth.tenant_id), "next_cursor": None}


@v1.post("/webhooks", status_code=201)
async def create_outgoing_webhook(body: WebhookCreate, auth: Auth, repo: Repo, cipher: Cipher) -> dict[str, Any]:
    _require_admin(auth)
    raw_secret = f"whsec_{secrets.token_urlsafe(32)}"
    ciphertext, key_id = await cipher.encrypt(raw_secret)
    secret = await repo.create_secret(auth.tenant_id, f"webhook-{secrets.token_hex(6)}", ciphertext, key_id)
    item = await repo.create_webhook(auth.tenant_id, {**body.model_dump(), "secret_id": secret["id"]})
    return {**item, "secret": raw_secret}


@v1.patch("/webhooks/{webhook_id}")
async def update_outgoing_webhook(webhook_id: UUID, body: WebhookPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    item = await repo.update_webhook(auth.tenant_id, webhook_id, body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(404, detail={"code": "webhook_not_found", "message": "Webhook not found"})
    return item


@v1.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_outgoing_webhook(webhook_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if not await repo.delete_webhook(auth.tenant_id, webhook_id):
        raise HTTPException(404, detail={"code": "webhook_not_found", "message": "Webhook not found"})


@v1.get("/webhooks/{webhook_id}/deliveries")
async def list_outgoing_webhook_deliveries(webhook_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    return {"data": await repo.list_webhook_deliveries(auth.tenant_id, webhook_id), "next_cursor": None}


@v1.post("/webhooks/{webhook_id}/deliveries/{delivery_id}/retry")
async def retry_outgoing_webhook(webhook_id: UUID, delivery_id: UUID, auth: Auth, repo: Repo) -> dict[str, bool]:
    _require_admin(auth)
    if not await repo.retry_webhook_delivery(auth.tenant_id, webhook_id, delivery_id):
        raise HTTPException(404, detail={"code": "delivery_not_found", "message": "Delivery not found"})
    return {"queued": True}


@v1.post("/exports", status_code=202)
async def create_export(body: ExportCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    return await repo.create_export(auth.tenant_id, body.model_dump())


@v1.get("/exports/{export_id}")
async def get_export(export_id: UUID, auth: Auth, repo: Repo, storage: ExportStore) -> dict[str, Any]:
    item = await repo.get_export(auth.tenant_id, export_id)
    if not item:
        raise HTTPException(404, detail={"code": "export_not_found", "message": "Export not found"})
    if item.get("status") == "ready" and item.get("s3_key"):
        item["download_url"] = await storage.download_url(str(item["s3_key"]))
    return item


@v1.get("/agents")
async def list_agents(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_agents(auth.tenant_id), "next_cursor": None}


@v1.get("/agent-templates")
async def agent_templates(auth: Auth) -> dict[str, Any]:
    return {"data": list_agent_templates(), "next_cursor": None}


@v1.post("/agents", status_code=201)
async def create_agent(body: AgentCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    await _enforce_agent_limit(auth, repo)
    template = get_agent_template(body.template_id) if body.template_id else None
    if body.template_id and not template:
        raise HTTPException(
            422, detail={"code": "template_not_found", "message": "Agent template not found"}
        )
    agent = await repo.create_agent(auth.tenant_id, body.name, auth.user_id)
    if template:
        draft = await repo.update_draft(
            auth.tenant_id,
            agent["id"],
            {
                "system_prompt": template["system_prompt"],
                "greeting": template["greeting"],
                "variables": template["variables"],
            },
        )
        if draft:
            agent = {**agent, "draft": draft}
    return agent


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
        raise HTTPException(
            404, detail={"code": "version_not_found", "message": "Version not found"}
        )
    return version


@v1.patch("/agents/{agent_id}/draft")
async def update_draft(
    agent_id: UUID, body: AgentDraftPatch, auth: Auth, repo: Repo
) -> dict[str, Any]:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    draft = await repo.update_draft(auth.tenant_id, agent_id, body.model_dump(exclude_unset=True))
    if not draft:
        raise HTTPException(404, detail={"code": "draft_not_found", "message": "Draft not found"})
    return draft


@v1.post("/agents/{agent_id}/draft/improve-prompt")
async def improve_agent_prompt(
    agent_id: UUID, body: PromptImproveRequest, auth: Auth, repo: Repo, improver: Improver
) -> dict[str, str]:
    _require_admin(auth)
    if not await repo.get_agent(auth.tenant_id, agent_id):
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    try:
        return {"improved_prompt": await improver.improve(body.prompt)}
    except RuntimeError as exc:
        raise HTTPException(
            503, detail={"code": "prompt_improvement_unavailable", "message": str(exc)}
        ) from exc


@v1.get("/voices")
async def list_voices(auth: Auth, voice: Voice) -> dict[str, Any]:
    _require_admin(auth)
    try:
        return {"data": await voice.list_voices(), "configured": voice.configured}
    except RuntimeError as exc:
        raise HTTPException(
            503, detail={"code": "voice_provider_unavailable", "message": str(exc)}
        ) from exc


@v1.post("/voices/{voice_id}/preview")
async def preview_voice(
    voice_id: str, body: VoicePreviewRequest, auth: Auth, voice: Voice
) -> Response:
    _require_admin(auth)
    try:
        audio = await voice.synthesize(voice_id, body.text, body.speed)
        return Response(
            audio,
            media_type="audio/mpeg",
            headers={"Cache-Control": "private, max-age=300"},
        )
    except RuntimeError as exc:
        raise HTTPException(
            503, detail={"code": "voice_preview_unavailable", "message": str(exc)}
        ) from exc


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
        if tool.get("native_kind") == "transfer_call" and not draft.get("behavior", {}).get(
            "transfer_number"
        ):
            errors.append("transfer_number is required when transfer_call is enabled")
    if draft.get("knowledge_base_id"):
        documents = await repo.list_documents(auth.tenant_id, draft["knowledge_base_id"])
        if not any(document["status"] == "ready" for document in documents):
            errors.append("selected knowledge base requires at least one ready document")
    if errors:
        raise HTTPException(
            422,
            detail={
                "code": "publish_validation_failed",
                "message": "Agent draft is not publishable",
                "details": {"errors": errors},
            },
        )
    agent = await repo.publish_agent(auth.tenant_id, agent_id)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return agent


@v1.post("/agents/{agent_id}/rollback")
async def rollback_agent(
    agent_id: UUID, body: AgentRollback, auth: Auth, repo: Repo
) -> dict[str, Any]:
    if auth.role not in {"owner", "admin"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin role required"})
    agent = await repo.rollback_agent(auth.tenant_id, agent_id, body.version_id)
    if not agent:
        raise HTTPException(
            404, detail={"code": "version_not_found", "message": "Published version not found"}
        )
    return agent


def _telephony_error(exc: TelephonyProviderError) -> HTTPException:
    return HTTPException(
        502,
        detail={"code": "telephony_provider_error", "message": str(exc)},
    )


@v1.get("/phone-numbers")
async def phone_numbers(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    return {"data": await repo.list_phone_numbers(auth.tenant_id)}


@v1.get("/phone-numbers/available")
async def available_phone_numbers(
    auth: Auth,
    phone: Phone,
    country: str = Query(default="BR", pattern=r"^[A-Z]{2}$"),
    area_code: str = Query(pattern=r"^\d{2,3}$"),
) -> dict[str, Any]:
    _require_admin(auth)
    try:
        return {"data": await phone.numbers.available(country, area_code)}
    except TelephonyProviderError as exc:
        raise _telephony_error(exc) from exc


@v1.post("/phone-numbers", status_code=201)
async def purchase_phone_number(
    body: PhoneNumberPurchase, auth: Auth, repo: Repo, phone: Phone
) -> dict[str, Any]:
    _require_admin(auth)
    if body.agent_id:
        agent = await repo.get_agent(auth.tenant_id, body.agent_id)
        if not agent:
            raise HTTPException(
                404, detail={"code": "agent_not_found", "message": "Agent not found"}
            )
        if agent["status"] != "active":
            raise HTTPException(
                409,
                detail={"code": "agent_not_active", "message": "Publish the agent first"},
            )
    existing = await repo.list_phone_numbers(auth.tenant_id)
    if any(item["e164"] == body.e164 and item["status"] == "active" for item in existing):
        raise HTTPException(
            409,
            detail={"code": "phone_number_exists", "message": "Phone number already exists"},
        )
    purchased = None
    rule_id = None
    try:
        purchased = await phone.numbers.purchase(body.e164)
        if body.agent_id:
            rule_id = await phone.dispatch.create(auth.tenant_id, body.agent_id, purchased.e164)
        return await repo.create_phone_number(
            auth.tenant_id,
            {
                "agent_id": body.agent_id,
                "e164": purchased.e164,
                "provider": "twilio",
                "provider_sid": purchased.provider_sid,
                "capabilities": purchased.capabilities,
                "livekit_dispatch_rule_id": rule_id,
            },
        )
    except Exception as exc:
        if rule_id:
            try:
                await phone.dispatch.delete(rule_id)
            except TelephonyProviderError:
                pass
        if purchased:
            try:
                await phone.numbers.release(purchased.provider_sid)
            except TelephonyProviderError:
                pass
        if isinstance(exc, TelephonyProviderError):
            raise _telephony_error(exc) from exc
        if isinstance(exc, ValueError):
            raise HTTPException(
                409,
                detail={
                    "code": "phone_number_exists",
                    "message": "Phone number already exists",
                },
            ) from exc
        raise


@v1.patch("/phone-numbers/{number_id}")
async def assign_phone_number(
    number_id: UUID,
    body: PhoneNumberPatch,
    auth: Auth,
    repo: Repo,
    phone: Phone,
) -> dict[str, Any]:
    _require_admin(auth)
    item = await repo.get_phone_number(auth.tenant_id, number_id)
    if not item or item["status"] != "active":
        raise HTTPException(
            404,
            detail={"code": "phone_number_not_found", "message": "Phone number not found"},
        )
    if body.agent_id:
        agent = await repo.get_agent(auth.tenant_id, body.agent_id)
        if not agent:
            raise HTTPException(
                404, detail={"code": "agent_not_found", "message": "Agent not found"}
            )
        if agent["status"] != "active":
            raise HTTPException(
                409,
                detail={"code": "agent_not_active", "message": "Publish the agent first"},
            )
    old_rule = item.get("livekit_dispatch_rule_id")
    new_rule = None
    try:
        if body.agent_id:
            new_rule = await phone.dispatch.create(auth.tenant_id, body.agent_id, str(item["e164"]))
        updated = await repo.update_phone_number(
            auth.tenant_id,
            number_id,
            {"agent_id": body.agent_id, "livekit_dispatch_rule_id": new_rule},
        )
        if old_rule:
            await phone.dispatch.delete(str(old_rule))
        assert updated is not None
        return updated
    except TelephonyProviderError as exc:
        if new_rule:
            try:
                await phone.dispatch.delete(new_rule)
            except TelephonyProviderError:
                pass
        raise _telephony_error(exc) from exc


@v1.delete("/phone-numbers/{number_id}", status_code=204)
async def release_phone_number(number_id: UUID, auth: Auth, repo: Repo, phone: Phone) -> Response:
    _require_admin(auth)
    item = await repo.get_phone_number(auth.tenant_id, number_id)
    if not item or item["status"] != "active":
        raise HTTPException(
            404,
            detail={"code": "phone_number_not_found", "message": "Phone number not found"},
        )
    try:
        if item.get("livekit_dispatch_rule_id"):
            await phone.dispatch.delete(str(item["livekit_dispatch_rule_id"]))
        await phone.numbers.release(str(item["provider_sid"]))
    except TelephonyProviderError as exc:
        raise _telephony_error(exc) from exc
    await repo.update_phone_number(
        auth.tenant_id,
        number_id,
        {"agent_id": None, "status": "released", "livekit_dispatch_rule_id": None},
    )
    return Response(status_code=204)


@v1.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, auth: Auth, repo: Repo, rtc: Rtc) -> dict[str, Any]:
    await _enforce_call_limit(auth, repo, "web")
    agent = await repo.get_agent(auth.tenant_id, body.agent_id)
    if not agent or agent["status"] != "active":
        raise HTTPException(
            404, detail={"code": "agent_not_found", "message": "Active agent not found"}
        )
    end_user = None
    if body.end_user:
        try:
            end_user = await repo.upsert_end_user(auth.tenant_id, body.end_user)
        except ValueError as exc:
            raise HTTPException(
                422, detail={"code": "invalid_end_user", "message": str(exc)}
            ) from exc
    call = await repo.create_call(
        auth.tenant_id,
        body.agent_id,
        body.variables,
        body.metadata,
        agent_version_id=agent["current_version_id"],
        end_user_id=end_user["id"] if end_user else None,
    )
    call_id = call["id"]
    session = await rtc.provision(
        call_id=call_id,
        agent_id=body.agent_id,
        version="current",
        variables=body.variables,
        end_user=body.end_user,
    )
    await repo.update_call(auth.tenant_id, call_id, {"livekit_room": session["room_name"]})
    return {
        "session_id": call_id,
        "call_id": call_id,
        "livekit_url": get_settings().livekit_url,
        "token": session["token"],
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }


@v1.post("/public/tenants/{tenant_id}/widget/sessions", status_code=201)
async def create_public_widget_session(
    tenant_id: UUID,
    body: SessionCreate,
    repo: Repo,
    rtc: Rtc,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    origin: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    api_key = await _require_public_widget_api_key(repo, tenant_id, x_api_key, origin)
    await _enforce_call_limit(Principal("widget-public", tenant_id, "viewer"), repo, "web")
    agent = await repo.get_agent(tenant_id, body.agent_id)
    if not agent or agent["status"] != "active":
        raise HTTPException(
            404, detail={"code": "agent_not_found", "message": "Active agent not found"}
        )
    end_user = None
    if body.end_user:
        try:
            end_user = await repo.upsert_end_user(tenant_id, body.end_user)
        except ValueError as exc:
            raise HTTPException(
                422, detail={"code": "invalid_end_user", "message": str(exc)}
            ) from exc
    metadata = {
        **body.metadata,
        "widget_session": True,
        "public_api_key_prefix": api_key["prefix"],
        "origin": origin,
    }
    call = await repo.create_call(
        tenant_id,
        body.agent_id,
        body.variables,
        metadata,
        agent_version_id=agent["current_version_id"],
        end_user_id=end_user["id"] if end_user else None,
    )
    call_id = call["id"]
    session = await rtc.provision(
        call_id=call_id,
        agent_id=body.agent_id,
        version="current",
        variables=body.variables,
        end_user=body.end_user,
    )
    await repo.update_call(tenant_id, call_id, {"livekit_room": session["room_name"]})
    return {
        "session_id": call_id,
        "call_id": call_id,
        "livekit_url": get_settings().livekit_url,
        "token": session["token"],
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }


@v1.delete("/public/tenants/{tenant_id}/widget/sessions/{session_id}", status_code=204)
async def delete_public_widget_session(
    tenant_id: UUID,
    session_id: UUID,
    repo: Repo,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    origin: Annotated[str | None, Header()] = None,
) -> None:
    await _require_public_widget_api_key(repo, tenant_id, x_api_key, origin)
    call = await repo.update_call(
        tenant_id,
        session_id,
        {"status": "cancelled", "end_reason": "user_hangup", "ended_at": datetime.now(UTC)},
    )
    if not call:
        raise HTTPException(
            404, detail={"code": "session_not_found", "message": "Session not found"}
        )


@v1.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: UUID, auth: Auth, repo: Repo) -> None:
    call = await repo.update_call(
        auth.tenant_id,
        session_id,
        {"status": "cancelled", "end_reason": "user_hangup", "ended_at": datetime.now(UTC)},
    )
    if not call:
        raise HTTPException(
            404, detail={"code": "session_not_found", "message": "Session not found"}
        )


@v1.post("/calls/outbound", status_code=202)
async def create_outbound_call(
    body: OutboundCallCreate,
    auth: Auth,
    repo: Repo,
    rtc: Rtc,
    phone: Phone,
    idempotency: Idempotency,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> dict[str, Any]:
    await _enforce_call_limit(auth, repo, "phone_outbound")
    agent = await repo.get_agent(auth.tenant_id, body.agent_id)
    if not agent or agent["status"] != "active":
        raise HTTPException(
            404, detail={"code": "agent_not_found", "message": "Active agent not found"}
        )
    assigned = next(
        (
            item
            for item in await repo.list_phone_numbers(auth.tenant_id)
            if item.get("agent_id") == body.agent_id
            and item.get("status") == "active"
            and bool((item.get("capabilities") or {}).get("voice"))
        ),
        None,
    )
    if not assigned:
        raise HTTPException(
            409,
            detail={
                "code": "outbound_number_required",
                "message": "Assign an active voice-capable number to the agent first",
            },
        )
    if phone.outbound is None:
        raise HTTPException(
            503,
            detail={"code": "sip_not_configured", "message": "Outbound SIP is not configured"},
        )
    operation = "calls:outbound"
    fingerprint = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if idempotency_key:
        cached = await idempotency.reserve(auth.tenant_id, operation, idempotency_key, fingerprint)
        if cached:
            if cached.get("_conflict"):
                raise HTTPException(
                    409,
                    detail={
                        "code": "idempotency_key_reused",
                        "message": "This Idempotency-Key was already used with another payload",
                    },
                )
            if cached.get("_pending"):
                raise HTTPException(
                    409,
                    detail={
                        "code": "idempotency_in_progress",
                        "message": "A request with this Idempotency-Key is still in progress",
                    },
                )
            if cached.get("_error"):
                raise HTTPException(int(cached["status_code"]), detail=cached["detail"])
            return cached
    call: dict[str, Any] | None = None
    try:
        end_user_data = {**(body.end_user or {}), "phone": body.to}
        end_user = await repo.upsert_end_user(auth.tenant_id, end_user_data)
        call = await repo.create_call(
            auth.tenant_id,
            body.agent_id,
            body.variables,
            body.metadata,
            agent_version_id=agent["current_version_id"],
            end_user_id=end_user["id"],
            channel="phone_outbound",
            from_number=str(assigned["e164"]),
            to_number=body.to,
        )
        session = await rtc.provision(
            call_id=call["id"],
            agent_id=body.agent_id,
            version="current",
            variables=body.variables,
            end_user=end_user_data,
            channel="phone_outbound",
            from_number=str(assigned["e164"]),
            to_number=body.to,
        )
        await repo.update_call(
            auth.tenant_id,
            call["id"],
            {
                "livekit_room": session["room_name"],
            },
        )
        response = {"call_id": str(call["id"])}
        if idempotency_key:
            await idempotency.complete(
                auth.tenant_id, operation, idempotency_key, fingerprint, response
            )
        return response
    except TelephonyProviderError as exc:
        if call:
            await repo.update_call(
                auth.tenant_id,
                call["id"],
                {"status": "failed", "end_reason": "error", "ended_at": datetime.now(UTC)},
            )
        detail = {"code": "telephony_provider_error", "message": str(exc)}
        if idempotency_key:
            await idempotency.complete(
                auth.tenant_id,
                operation,
                idempotency_key,
                fingerprint,
                {"_error": True, "status_code": 502, "detail": detail},
            )
        raise HTTPException(502, detail=detail) from exc
    except Exception:
        if call:
            await repo.update_call(
                auth.tenant_id,
                call["id"],
                {"status": "failed", "end_reason": "error", "ended_at": datetime.now(UTC)},
            )
        if idempotency_key:
            await idempotency.release(auth.tenant_id, operation, idempotency_key)
        raise


@v1.get("/campaigns")
async def list_campaigns(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_campaigns(auth.tenant_id)}


@v1.post("/campaigns", status_code=201)
async def create_campaign(
    body: CampaignCreate,
    auth: Auth,
    repo: Repo,
    idempotency: Idempotency,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> dict[str, Any]:
    agent = await repo.get_agent(auth.tenant_id, body.agent_id)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    if idempotency_key:
        cached = await idempotency.reserve(
            auth.tenant_id, "campaigns:create", idempotency_key, fingerprint
        )
        if cached:
            if cached.get("_conflict"):
                raise HTTPException(
                    409,
                    detail={
                        "code": "idempotency_key_reused",
                        "message": "This Idempotency-Key was already used with another payload",
                    },
                )
            if cached.get("_pending"):
                raise HTTPException(
                    409,
                    detail={
                        "code": "idempotency_in_progress",
                        "message": "A request with this Idempotency-Key is still in progress",
                    },
                )
            return cached
    campaign = await repo.create_campaign(auth.tenant_id, body.model_dump())
    response = {
        **campaign,
        "id": str(campaign["id"]),
        "agent_id": str(campaign["agent_id"]),
        "tenant_id": str(campaign["tenant_id"]),
    }
    if idempotency_key:
        await idempotency.complete(
            auth.tenant_id, "campaigns:create", idempotency_key, fingerprint, response
        )
    return response


@v1.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    campaign = await repo.get_campaign(auth.tenant_id, campaign_id)
    if not campaign:
        raise HTTPException(
            404, detail={"code": "campaign_not_found", "message": "Campaign not found"}
        )
    return campaign


@v1.patch("/campaigns/{campaign_id}")
async def patch_campaign(
    campaign_id: UUID, body: CampaignPatch, auth: Auth, repo: Repo
) -> dict[str, Any]:
    campaign = await repo.get_campaign(auth.tenant_id, campaign_id)
    if not campaign:
        raise HTTPException(
            404, detail={"code": "campaign_not_found", "message": "Campaign not found"}
        )
    if campaign["status"] not in {"draft", "paused"}:
        raise HTTPException(
            409,
            detail={
                "code": "campaign_not_editable",
                "message": "Only draft or paused campaigns can be edited",
            },
        )
    return (
        await repo.update_campaign(auth.tenant_id, campaign_id, body.model_dump(exclude_none=True))
    ) or campaign


@v1.post("/campaigns/{campaign_id}/contacts", status_code=201)
async def add_campaign_contacts(
    campaign_id: UUID, request: Request, auth: Auth, repo: Repo
) -> list[dict[str, Any]]:
    campaign = await repo.get_campaign(auth.tenant_id, campaign_id)
    if not campaign:
        raise HTTPException(
            404, detail={"code": "campaign_not_found", "message": "Campaign not found"}
        )
    try:
        if request.headers.get("content-type", "").startswith("multipart/form-data"):
            form = await request.form()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "read"):
                raise ValueError("multipart field 'file' is required")
            raw = await upload.read()
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            payload = CampaignContactsCreate(
                contacts=[
                    CampaignContactCreate(
                        phone=row.get("phone", ""),
                        name=row.get("name") or None,
                        variables={
                            key[4:]: value
                            for key, value in row.items()
                            if key.startswith("var.") and value
                        },
                    )
                    for row in rows
                ]
            )
        else:
            payload = CampaignContactsCreate.model_validate(await request.json())
    except (ValueError, UnicodeDecodeError, PydanticValidationError) as exc:
        raise HTTPException(422, detail={"code": "invalid_contacts", "message": str(exc)}) from exc
    blocked = {item["phone"] for item in await repo.list_do_not_call(auth.tenant_id)}
    contacts = [item.model_dump() for item in payload.contacts if item.phone not in blocked]
    if not contacts:
        raise HTTPException(
            422,
            detail={
                "code": "all_contacts_blocked",
                "message": "All contacts are on the do-not-call list",
            },
        )
    return await repo.add_campaign_contacts(auth.tenant_id, campaign_id, contacts)


@v1.get("/campaigns/{campaign_id}/contacts")
async def list_campaign_contacts(
    campaign_id: UUID, auth: Auth, repo: Repo, status: str | None = None
) -> list[dict[str, Any]]:
    if not await repo.get_campaign(auth.tenant_id, campaign_id):
        raise HTTPException(
            404, detail={"code": "campaign_not_found", "message": "Campaign not found"}
        )
    return await repo.list_campaign_contacts(auth.tenant_id, campaign_id, status)


@v1.post("/campaigns/{campaign_id}/{action}")
async def campaign_action(campaign_id: UUID, action: str, auth: Auth, repo: Repo) -> dict[str, Any]:
    if action not in {"start", "pause", "resume", "cancel"}:
        raise HTTPException(
            404, detail={"code": "action_not_found", "message": "Campaign action not found"}
        )
    campaign = await repo.get_campaign(auth.tenant_id, campaign_id)
    if not campaign:
        raise HTTPException(
            404, detail={"code": "campaign_not_found", "message": "Campaign not found"}
        )
    if action == "start" and not await repo.list_campaign_contacts(auth.tenant_id, campaign_id):
        raise HTTPException(
            409,
            detail={
                "code": "campaign_empty",
                "message": "Import at least one contact before starting",
            },
        )
    try:
        target = transition_status(str(campaign["status"]), action)
    except ValueError as exc:
        raise HTTPException(
            409, detail={"code": "invalid_campaign_transition", "message": str(exc)}
        ) from exc
    return (await repo.update_campaign(auth.tenant_id, campaign_id, {"status": target})) or campaign


@v1.get("/do-not-call")
async def list_do_not_call(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_do_not_call(auth.tenant_id)}


@v1.post("/do-not-call", status_code=201)
async def add_do_not_call(body: DoNotCallCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    return await repo.add_do_not_call(auth.tenant_id, body.phone, body.reason)


@v1.delete("/do-not-call/{phone}", status_code=204)
async def delete_do_not_call(phone: str, auth: Auth, repo: Repo) -> None:
    if not await repo.remove_do_not_call(auth.tenant_id, phone):
        raise HTTPException(
            404, detail={"code": "do_not_call_not_found", "message": "Phone not found"}
        )


@v1.get("/billing/plan")
async def billing_plan(auth: Auth, repo: Repo) -> dict[str, Any]:
    plan = await repo.get_billing_plan(auth.tenant_id)
    if not plan:
        raise HTTPException(
            404, detail={"code": "plan_not_found", "message": "Billing plan not found"}
        )
    return plan


@v1.get("/billing/usage")
async def billing_usage(auth: Auth, repo: Repo, period: str | None = None) -> dict[str, Any]:
    value = period or datetime.now(UTC).strftime("%Y-%m")
    try:
        month = datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(
            422, detail={"code": "invalid_period", "message": "period must be YYYY-MM"}
        ) from exc
    return await repo.get_billing_usage(auth.tenant_id, month)


@v1.get("/billing/invoices")
async def billing_invoices(auth: Auth, repo: Repo) -> dict[str, Any]:
    return {"data": await repo.list_invoices(auth.tenant_id)}


@v1.post("/billing/checkout")
async def billing_checkout(
    body: BillingCheckoutRequest, auth: Auth, repo: Repo, stripe: Stripe
) -> dict[str, str]:
    _require_admin(auth)
    current = await repo.get_billing_plan(auth.tenant_id)
    target = await repo.get_plan_by_code(body.plan_code)
    if not target:
        raise HTTPException(404, detail={"code": "plan_not_found", "message": "Plan not found"})
    if get_settings().app_env not in {"dev", "test"} and not target.get("stripe_price_id"):
        raise HTTPException(
            503, detail={"code": "stripe_plan_not_synced", "message": "Plan has no Stripe price"}
        )
    return await stripe.checkout(
        (current or {}).get("stripe_customer_id"), target, str(auth.tenant_id)
    )


@v1.post("/billing/portal")
async def billing_portal(auth: Auth, repo: Repo, stripe: Stripe) -> dict[str, str]:
    _require_admin(auth)
    plan = await repo.get_billing_plan(auth.tenant_id)
    customer_id = (plan or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(
            409, detail={"code": "stripe_customer_missing", "message": "Complete checkout first"}
        )
    return await stripe.portal(str(customer_id))


@v1.post("/agents/{agent_id}/test-session", status_code=201)
async def create_test_session(
    agent_id: UUID, body: SessionCreate, auth: Auth, repo: Repo, rtc: Rtc
) -> dict[str, Any]:
    await _enforce_call_limit(auth, repo, "web")
    if body.agent_id != agent_id:
        raise HTTPException(
            422, detail={"code": "agent_mismatch", "message": "Path and body agent_id must match"}
        )
    agent = await repo.get_agent(auth.tenant_id, agent_id)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    end_user = await repo.upsert_end_user(auth.tenant_id, body.end_user) if body.end_user else None
    metadata = {**body.metadata, "test_session": True}
    call = await repo.create_call(
        auth.tenant_id,
        agent_id,
        body.variables,
        metadata,
        agent_version_id=agent["draft_version_id"],
        end_user_id=end_user["id"] if end_user else None,
    )
    call_id = call["id"]
    session = await rtc.provision(
        call_id=call_id,
        agent_id=agent_id,
        version="draft",
        variables=body.variables,
        end_user=body.end_user,
    )
    await repo.update_call(auth.tenant_id, call_id, {"livekit_room": session["room_name"]})
    return {
        "session_id": call_id,
        "call_id": call_id,
        "livekit_url": get_settings().livekit_url,
        "token": session["token"],
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }


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
    filters = {
        "agent_id": agent_id,
        "channel": channel,
        "status": status,
        "end_user_id": end_user_id,
        "from": from_date,
        "to": to_date,
        "q": q,
    }
    return {"data": await repo.list_calls(auth.tenant_id, filters), "next_cursor": None}


@v1.get("/calls/{call_id}")
async def get_call(call_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    call = await repo.get_call_detail(auth.tenant_id, call_id)
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    return call


@v1.patch("/calls/{call_id}/qa")
async def update_call_qa(call_id: UUID, body: CallQaPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    if auth.role not in {"owner", "admin", "operator"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Operator role required"})
    item = await repo.upsert_call_qa(auth.tenant_id, call_id, {**body.model_dump(), "model": "manual"})
    if not item:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    return item


@v1.get("/calls/{call_id}/recording", response_class=RedirectResponse)
async def get_call_recording(
    call_id: UUID, auth: Auth, repo: Repo, storage: Storage
) -> RedirectResponse:
    call = await repo.get_call_detail(auth.tenant_id, call_id)
    recording = call.get("recording") if call else None
    if not recording or recording.get("status") != "ready" or not recording.get("s3_key"):
        raise HTTPException(
            404, detail={"code": "recording_not_found", "message": "Recording not found"}
        )
    return RedirectResponse(await storage.playback_url(str(recording["s3_key"])), status_code=307)


@v1.get("/calls/{call_id}/live")
async def live_call(
    call_id: UUID, request: Request, auth: Auth, repo: Repo, bus: Bus
) -> StreamingResponse:
    if not await repo.get_call(auth.tenant_id, call_id):
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})

    async def stream() -> Any:
        yield encode_sse({"type": "connected", "call_id": call_id})
        async for event in bus.subscribe(auth.tenant_id, call_id):
            if await request.is_disconnected():
                break
            yield encode_sse(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@v1.post("/calls/{call_id}/takeover")
async def takeover_call(
    call_id: UUID,
    body: CallTakeoverRequest,
    auth: Auth,
    repo: Repo,
    rtc: Rtc,
    phone: Phone,
    bus: Bus,
) -> dict[str, Any]:
    if auth.role not in {"owner", "admin", "operator"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Operator role required"})
    call = await repo.get_call(auth.tenant_id, call_id)
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    if call.get("status") not in {"queued", "ringing", "in_progress"} or not call.get(
        "livekit_room"
    ):
        raise HTTPException(409, detail={"code": "call_not_live", "message": "Call is not active"})
    event = {
        "type": "operator.takeover",
        "payload": {
            "operator_id": auth.user_id,
            "mode": "phone" if call["channel"].startswith("phone") else "web",
        },
        "at": datetime.now(UTC),
    }
    response: dict[str, Any]
    if call["channel"].startswith("phone"):
        if not body.operator_extension:
            raise HTTPException(
                422,
                detail={
                    "code": "operator_extension_required",
                    "message": "Operator extension is required for phone takeover",
                },
            )
        if phone.outbound is None:
            raise HTTPException(
                503,
                detail={"code": "sip_not_configured", "message": "Outbound SIP is not configured"},
            )
        business_number = (
            call.get("from_number")
            if call["channel"] == "phone_outbound"
            else call.get("to_number")
        )
        if not business_number:
            raise HTTPException(
                409,
                detail={
                    "code": "business_number_missing",
                    "message": "Call has no business phone number",
                },
            )
        leg_sid = await phone.outbound.dial(
            str(call["livekit_room"]), body.operator_extension, str(business_number)
        )
        response = {"mode": "phone", "operator_leg_sid": leg_sid}
    else:
        response = {
            "mode": "web",
            "livekit_url": get_settings().livekit_url,
            "room_name": call["livekit_room"],
            "token": rtc.operator_token(str(call["livekit_room"]), auth.user_id),
        }
    await repo.append_call_events(call_id, [event])
    await bus.publish(auth.tenant_id, call_id, event)
    return response


@v1.post("/calls/{call_id}/hangup")
async def hangup_call(call_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    call = await repo.update_call(
        auth.tenant_id,
        call_id,
        {"status": "completed", "end_reason": "agent_hangup", "ended_at": datetime.now(UTC)},
    )
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    return call


@v1.post("/calls/{call_id}/whatsapp-handoff")
async def send_whatsapp_handoff_message(
    call_id: UUID,
    body: WhatsAppHandoffMessage,
    auth: Auth,
    repo: Repo,
    cipher: Cipher,
    bus: Bus,
) -> dict[str, Any]:
    if auth.role not in {"owner", "admin", "operator"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Operator role required"})
    call = await repo.get_call_detail(auth.tenant_id, call_id)
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    if call.get("channel") != "whatsapp":
        raise HTTPException(
            409,
            detail={"code": "invalid_channel", "message": "Call is not a WhatsApp conversation"},
        )
    integration = await repo.get_integration(auth.tenant_id, "whatsapp")
    if not integration or integration.get("status") != "active":
        raise HTTPException(
            409,
            detail={
                "code": "integration_unavailable",
                "message": "WhatsApp integration is not connected",
            },
        )
    secret_id_raw = integration.get("refresh_token_secret_id")
    try:
        secret_id = UUID(str(secret_id_raw))
    except (TypeError, ValueError):
        raise HTTPException(
            409,
            detail={"code": "secret_missing", "message": "WhatsApp access token is unavailable"},
        )
    secret = await repo.get_secret(auth.tenant_id, secret_id)
    if not secret:
        raise HTTPException(
            409,
            detail={"code": "secret_missing", "message": "WhatsApp access token is unavailable"},
        )
    config = dict(integration.get("config") or {})
    phone_number_id = str(config.get("phone_number_id") or "")
    recipient = str(call.get("from_number") or "")
    if not phone_number_id or not recipient:
        raise HTTPException(
            409,
            detail={"code": "handoff_unavailable", "message": "Missing WhatsApp routing data"},
        )
    access_token = await cipher.decrypt(secret["ciphertext"], str(secret["kms_key_id"]))
    message_id = await WhatsAppGateway(get_settings(), access_token, phone_number_id).send_text(
        recipient, body.text
    )
    metadata = dict(call.get("metadata") or {})
    metadata["human_handoff"] = True
    await repo.update_call(auth.tenant_id, call_id, {"metadata": metadata})
    turn = {
        "ordinal": len(call.get("turns") or []),
        "role": "operator",
        "text": body.text,
        "started_at": datetime.now(UTC),
        "ended_at": datetime.now(UTC),
        "audio_offset_ms": 0,
    }
    await repo.append_call_turns(call_id, [turn])
    event = {
        "type": "operator.message",
        "turn": {"role": "operator", "text": body.text},
        "provider_message_id": message_id,
        "at": datetime.now(UTC),
    }
    await repo.append_call_events(call_id, [event])
    await bus.publish(auth.tenant_id, call_id, event)
    return {"status": "sent", "provider_message_id": message_id}


@v1.post("/tools", status_code=201)
async def create_tool(body: ToolCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    return await repo.create_tool(auth.tenant_id, body.model_dump(by_alias=True))


@v1.get("/tools")
async def list_tools(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    return {"data": await repo.list_tools(auth.tenant_id), "next_cursor": None}


@v1.get("/tools/{tool_id}")
async def get_tool(tool_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    tool = await repo.get_tool(auth.tenant_id, tool_id)
    if not tool:
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})
    return tool


@v1.patch("/tools/{tool_id}")
async def update_tool(tool_id: UUID, body: ToolPatch, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    tool = await repo.update_tool(
        auth.tenant_id, tool_id, body.model_dump(exclude_unset=True, by_alias=True)
    )
    if not tool:
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})
    return tool


@v1.delete("/tools/{tool_id}", status_code=204)
async def delete_tool(tool_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if not await repo.delete_tool(auth.tenant_id, tool_id):
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})


@v1.post("/tools/{tool_id}/test")
async def test_tool(
    tool_id: UUID, body: ToolTestRequest, auth: Auth, repo: Repo, executor: Executor, cipher: Cipher
) -> dict[str, Any]:
    _require_admin(auth)
    tool = await repo.get_tool(auth.tenant_id, tool_id)
    if not tool:
        raise HTTPException(404, detail={"code": "tool_not_found", "message": "Tool not found"})
    secret = await _resolve_tool_secret(repo, cipher, auth.tenant_id, tool)
    result = await executor.execute(
        tool,
        body.arguments,
        {
            "tenant_id": auth.tenant_id,
            "session_variables": body.session_variables,
            "end_user": body.end_user,
            "call": {},
            "secret": secret,
        },
    )
    if "error" not in result and result.get("status", 500) < 300:
        await repo.update_tool(auth.tenant_id, tool_id, {"last_test_ok_at": datetime.now(UTC)})
    return result


@v1.get("/secrets")
async def list_secrets(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    return {"data": await repo.list_secrets(auth.tenant_id), "next_cursor": None}


@v1.post("/secrets", status_code=201)
async def create_secret(
    body: SecretCreate, auth: Auth, repo: Repo, cipher: Cipher
) -> dict[str, Any]:
    _require_admin(auth)
    ciphertext, key_id = await cipher.encrypt(body.value)
    return await repo.create_secret(auth.tenant_id, body.name, ciphertext, key_id)


@v1.delete("/secrets/{secret_id}", status_code=204)
async def delete_secret(secret_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if not await repo.delete_secret(auth.tenant_id, secret_id):
        raise HTTPException(404, detail={"code": "secret_not_found", "message": "Secret not found"})


@v1.get("/integrations/google/connect")
async def google_connect(auth: Auth, native: Native) -> dict[str, str]:
    _require_admin(auth)
    try:
        return {"url": native.google_connect_url(auth.tenant_id, auth.user_id)}
    except RuntimeError as exc:
        raise HTTPException(
            503, detail={"code": "integration_unavailable", "message": str(exc)}
        ) from exc


@v1.get("/integrations/google/callback")
async def google_callback(
    code: str, state: str, repo: Repo, cipher: Cipher, native: Native
) -> dict[str, Any]:
    try:
        integration = await native.google_callback(code, state, repo, cipher)
    except (ValueError, jwt.PyJWTError, httpx.HTTPError) as exc:
        raise HTTPException(400, detail={"code": "oauth_failed", "message": str(exc)}) from exc
    return {key: value for key, value in integration.items() if key != "refresh_token_secret_id"}


@v1.get("/integrations")
async def list_integrations(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    items = [
        _sanitize_integration(await repo.get_integration(auth.tenant_id, provider))
        for provider in ("google", "whatsapp")
    ]
    return {"data": [item for item in items if item], "next_cursor": None}


@v1.post("/integrations/whatsapp", status_code=201)
async def connect_whatsapp(
    body: WhatsAppConnect, auth: Auth, repo: Repo, cipher: Cipher
) -> dict[str, Any]:
    _require_admin(auth)
    if not await repo.get_agent(auth.tenant_id, body.agent_id):
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    ciphertext, key_id = await cipher.encrypt(body.access_token)
    secret = await repo.create_secret(
        auth.tenant_id, f"whatsapp_{body.phone_number_id}", ciphertext, key_id
    )
    integration = await repo.upsert_integration(
        auth.tenant_id,
        "whatsapp",
        {
            "scopes": ["whatsapp_business_messaging"],
            "refresh_token_secret_id": secret["id"],
            "account_email": body.business_account_id,
            "status": "active",
            "config": {
                "phone_number_id": body.phone_number_id,
                "business_account_id": body.business_account_id,
                "agent_id": str(body.agent_id),
            },
        },
    )
    return _sanitize_integration(integration) or {}


@v1.put("/agents/{agent_id}/draft/tools")
async def set_draft_tools(
    agent_id: UUID, body: AgentToolsSet, auth: Auth, repo: Repo
) -> dict[str, Any]:
    _require_admin(auth)
    try:
        tools = await repo.set_draft_tools(auth.tenant_id, agent_id, body.tool_ids)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_tools", "message": str(exc)}) from exc
    if tools is None:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return {"data": tools}


@v1.get("/agents/{agent_id}/draft/tools")
async def get_draft_tools(agent_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    if not await repo.get_agent(auth.tenant_id, agent_id):
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    runtime = await repo.get_runtime(agent_id, "draft")
    return {"data": runtime.get("tools", []) if runtime else []}


@v1.post("/simulations", status_code=201)
async def create_simulation(body: SimulationCreate, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    if not await repo.get_agent(auth.tenant_id, body.agent_id):
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    simulation = await repo.create_simulation(auth.tenant_id, body.model_dump())
    runtime = await repo.get_runtime(body.agent_id, "current") or await repo.get_runtime(
        body.agent_id, "draft"
    )
    report = run_simulation(
        body.persona,
        body.objective,
        body.conversation_count,
        greeting=str((runtime or {}).get("greeting") or "Olá! Como posso ajudar?"),
    )
    completed = await repo.complete_simulation(auth.tenant_id, UUID(str(simulation["id"])), report)
    return completed or simulation


@v1.get("/simulations/{simulation_id}")
async def get_simulation(simulation_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    item = await repo.get_simulation(auth.tenant_id, simulation_id)
    if not item:
        raise HTTPException(
            404, detail={"code": "simulation_not_found", "message": "Simulation not found"}
        )
    return item


@v1.get("/simulations/{simulation_id}/yaml")
async def get_simulation_yaml(simulation_id: UUID, auth: Auth, repo: Repo) -> Response:
    _require_admin(auth)
    item = await repo.get_simulation(auth.tenant_id, simulation_id)
    if not item:
        raise HTTPException(
            404, detail={"code": "simulation_not_found", "message": "Simulation not found"}
        )
    report = dict(item.get("report") or {})
    if not report:
        raise HTTPException(
            409,
            detail={
                "code": "simulation_pending",
                "message": "Simulation report is not available yet",
            },
        )
    return Response(content=simulation_yaml(report), media_type="application/yaml")


@v1.get("/knowledge-bases")
async def list_knowledge_bases(auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    return {"data": await repo.list_knowledge_bases(auth.tenant_id), "next_cursor": None}


@v1.post("/knowledge-bases", status_code=201)
async def create_knowledge_base(
    body: KnowledgeBaseCreate, auth: Auth, repo: Repo
) -> dict[str, Any]:
    _require_admin(auth)
    return await repo.create_knowledge_base(auth.tenant_id, body.model_dump())


@v1.get("/knowledge-bases/{kb_id}")
async def get_knowledge_base(kb_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    item = await repo.get_knowledge_base(auth.tenant_id, kb_id)
    if not item:
        raise HTTPException(
            404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"}
        )
    return item


@v1.patch("/knowledge-bases/{kb_id}")
async def update_knowledge_base(
    kb_id: UUID, body: KnowledgeBasePatch, auth: Auth, repo: Repo
) -> dict[str, Any]:
    _require_admin(auth)
    item = await repo.update_knowledge_base(
        auth.tenant_id, kb_id, body.model_dump(exclude_unset=True)
    )
    if not item:
        raise HTTPException(
            404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"}
        )
    return item


@v1.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_knowledge_base(kb_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if not await repo.delete_knowledge_base(auth.tenant_id, kb_id):
        raise HTTPException(
            404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"}
        )


@v1.get("/knowledge-bases/{kb_id}/documents")
async def list_documents(kb_id: UUID, auth: Auth, repo: Repo) -> dict[str, Any]:
    _require_admin(auth)
    if not await repo.get_knowledge_base(auth.tenant_id, kb_id):
        raise HTTPException(
            404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"}
        )
    return {"data": await repo.list_documents(auth.tenant_id, kb_id), "next_cursor": None}


@v1.post("/knowledge-bases/{kb_id}/documents", status_code=202)
async def create_document(
    kb_id: UUID,
    request: Request,
    background: BackgroundTasks,
    auth: Auth,
    repo: Repo,
    embeddings: Embedder,
) -> dict[str, Any]:
    _require_admin(auth)
    upload_bytes: bytes | None = None
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        uploaded = form.get("file")
        if not hasattr(uploaded, "read"):
            raise HTTPException(
                422,
                detail={"code": "file_required", "message": "Multipart field 'file' is required"},
            )
        upload_bytes = await uploaded.read()  # type: ignore[union-attr]
        body = DocumentCreate(
            name=getattr(uploaded, "filename", None) or "documento", text="uploaded"
        )
        source_type, mime = "upload", getattr(uploaded, "content_type", None)
    else:
        try:
            body = DocumentCreate.model_validate(await request.json())
        except PydanticValidationError as exc:
            raise HTTPException(
                422, detail={"code": "invalid_document", "message": "Document requires text or URL"}
            ) from exc
        source_type, mime = ("url" if body.url else "text"), None
    item = await repo.create_document(
        auth.tenant_id,
        kb_id,
        {
            "name": body.name,
            "source_type": source_type,
            "source_uri": body.url,
            "mime": mime,
            "size_bytes": len(upload_bytes) if upload_bytes is not None else None,
        },
    )
    if not item:
        raise HTTPException(
            404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"}
        )
    kb = await repo.get_knowledge_base(auth.tenant_id, kb_id)
    assert kb is not None
    background.add_task(
        _ingest_document,
        repo,
        embeddings,
        auth.tenant_id,
        item,
        kb,
        None if source_type == "upload" else body.text,
        upload_bytes,
    )
    return item


@v1.delete("/knowledge-bases/{kb_id}/documents/{document_id}", status_code=204)
async def delete_document(kb_id: UUID, document_id: UUID, auth: Auth, repo: Repo) -> None:
    _require_admin(auth)
    if not await repo.delete_document(auth.tenant_id, kb_id, document_id):
        raise HTTPException(
            404, detail={"code": "document_not_found", "message": "Document not found"}
        )


@v1.post("/knowledge-bases/{kb_id}/query")
async def query_knowledge_base(
    kb_id: UUID, body: KnowledgeQuery, auth: Auth, repo: Repo, embeddings: Embedder
) -> dict[str, Any]:
    _require_admin(auth)
    kb = await repo.get_knowledge_base(auth.tenant_id, kb_id)
    if not kb:
        raise HTTPException(
            404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"}
        )
    vector = (await embeddings.create([body.query], kb["embedding_model"]))[0]
    return {
        "data": await repo.query_chunks(auth.tenant_id, kb_id, vector, body.top_k, body.min_score)
    }


@internal.get("/agents/{agent_id}/runtime")
async def runtime(agent_id: UUID, repo: Repo, version: str = "current") -> dict[str, Any]:
    agent = await repo.get_runtime(agent_id, version)
    if not agent:
        raise HTTPException(404, detail={"code": "agent_not_found", "message": "Agent not found"})
    return {
        "tenant_id": agent["tenant_id"],
        "tenant_settings": agent.get("tenant_settings") or {},
        "agent_id": agent_id,
        "version_id": agent["version_id"],
        "system_prompt": agent["system_prompt"],
        "greeting": agent["greeting"],
        "language": agent["language"],
        "llm": agent["llm"],
        "stt": agent["stt"],
        "tts": agent["tts"],
        "turn": agent["turn_config"],
        "behavior": agent["behavior"],
        "knowledge_base_id": agent["knowledge_base_id"],
        "rag": agent["rag"],
        "variables": agent["variables"],
        "tools": agent["tools"],
    }


@internal.post("/calls", status_code=201)
async def create_internal_call(body: InternalCallCreate, repo: Repo) -> dict[str, Any]:
    call = await repo.create_internal_call(body.model_dump())
    await repo.queue_webhook_event(body.tenant_id, "call.started", {"call": call})
    return call


@internal.post("/campaigns/tick")
async def campaign_runner_tick(repo: Repo, rtc: Rtc, phone: Phone) -> dict[str, int]:
    now = datetime.now(UTC)
    claimed = await repo.claim_campaign_contacts()
    dispatched = deferred = failed = 0
    for contact in claimed:
        contact_id = contact["id"]
        tenant_id = contact["tenant_id"]
        schedule = dict(contact.get("schedule") or {})
        timezone = dict(contact.get("variables") or {}).get("timezone")
        if not dialing_allowed(schedule, now=now, contact_timezone=timezone):
            await repo.update_campaign_contact_internal(
                contact_id, {"status": "retry", "next_attempt_at": now + timedelta(minutes=5)}
            )
            deferred += 1
            continue
        all_calls = await repo.list_calls(tenant_id)
        active = [
            call for call in all_calls if call.get("status") in {"queued", "ringing", "in_progress"}
        ]
        campaign_active = [
            call for call in active if call.get("campaign_id") == contact["campaign_id"]
        ]
        plan_limit = await repo.get_plan_concurrency(tenant_id)
        campaign_limit = min(int(schedule.get("max_concurrency", plan_limit)), plan_limit)
        if len(active) >= plan_limit or len(campaign_active) >= campaign_limit:
            await repo.update_campaign_contact_internal(
                contact_id, {"status": "retry", "next_attempt_at": now + timedelta(seconds=30)}
            )
            deferred += 1
            continue
        agent = await repo.get_agent(tenant_id, contact["agent_id"])
        assigned = next(
            (
                item
                for item in await repo.list_phone_numbers(tenant_id)
                if item.get("agent_id") == contact["agent_id"]
                and item.get("status") == "active"
                and bool((item.get("capabilities") or {}).get("voice"))
            ),
            None,
        )
        if not agent or agent.get("status") != "active" or not assigned or phone.outbound is None:
            await repo.update_campaign_contact_internal(
                contact_id, {"status": "failed", "next_attempt_at": None}
            )
            failed += 1
            continue
        variables = {**dict(contact.get("variables") or {}), "campaign_contact_id": str(contact_id)}
        end_user_data = {"phone": contact["phone"], "name": contact.get("name")}
        try:
            end_user = await repo.upsert_end_user(tenant_id, end_user_data)
            call = await repo.create_call(
                tenant_id,
                contact["agent_id"],
                variables,
                {"campaign_contact_id": str(contact_id)},
                agent_version_id=agent["current_version_id"],
                end_user_id=end_user["id"],
                channel="phone_outbound",
                from_number=str(assigned["e164"]),
                to_number=contact["phone"],
                campaign_id=contact["campaign_id"],
            )
            session = await rtc.provision(
                call_id=call["id"],
                agent_id=contact["agent_id"],
                version="current",
                variables=variables,
                end_user=end_user_data,
                channel="phone_outbound",
                from_number=str(assigned["e164"]),
                to_number=contact["phone"],
            )
            await repo.update_call(tenant_id, call["id"], {"livekit_room": session["room_name"]})
            await repo.update_campaign_contact_internal(
                contact_id,
                {"status": "calling", "last_call_id": call["id"], "next_attempt_at": None},
            )
            dispatched += 1
        except Exception:
            await repo.update_campaign_contact_internal(
                contact_id, {"status": "retry", "next_attempt_at": now + timedelta(minutes=5)}
            )
            failed += 1
    return {
        "claimed": len(claimed),
        "dispatched": dispatched,
        "deferred": deferred,
        "failed": failed,
    }


@internal.post("/billing/tick")
async def billing_meter_tick(repo: Repo, stripe: Stripe) -> dict[str, int]:
    batches = await repo.billing_meter_batches()
    reported = synced_phones = failed = 0
    for batch in batches:
        tenant_id = batch["tenant_id"]
        record_ids = list(batch.get("record_ids") or [])
        delta = int(batch.get("overage_delta") or 0)
        try:
            if delta > 0:
                item_id = batch.get("stripe_overage_item_id")
                if not item_id:
                    failed += 1
                    continue
                marker = await stripe.report_usage(
                    str(item_id), delta, f"usage-{tenant_id}-{datetime.now(UTC):%Y-%m-%d-%H}"
                )
            else:
                marker = "included"
            await repo.mark_usage_reported(tenant_id, record_ids, marker)
            reported += len(record_ids)
            if batch.get("stripe_phone_item_id"):
                await stripe.set_quantity(
                    str(batch["stripe_phone_item_id"]), int(batch.get("phone_quantity") or 0)
                )
                synced_phones += 1
        except Exception:
            failed += 1
    alerts = await repo.billing_threshold_events()
    for alert in alerts:
        await repo.queue_webhook_event(UUID(str(alert["tenant_id"])), "usage.threshold", {"usage": alert})
    return {"tenants": len(batches), "records": reported, "phones": synced_phones, "alerts": len(alerts), "failed": failed}


@internal.post("/webhooks/tick")
async def outgoing_webhook_tick(repo: Repo, cipher: Cipher) -> dict[str, int]:
    deliveries = await repo.claim_webhook_deliveries()
    sender = OutgoingWebhookSender()
    delivered = retrying = failed = 0
    for item in deliveries:
        status_code: int | None = None
        try:
            secret = await cipher.decrypt(bytes(item["ciphertext"]), str(item["kms_key_id"]))
            status_code = await sender.send(str(item["url"]), dict(item["payload"]), secret)
        except Exception:
            status_code = None
        result = delivery_result(int(item["attempts"]), status_code)
        await repo.update_webhook_delivery(item["id"], result)
        if result["status"] == "delivered":
            delivered += 1
        elif result["status"] == "retrying":
            retrying += 1
        else:
            failed += 1
    return {"claimed": len(deliveries), "delivered": delivered, "retrying": retrying, "failed": failed}


@internal.post("/whatsapp/tick")
async def whatsapp_tick(
    repo: Repo, cipher: Cipher, bus: Bus, voice: Voice, executor: Executor, native: Native
) -> dict[str, int]:
    messages = await repo.claim_whatsapp_messages()
    processed = failed = handoffs = tool_runs = 0
    settings = get_settings()
    for item in messages:
        tenant_id = UUID(str(item["tenant_id"]))
        call_id = UUID(str(item["call_id"]))
        try:
            call = dict(item.get("call") or {})
            config = dict(item.get("config") or {})
            metadata = dict(call.get("metadata") or {})
            phone_number_id = str(
                config.get("phone_number_id")
                or metadata.get("phone_number_id")
                or item.get("phone_number_id")
                or ""
            )
            if not phone_number_id:
                raise ValueError("WhatsApp phone_number_id is missing")
            access_token = await cipher.decrypt(bytes(item["ciphertext"]), str(item["kms_key_id"]))
            gateway = WhatsAppGateway(settings, access_token, phone_number_id)
            runtime = (
                await repo.get_runtime(UUID(str(call["agent_id"])), "current")
                if call.get("agent_id")
                else None
            ) or (
                await repo.get_runtime(UUID(str(call["agent_id"])), "draft")
                if call.get("agent_id")
                else None
            )
            inbound_type = str(item.get("type") or "text")
            user_text = str(item.get("text") or "").strip()
            if inbound_type == "audio" and item.get("media_id"):
                try:
                    media = await gateway.download_media(str(item["media_id"]))
                    if not user_text:
                        user_text = await transcribe_whatsapp_audio(settings, runtime, media)
                except Exception:
                    if not user_text:
                        user_text = "Mensagem de voz recebida."
            elif not user_text:
                user_text = f"Mensagem recebida pelo canal WhatsApp ({inbound_type})."
            callback_tenant_id = tenant_id
            callback_call_id = call_id
            callback_call = dict(call)
            callback_session_variables = dict(call.get("variables") or {})

            async def execute_tool_callback(
                tool: dict[str, Any],
                arguments: dict[str, Any],
                callback_tenant_id: UUID = callback_tenant_id,
                callback_call_id: UUID = callback_call_id,
                callback_call: dict[str, Any] = callback_call,
                callback_session_variables: dict[str, Any] = callback_session_variables,
            ) -> dict[str, Any]:
                nonlocal tool_runs
                started = datetime.now(UTC)
                llm_result, raw_result = await _execute_runtime_tool(
                    repo,
                    executor,
                    cipher,
                    native,
                    callback_tenant_id,
                    callback_call,
                    tool,
                    arguments,
                    session_variables=callback_session_variables,
                )
                duration_ms = round((datetime.now(UTC) - started).total_seconds() * 1000)
                item = await repo.append_call_tool_call(
                    callback_call_id,
                    {
                        "id": None,
                        "turn_id": None,
                        "tool_id": tool.get("id"),
                        "name": tool["name"],
                        "arguments": arguments,
                        "result": llm_result,
                        "status": "error" if "error" in llm_result else "ok",
                        "duration_ms": raw_result.get("latency_ms", duration_ms),
                        "started_at": started,
                    },
                )
                if item:
                    await bus.publish(
                        callback_tenant_id,
                        callback_call_id,
                        {"type": "tool.called", "tool_call": item},
                    )
                tool_runs += 1
                return llm_result

            mode = _whatsapp_reply_mode(runtime)
            agent_text, handoff, _tool_records = await generate_whatsapp_reply(
                settings,
                runtime,
                user_text,
                inbound_type,
                execute_tool=execute_tool_callback if list((runtime or {}).get("tools") or []) else None,
            )
            if not agent_text:
                agent_text, handoff = fallback_reply(runtime, user_text, inbound_type)
            mode = _whatsapp_reply_mode(runtime)
            recipient = str(item.get("from") or call.get("from_number") or "")
            if not recipient:
                raise ValueError("WhatsApp recipient is missing")
            provider_message_ids: list[str] = []
            if mode != "audio":
                provider_message_ids.append(await gateway.send_text(recipient, agent_text))
            audio_payload = (
                await synthesize_whatsapp_audio(settings, runtime, agent_text, voice)
                if mode in {"audio", "both"}
                else None
            )
            if audio_payload:
                audio, filename, content_type = audio_payload
                provider_message_ids.append(
                    await gateway.send_audio_bytes(
                        recipient,
                        audio,
                        filename=filename,
                        content_type=content_type,
                    )
                )
            elif mode == "audio":
                provider_message_ids.append(await gateway.send_text(recipient, agent_text))
            await repo.complete_whatsapp_message(
                UUID(str(item["id"])),
                {
                    "user_text": user_text,
                    "agent_text": agent_text,
                    "handoff": handoff,
                    "status": "done",
                },
            )
            user_event = {
                "type": "turn.user",
                "turn": {"role": "user", "text": user_text},
                "at": datetime.now(UTC),
            }
            agent_event = {
                "type": "turn.agent",
                "turn": {"role": "agent", "text": agent_text},
                "provider_message_ids": provider_message_ids,
                "at": datetime.now(UTC),
            }
            await bus.publish(tenant_id, call_id, user_event)
            await bus.publish(tenant_id, call_id, agent_event)
            if handoff:
                handoff_event = {
                    "type": "operator.takeover_requested",
                    "payload": {"source": "whatsapp"},
                    "at": datetime.now(UTC),
                }
                await repo.append_call_events(call_id, [handoff_event])
                await bus.publish(tenant_id, call_id, handoff_event)
                handoffs += 1
            processed += 1
        except Exception as exc:
            await repo.complete_whatsapp_message(
                UUID(str(item["id"])), {"status": "failed", "error": type(exc).__name__}
            )
            failed += 1
    return {
        "claimed": len(messages),
        "processed": processed,
        "failed": failed,
        "handoffs": handoffs,
        "tool_runs": tool_runs,
    }


@internal.post("/exports/tick")
async def export_tick(repo: Repo, storage: ExportStore) -> dict[str, int]:
    exports = await repo.claim_exports()
    ready = failed = 0
    for item in exports:
        try:
            rows = list(item.get("rows") or [])
            columns = sorted({str(key) for row in rows for key in row}) or ["empty"]
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else value for key, value in row.items()})
            key = f"{item['tenant_id']}/{item['id']}.csv"
            await storage.upload(key, output.getvalue().encode("utf-8-sig"))
            await repo.complete_export(item["id"], key)
            ready += 1
        except Exception:
            await repo.complete_export(item["id"], None, error=True)
            failed += 1
    return {"claimed": len(exports), "ready": ready, "failed": failed}


@internal.post("/retention/tick")
async def retention_tick(repo: Repo, storage: RetentionStore) -> dict[str, int]:
    result = await repo.purge_retention()
    await storage.delete(list(result["recording_keys"]), list(result["document_keys"]))
    return {
        "recordings_deleted": len(result["recording_keys"]),
        "documents_deleted": int(result["documents_deleted"]),
        "turns_anonymized": int(result["turns_anonymized"]),
    }


@internal.patch("/calls/{call_id}")
async def update_internal_call(call_id: UUID, body: CallPatch, repo: Repo) -> dict[str, Any]:
    call = await repo.update_internal_call(call_id, body.model_dump(exclude_unset=True))
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    if body.status in {"completed", "failed", "no_answer", "busy", "voicemail", "cancelled"}:
        await repo.queue_webhook_event(UUID(str(call["tenant_id"])), "call.ended", {"call": call})
    return call


async def _postprocess_call(
    call_id: UUID, call: dict[str, Any], repo: Repository, processor: Postprocessor
) -> None:
    try:
        result = await processor.process(call)
        qa = dict(result.pop("qa", {}))
        await repo.update_internal_call(call_id, result)
        await repo.upsert_call_qa(
            UUID(str(call["tenant_id"])),
            call_id,
            {
                "score": max(0, min(100, int(qa.get("score", 0)))),
                "rubric": dict(qa.get("rubric") or {}),
                "issues": list(qa.get("issues") or []),
                "model": get_settings().anthropic_postprocess_model,
            },
        )
        await repo.append_call_events(
            call_id,
            [
                {
                    "type": "call.postprocessed",
                    "payload": {"model": get_settings().anthropic_postprocess_model},
                    "at": datetime.now(UTC),
                }
            ],
        )
    except Exception as exc:
        await repo.upsert_call_qa(
            UUID(str(call["tenant_id"])),
            call_id,
            {"score": 0, "rubric": {}, "issues": ["qa_processing_failed"], "model": "fallback"},
        )
        await repo.append_call_events(
            call_id,
            [
                {
                    "type": "call.postprocess_failed",
                    "payload": {"error": type(exc).__name__},
                    "at": datetime.now(UTC),
                }
            ],
        )


@internal.post("/calls/{call_id}/postprocess", status_code=202)
async def postprocess_call(
    call_id: UUID, background: BackgroundTasks, repo: Repo, processor: Processor
) -> dict[str, bool]:
    tenant_id = await repo.get_call_tenant(call_id)
    call = await repo.get_call_detail(tenant_id, call_id) if tenant_id else None
    if not call:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    background.add_task(_postprocess_call, call_id, call, repo, processor)
    return {"queued": True}


@internal.post("/calls/{call_id}/events")
async def append_call_events(
    call_id: UUID, body: CallEventBatch, repo: Repo, bus: Bus
) -> dict[str, int]:
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
async def append_call_turns(
    call_id: UUID, body: CallTurnBatch, repo: Repo, bus: Bus
) -> dict[str, int]:
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
async def append_call_tool_call(
    call_id: UUID, body: CallToolCallCreate, repo: Repo, bus: Bus
) -> dict[str, Any]:
    item = await repo.append_call_tool_call(call_id, body.model_dump())
    if not item:
        raise HTTPException(404, detail={"code": "call_not_found", "message": "Call not found"})
    tenant_id = await repo.get_call_tenant(call_id)
    if tenant_id:
        await bus.publish(tenant_id, call_id, {"type": "tool.called", "tool_call": item})
    return item


@internal.post("/tools/execute")
async def execute_tool(
    body: InternalToolExecute, repo: Repo, executor: Executor, cipher: Cipher, native: Native
) -> dict[str, Any]:
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
        raw_result, result = await _execute_runtime_tool(
            repo,
            executor,
            cipher,
            native,
            tenant_id,
            call,
            tool,
            body.arguments,
            session_variables=body.session_variables,
            end_user=body.end_user,
        )
    llm_result: dict[str, Any] = (
        raw_result if isinstance(raw_result, dict) else {"value": raw_result}
    )
    await repo.append_call_tool_call(
        body.call_id,
        {
            "id": None,
            "turn_id": None,
            "tool_id": body.tool_id,
            "name": tool["name"],
            "arguments": body.arguments,
            "result": llm_result,
            "status": "error" if "error" in llm_result else "ok",
            "duration_ms": result.get("latency_ms"),
            "started_at": datetime.now(UTC),
        },
    )
    return llm_result


@internal.post("/rag/query")
async def internal_rag_query(
    body: InternalRagQuery, repo: Repo, embeddings: Embedder
) -> dict[str, Any]:
    tenant_id = await repo.get_knowledge_base_tenant(body.knowledge_base_id)
    if not tenant_id:
        raise HTTPException(
            404, detail={"code": "knowledge_base_not_found", "message": "Knowledge base not found"}
        )
    kb = await repo.get_knowledge_base(tenant_id, body.knowledge_base_id)
    assert kb is not None
    vector = (await embeddings.create([body.query], kb["embedding_model"]))[0]
    return {
        "data": await repo.query_chunks(
            tenant_id, body.knowledge_base_id, vector, body.top_k, body.min_score
        )
    }
