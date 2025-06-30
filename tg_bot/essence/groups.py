from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.mysql import insert

Base = declarative_base()


class GroupModel(Base):
    """Модель SQLAlchemy для таблицы groups"""
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(40), unique=True)


@dataclass
class GroupData:
    id: int
    name: str


class Group:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_table(self):
        """Создает таблицу (обычно вызывается при старте приложения)"""
        async with self.session.begin():
            await self.session.run_sync(Base.metadata.create_all)

    async def create_group(self, name: str) -> Optional[int]:
        """
        Создает новую группу или возвращает ID существующей
        Возвращает ID группы или None в случае ошибки
        """
        try:
            # Используем insert().on_duplicate_key_update() для MySQL
            stmt = (
                insert(GroupModel)
                .values(name=name)
                .on_duplicate_key_update(name=name)
            )

            await self.session.execute(stmt)
            await self.session.commit()

            # Получаем ID группы
            result = await self.session.execute(
                select(GroupModel.id).where(GroupModel.name == name)
            )
            group = result.scalar_one_or_none()
            return group
        except Exception as e:
            await self.session.rollback()
            print(f"Error creating group: {e}")
            return None

    async def get_all_groups(self) -> List[GroupData]:
        """Получает все группы"""
        result = await self.session.execute(select(GroupModel))
        groups = result.scalars().all()
        return [GroupData(id=group.id, name=group.name) for group in groups]

    async def delete_groups(self):
        """Удаляет все группы (очищает таблицу)"""
        try:
            await self.session.execute(delete(GroupModel))
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"Error deleting groups: {e}")