from typing import Annotated

from fastapi import Depends, Request, HTTPException, status, Cookie

from src.auth.repository import APIKeyRepository, AuthRepository
from src.auth.service import APIKeyService, AuthService
from src.auth.types import AuthType

from src.database import Session
from src.models import APIKey, DashboardUser


def get_access_token(access_token: Annotated[str | None, Cookie()] = None) -> str | None:
    return access_token


def get_refresh_token(refresh_token: Annotated[str | None, Cookie()] = None) -> str:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie missing.",
        )
    return refresh_token


GetAccessToken = Annotated[str | None, Depends(get_access_token)]
GetRefreshToken = Annotated[str, Depends(get_refresh_token)]


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
    request: Request,
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
    token: GetAccessToken,
) -> DashboardUser:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token cookie missing.",
        )
    user = await auth_svc.get_current_user_from_token(token)

    request.state.auth_type = AuthType.DASHBOARD
    request.state.dashboard_user_id = user.id
    
    return user


async def verify_api_key(
    request: Request,
    api_key_svc: Annotated[APIKeyService, Depends(get_api_key_service)],
) -> APIKey:
    raw_key = request.headers.get("X-API-Key")
    
    api_key = await api_key_svc.verify_api_key(raw_key or "")
    
    request.state.auth_type = AuthType.API_KEY
    request.state.api_key_id = api_key.id
    request.state.dashboard_user_id = api_key.created_by
    
    return api_key


async def disable_usage_collection(request: Request) -> None:
    request.state.collect_usage = False


GetAuthService = Annotated[AuthService, Depends(get_auth_service)]
GetAPIKeyService = Annotated[APIKeyService, Depends(get_api_key_service)]
GetCurrentDashboardUser = Annotated[DashboardUser, Depends(get_current_dashboard_user)]
VerifyAPIKey = Annotated[APIKey, Depends(verify_api_key)]



