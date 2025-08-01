from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import DATABASE_URL


def get_engine():
    return create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=5,
        pool_use_lifo=True,
        pool_recycle=3600,
        pool_pre_ping=True
    )


def get_session_pool():
    engine = get_engine()
    return async_sessionmaker(engine, expire_on_commit=False), engine
