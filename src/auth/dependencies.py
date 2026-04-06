from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from src.database import Session
from src.models import APIKey, DashboardUser
from src.auth.repository import APIKeyRepository, AuthRepository
from src.auth.service import APIKeyService, AuthService
from src.auth.utils import hash_api_key
from src.logging_utils import get_logger, log_event


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
logger = get_logger(__name__)


def get_auth_repository(db: Session):
    return AuthRepository(db)


def get_auth_service(
    repo: Annotated[AuthRepository, Depends(get_auth_repository)],
):
    return AuthService(repo=repo)


def get_api_key_repo(db: Session):
    return APIKeyRepository(db)


def get_api_key_service(
    repo: Annotated[APIKeyRepository, Depends(get_api_key_repo)],
):
    return APIKeyService(repo=repo)


async def get_current_dashboard_user(
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> DashboardUser:
    return await auth_svc.get_current_user_from_token(token)


async def verify_api_key(
    request: Request,
    api_key_repo: Annotated[APIKeyRepository, Depends(get_api_key_repo)],
) -> APIKey:
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        log_event(logger, "WARNING", "auth.api_key.verify.missing_header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )

    key_hash = hash_api_key(raw_key)
    api_key = await api_key_repo.get_by_hash(key_hash)
    if api_key is None or not api_key.is_active:
        log_event(logger, "WARNING", "auth.api_key.verify.invalid_or_inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key.",
        )

    await api_key_repo.update_last_used(api_key)
    await api_key_repo.commit()
    log_event(
        logger,
        "INFO",
        "auth.api_key.verify.success",
        key_id=api_key.id,
        key_prefix=api_key.key_prefix,
        user_id=api_key.created_by,
    )
    return api_key


GetAuthService = Annotated[AuthService, Depends(get_auth_service)]
GetAPIKeyService = Annotated[APIKeyService, Depends(get_api_key_service)]
GetCurrentDashboardUser = Annotated[DashboardUser, Depends(get_current_dashboard_user)]
VerifyAPIKey = Annotated[APIKey, Depends(verify_api_key)]
