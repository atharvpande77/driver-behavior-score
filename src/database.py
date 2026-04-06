from collections.abc import AsyncGenerator
from typing import Annotated
from fastapi import Depends

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

from src.config import app_settings


class Base(DeclarativeBase, MappedAsDataclass):
    pass


DATABASE_URL = getattr(app_settings, "DATABASE_URL", None)

if DATABASE_URL is None:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_async_engine(url=DATABASE_URL)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

Session = Annotated[AsyncSession, Depends(get_db_session)]


class BaseDBRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
        
    async def commit(self):
        await self.db.commit()
        
        
    async def rollback(self):
        await self.db.rollback()
        
        
    async def flush(self):
        await self.db.flush()