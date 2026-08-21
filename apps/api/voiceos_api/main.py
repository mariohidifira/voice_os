import uuid
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, Response

from .config import get_settings
from .health import HealthChecker, get_health_checker
from .observability import configure_observability, logger
from .routes import internal, v1, webhooks

app = FastAPI(title="VoiceOS API", version="1.0.0", openapi_version="3.1.0")
app.include_router(v1)
app.include_router(internal)
app.include_router(webhooks)
configure_observability(app, get_settings())
log = logger()


@app.middleware("http")
async def request_id(request: Request, call_next: Any) -> Response:
    request.state.request_id = request.headers.get("X-Request-Id", f"req_{uuid.uuid4().hex}")
    response = cast(Response, await call_next(request))
    response.headers["X-Request-Id"] = request.state.request_id
    log.info("http_request", request_id=request.state.request_id, method=request.method, path=request.url.path, status=response.status_code)
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": detail.get("code", "http_error"), "message": detail.get("message", "Request failed"), "details": detail.get("details", {}), "request_id": request.state.request_id}})


@app.get("/health")
async def health(checker: Annotated[HealthChecker, Depends(get_health_checker)]) -> JSONResponse:
    result = await checker.check()
    return JSONResponse(result, status_code=200 if result["status"] == "ok" else 503)


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
