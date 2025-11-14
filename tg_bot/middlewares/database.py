from sqlalchemy.ext.asyncio import async_sessionmaker
from aiogram import BaseMiddleware, Dispatcher
from typing import Callable, Dict, Any, Awaitable


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
            self,
            handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
            event: Any,
            data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data["session"] = session
            try:
                return await handler(event, data)
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()


def register_global_middlewares(dp: Dispatcher, session_pool: async_sessionmaker):
    """
    Регистрирует глобальные middleware для всех типов событий

    :param dp: Диспетчер aiogram
    :param session_pool: Пул асинхронных сессий SQLAlchemy
    """
    db_middleware = DatabaseMiddleware(session_pool)

    # Для всех типов сообщений
    dp.update.outer_middleware(db_middleware)

    # Альтернативно можно регистрировать для конкретных типов:
    # dp.message.middleware(db_middleware)
    # dp.callback_query.middleware(db_middleware)
    # dp.inline_query.middleware(db_middleware)
