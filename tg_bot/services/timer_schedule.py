import asyncio
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from config import MANAGER, ADMIN, REMINDER_TEXT_HOUR, REMINDER_TEXT_MINUTES
from tg_bot.essence.balance import Balance
from tg_bot.essence.dishes import DishModel
from tg_bot.essence.groups import GroupModel
from tg_bot.essence.items_in_order import ItemsOrderModel
from tg_bot.essence.orders import Order, OrderModel
from tg_bot.essence.users import User
from tg_bot.essence.weekly_menu import WeeklyMenuModel
from tg_bot.services.create_text_total_lunch_order import lunch_picker
from tg_bot.services.days_operations import days_week, next_work_day_string
from tg_bot.services.parse_menu import get_dict_all_dishes
from tg_bot.services.resources import Messages
from tg_bot.services.send_message_bot import send_message_bot
from tg_bot.services.statuses import StatusOrder


async def get_menu_by_kind(session: AsyncSession, path_pdf_file: str) -> bool:
    dishes_dict = await get_dict_all_dishes(path_pdf_file)

    if not dishes_dict:
        return False

    # Удаляем старые данные
    await session.execute(delete(ItemsOrderModel))
    await session.execute(delete(OrderModel))
    await session.execute(delete(WeeklyMenuModel))
    await session.execute(delete(DishModel))
    await session.execute(delete(GroupModel))
    await session.commit()

    # Вставляем группы
    group_names = list({cat for categories in dishes_dict.values() for cat in categories})
    group_list = [{"name": name} for name in group_names]

    await session.execute(insert(GroupModel), group_list)
    await session.commit()

    # Получаем id-шники групп
    result = await session.execute(select(GroupModel))
    groups = result.scalars().all()
    group_map = {g.name: g.id for g in groups}

    # Подготовка блюд
    dish_list = []
    seen_dish_names = set()
    for day, categories in dishes_dict.items():
        for category, dishes in categories.items():
            for dish in dishes:
                dish_name = dish["name"]
                if dish_name in seen_dish_names:
                    continue  # пропускаем дубликаты
                seen_dish_names.add(dish_name)
                dish_list.append({
                    "name": dish["name"],
                    "weight": dish["weight"],
                    "amount": dish["price"],
                    "group_id": group_map[category]
                })

    await session.execute(insert(DishModel), dish_list)
    await session.commit()

    # Получаем id-шники блюд
    result = await session.execute(select(DishModel))
    dishes = result.scalars().all()
    dish_map = {(d.name, d.group_id): d.id for d in dishes}
    # Подготовка меню
    menu_list = []
    for day, categories in dishes_dict.items():
        day_number = next(k for k, v in days_week.items() if v == day)
        for category, dishes in categories.items():
            group_id = group_map[category]
            for dish in dishes:
                dish_name = dish["name"]
                dish_id = dish_map.get((dish_name, group_id))
                if dish_id:
                    menu_list.append({
                        "day_id": day_number + 1,
                        "dish_id": dish_id
                    })

    await session.execute(insert(WeeklyMenuModel), menu_list)
    await session.commit()

    return True


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
                await send_message_bot(user.telegram_id, Messages.REMINDER_TEXT.format(next_work_date=next_work_date,
                                                                                       hour=REMINDER_TEXT_HOUR,
                                                                                       minute=REMINDER_TEXT_MINUTES))
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
        if Messages.CODE_OPEN_TAG in part and Messages.CODE_CLOSE_TAG not in part:
            part += Messages.CODE_CLOSE_TAG
        elif Messages.CODE_CLOSE_TAG in part and Messages.CODE_OPEN_TAG not in part:
            part = Messages.CODE_OPEN_TAG + part

        messages.append(part)

    if text:
        if Messages.CODE_OPEN_TAG in text and Messages.CODE_CLOSE_TAG not in text:
            text += Messages.CODE_CLOSE_TAG
        elif Messages.CODE_CLOSE_TAG in text and Messages.CODE_OPEN_TAG not in text:
            text = Messages.CODE_OPEN_TAG + text
        messages.append(text)

    # Отправляем сообщения
    for message in messages:
        await send_message_bot(ADMIN, message)
        await asyncio.sleep(1)
    for message in messages:
        await send_message_bot(MANAGER, message)
        await asyncio.sleep(1)

    # Обновляем статусы заказов
    next_work_date = await next_work_day_string()
    if next_work_date:
        order_table = Order(session)
        await order_table.close_orders_by_date(next_work_date)


async def resetting_the_balance(session: AsyncSession):
    """
    Обнуление баланса у всех пользователей
    """
    balance_table = Balance(session)
    await balance_table.reset_all_balances()


if __name__ == "__main__":
    pass
