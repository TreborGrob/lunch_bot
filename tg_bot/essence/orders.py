from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Date, Enum, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import relationship

from tg_bot.services.statuses import StatusOrder
from tg_bot.essence.base_model import Base


@dataclass
class OrderData:
    id: int
    user_id: int
    dish_id: int
    amount: int
    status: str
    date: str


class OrderModel(Base):
    """Модель SQLAlchemy для таблицы orders"""
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)  # Предполагается, что users(telegram_id) существует
    amount = Column(Integer, default=0)
    status = Column(String(20), default=StatusOrder.CREATE.value)
    date = Column(String(100), nullable=False)  # Можно использовать Date для дат
    item_associations = relationship("ItemsOrderModel", back_populates="order")

    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4'
    }


class Order:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу (обычно вызывается при старте приложения)"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    async def create_order(self, user_id: int, date: str) -> Optional[int]:
        """
        Создает новый заказ или возвращает существующий
        Возвращает ID заказа или None в случае ошибки
        """
        try:
            # Используем INSERT ... ON DUPLICATE KEY для MySQL
            stmt = (
                insert(OrderModel)
                .values(user_id=user_id, date=date)
                .on_duplicate_key_update(user_id=user_id)
            )

            await self.session.execute(stmt)
            await self.session.commit()

            # Получаем ID заказа
            result = await self.session.execute(
                select(OrderModel.id)
                .where(OrderModel.user_id == user_id)
                .where(OrderModel.date == date)
            )
            order = result.scalar_one_or_none()
            return order
        except Exception as e:
            await self.session.rollback()
            print(f"Error creating order: {e}")
            return None

    async def get_order_by_id(self, order_id: int) -> Optional[OrderData]:
        """Получает заказ по ID"""
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.id == order_id)
        )
        order = result.scalar_one_or_none()
        return OrderData(*order.__dict__.values()) if order else None

    async def get_id_order_by_user_id_and_date(self, user_id: int, date: str,
                                               status: str = StatusOrder.CREATE.value) -> Optional[int]:
        """Получает ID заказа по user_id, дате и статусу"""
        result = await self.session.execute(
            select(OrderModel.id)
            .where(OrderModel.user_id == user_id)
            .where(OrderModel.date == date)
            .where(OrderModel.status == status)
        )
        return result.scalar_one_or_none()

    async def get_order_by_user_id_and_date_status(self, user_id: int, date: str,
                                                   status: str = StatusOrder.CREATE.value) -> Optional[OrderData]:
        """Получает заказ по user_id, дате и статусу"""
        result = await self.session.execute(
            select(OrderModel)
            .where(OrderModel.user_id == user_id)
            .where(OrderModel.date == date)
            .where(OrderModel.status == status)
        )
        order = result.scalar_one_or_none()
        return OrderData(*order.__dict__.values()) if order else None

    async def get_order_by_user_id_and_date(self, user_id: int, date: str) -> Optional[OrderData]:
        """Получает заказ по user_id и дате"""
        result = await self.session.execute(
            select(OrderModel)
            .where(OrderModel.user_id == user_id)
            .where(OrderModel.date == date)
        )
        order = result.scalar_one_or_none()
        return OrderData(*order.__dict__.values()) if order else None

    async def get_all_orders_by_date(self, date: str) -> List[OrderData]:
        """Получает все заказы на указанную дату"""
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.date == date)
        )
        orders = result.scalars().all()
        return [OrderData(*order.__dict__.values()) for order in orders]

    async def get_orders_by_user_id(self, user_id: int) -> List[OrderData]:
        """Получает все заказы пользователя"""
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.user_id == user_id)
        )
        orders = result.scalars().all()
        return [OrderData(*order.__dict__.values()) for order in orders]

    async def get_confirm_orders_by_date(self, date: str) -> List[OrderData]:
        """Получает все НЕ закрытые заказы на указанную дату"""
        result = await self.session.execute(
            select(OrderModel)
            .where(OrderModel.status != StatusOrder.CLOSE.value)
            .where(OrderModel.date == date)
        )
        orders = result.scalars().all()
        return [OrderData(*order.__dict__.values()) for order in orders]

    async def update_order(self, user_id: int, date: str, **kwargs):
        """Обновляет данные заказа"""
        try:
            await self.session.execute(
                update(OrderModel)
                .where(OrderModel.user_id == user_id)
                .where(OrderModel.date == date)
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
                delete(OrderModel).where(OrderModel.id == order_id)
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
                .where(OrderModel.date == date)
                .values(status=StatusOrder.CLOSE.value)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error updating orders by date: {e}")