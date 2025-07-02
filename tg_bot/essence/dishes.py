from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import select, update, delete, BigInteger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from tg_bot.essence.base_model import Base


class DishModel(Base):
    """Модель SQLAlchemy для таблицы dishes"""
    __tablename__ = 'dishes'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(40), unique=True)
    weight = Column(String(20))
    amount = Column(Integer, nullable=False)
    compound = Column(Text)
    image_url = Column(String(255))
    calories = Column(String(20))
    group_id = Column(BigInteger)
    order_associations = relationship("ItemsOrderModel", back_populates="dish")


@dataclass
class DishData:
    id: int
    name: str
    weight: str
    amount: int
    compound: str
    image_url: Optional[str]
    calories: Optional[str]
    group_id: Optional[int]


class Dish:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу (обычно вызывается при старте приложения)"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    # Create
    async def create_dish(self, name: str, weight: str, amount: int,
                          compound: str, image_url: Optional[str] = None,
                          calories: Optional[str] = None,
                          group_id: Optional[int] = None) -> Optional[int]:
        """
        Создает новое блюдо или возвращает ID существующего
        Возвращает ID блюда или None в случае ошибки
        """
        try:
            dish = DishModel(
                name=name,
                weight=weight,
                amount=amount,
                compound=compound,
                image_url=image_url,
                calories=calories,
                group_id=group_id
            )

            # Пытаемся добавить новое блюдо, игнорируя конфликты
            self.session.add(dish)
            await self.session.flush()

            # Если блюдо с таким именем уже существует, получаем его ID
            if not dish.id:
                result = await self.session.execute(
                    select(DishModel.id).where(DishModel.name == name)
                )
                existing_dish = result.scalar_one_or_none()
                return existing_dish

            await self.session.commit()
            return dish.id
        except Exception as e:
            await self.session.rollback()
            print(f"Error creating dish: {e}")
            return None

    # Read
    async def get_dish_by_id(self, dish_id: int) -> Optional[DishData]:
        """Получает блюдо по ID"""
        result = await self.session.execute(
            select(DishModel).where(DishModel.id == dish_id)
        )
        dish = result.scalar_one_or_none()
        return DishData(*dish.__dict__.values()) if dish else None

    async def get_dish_by_group_id(self, group_id: int) -> List[DishData]:
        """Получает все блюда по group_id"""
        result = await self.session.execute(
            select(DishModel).where(DishModel.group_id == group_id)
        )
        dishes = result.scalars().all()
        return [DishData(*dish.__dict__.values()) for dish in dishes]

    async def get_all_dishes(self) -> List[DishData]:
        """Получает все блюда"""
        result = await self.session.execute(select(DishModel))
        dishes = result.scalars().all()
        return [DishData(*dish.__dict__.values()) for dish in dishes]

    # Update
    async def update_dish(self, dish_id: int, **kwargs):
        """Обновляет данные блюда"""
        try:
            await self.session.execute(
                update(DishModel)
                .where(DishModel.id == dish_id)
                .values(**kwargs)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error updating dish: {e}")

    # Delete
    async def delete_dishes(self):
        """Удаляет все блюда (очищает таблицу)"""
        try:
            await self.session.execute(delete(DishModel))
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error deleting dishes: {e}")

    async def get_dish_by_name(self, dish_name: str):
        result = await self.session.execute(select(DishModel).where(DishModel.name == dish_name))
        dish = result.scalar_one_or_none()
        return DishData(*dish.__dict__.values()) if dish else None
