from asyncio.log import logger
from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import Column, Integer, String, select, update, delete, BigInteger, Date, literal, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import relationship

from tg_bot.services.statuses import StatusOrder
from tg_bot.essence.base_model import Base


@dataclass
class OrderData:
    id: int
    user_id: int
    amount: int
    status: str
    date: str
    dish_id: Optional[int] = None


class OrderModel(Base):
    """Модель SQLAlchemy для таблицы orders"""
    __tablename__ = 'orders'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)  # Предполагается, что users(telegram_id) существует
    amount = Column(Integer, default=0)
    status = Column(String(20), default=StatusOrder.CREATE.value)
    date = Column(Date, nullable=False)  # Можно использовать Date для дат
    item_associations = relationship("ItemsOrderModel", back_populates="order")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uq_user_date'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    )


class Order:
    _fields = ("id", "user_id", "amount", "status", "date")

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    def _to_order_data(self, order) -> Optional[OrderData]:
        """Конвертирует SQLAlchemy модель в OrderData"""
        if not order:
            return None
        return OrderData(**{f: getattr(order, f) for f in self._fields})

    async def create_order(self, user_id: int, date: str) -> int | Column[int] | None:
        """
        Создает новый заказ, если его еще нет для данного пользователя и даты.
        Возвращает ID заказа или None в случае ошибки.
        """
        try:
            # Сначала проверяем существующий заказ
            existing_order = await self.session.execute(
                select(OrderModel.id)
                .where(OrderModel.user_id == literal(user_id))
                .where(OrderModel.date == literal(date))
            )
            order = existing_order.scalar_one_or_none()

            if order:
                return order  # Возвращаем ID существующего заказа

            # Создаем новый заказ
            new_order = OrderModel(user_id=user_id, date=date)
            self.session.add(new_order)
            await self.session.commit()
            await self.session.refresh(new_order)

            return new_order.id

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating order for user {user_id} on {date}: {e}")
            return None

    async def _get_order_by_conditions(self, *conditions) -> Optional[OrderData]:
        result = await self.session.execute(
            select(OrderModel).where(*conditions)
        )
        return self._to_order_data(result.scalar_one_or_none())

    async def _get_orders_by_conditions(self, *conditions) -> List[OrderData]:
        result = await self.session.execute(
            select(OrderModel).where(*conditions)
        )
        return [self._to_order_data(order) for order in result.scalars()]

    async def get_order_by_id(self, order_id: int) -> Optional[OrderData]:
        """Получает заказ по ID"""
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.id == literal(order_id))
        )
        return self._to_order_data(result.scalar_one_or_none())

    async def get_id_order_by_user_id_and_date(self, user_id: int, date: str,
                                               status: str = StatusOrder.CREATE.value) -> Optional[int]:
        result = await self.session.execute(
            select(OrderModel.id)
            .where(OrderModel.user_id == literal(user_id),
                   OrderModel.date == literal(date),
                   OrderModel.status == literal(status))
        )
        return result.scalar_one_or_none()

    async def get_order_by_user_id_and_date_status(self, user_id: int, date: str,
                                                   status: str = StatusOrder.CREATE.value) -> Optional[OrderData]:
        """Получает заказ по user_id, дате и статусу"""
        result = await self.session.execute(
            select(OrderModel)
            .where(OrderModel.user_id == literal(user_id))
            .where(OrderModel.date == literal(date))
            .where(OrderModel.status == literal(status))
        )
        order = result.scalar_one_or_none()
        return OrderData(**{f: getattr(order, f) for f in self._fields}) if order else None

    async def get_order_by_user_id_and_date(self, user_id: int, date: str) -> Optional[OrderData]:
        """Получает заказ по user_id и дате"""
        result = await self.session.execute(
            select(OrderModel)
            .where(OrderModel.user_id == literal(user_id))
            .where(OrderModel.date == literal(date))
        )
        order = result.scalar_one_or_none()
        return OrderData(**{f: getattr(order, f) for f in self._fields}) if order else None

    async def get_all_orders_by_date(self, date: str) -> List[OrderData]:
        return await self._get_orders_by_conditions(OrderModel.date == date)

    async def get_orders_by_user_id(self, user_id: int) -> List[OrderData]:
        return await self._get_orders_by_conditions(OrderModel.user_id == user_id)

    async def get_confirm_orders_by_date(self, date: str) -> List[OrderData]:
        return await self._get_orders_by_conditions(
            OrderModel.status != StatusOrder.CLOSE.value,
            OrderModel.date == date
        )

    async def update_order(self, user_id: int, date: str, **kwargs):
        """Обновляет данные заказа"""
        try:
            await self.session.execute(
                update(OrderModel)
                .where(OrderModel.user_id == literal(user_id))
                .where(OrderModel.date == literal(date))
                .values(**kwargs)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error updating order: {e}")

    async def delete_order(self, order_id: int):
        """Удаляет заказ по ID"""
        try:
            await self.session.execute(
                delete(OrderModel).where(OrderModel.id == literal(order_id))
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error deleting order: {e}")

    async def update_orders_by_date(self, date: str):
        """Закрывает все заказы на указанную дату"""
        try:
            await self.session.execute(
                update(OrderModel)
                .where(OrderModel.date == literal(date))
                .values(status=StatusOrder.CLOSE.value)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error updating orders by date: {e}")

    async def delete_orders_by_date(self, date):
        """Удаляет заказы за указанную дату"""
        try:
            await self.session.execute(
                delete(OrderModel).where(OrderModel.date == date)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error deleting order: {e}")

    async def delete_all_orders(self):
        """Удаляет все заказы"""
        try:
            await self.session.execute(
                delete(OrderModel)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error deleting order: {e}")
