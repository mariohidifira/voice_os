import json
import os
import urllib.request

base = os.getenv("API_BASE_URL", "http://localhost:8005")
with urllib.request.urlopen(f"{base}/health", timeout=5) as response:
    payload = json.load(response)
if payload.get("status") != "ok":
    raise SystemExit("API health check failed")
print("VoiceOS smoke test passed")
