from fastapi import FastAPI, HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contextlib import asynccontextmanager
import httpx

from src.usage.middleware import register_usage_event_collection_middleware
from src.usage.router import router as usage_router
from src.score.router import router as score_router
from src.violations.router import router as violations_router
from src.vehicles.router import router as vehicles_router
from src.dashboard.router import router as dashboard_router
from src.auth.router import router as auth_router
from src.logging_utils import (
    configure_logging,
    get_logger,
    log_event,
)


VERSIONED_BASE_PREFIX = "/api/v1"
APP_TITLE = "Driver Behavior Score API"
APP_SUMMARY = "Vehicle scoring and dashboard APIs for DBS."
APP_DESCRIPTION = """
Driver Behavior Score is a FastAPI service for vehicle risk scoring and dashboard workflows.

It provides:
- score, violation, and vehicle APIs under `/api/v1`
- dashboard lookup APIs for authenticated users
- auth endpoints for dashboard users and API key management

The service also exposes request IDs, structured logs, and a health endpoint for operational checks.
"""


configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=10,
        timeout=httpx.Timeout(10.0, connect=5.0),
    ) as client:
        yield {"http_client": client}



app = FastAPI(
    title=APP_TITLE,
    summary=APP_SUMMARY,
    description=APP_DESCRIPTION,
    version="0.1.0",
    root_path="/dbs",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Surrogate-Control"] = "no-store"
    return response



app.include_router(score_router, prefix=f"{VERSIONED_BASE_PREFIX}/score")
app.include_router(violations_router, prefix=f"{VERSIONED_BASE_PREFIX}/violations")
app.include_router(vehicles_router, prefix=f"{VERSIONED_BASE_PREFIX}/vehicles")
app.include_router(auth_router, prefix="/auth")
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(usage_router, prefix="/dashboard/usage")

register_usage_event_collection_middleware(app)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    log_event(
        logger,
        "WARNING",
        "http.exception.handled",
        status_code=exc.status_code,
        detail=exc.detail,
        error_type="HTTPException",
    )
    response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("event=http.exception.unhandled error_type=%s", type(exc).__name__)
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", summary="Health Check", tags=["health"])
async def health_check():
    return {"status": "healthy"}
