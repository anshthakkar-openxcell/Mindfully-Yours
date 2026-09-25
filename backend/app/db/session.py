"""
Async SQLAlchemy engine + session factory, and the FastAPI dependency that hands a session to a
request handler. Single data spine (Postgres + pgvector) per
documnets/understanding/02_ARCHITECTURE.md §1 -- no separate database for embeddings.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=(settings.app_env == "development"),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: `db: AsyncSession = Depends(get_db)`."""
    async with AsyncSessionLocal() as session:
        yield session
