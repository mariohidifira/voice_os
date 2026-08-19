from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="VoiceOS provider/tool mock")
last_email: dict[str, str] = {}


class EmailMessage(BaseModel):
    to: str
    url: str


@app.post("/email", status_code=202)
async def email(message: EmailMessage) -> dict[str, bool]:
    last_email.update({"to": str(message.to), "url": message.url})
    return {"accepted": True}


@app.get("/email/last")
async def get_last_email() -> dict[str, str]:
    if not last_email:
        raise HTTPException(404, "no email captured")
    return last_email


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/tools/{name}", methods=["GET", "POST"])
async def tool(name: str) -> dict[str, object]:
    if name == "timeout":
        raise HTTPException(504, "simulated timeout")
    if name == "error":
        raise HTTPException(500, "simulated failure")
    return {"ok": True, "tool": name, "data": {"status": "confirmed"}}
