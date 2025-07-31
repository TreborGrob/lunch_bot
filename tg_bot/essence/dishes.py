from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import select, update, delete, BigInteger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from tg_bot.essence.base_model import Base

# TODO:

class DishModel(Base):
    """Модель SQLAlchemy для таблицы dishes"""
    __tablename__ = 'dishes'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True)
    weight = Column(String(20))
    amount = Column(Integer, nullable=False)
    compound = Column(Text)
    image_url = Column(String(255))
    calories = Column(String(20))
    group_id = Column(BigInteger)
    order_associations = relationship("ItemsOrderModel", back_populates="dish")


@dataclass(frozen=True)
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
    _fields = ('id', 'name', 'weight', 'amount', 'compound', 'image_url', 'calories', 'group_id')

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу (обычно вызывается при старте приложения)"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    @staticmethod
    def to_dish_data(dish: DishModel) -> Optional[DishData]:
        if not dish:
            return None
        return DishData(**{f: getattr(dish, f) for f in Dish._fields})

    async def _execute_query(self, query, is_many: bool = False):
        """Выполняет запрос и возвращает результат"""
        result = await self.session.execute(query)
        return result.scalars().all() if is_many else result.scalar_one_or_none()

    async def create_dish(self, **kwargs) -> Column[int] | None:  # Сомнительно !
        """
        Создает новое блюдо или возвращает ID существующего
        Возвращает ID блюда или None в случае ошибки
        """
        try:
            dish = DishModel(**kwargs)
            self.session.add(dish)
            await self.session.flush()

            if not dish.id:  # Если ID не был сгенерирован (уже существует)
                existing = await self._execute_query(
                    select(DishModel.id).where(DishModel.name == kwargs['name']))
                return existing

            await self.session.commit()
            return dish.id
        except Exception as e:
            await self.session.rollback()
            print(f"Error creating dish: {e}")
            return None

    async def get_dish_by_id(self, dish_id: int) -> Optional[DishData]:
        """Получает блюдо по ID"""
        dish = await self._execute_query(select(DishModel).where(DishModel.id == dish_id))
        return self.to_dish_data(dish)

    async def get_dish_by_name(self, name: str) -> Optional[DishData]:
        """Получает блюдо по названию"""
        dish = await self._execute_query(select(DishModel).where(DishModel.name == name))
        return self.to_dish_data(dish)

    async def get_dishes_by_condition(self, *conditions) -> List[DishData]:
        """Универсальный метод для получения списка блюд по условиям"""
        dishes = await self._execute_query(
            select(DishModel).where(*conditions),
            is_many=True
        )
        return [self.to_dish_data(d) for d in dishes]

    async def get_dish_by_group_id(self, group_id: int) -> List[DishData]:
        """Получает все блюда по group_id"""
        return await self.get_dishes_by_condition(DishModel.group_id == group_id)

    async def get_all_dishes(self) -> List[DishData]:
        """Получает все блюда"""
        return await self.get_dishes_by_condition()

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

    async def delete_dishes(self):
        """Удаляет все блюда (очищает таблицу)"""
        try:
            await self.session.execute(delete(DishModel))
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error deleting dishes: {e}")
