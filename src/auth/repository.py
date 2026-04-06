from datetime import datetime, timezone
import uuid

from sqlalchemy import insert, select

from src.database import BaseDBRepository
from src.models import APIKey, DashboardUser


class AuthRepository(BaseDBRepository):
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


class APIKeyRepository(BaseDBRepository):
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

    async def list_by_user(self, user_id: uuid.UUID) -> list[APIKey]:
        result = await self.db.execute(
            select(APIKey)
            .where(APIKey.created_by == user_id)
            .order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def insert(self, api_key: APIKey) -> APIKey:
        self.db.add(api_key)
        await self.flush()
        return api_key

    async def revoke(self, api_key: APIKey) -> None:
        api_key.is_active = False
        await self.flush()

    async def rename(self, api_key: APIKey, name: str) -> None:
        api_key.name = name
        await self.flush()

    async def update_last_used(self, api_key: APIKey) -> None:
        api_key.last_used_at = datetime.now(timezone.utc)
        await self.flush()
