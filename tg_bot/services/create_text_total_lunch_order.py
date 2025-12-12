from collections import Counter
from sqlalchemy.ext.asyncio import AsyncSession
from config import MIN_AMOUNT_ORDER, FIX_SUM
from tg_bot.essence.balance import Balance
from tg_bot.essence.orders import Order, OrderData
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.users import User, UserData
from tg_bot.services.days_operations import next_work_day_string
from tg_bot.services.handler_dishes import dishes_in_side_items
from tg_bot.services.resources import Messages


async def lunch_picker(session: AsyncSession) -> str:
    next_date = await next_work_day_string()
    orders_data = await get_users_with_orders_without_min_amount(session, next_date)
    # Получаем всех активных пользователей
    user_repo = User(session)
    all_active_users = await user_repo.get_all_active_users()
    # Находим пользователей без заказов
    users_with_orders = {data["user"].telegram_id for data in orders_data}
    users_without_orders = [user for user in all_active_users if user.telegram_id not in users_with_orders]

    # Если есть пользователи без заказов и есть хотя бы один заказ
    if users_without_orders and orders_data:
        balance_repo = Balance(session)
        # Для каждого пользователя без заказа находим подходящий заказ
        for user in users_without_orders:
            balance_for_order = FIX_SUM
            balance_user = await balance_repo.get_balance_by_user_id(user.telegram_id)
            if balance_user:
                balance_for_order = balance_user.balance + FIX_SUM

            # Ищем подходящие заказы для конкретного пользователя
            suitable_orders = []
            for user_order in orders_data:
                order = user_order.get("order")
                if order.amount <= balance_for_order:
                    suitable_orders.append(order)
            if suitable_orders:
                # Берем максимальный по стоимости среди подходящих
                base_order = max(suitable_orders, key=lambda x: x.amount)

            else:
                # Берем минимальный по стоимости среди всех сделанных заказов
                base_order = min(orders_data, key=lambda x: x["order"].amount)["order"]

            # Копируем заказ для пользователя
            copied_order = {
                "user": user,
                "order": base_order
            }
            orders_data.append(copied_order)
    result_lines = []
    all_dishes = Counter()
    for data in orders_data:
        text, dict_dishes = await format_user_order(data.get("user"), data.get("order"), session)
        all_dishes += dict_dishes
        result_lines.append(text)
    total_block = ""
    for dish, count in all_dishes.items():
        total_block += f"{dish} - {count}\n"
    return "".join(result_lines) + "Общий заказ:\n\n" + Messages.CODE_OPEN_TAG + total_block + Messages.CODE_CLOSE_TAG


async def get_users_with_orders_without_min_amount(session, date):
    order_repo = Order(session)
    user_repo = User(session)

    orders = await order_repo.get_all_orders_by_date(date)
    results = []

    for order in orders:
        if order.amount < MIN_AMOUNT_ORDER:
            continue
        user = await user_repo.get_user_by_tg_id(order.user_id)

        if not user:
            continue

        results.append({
            "user": user,
            "order": order
        })
    return results


async def format_user_order(user: UserData, order: OrderData, session: AsyncSession) -> (str, Counter):
    items_order_table = ItemsOrder(session)
    dishes = await items_order_table.get_dishes_for_order(order.id)
    text_user = f"{user.username} {user.phone_number} заказал на {order.amount}:\n"
    user_dish_counter = Counter()
    if dishes:
        user_lines = []
        dish_counter = await dishes_in_side_items(dishes, session)
        for dish, count in dish_counter.items():
            user_dish_counter[dish] += count
        for dish, count in user_dish_counter.items():
            user_lines.append(f"{dish} - {count}")
        text_user += "\n".join(user_lines) + "\n"
    return text_user + "\n", user_dish_counter
