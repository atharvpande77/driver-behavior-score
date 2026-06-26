from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from src.auth.dependencies import (
    GetAPIKeyService,
    GetAuthService,
    GetCurrentDashboardUser,
    disable_usage_collection,
    GetRefreshToken,
)
from src.auth.schemas import (
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    LoginRequest,
    RenameAPIKeyRequest,
    RegisterRequest,
    RegisterResponse,
    LoginResponse,
)
from src.core.rate_limit import limiter
from src.core.config import app_settings


router = APIRouter(tags=["auth"], dependencies=[Depends(disable_usage_collection)])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(app_settings.AUTH_REGISTER_RATE_LIMIT)
async def register(
    request: Request,
    payload: RegisterRequest,
    auth_svc: GetAuthService,
):
    return await auth_svc.register(
        email=payload.email,
        password=payload.password,
        name=payload.name,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
)
@limiter.limit(app_settings.AUTH_LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    payload: LoginRequest,
    auth_svc: GetAuthService,
    response: Response
):
    login_data = await auth_svc.login(
        response=response,
        username=payload.username,
        password=payload.password,
    )
    
    return LoginResponse(
        user={
            "email": login_data["email"],
            "name": login_data["name"],
        },
        access_expires_in=login_data["access_expires_in"],
    )


@router.post(
    "/refresh",
    response_model=LoginResponse,
)
@limiter.limit(app_settings.AUTH_REFRESH_RATE_LIMIT)
async def refresh_tokens(
    request: Request,
    refresh_token: GetRefreshToken,
    auth_svc: GetAuthService,
    response: Response,
):
    refresh_data = await auth_svc.refresh(
        response=response,
        refresh_token=refresh_token,
    )
    return LoginResponse(
        user={
            "email": refresh_data["email"],
            "name": refresh_data["name"],
        },
        access_expires_in=refresh_data["access_expires_in"],
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    response: Response,
    auth_svc: GetAuthService,
):
    auth_svc.logout(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/api-keys",
    response_model=list[APIKeyResponse],
)
async def list_api_keys(
    current_user: GetCurrentDashboardUser,
    api_key_svc: GetAPIKeyService,
):
    return await api_key_svc.list_keys(current_user.id)


@router.post(
    "/api-keys",
    response_model=CreateAPIKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    payload: CreateAPIKeyRequest,
    current_user: GetCurrentDashboardUser,
    api_key_svc: GetAPIKeyService,
):
    raw_key, api_key = await api_key_svc.create_key(current_user.id, payload.name)
    return CreateAPIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        raw_key=raw_key,
    )


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    key_id: UUID,
    current_user: GetCurrentDashboardUser,
    api_key_svc: GetAPIKeyService,
):
    await api_key_svc.revoke_key(current_user.id, key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/api-keys/{key_id}",
    response_model=APIKeyResponse,
)
async def rename_api_key(
    key_id: UUID,
    payload: RenameAPIKeyRequest,
    current_user: GetCurrentDashboardUser,
    api_key_svc: GetAPIKeyService,
):
    api_key = await api_key_svc.rename_key(current_user.id, key_id, payload.name)
    return api_key


@router.post(
    "/api-keys/{key_id}/rotate",
    response_model=CreateAPIKeyResponse,
)
async def rotate_api_key(
    key_id: UUID,
    current_user: GetCurrentDashboardUser,
    api_key_svc: GetAPIKeyService,
):
    raw_key, api_key = await api_key_svc.rotate_key(current_user.id, key_id)
    return CreateAPIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        raw_key=raw_key,
    )