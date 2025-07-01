from sqlalchemy import Column, Integer, String, ForeignKey, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import insert
from tg_bot.essence.dishes import DishData, DishModel
from tg_bot.essence.base_model import Base


class DayModel(Base):
    """Модель для дней недели"""
    __tablename__ = 'days'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(20), unique=True)

    # Связь с блюдами через relationship
    dishes = relationship("WeeklyMenuModel", back_populates="day")


class WeeklyMenuModel(Base):
    """Модель для связи дней недели с блюдами"""
    __tablename__ = 'weekly_menu'

    id = Column(Integer, primary_key=True, autoincrement=True)
    day_id = Column(Integer, ForeignKey('days.id'), nullable=False)
    dish_id = Column(Integer, ForeignKey('dishes.id'), nullable=False)

    # Связи с другими таблицами
    day = relationship("DayModel", back_populates="dishes")
    dish = relationship("DishModel")

    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }


class WeeklyMenu:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицы (обычно вызывается при старте приложения)"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    async def initialize_days(self):
        """Инициализирует дни недели (если еще не созданы)"""
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        try:
            for day in days:
                stmt = insert(DayModel).values(name=day).on_duplicate_key_update(name=day)
                await self.session.execute(stmt)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error initializing days: {e}")

    async def add_dish_to_day(self, day_id: int, dish_id: int):
        """Добавляет блюдо в день недели"""
        try:
            stmt = insert(WeeklyMenuModel).values(day_id=day_id, dish_id=dish_id)
            await self.session.execute(stmt)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error adding dish to day: {e}")

    async def get_dishes_for_day(self, day_id: int) -> list[DishData]:
        """Получает все блюда для указанного дня"""
        result = await self.session.execute(
            select(DishModel)
            .join(WeeklyMenuModel, DishModel.id == WeeklyMenuModel.dish_id)
            .where(WeeklyMenuModel.day_id == day_id)
        )
        dishes = result.scalars().all()
        return [DishData(*dish.__dict__.values()) for dish in dishes]

    async def get_dishes_for_day_by_group(self, day_id: int, group_id: int) -> list[DishData]:
        """Получает блюда для дня недели по group_id"""
        result = await self.session.execute(
            select(DishModel)
            .join(WeeklyMenuModel, DishModel.id == WeeklyMenuModel.dish_id)
            .where(WeeklyMenuModel.day_id == day_id)
            .where(DishModel.group_id == group_id)
        )
        dishes = result.scalars().all()
        return [DishData(*dish.__dict__.values()) for dish in dishes]

    async def remove_dish_from_day(self, day_id: int, dish_id: int):
        """Удаляет блюдо из дня недели"""
        try:
            await self.session.execute(
                delete(WeeklyMenuModel)
                .where(WeeklyMenuModel.day_id == day_id)
                .where(WeeklyMenuModel.dish_id == dish_id)
            )
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error removing dish from day: {e}")

    async def remove_menu(self):
        """Очищает меню на неделю"""
        try:
            await self.session.execute(delete(WeeklyMenuModel))
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error removing weekly menu: {e}")
