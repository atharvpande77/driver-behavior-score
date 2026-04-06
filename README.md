# Driver Behavior Score

FastAPI backend for scoring vehicles, tracking violations, and supporting dashboard workflows for insurers.

## What it does

- Scores vehicles using the DBS engine
- Exposes violation and vehicle lookup APIs
- Supports dashboard user login, registration, refresh tokens, and API keys
- Ingests vehicle and challan data into PostgreSQL

## API Layout

- `/api/v1/score`
- `/api/v1/violations`
- `/api/v1/vehicles`
- `/auth/*`
- `/dashboard/*`

## Local Setup

1. Create a Python 3.13 environment.
2. Install dependencies with `uv sync`.
3. Configure environment variables in `.env`.
4. Run the app with:

```bash
uvicorn src.main:app --reload
```

## Required Environment

- `DATABASE_URL`
- `SUREPASS_BASE_URL`
- `SUREPASS_API_KEY`

## Notes

- Logs are structured and include request IDs.
- OpenAPI metadata is configured in `src/main.py`.
