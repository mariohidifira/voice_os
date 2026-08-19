"""Exercise the development magic-link login against the running stack."""

import http.cookiejar
import json
import urllib.parse
import urllib.request

WEB = "http://localhost:3000"
EMAIL = "owner@demo.voiceos.local"


def opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


client = opener()
with client.open(f"{WEB}/api/auth/csrf", timeout=10) as response:
    csrf = json.load(response)["csrfToken"]

body = urllib.parse.urlencode({"csrfToken": csrf, "email": EMAIL, "callbackUrl": f"{WEB}/app/demo"}).encode()
request = urllib.request.Request(
    f"{WEB}/api/auth/signin/resend",
    data=body,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
with client.open(request, timeout=10):
    pass

with urllib.request.urlopen("http://localhost:9000/email/last", timeout=10) as response:
    magic_link = json.load(response)["url"]
with client.open(magic_link, timeout=10) as response:
    callback_destination = response.geturl()
with client.open(f"{WEB}/api/auth/session", timeout=10) as response:
    session = json.load(response)
assert session.get("user", {}).get("email") == EMAIL, {"destination": callback_destination, "session": session}

with client.open(f"{WEB}/app/demo", timeout=10) as response:
    assert response.status == 200 and response.geturl() == f"{WEB}/app/demo"

with client.open(f"{WEB}/api/token", timeout=10) as response:
    api_credentials = json.load(response)
tenant_id = api_credentials["tenants"][0]["id"]
me_request = urllib.request.Request(
    "http://localhost:8005/v1/me",
    headers={"Authorization": f"Bearer {api_credentials['access_token']}", "X-Tenant-ID": tenant_id},
)
with urllib.request.urlopen(me_request, timeout=10) as response:
    me = json.load(response)
assert me["tenant_id"] == tenant_id and me["role"] == "owner", me

forged = urllib.request.build_opener()
forged.addheaders = [("Cookie", "voiceos.session-token=forged")]
with forged.open(f"{WEB}/app/demo", timeout=10) as response:
    assert urllib.parse.urlparse(response.geturl()).path == "/login", response.geturl()

print("Auth.js magic-link login, API JWT /v1/me and forged-session rejection passed")
