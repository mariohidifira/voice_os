"""Exercise agent draft, publish, version history and rollback against PostgreSQL."""

import json
import time
import urllib.request
from http.client import RemoteDisconnected
from typing import Any
from urllib.error import URLError

import jwt
from voiceos_api.config import get_settings

API = "http://localhost:8005"
TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-000000000002"


def request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": USER,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "tenants": [{"id": TENANT, "role": "owner"}],
        },
        settings.auth_secret,
        algorithm="HS256",
    )
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": TENANT,
            "Content-Type": "application/json",
        },
    )
    for attempt in range(10):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except (RemoteDisconnected, URLError):
            if attempt == 9:
                raise
            time.sleep(1)
    raise RuntimeError("unreachable")


status, agent = request("POST", "/v1/agents", {"name": "Version acceptance"})
assert status == 201
agent_id = agent["id"]
try:
    status, draft = request(
        "PATCH",
        f"/v1/agents/{agent_id}/draft",
        {"system_prompt": "Primeira versão publicada.", "rag": {"enabled": True, "top_k": 5}},
    )
    assert status == 200 and draft["version"] == 1

    _, first = request("POST", f"/v1/agents/{agent_id}/publish")
    first_version = first["current_version_id"]
    request("PATCH", f"/v1/agents/{agent_id}/draft", {"system_prompt": "Segunda versão publicada."})
    _, second = request("POST", f"/v1/agents/{agent_id}/publish")
    assert second["current_version_id"] != first_version

    _, versions = request("GET", f"/v1/agents/{agent_id}/versions")
    assert [item["version"] for item in versions["data"]] == [3, 2, 1]
    _, rolled_back = request(
        "POST", f"/v1/agents/{agent_id}/rollback", {"version_id": first_version}
    )
    assert rolled_back["current_version_id"] == first_version

    settings = get_settings()
    internal = urllib.request.Request(
        f"{API}/internal/agents/{agent_id}/runtime",
        headers={"X-Internal-Token": settings.internal_api_token},
    )
    with urllib.request.urlopen(internal, timeout=15) as response:
        runtime = json.load(response)
    assert runtime["system_prompt"] == "Primeira versão publicada."
finally:
    request("DELETE", f"/v1/agents/{agent_id}")

print("PostgreSQL agent draft/publish/history/rollback/runtime acceptance passed")
