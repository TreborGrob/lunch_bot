import logging

from sqlalchemy import Column, Integer, ForeignKey, select, func, update, delete, BigInteger, literal, exists, \
    UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import insert
from tg_bot.essence.dishes import DishData, DishModel
from tg_bot.essence.base_model import Base


class ItemsOrderModel(Base):
    """Модель SQLAlchemy для таблицы items_order"""
    __tablename__ = 'items_order'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(BigInteger, ForeignKey('orders.id'), nullable=False)
    dish_id = Column(BigInteger, ForeignKey('dishes.id'), nullable=False)
    count = Column(Integer, default=0)
    dish = relationship("DishModel", back_populates="order_associations")
    order = relationship("OrderModel", back_populates="item_associations")
    __table_args__ = (
        UniqueConstraint('order_id', 'dish_id', name='uq_order_dish'),
    )


class ItemsOrder:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу (обычно вызывается при старте приложения)"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    async def add_dish_to_order(self, order_id: int, dish_id: int, count: int = 1) -> bool:
        """
        Добавляет блюдо в заказ или обновляет количество.
        Возвращает True при успехе, False при ошибке.
        """
        try:
            # Проверяем существование блюда
            dish_exists = await self.session.execute(
                select(exists().where(DishModel.id == dish_id)))
            if not dish_exists.scalar():
                logging.error(f"Dish {dish_id} does not exist")
                return False

            # Добавляем или обновляем блюдо в заказе
            stmt = (
                insert(ItemsOrderModel)
                .values(order_id=order_id, dish_id=dish_id, count=count)
                .on_duplicate_key_update(
                    count=ItemsOrderModel.count + count
                )
            )

            await self.session.execute(stmt)
            await self.session.commit()
            return True

        except Exception as e:
            await self.session.rollback()
            logging.error(f"Error adding dish {dish_id} to order {order_id}: {e}")
            return False

    async def get_dishes_for_order(self, order_id: int) -> list[dict]:
        """
        Возвращает список блюд в заказе с их количеством
        Формат: [{'dish': DishData, 'count': int}, ...]
        """
        result = await self.session.execute(
            select(DishModel, ItemsOrderModel.count)
            .join(ItemsOrderModel, DishModel.id == ItemsOrderModel.dish_id)
            .where(ItemsOrderModel.order_id == literal(order_id))
        )

        dishes = []
        for dish, count in result.all():
            dish_data = DishData(
                id=dish.id,
                name=dish.name,
                weight=dish.weight,
                amount=dish.amount,
                compound=dish.compound,
                image_url=dish.image_url,
                calories=dish.calories,
                group_id=dish.group_id
            )
            dishes.append({'dish': dish_data, 'count': count})

        return dishes

    async def remove_dish_from_order(self, order_id: int, dish_id: int):
        """
        Удаляет блюдо из заказа или уменьшает его количество
        """
        try:
            # Получаем текущее количество
            count_result = await self.session.execute(
                select(ItemsOrderModel.count)
                .where(ItemsOrderModel.order_id == literal(order_id))
                .where(ItemsOrderModel.dish_id == literal(dish_id))
            )
            count = count_result.scalar_one_or_none()

            if count:
                if count > 1:
                    # Уменьшаем количество
                    await self.session.execute(
                        update(ItemsOrderModel)
                        .where(ItemsOrderModel.order_id == literal(order_id))
                        .where(ItemsOrderModel.dish_id == literal(dish_id))
                        .values(count=ItemsOrderModel.count - 1)
                    )
                else:
                    # Удаляем полностью
                    await self.session.execute(
                        delete(ItemsOrderModel)
                        .where(ItemsOrderModel.order_id == literal(order_id))
                        .where(ItemsOrderModel.dish_id == literal(dish_id))
                    )
                await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            logging.error(f"Error removing dish from order: {e}")

    async def get_amount_for_order(self, order_id: int) -> int:
        """
        Возвращает общее количество порций в заказе
        """
        result = await self.session.execute(
            select(func.coalesce(func.sum(DishModel.amount * ItemsOrderModel.count), 0))
            .select_from(ItemsOrderModel)
            .join(DishModel, DishModel.id == ItemsOrderModel.dish_id)
            .where(ItemsOrderModel.order_id == literal(order_id))
        )
        return result.scalar_one()

    async def delete_all_items_in_all_orders(self):
        """Удаляет заказы за указанную дату"""
        try:
            result = await self.session.execute(delete(ItemsOrderModel))
            deleted_count = result.rowcount
            logging.info(f"Deleted {deleted_count} items from all orders")
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            logging.error(f"Error deleting order: {e}")
