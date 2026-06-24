from datetime import datetime, timezone
import uuid

from sqlalchemy import func, insert, select

from src.core.database import BaseDBRepository
from src.core.models import APIKey, DashboardUser, BlacklistedToken


class AuthRepository(BaseDBRepository):
    async def get_by_id(self, user_id: uuid.UUID) -> DashboardUser | None:
        result = await self.db.execute(
            select(DashboardUser).where(DashboardUser.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> DashboardUser | None:
        result = await self.db.execute(
            select(DashboardUser).where(DashboardUser.email == email)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        email: str,
        hashed_password: str,
        name: str,
        active: bool = True,
    ) -> DashboardUser:
        result = await self.db.execute(
            insert(DashboardUser)
            .values(
                email=email,
                password=hashed_password,
                name=name,
                active=active,
            )
            .returning(DashboardUser)
        )
        return result.scalar_one()

    async def is_refresh_token_blacklisted(self, jti: str) -> bool:
        result = await self.db.execute(
            select(func.count(BlacklistedToken.id)).where(BlacklistedToken.jti == jti)
        )
        return int(result.scalar_one() or 0) > 0

    async def blacklist_refresh_token(self, jti: str, expires_at: datetime) -> None:
        await self.db.execute(
            insert(BlacklistedToken).values(jti=jti, expires_at=expires_at)
        )
        await self.flush()


class APIKeyRepository(BaseDBRepository):
    async def count_active_by_user(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(APIKey.id))
            .where(
                APIKey.created_by == user_id,
                APIKey.is_active.is_(True),
                APIKey.expires_at.is_(None),
            )
        )
        return int(result.scalar_one() or 0)

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        result = await self.db.execute(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, key_id: uuid.UUID) -> APIKey | None:
        result = await self.db.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def is_owner_active(self, key_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(DashboardUser.active)
            .join(APIKey, APIKey.created_by == DashboardUser.id)
            .where(APIKey.id == key_id)
        )
        return bool(result.scalar_one_or_none())

    async def list_all_active_by_user(self, user_id: uuid.UUID) -> list[APIKey]:
        result = await self.db.execute(
            select(APIKey)
            .where(
                APIKey.created_by == user_id,
                APIKey.is_active.is_(True)
            )
            .order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def insert(
        self,
        created_by: uuid.UUID,
        name: str,
        key_prefix: str,
        key_hash: str,
        is_active: bool,
        last_used_at: datetime | None,
        expires_at: datetime | None = None
    ) -> APIKey:
        result = await self.db.execute(
            insert(APIKey)
            .values(
                created_by=created_by,
                name=name,
                key_prefix=key_prefix,
                key_hash=key_hash,
                is_active=is_active,
                last_used_at=last_used_at,
                expires_at=expires_at,
            )
            .returning(APIKey)
        )
        return result.scalar_one()

    async def revoke(self, api_key: APIKey) -> None:
        api_key.is_active = False
        await self.flush()

    async def update_last_used(self, api_key: APIKey) -> None:
        now = datetime.now(timezone.utc)
        if api_key.last_used_at is None or (now - api_key.last_used_at).total_seconds() > 300:
            api_key.last_used_at = now
            await self.flush()

    async def rename(self, api_key: APIKey, name: str) -> None:
        api_key.name = name
        await self.flush()


    async def set_expiry(self, api_key: APIKey, expires_at: datetime) -> None:
        api_key.expires_at = expires_at
        await self.flush()
