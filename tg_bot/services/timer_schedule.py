import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from config import MANAGER, ADMIN
from tg_bot.essence.dishes import Dish
from tg_bot.essence.groups import Group
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.orders import Order
from tg_bot.essence.users import User
from tg_bot.essence.weekly_menu import WeeklyMenu
from tg_bot.services.create_text_total_lunch_order import lunch_picker
from tg_bot.services.days_operations import days_week, next_work_day_string
from tg_bot.services.parse_menu import get_day_text_page, parse_page
from tg_bot.services.send_message_bot import send_message_bot
from tg_bot.services.statuses import StatusEmployee, StatusOrder


async def get_menu_by_kind(session: AsyncSession, path_pdf_file: str):
    # Получаем словарь всех блюд
    dishes_dict = await get_dict_all_dishes(path_pdf_file)
    if dishes_dict:
        dishes_table = Dish(session)
        group_table = Group(session)
        weekly_menu_table = WeeklyMenu(session)
        items_order_table = ItemsOrder(session)
        orders_table = Order(session)

        # Очищаем существующее меню
        await dishes_table.delete_dishes()
        await group_table.delete_groups()
        await weekly_menu_table.remove_menu()
        await items_order_table.delete_all_items_in_all_orders()
        await orders_table.delete_all_orders()

        # Парсим меню для каждого дня недели
        for day, categories in dishes_dict.items():
            # Находим номер дня
            day_number = next(key for key, value in days_week.items() if value == day)
            for category, dishes in categories.items():
                # Создаем группу (категорию)
                group_id = await group_table.create_group(category)
                for dish in dishes:
                    # Извлекаем данные блюда
                    dish_name = dish['name']
                    weight = dish['weight']
                    price = dish['price']
                    # Создаем блюдо и добавляем его в меню
                    id_dish = await dishes_table.create_dish(dish_name, weight, price, group_id)
                    await weekly_menu_table.add_dish_to_day(day_number + 1, id_dish)
        return True
    else:
        return False


async def reminder(session: AsyncSession):
    """
    Отправляет напоминания пользователям, которые не подтвердили заказ
    """
    next_work_date = await next_work_day_string()
    if not next_work_date:
        return

    order_table = Order(session)
    users_table = User(session)

    users = await users_table.get_all_users()
    orders = await order_table.get_all_orders_by_date(next_work_date)

    # Создаем множество пользователей, у которых есть подтвержденный заказ
    confirmed_users = {order.user_id for order in orders if order.status in
                       {StatusOrder.CONFIRM.value, StatusOrder.CLOSE.value}}

    for user in users:
        if user.telegram_id:
            if user.telegram_id not in confirmed_users:  # Если у пользователя нет подтвержденного заказа
                await send_message_bot(user.telegram_id, f"Не забудь выбрать обед на {next_work_date} до 13:00!")
                await asyncio.sleep(1)


async def total_text_lunch_send_admin(session: AsyncSession):
    """
    Формирует и отправляет итоговый заказ администратору
    """
    # Получаем текст заказа
    text = await lunch_picker(session)
    if not text:
        return

    # Разбиваем длинный текст на части
    messages = []
    while len(text) > 4000:
        part = text[:4000]
        text = text[4000:]

        # Проверяем незакрытые HTML-теги
        if "<code>" in part and "</code>" not in part:
            part += "</code>"
        elif "</code>" in part and "<code>" not in part:
            part = "<code>" + part

        messages.append(part)

    if text:
        if "<code>" in text and "</code>" not in text:
            text += "</code>"
        elif "</code>" in text and "<code>" not in text:
            text = "<code>" + text
        messages.append(text)

    # Отправляем сообщения
    for message in messages:
        await send_message_bot(MANAGER, message)
        await asyncio.sleep(1)
        await send_message_bot(ADMIN, message)
        await asyncio.sleep(1)

    # Обновляем статусы заказов
    next_work_date = await next_work_day_string()
    if next_work_date:
        order_table = Order(session)
        await order_table.update_orders_by_date(next_work_date)

if __name__ == "__main__":
    pass
