# AGENTS.md — Driver Behavior Score API

## Project Overview

FastAPI + PostgreSQL backend for vehicle risk scoring. Async throughout (SQLAlchemy `AsyncSession`, `asyncpg`). Two main surfaces:

- **`src/`** — HTTP API (score, violations, vehicles, dashboard, auth, usage)
- **`workers/`** — Trip detection worker that processes telematics events

Run locally with Docker Compose. Alembic manages migrations.

---

## Running & Validation

```bash
# Syntax check without a running DB
.venv/bin/python -m py_compile src/path/to/file.py

# Start services
docker compose up

# Migrations
.venv/bin/alembic upgrade head
```

There are no automated tests yet. After edits, always run `py_compile` on changed files.

---

## Code Conventions

### General
- Python 3.13+. Use `X | Y` union syntax, not `Optional[X]`.
- All dependency-injected annotated types (`GetAuthService`, `Session`, `GetCurrentDashboardUser`, etc.) are defined at the bottom of their module and use `Annotated[T, Depends(...)]`.
- Never share a single `AsyncSession` across concurrent `asyncio.gather` tasks — each task must obtain its own session.

### Service Pattern
- Routes inject services via `Depends`; services contain all business logic.
- Services return plain `dict` or dataclass results; routes map them to Pydantic response models.
- Usage stats are accumulated in `request.state.stats_per_vehicle` by services via `UsageRecorder`, then persisted by the middleware — never persist usage directly from a service or route.

### Repository Pattern
- All DB access goes through a repository class that extends `BaseDBRepository`.
- Repositories call `self.db.commit()` only via `self.commit()` (inherited helper).
- Do not call `session.commit()` directly from services or routes.

### Logging
- Always use `log_event(logger, level, event_key, **kwargs)` from `src/logging_utils.py`.
- Event keys follow the pattern `domain.subdomain.action` (e.g. `auth.login.success`).

---

## Authentication

- Tokens are stored in `HttpOnly`, `Secure`, `SameSite=Strict` cookies — never in response bodies.
- `access_token` cookie: `path="/"`, TTL = `JWT_ACCESS_EXPIRY_SECONDS`.
- `refresh_token` cookie: `path="/auth/refresh"`, TTL = `JWT_REFRESH_EXPIRY_SECONDS`.
- Cookie extraction uses `fastapi.Cookie` via `GetAccessToken` / `GetRefreshToken` in `src/auth/dependencies.py`.
- `get_current_dashboard_user` reads the access token cookie; do **not** reintroduce `OAuth2PasswordBearer`.
- Cookie writing (`set_tokens_in_response_cookies`) lives on `AuthService`, not in route handlers.
- Auth routes (`/login`, `/register`, `/refresh`) disable usage collection via `disable_usage_collection`.

---

## Trip Detection Worker

- Constants → `workers/trips/constants.py` only. Never declare them locally.
- Detection logic → `TripDetector` class in `workers/trips/detector.py` as `@classmethod` methods.
- Stateless helpers (`segment_distance`, `is_night`) → `workers/trips/utils.py` as standalone functions.

---

## Database & Migrations

- Schema changes go in `src/models.py` only — the agent may add or edit model definitions here.
- **Never run any `alembic` commands** — migration creation and application is the user's responsibility.
- **Never create migration files** inside `alembic/versions/` on your own. Only edit an existing migration file when the user explicitly asks you to fix it.
- After any model change, report: _"A migration needs to be created and applied for this change."_
- Do not use `Base.metadata.create_all` in application code.

---

## What NOT to Do

- Do not write constants inside service, util, or detector files — use `constants.py`.
- Do not return raw tokens in HTTP response bodies.
- Do not call `set_tokens_in_response_cookies` from route handlers — call it from the service.
- Do not mutate `request.state` outside of middleware and dependency functions.
- Do not use `request.cookies.get(...)` directly in routes — use the `GetAccessToken` / `GetRefreshToken` dependencies.
- **Never run `docker inspect`** or any `docker` introspection commands.
- **Never read `.env`** — to look up a config key or secret name, read `src/config.py` only.
