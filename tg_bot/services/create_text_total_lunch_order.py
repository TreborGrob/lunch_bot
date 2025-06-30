from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from tg_bot.essence.orders import Order
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.users import User
from tg_bot.services.days_operations import next_work_day_string


async def lunch_picker(session: AsyncSession) -> str:
    """
    Формирует сводку заказов на следующий рабочий день
    Возвращает отформатированную строку с информацией о заказах
    """
    next_work_date = await next_work_day_string()
    result_lines = []
    combined_dish_counter = defaultdict(int)

    # Инициализация репозиториев
    order_repo = Order(session)
    items_order_repo = ItemsOrder(session)
    user_repo = User(session)

    # Получаем подтвержденные заказы на дату
    orders = await order_repo.get_confirm_orders_by_date(next_work_date)

    for order in orders:
        # Получаем блюда для заказа и данные пользователя
        dishes = await items_order_repo.get_dishes_for_order(order.id)
        user = await user_repo.get_user_by_tg_id(order.user_id)

        if not user:
            continue

        user_lines = []
        user_dish_counter = defaultdict(int)
        text_user = f"{user.username} {user.phone_number}"

        if dishes:
            text_user += " заказал:\n"

            # Считаем блюда для текущего пользователя
            for item in dishes:
                dish_name = item['dish'].name
                count = item['count']
                user_dish_counter[dish_name] += count
                combined_dish_counter[dish_name] += count

            # Формируем строки для пользователя
            user_lines.extend(
                f"{dish} - {count}"
                for dish, count in user_dish_counter.items()
            )

            text_user += "\n".join(user_lines)
            text_user += "\n\n"

        result_lines.append(text_user)

    # Формируем общий заказ
    total_order = "\n".join(
        f"{dish} - {count}"
        for dish, count in sorted(combined_dish_counter.items())
    )

    # Собираем итоговый результат
    result_text = "".join(result_lines)
    result_text += "Общий заказ: \n\n"
    result_text += f"<code>{total_order}</code>"

    return result_text
