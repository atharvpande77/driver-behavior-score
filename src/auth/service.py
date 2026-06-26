from fastapi import HTTPException, status, Response
import secrets
import uuid
from datetime import datetime, timezone, timedelta

from src.core.config import app_settings
from src.core.models import APIKey, DashboardUser
from src.auth.repository import APIKeyRepository, AuthRepository

from src.auth.utils import (
    create_token,
    decode_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from src.core.logging_utils import get_logger, log_event


class AuthService:
    def __init__(self, *, repo: AuthRepository):
        self.repo = repo
        self.logger = get_logger(__name__)

    async def register(self, *, email: str, password: str, name: str) -> dict:
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
        return {
            "email": user.email,
            "name": user.name,
            "active": user.active,
        }
    

    async def login(self, response: Response, *, username: str, password: str) -> dict:
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
        
        access_token = create_token(
            subject=str(user.id),
            token_type="access",
            expires_in_seconds=access_expires_in,
        )
        refresh_jti = str(uuid.uuid4())
        refresh_token = create_token(
            subject=str(user.id),
            token_type="refresh",
            expires_in_seconds=refresh_expires_in,
            jti=refresh_jti,
        )
        
        self.set_tokens_in_response_cookies(
            response,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        
        return {
            "email": user.email,
            "name": user.name,
            "access_expires_in": access_expires_in,
        }


    async def refresh(self, response: Response, *, refresh_token: str) -> dict:
        log_event(self.logger, "INFO", "auth.refresh.attempt")
        user = await self.get_current_user_from_token(refresh_token, token_type="refresh")

        # Decode payload of old refresh token to blacklist its jti
        payload = decode_token(refresh_token, token_type="refresh")
        if payload:
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expires_at = datetime.fromtimestamp(exp, timezone.utc)
                await self.repo.blacklist_refresh_token(jti=jti, expires_at=expires_at)
                await self.repo.commit()

        access_expires_in = app_settings.JWT_ACCESS_EXPIRY_SECONDS
        refresh_expires_in = app_settings.JWT_REFRESH_EXPIRY_SECONDS
        
        access_token = create_token(
            subject=str(user.id),
            token_type="access",
            expires_in_seconds=access_expires_in,
        )
        new_refresh_jti = str(uuid.uuid4())
        refresh_token = create_token(
            subject=str(user.id),
            token_type="refresh",
            expires_in_seconds=refresh_expires_in,
            jti=new_refresh_jti,
        )
        
        self.set_tokens_in_response_cookies(
            response,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        
        log_event(self.logger, "INFO", "auth.refresh.success", email=user.email, user_id=user.id)
        return {
            "email": user.email,
            "name": user.name,
            "access_expires_in": access_expires_in,
        }

    async def get_current_user_from_token(self, token: str, token_type: str = "access") -> DashboardUser:
        payload = decode_token(token, token_type=token_type)
        if payload is None or payload.get("typ") != token_type:
            log_event(self.logger, "WARNING", f"auth.{token_type}.invalid_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired {token_type} token.",
            )

        if token_type == "refresh":
            jti = payload.get("jti")
            if not jti:
                log_event(self.logger, "WARNING", "auth.refresh.missing_jti")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload.",
                )
            is_blacklisted = await self.repo.is_refresh_token_blacklisted(jti)
            if is_blacklisted:
                log_event(self.logger, "WARNING", "auth.refresh.jti_blacklisted", jti=jti)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token.",
                )

        subject = payload.get("sub")
        if not subject:
            log_event(self.logger, "WARNING", f"auth.{token_type}.invalid_payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )

        try:
            user_uuid = uuid.UUID(subject)
        except ValueError:
            log_event(self.logger, "WARNING", f"auth.{token_type}.invalid_sub_format", subject=subject)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )

        user = await self.repo.get_by_id(user_uuid)
        if user is None:
            log_event(self.logger, "WARNING", f"auth.{token_type}.user_not_found", user_id=subject)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found.",
            )

        if not user.active:
            log_event(self.logger, "WARNING", f"auth.{token_type}.inactive_user", email=user.email, user_id=user.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive.",
            )

        log_event(self.logger, "INFO", f"auth.{token_type}.validated", email=user.email, user_id=user.id)
        return user
    
    
    def set_tokens_in_response_cookies(
        self,
        response: Response,
        *,
        access_token: str,
        refresh_token: str,
    ):
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            max_age=app_settings.JWT_ACCESS_EXPIRY_SECONDS,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/auth/refresh",
            max_age=app_settings.JWT_REFRESH_EXPIRY_SECONDS,
        )
    
    def logout(self, response: Response):
        response.delete_cookie(key="access_token", path="/")
        response.delete_cookie(key="refresh_token", path="/auth/refresh")
        log_event(self.logger, "INFO", "auth.logout.success")
    

class APIKeyService:
    MAX_ACTIVE_KEYS_PER_USER = 5

    def __init__(self, *, repo: APIKeyRepository):
        self.repo = repo
        self.logger = get_logger(__name__)

    async def verify_api_key(self, raw_key: str) -> APIKey:
        if not raw_key:
            log_event(self.logger, "WARNING", "auth.api_key.verify.missing_header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )

        key_hash = hash_api_key(raw_key)
        api_key = await self.repo.get_by_hash(key_hash)
        if api_key is None or not api_key.is_active:
            log_event(self.logger, "WARNING", "auth.api_key.verify.invalid_or_inactive")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive API key.",
            )

        owner_active = await self.repo.is_owner_active(api_key.id)
        if not owner_active:
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.verify.owner_inactive",
                key_id=api_key.id,
                user_id=api_key.created_by,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive API key.",
            )

        # Check if the key has expired (lazy deactivation)
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            await self.repo.revoke(api_key)
            await self.repo.commit()
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.verify.expired",
                key_id=api_key.id,
                user_id=api_key.created_by,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive API key.",
            )

        await self.repo.update_last_used(api_key)
        await self.repo.commit()
        log_event(
            self.logger,
            "INFO",
            "auth.api_key.verify.success",
            key_id=api_key.id,
            key_prefix=api_key.key_prefix,
            user_id=api_key.created_by,
        )
        return api_key

    async def create_key(self, user_id: uuid.UUID, name: str) -> tuple[str, APIKey]:
        log_event(self.logger, "INFO", "auth.api_key.create.attempt", user_id=user_id)
        active_key_count = await self.repo.count_active_by_user(user_id)
        if active_key_count >= self.MAX_ACTIVE_KEYS_PER_USER:
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.create.limit_reached",
                user_id=user_id,
                active_key_count=active_key_count,
                limit=self.MAX_ACTIVE_KEYS_PER_USER,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You can have at most {self.MAX_ACTIVE_KEYS_PER_USER} active API keys.",
            )

        raw_key = f"dbs_sk_{secrets.token_urlsafe(32)}"
        
        api_key = await self.repo.insert(
            created_by=user_id,
            name=name.strip(),
            key_prefix=raw_key[:12],
            key_hash=hash_api_key(raw_key),
            is_active=True,
            last_used_at=None
        )
        
        # api_key = APIKey(
        #     created_by=user_id,
        #     name=name.strip(),
        #     key_prefix=raw_key[:12],
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
        keys = await self.repo.list_all_active_by_user(user_id)
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

    async def rotate_key(
        self, user_id: uuid.UUID, key_id: uuid.UUID, grace_period_hours: int = 24
    ) -> tuple[str, APIKey]:
        log_event(
            self.logger,
            "INFO",
            "auth.api_key.rotate.attempt",
            user_id=user_id,
            key_id=key_id,
        )
        api_key = await self.repo.get_by_id(key_id)
        if api_key is None:
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.rotate.not_found",
                user_id=user_id,
                key_id=key_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found.",
            )

        if api_key.created_by != user_id:
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.rotate.forbidden",
                user_id=user_id,
                key_id=key_id,
                owner_id=api_key.created_by,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to modify this API key.",
            )

        if not api_key.is_active:
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.rotate.inactive",
                user_id=user_id,
                key_id=key_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot rotate an inactive API key.",
            )

        if api_key.expires_at is not None:
            log_event(
                self.logger,
                "WARNING",
                "auth.api_key.rotate.already_rotating",
                user_id=user_id,
                key_id=key_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key is already scheduled for expiration.",
            )

        # Set the old key to expire in grace_period_hours
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=grace_period_hours)
        await self.repo.set_expiry(api_key, expires_at)

        # Create a new key
        raw_key = f"dbs_sk_{secrets.token_urlsafe(32)}"
        new_key = await self.repo.insert(
            created_by=user_id,
            name=api_key.name,
            key_prefix=raw_key[:12],
            key_hash=hash_api_key(raw_key),
            is_active=True,
            last_used_at=None,
            expires_at=None,
        )

        await self.repo.commit()

        log_event(
            self.logger,
            "INFO",
            "auth.api_key.rotate.success",
            user_id=user_id,
            old_key_id=api_key.id,
            new_key_id=new_key.id,
        )

        return raw_key, new_key
