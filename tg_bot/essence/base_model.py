import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

from config import USER_DB

Base = declarative_base()


async def ensure_database_exists(db_url: str, db_name: str):
    temp_engine = create_async_engine(
        db_url.rsplit('/', 1)[0] + "/",
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True
    )
    try:
        async with temp_engine.connect() as conn:
            # Проверяем существование базы данных
            result = await conn.execute(
                text(f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{db_name}'"))
            if not result.scalar():
                await conn.execute(
                    text(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                logging.info(f"Database {db_name} created successfully")
                await conn.execute(text(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{USER_DB}'@'%'"))
                await conn.execute(text("FLUSH PRIVILEGES"))
            else:
                logging.info(f"Database {db_name} already exists")

    except Exception as e:
        logging.error(f"Error ensuring database exists: {e}")
        raise
    finally:
        await temp_engine.dispose()
