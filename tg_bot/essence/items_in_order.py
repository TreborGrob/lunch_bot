from sqlalchemy import Column, Integer, ForeignKey, select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import insert
from tg_bot.essence.dishes import DishData, DishModel
from tg_bot.essence.base_model import Base


class ItemsOrderModel(Base):
    """Модель SQLAlchemy для таблицы items_order"""
    __tablename__ = 'items_order'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    dish_id = Column(Integer, ForeignKey('dishes.id'), nullable=False)
    count = Column(Integer, default=0)
    dish = relationship("DishModel", back_populates="order_associations")
    order = relationship("OrderModel", back_populates="item_associations")


class ItemsOrder:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу (обычно вызывается при старте приложения)"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    async def add_dish_to_order(self, order_id: int, dish_id: int, count: int = 1):
        """
        Добавляет блюдо в заказ или увеличивает количество, если уже есть
        """
        try:
            stmt = (
                insert(ItemsOrderModel)
                .values(order_id=order_id, dish_id=dish_id, count=count)
                .on_duplicate_key_update(count=ItemsOrderModel.count + count)
            )
            await self.session.execute(stmt)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error adding dish to order: {e}")

    async def get_dishes_for_order(self, order_id: int) -> list[dict]:
        """
        Возвращает список блюд в заказе с их количеством
        Формат: [{'dish': DishData, 'count': int}, ...]
        """
        result = await self.session.execute(
            select(DishModel, ItemsOrderModel.count)
            .join(ItemsOrderModel, DishModel.id == ItemsOrderModel.dish_id)
            .where(ItemsOrderModel.order_id == order_id)
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
                .where(ItemsOrderModel.order_id == order_id)
                .where(ItemsOrderModel.dish_id == dish_id)
            )
            count = count_result.scalar_one_or_none()

            if count:
                if count > 1:
                    # Уменьшаем количество
                    await self.session.execute(
                        update(ItemsOrderModel)
                        .where(ItemsOrderModel.order_id == order_id)
                        .where(ItemsOrderModel.dish_id == dish_id)
                        .values(count=ItemsOrderModel.count - 1)
                    )
                else:
                    # Удаляем полностью
                    await self.session.execute(
                        delete(ItemsOrderModel)
                        .where(ItemsOrderModel.order_id == order_id)
                        .where(ItemsOrderModel.dish_id == dish_id)
                    )
                await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error removing dish from order: {e}")

    async def get_amount_for_order(self, order_id: int) -> int:
        """
        Возвращает общее количество порций в заказе
        """
        result = await self.session.execute(
            select(func.coalesce(func.sum(DishModel.amount * ItemsOrderModel.count), 0)
                   .join(ItemsOrderModel, DishModel.id == ItemsOrderModel.dish_id)
                   .where(ItemsOrderModel.order_id == order_id)
                   ))
        return result.scalar_one()