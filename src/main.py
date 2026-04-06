from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.score.router import router as score_router
from src.violations.router import router as violations_router
from src.vehicles.router import router as vehicles_router
from src.dashboard.router import router as dashboard_router
from src.auth.router import router as auth_router
from src.logging_utils import (
    configure_logging,
    get_logger,
    log_event,
    reset_request_id,
    set_request_id,
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


app = FastAPI(
    title=APP_TITLE,
    summary=APP_SUMMARY,
    description=APP_DESCRIPTION,
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(score_router, prefix=f"{VERSIONED_BASE_PREFIX}/score")
app.include_router(violations_router, prefix=f"{VERSIONED_BASE_PREFIX}/violations")
app.include_router(vehicles_router, prefix=f"{VERSIONED_BASE_PREFIX}/vehicles")
app.include_router(auth_router, prefix="/auth")
app.include_router(dashboard_router, prefix="/dashboard")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    token = set_request_id(request_id)
    request.state.request_id = request_id
    start = perf_counter()
    log_event(
        logger,
        "INFO",
        "http.request.start",
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)
    except Exception:
        reset_request_id(token)
        raise

    duration_ms = int((perf_counter() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    log_event(
        logger,
        "INFO",
        "http.request.end",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    reset_request_id(token)
    return response


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
