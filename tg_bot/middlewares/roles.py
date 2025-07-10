from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable
from config import ADMIN, MANAGER


class RoleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id

        if user_id == ADMIN:
            data["role"] = "admin"
        elif user_id in (ADMIN, MANAGER):
            data["role"] = "manager"
        else:
            data["role"] = "user"

        return await handler(event, data)
