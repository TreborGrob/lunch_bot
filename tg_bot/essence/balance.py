from asyncio.log import logger
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import Column, Integer, select, update, BigInteger, literal
from sqlalchemy.ext.asyncio import AsyncSession
from tg_bot.essence.base_model import Base


@dataclass
class BalanceData:
    id: int
    user_id: int
    balance: int


class BalanceModel(Base):
    """Модель SQLAlchemy для таблицы orders"""
    __tablename__ = 'balance'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)  # Предполагается, что users(telegram_id) существует
    balance = Column(Integer, default=0)


class Balance:
    _fields = ("id", "user_id", "balance")

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    def _to_balance_data(self, order) -> Optional[BalanceData]:
        """Конвертирует SQLAlchemy модель в BalanceData"""
        if not order:
            return None
        return BalanceData(**{f: getattr(order, f) for f in self._fields})

    async def get_balance_by_user_id(self, user_id: int) -> Optional[BalanceData]:
        """Получает баланс по user_id"""
        result = await self.session.execute(
            select(BalanceModel)
            .where(BalanceModel.user_id == literal(user_id))
        )
        order = result.scalar_one_or_none()
        return BalanceData(**{f: getattr(order, f) for f in self._fields}) if order else None

    async def update_balance(self, user_id: int, **kwargs):
        """Обновляет данные баланса"""
        try:
            await self.session.execute(
                update(BalanceModel)
                .where(BalanceModel.user_id == literal(user_id))
                .values(**kwargs)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating order: {e}")

    async def reset_all_balances(self) -> bool:
        """Обнуляет балансы всех пользователей

        Returns:
            int: Количество обновленных записей
        """
        try:
            await self.session.execute(
                update(BalanceModel)
                .values(balance=0)
            )
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error resetting all balances: {e}")
            return False
