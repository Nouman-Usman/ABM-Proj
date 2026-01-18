from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from ..core.config import settings_server

# Configure engine with conservative pool settings for Supabase Session mode pooler
# Session mode has strict connection limits, so we use small pool and NullPool (no connection reuse)
engine = create_async_engine(
    settings_server.DATABASE_URL,
    future=True,
    echo=True,
    pool_size=2,  # Minimal connections in pool for Supabase Session mode
    max_overflow=1,  # Allow only 1 overflow connection
    pool_pre_ping=True,  # Test connections before using them
    pool_recycle=3600,  # Recycle connections after 1 hour
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def create_tables():
    """Create all tables in database"""
    # Import models to ensure they are registered with Base
    from ..models.user import User
    from ..models.TokenLLM import TokenLLM
    from ..models.chat_message import ChatMessage
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """
    Database session dependency for HTTP requests.
    Session is automatically closed after request completes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # Explicitly close the session to return connection to pool
            await session.close()

async def get_db_for_ws():
    """
    Database session dependency specifically for WebSocket connections.
    Uses shorter session lifetime to avoid connection pool exhaustion.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # Explicitly close the session immediately
            await session.close()
