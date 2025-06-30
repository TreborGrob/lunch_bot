import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from config import MANAGER
from tg_bot.essence.dishes import Dish
from tg_bot.essence.groups import Group
from tg_bot.essence.orders import Order
from tg_bot.essence.users import User
from tg_bot.essence.weekly_menu import WeeklyMenu
from tg_bot.services.create_text_total_lunch_order import lunch_picker
from tg_bot.services.days_operations import days_week, next_work_day_string
from tg_bot.services.parse_menu import get_day_text_page, parse_page
from tg_bot.services.send_message_bot import send_message_bot
from tg_bot.services.statuses import StatusEmployee, StatusOrder


async def get_menu_by_kind(session: AsyncSession):
    """
    Парсит меню и сохраняет его в базу данных
    """
    dishes_table = Dish(session)
    group_table = Group(session)
    weekly_menu_table = WeeklyMenu(session)

    # Очищаем существующее меню
    await dishes_table.delete_dishes()
    await group_table.delete_groups()
    await weekly_menu_table.remove_menu()

    # Парсим меню для каждого дня недели
    for day_number, day_name in days_week.items():
        text = get_day_text_page(day_name)
        dishes_dict = parse_page(text)

        for category, dishes in dishes_dict.items():
            # Создаем группу блюд
            group_id = await group_table.create_group(category)

            # Добавляем блюда в группу
            for dish_name, dish_info in dishes.items():
                await dishes_table.create_dish(
                    name=dish_name,
                    weight=dish_info['weight'],
                    amount=dish_info["price"],
                    compound=dish_info['compound'],
                    image_url=dish_info["image"],
                    calories=dish_info['calories'],
                    group_id=group_id
                )

                # Получаем ID последнего добавленного блюда
                dish = await dishes_table.get_dish_by_name(dish_name)
                if dish:
                    await weekly_menu_table.add_dish_to_day(day_number + 1, dish.id)


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

    for user in users:
        if user.status != StatusEmployee.WORK.value:
            continue

        needs_reminder = True
        for order in orders:
            if order.user_id == user.telegram_id and order.status == StatusOrder.CONFIRM.value:
                needs_reminder = False
                break

        if needs_reminder:
            await send_message_bot(
                user.telegram_id,
                f"Не забудь выбрать обед на {next_work_date} до 13:00!"
            )
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

    # Отправляем сообщения администратору
    for message in messages:
        await send_message_bot(MANAGER, message)
        await asyncio.sleep(1)

    # Обновляем статусы заказов
    next_work_date = await next_work_day_string()
    if next_work_date:
        order_table = Order(session)
        await order_table.update_orders_by_date(next_work_date)

if __name__ == "__main__":
    pass
