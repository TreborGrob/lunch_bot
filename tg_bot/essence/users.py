from dataclasses import dataclass
from typing import Optional, List
from sqlalchemy import Column, Integer, String, select, update, delete, BigInteger
from sqlalchemy.ext.asyncio import AsyncSession
from tg_bot.essence.base_model import Base
from sqlalchemy import CheckConstraint


@dataclass
class UserData:
    telegram_id: int
    username: str
    phone_number: int
    status: str
    last_msg_id: int


class UserModel(Base):
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, unique=True, default=0)
    username = Column(String(50))
    phone_number = Column(BigInteger, primary_key=True, default=0)
    status = Column(String(10), default='office')
    last_msg_id = Column(Integer)

    __table_args__ = (
        CheckConstraint("status IN ('office', 'relax')", name="check_user_status"),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    )


class User:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу (обычно вызывается при старте приложения)"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    async def get_user_by_tg_id(self, tg_id: int) -> Optional[UserData]:
        """Получает пользователя по telegram_id"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.telegram_id == tg_id)
        )
        user = result.scalar_one_or_none()
        return UserData(*user.__dict__.values()) if user else None

    async def get_user_by_phone(self, phone_number: int) -> Optional[UserData]:
        """Получает пользователя по номеру телефона"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.phone_number == phone_number)
        )
        user = result.scalar_one_or_none()
        return UserData(*user.__dict__.values()) if user else None

    async def get_all_users(self) -> List[UserData]:
        """Получает всех пользователей"""
        result = await self.session.execute(select(UserModel))
        users = result.scalars().all()
        return [UserData(*user.__dict__.values()) for user in users]

    async def get_last_msg_id(self, user_id: int) -> Optional[int]:
        """Получает last_msg_id пользователя"""
        result = await self.session.execute(
            select(UserModel.last_msg_id).where(UserModel.telegram_id == user_id)
        )
        return result.scalar_one_or_none()

    async def set_last_msg_id(self, user_id: int, id_msg: int):
        """Устанавливает last_msg_id для пользователя"""
        try:
            await self.session.execute(
                update(UserModel)
                .where(UserModel.telegram_id == user_id)
                .values(last_msg_id=id_msg)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error setting last_msg_id: {e}")

    async def add_user(self, phone_number: int):
        """Добавляет нового пользователя (только phone_number)"""
        try:
            user = UserModel(phone_number=phone_number)
            self.session.add(user)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error adding user: {e}")

    async def update_user_by_id(self, telegram_id: int, **kwargs):
        """Обновляет данные пользователя по telegram_id"""
        try:
            await self.session.execute(
                update(UserModel)
                .where(UserModel.telegram_id == telegram_id)
                .values(**kwargs)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error updating user by id: {e}")

    async def update_user(self, phone_number: int, **kwargs):
        """Обновляет данные пользователя по номеру телефона"""
        try:
            await self.session.execute(
                update(UserModel)
                .where(UserModel.phone_number == phone_number)
                .values(**kwargs)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error updating user: {e}")

    async def delete_user(self, phone_number: int):
        """Удаляет пользователя по номеру телефона"""
        try:
            await self.session.execute(
                delete(UserModel).where(UserModel.phone_number == phone_number)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error deleting user: {e}")
