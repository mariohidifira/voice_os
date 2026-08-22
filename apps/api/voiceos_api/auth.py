from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Header, HTTPException

from .config import get_settings


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: UUID
    role: str
    is_platform_admin: bool = False


async def principal(
    authorization: Annotated[str | None, Header()] = None,
    x_tenant_id: Annotated[UUID | None, Header()] = None,
) -> Principal:
    if not authorization or not authorization.startswith("Bearer ") or x_tenant_id is None:
        raise HTTPException(401, detail={"code": "unauthenticated", "message": "Authentication required"})
    token = authorization.removeprefix("Bearer ")
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, detail={"code": "unauthenticated", "message": "Invalid token"}) from exc
    memberships = payload.get("tenants", [])
    membership = next((m for m in memberships if m.get("id") == str(x_tenant_id)), None)
    if membership is None:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Tenant access denied"})
    return Principal(
        str(payload["sub"]),
        x_tenant_id,
        str(membership["role"]),
        bool(payload.get("is_platform_admin", False)),
    )


async def internal_token(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    if x_internal_token != get_settings().internal_api_token:
        raise HTTPException(401, detail={"code": "unauthenticated", "message": "Invalid internal token"})
