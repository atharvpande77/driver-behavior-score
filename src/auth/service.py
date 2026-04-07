from fastapi import HTTPException, status
import secrets
import uuid

from src.config import app_settings
from src.models import APIKey, DashboardUser
from src.auth.repository import APIKeyRepository, AuthRepository
from src.auth.types import AuthTokens
from src.auth.utils import (
    create_token,
    decode_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from src.logging_utils import get_logger, log_event


class AuthService:
    def __init__(self, *, repo: AuthRepository):
        self.repo = repo
        self.logger = get_logger(__name__)

    async def register(self, *, email: str, password: str, name: str) -> DashboardUser:
        normalized_email = email.strip().lower()
        log_event(self.logger, "INFO", "auth.register.attempt", email=normalized_email)
        existing = await self.repo.get_by_email(normalized_email)
        if existing:
            log_event(self.logger, "WARNING", "auth.register.conflict", email=normalized_email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered.",
            )

        user = await self.repo.create_user(
            email=normalized_email,
            hashed_password=hash_password(password),
            name=name.strip(),
            active=True,
        )
        await self.repo.commit()
        log_event(self.logger, "INFO", "auth.register.success", email=user.email, user_id=user.id)
        return user

    async def login(self, *, username: str, password: str) -> AuthTokens:
        email = username.strip().lower()
        log_event(self.logger, "INFO", "auth.login.attempt", email=email)
        user = await self.repo.get_by_email(email)
        if user is None or not verify_password(password, user.password):
            log_event(self.logger, "WARNING", "auth.login.invalid_credentials", email=email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        if not user.active:
            log_event(self.logger, "WARNING", "auth.login.inactive_user", email=email, user_id=user.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive.",
            )

        access_expires_in = app_settings.JWT_ACCESS_EXPIRY_SECONDS
        refresh_expires_in = app_settings.JWT_REFRESH_EXPIRY_SECONDS
        log_event(self.logger, "INFO", "auth.login.success", email=user.email, user_id=user.id)
        return AuthTokens(
            email=user.email,
            name=user.name,
            access_token=create_token(
                subject=user.email,
                token_type="access",
                expires_in_seconds=access_expires_in,
            ),
            refresh_token=create_token(
                subject=user.email,
                token_type="refresh",
                expires_in_seconds=refresh_expires_in,
            ),
            access_expires_in=access_expires_in,
            refresh_expires_in=refresh_expires_in,
        )


    async def refresh(self, *, refresh_token: str) -> AuthTokens:
        log_event(self.logger, "INFO", "auth.refresh.attempt")
        payload = decode_token(refresh_token)
        if payload is None or payload.get("typ") != "refresh":
            log_event(self.logger, "WARNING", "auth.refresh.invalid_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        subject = payload.get("sub")
        if not subject:
            log_event(self.logger, "WARNING", "auth.refresh.invalid_payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )

        user = await self.repo.get_by_email(subject)
        if user is None:
            log_event(self.logger, "WARNING", "auth.refresh.user_not_found", email=subject)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found.",
            )

        if not user.active:
            log_event(self.logger, "WARNING", "auth.refresh.inactive_user", email=user.email, user_id=user.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive.",
            )

        access_expires_in = app_settings.JWT_ACCESS_EXPIRY_SECONDS
        refresh_expires_in = app_settings.JWT_REFRESH_EXPIRY_SECONDS
        tokens = AuthTokens(
            email=user.email,
            name=user.name,
            access_token=create_token(
                subject=user.email,
                token_type="access",
                expires_in_seconds=access_expires_in,
            ),
            refresh_token=create_token(
                subject=user.email,
                token_type="refresh",
                expires_in_seconds=refresh_expires_in,
            ),
            access_expires_in=access_expires_in,
            refresh_expires_in=refresh_expires_in,
        )
        log_event(self.logger, "INFO", "auth.refresh.success", email=user.email, user_id=user.id)
        return tokens

    async def get_current_user_from_token(self, token: str) -> DashboardUser:
        payload = decode_token(token)
        if payload is None or payload.get("typ") != "access":
            log_event(self.logger, "WARNING", "auth.access.invalid_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
            )

        subject = payload.get("sub")
        if not subject:
            log_event(self.logger, "WARNING", "auth.access.invalid_payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )

        user = await self.repo.get_by_email(subject)
        if user is None:
            log_event(self.logger, "WARNING", "auth.access.user_not_found", email=subject)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found.",
            )

        if not user.active:
            log_event(self.logger, "WARNING", "auth.access.inactive_user", email=user.email, user_id=user.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive.",
            )

        log_event(self.logger, "INFO", "auth.access.validated", email=user.email, user_id=user.id)
        return user


class APIKeyService:
    def __init__(self, *, repo: APIKeyRepository):
        self.repo = repo
        self.logger = get_logger(__name__)

    async def create_key(self, user_id: uuid.UUID, name: str) -> tuple[str, APIKey]:
        log_event(self.logger, "INFO", "auth.api_key.create.attempt", user_id=user_id)
        raw_key = f"dbs_sk_{secrets.token_urlsafe(32)}"
        
        api_key = await self.repo.insert(
            created_by=user_id,
            name=name.strip(),
            key_prefix=raw_key[:8],
            key_hash=hash_api_key(raw_key),
            is_active=True,
            last_used_at=None
        )
        
        # api_key = APIKey(
        #     created_by=user_id,
        #     name=name.strip(),
        #     key_prefix=raw_key[:8],
        #     key_hash=hash_api_key(raw_key),
        #     last_used_at=None
        # )
        # await self.repo.insert(api_key)
        await self.repo.commit()
        log_event(
            self.logger,
            "INFO",
            "auth.api_key.create.success",
            user_id=user_id,
            key_id=api_key.id,
            key_prefix=api_key.key_prefix,
        )
        return raw_key, api_key

    async def list_keys(self, user_id: uuid.UUID) -> list[APIKey]:
        keys = await self.repo.list_by_user(user_id)
        log_event(self.logger, "INFO", "auth.api_key.list", user_id=user_id, count=len(keys))
        return keys

    async def revoke_key(self, user_id: uuid.UUID, key_id: uuid.UUID) -> None:
        log_event(self.logger, "INFO", "auth.api_key.revoke.attempt", user_id=user_id, key_id=key_id)
        api_key = await self.repo.get_by_id(key_id)
        if api_key is None:
            log_event(self.logger, "WARNING", "auth.api_key.revoke.not_found", user_id=user_id, key_id=key_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found.",
            )

        if api_key.created_by != user_id:
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.revoke.forbidden",
                user_id=user_id,
                key_id=key_id,
                owner_id=api_key.created_by,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to modify this API key.",
            )

        await self.repo.revoke(api_key)
        await self.repo.commit()
        log_event(self.logger, "INFO", "auth.api_key.revoke.success", user_id=user_id, key_id=key_id)

    async def rename_key(self, user_id: uuid.UUID, key_id: uuid.UUID, name: str) -> APIKey:
        log_event(self.logger, "INFO", "auth.api_key.rename.attempt", user_id=user_id, key_id=key_id)
        api_key = await self.repo.get_by_id(key_id)
        if api_key is None:
            log_event(self.logger, "WARNING", "auth.api_key.rename.not_found", user_id=user_id, key_id=key_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found.",
            )

        if api_key.created_by != user_id:
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.rename.forbidden",
                user_id=user_id,
                key_id=key_id,
                owner_id=api_key.created_by,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to modify this API key.",
            )

        await self.repo.rename(api_key, name.strip())
        await self.repo.commit()
        log_event(self.logger, "INFO", "auth.api_key.rename.success", user_id=user_id, key_id=key_id)
        return api_key
