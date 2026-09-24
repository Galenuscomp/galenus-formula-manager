from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, formulas, users
from app.config import get_settings
from app.services import RuleViolation

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop = None
    if get_settings().embedded_worker:
        from app.worker import start_in_thread

        stop = start_in_thread()
    yield
    if stop is not None:
        stop.set()


app = FastAPI(title="Formula Manager", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(formulas.router)


@app.exception_handler(RuleViolation)
async def rule_violation(_request: Request, exc: RuleViolation):
    return JSONResponse({"detail": exc.errors[0], "errors": exc.errors}, status_code=exc.status_code)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/api/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    candidate = (STATIC_DIR / path).resolve()
    if path and candidate.is_file() and STATIC_DIR in candidate.parents:
        return FileResponse(candidate)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"detail": "Frontend not built"}, status_code=404)
