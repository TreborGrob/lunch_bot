from sqlalchemy.ext.asyncio import AsyncSession

from config import currency
from tg_bot.essence.dishes import DishData, Dish


class Messages:

    SELECT_LUNCH = "Выбор обеда на {date_tomorrow}"
    SELECT_DISHES = "Выберите из блюд"
    NEED_UPDATE_CALENDAR = "Нужно обновление календаря"
    DISH_NOT_FOUND = "Блюдо не найдено"
    ORDER_OVER_SUM = "С этим блюдом сумма заказа превысит допустимую."
    ERROR = "Произошла ошибка"
    ORDER_VOID = "Заказ пуст"
    ORDER = "Заказ"
    ORDER_NOT_FOUND = "Заказ не найден"
    ORDER_YOUR_FOR_DATE = "Твой заказ на {date}:\n"
    CODE_OPEN_TAG = "<code>"
    CODE_CLOSE_TAG = "</code>"
    BEING_LATE = "Опоздали, заявка уже отправлена.\nПриносите обед с собой."
    NO_ACCESS = "Нет прав на данную команду."
    REMINDER_TEXT = "Не забудь выбрать обед на {next_work_date} до {hour}:{minute}!"


class Buttons:

    ORDER_TEXT = "Заказ ({amount} {currency}) 🛒"
    BACK = "🔙Назад"
    ORDER_CONFIRM = "Заказать на след.рабочий день"
    IN_MENU = "📝В меню"
    SEND_CONTACT = "Отправить контакт"
    TICK = "✅"
    CROSS = "❌"


async def create_description_for_dish(item: DishData):
    description = (f"{item.name}\n\n"
                   f"{item.compound}\n\n"
                   f"Вес: {item.weight}\n\n"
                   f"Ккал: {item.calories}\n\n"
                   f"Цена: {item.amount} {currency}")
    return description


async def create_dish_for_menu(name: str, amount: int, session: AsyncSession, group_id: int, weight: int = 0,
                               compound: str = "", calories: int = 0) -> int | bool:
    dish_table = Dish(session)
    dish_id = await dish_table.create_dish(
        name=name,
        weight=f"{weight} гр.",
        amount=amount,
        compound=compound,
        image_url="",
        calories=calories,
        group_id=group_id
    )
    return dish_id
