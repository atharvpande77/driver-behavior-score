from uuid import UUID

from fastapi import APIRouter, Response, status

from src.auth.dependencies import GetAPIKeyService, GetAuthService, GetCurrentDashboardUser
from src.auth.schemas import (
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    LoginRequest,
    RenameAPIKeyRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)


router = APIRouter(tags=['auth'])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
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
    response_model=TokenResponse,
)
async def login(
    payload: LoginRequest,
    auth_svc: GetAuthService,
):
    tokens = await auth_svc.login(
        username=payload.username,
        password=payload.password,
    )
    return TokenResponse(
        email=tokens.email,
        name=tokens.name,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_expires_in=tokens.access_expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    auth_svc: GetAuthService,
):
    tokens = await auth_svc.refresh(
        refresh_token=payload.refresh_token,
    )
    return TokenResponse(
        email=tokens.email,
        name=tokens.name,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_expires_in=tokens.access_expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
    )


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
