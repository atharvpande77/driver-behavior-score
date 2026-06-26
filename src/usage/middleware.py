import asyncio
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request

from src.core.database import async_session
from src.core.logging_utils import get_logger, log_event, reset_request_id, set_request_id
from src.usage.repository import UsageEventRepository
from src.usage.service import UsageEventService


logger = get_logger(__name__)

def _track_background_task(app: FastAPI, task: asyncio.Task[None]) -> None:
    background_tasks = getattr(app.state, "usage_background_tasks", None)
    if background_tasks is None:
        background_tasks = set()
        app.state.usage_background_tasks = background_tasks

    background_tasks.add(task)

    def _cleanup(completed_task: asyncio.Task[None]) -> None:
        background_tasks.discard(completed_task)
        try:
            exc = completed_task.exception()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("event=usage.persist.background_task_error")
        else:
            if exc is not None:
                logger.error("event=usage.persist.background_task_error error=%s", exc)

    task.add_done_callback(_cleanup)


def _schedule_usage_persistence(
    app: FastAPI,
    request: Request,
    *,
    total_latency_ms: float,
    http_status_code: int,
    error_type: str | None,
) -> None:
    async def _persist() -> None:
        async with async_session() as session:
            repo = UsageEventRepository(session)
            service = UsageEventService(repo=repo)
            await service.persist_request_usage(
                request=request,
                total_latency_ms=total_latency_ms,
                http_status_code=http_status_code,
                error_type=error_type,
            )

    task = asyncio.create_task(_persist())
    _track_background_task(app, task)


def register_usage_event_collection_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def usage_event_collection_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        token = set_request_id(request_id)
        request.state.request_id = request_id
        if getattr(request.state, "collect_usage", True):
            request.state.stats_per_vehicle = []
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
        except Exception as exc:
            duration_ms = int((perf_counter() - start) * 1000)
            if getattr(request.state, "collect_usage", True):
                _schedule_usage_persistence(
                    app,
                    request,
                    total_latency_ms=duration_ms,
                    http_status_code=500,
                    error_type=type(exc).__name__,
                )
            reset_request_id(token)
            raise

        duration_ms = int((perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        if getattr(request.state, "collect_usage", True):
            if response.status_code < 400:
                error_type = None
            elif response.status_code < 500:
                error_type = "ClientError"
            else:
                error_type = "ServerError"
            _schedule_usage_persistence(
                app,
                request,
                total_latency_ms=duration_ms,
                http_status_code=response.status_code,
                error_type=error_type,
            )
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
