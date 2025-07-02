import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

from config import USER_DB

Base = declarative_base()


async def ensure_database_exists(db_url: str, db_name: str):
    logging.info(f"[ensure_database_exists] Получен db_url: {db_url}")
    logging.info(f"[ensure_database_exists] Проверяем наличие базы: {db_name}")

    temp_engine = create_async_engine(
        db_url.rsplit('/', 1)[0] + "/",
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True
    )

    logging.info(f"[ensure_database_exists] Создан движок с URL: {db_url.rsplit('/', 1)[0] + '/'}")

    try:
        async with temp_engine.connect() as conn:
            logging.info("[ensure_database_exists] Установлено соединение с сервером")

            result = await conn.execute(
                text(f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{db_name}'"))
            db_exists = result.scalar()
            logging.info(f"[ensure_database_exists] Существование базы: {bool(db_exists)}")

            if not db_exists:
                logging.info(f"[ensure_database_exists] База не найдена. Пытаемся создать: {db_name}")
                await conn.execute(
                    text(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                logging.info(f"[ensure_database_exists] База {db_name} успешно создана")

                # ВНИМАНИЕ: переменной USER_DB тут нет
                logging.warning(f"[ensure_database_exists] GRANT пропущен — {USER_DB} не определён!")

                # Если хочешь — передавай USER_DB как параметр и добавь GRANT
            else:
                logging.info(f"[ensure_database_exists] База {db_name} уже существует")

    except Exception as e:
        logging.error(f"[ensure_database_exists] Ошибка при проверке/создании базы: {e}")
        raise
    finally:
        await temp_engine.dispose()
        logging.info("[ensure_database_exists] Движок освобождён")
