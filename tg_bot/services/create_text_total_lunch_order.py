from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession

from config import MIN_AMOUNT_ORDER
from tg_bot.essence.groups import Group
from tg_bot.essence.orders import Order
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.users import User
from tg_bot.services.days_operations import next_work_day_string
from tg_bot.services.resources import Messages
from collections import Counter


async def lunch_picker(session: AsyncSession) -> str:
    next_date = await next_work_day_string()
    orders_data = await get_orders_with_dishes(session, next_date)

    # Получаем всех активных пользователей
    user_repo = User(session)
    all_active_users = await user_repo.get_all_active_users()
    # Находим пользователей без заказов
    # users_with_orders = {data["user"].telegram_id for data in orders_data}
    users_with_orders = []
    for data in orders_data:
        users_with_orders.append(data["user"].telegram_id)
    users_without_orders = [user for user in all_active_users if user.telegram_id not in users_with_orders]
    # Если есть пользователи без заказов и есть хотя бы один заказ
    if users_without_orders and orders_data:
        # Находим самый дорогой заказ
        most_expensive_order = max(orders_data, key=lambda x: x["amount_order"])

        # Копируем этот заказ для пользователей без заказов
        for user in users_without_orders:
            copied_order = {
                "user": user,
                "dishes": most_expensive_order["dishes"].copy(),
                "amount_order": most_expensive_order["amount_order"]
            }
            orders_data.append(copied_order)

    result_lines = []
    user_dishes_list = []

    for data in orders_data:
        result_lines.append(format_user_order(data["user"], data["dishes"], data["amount_order"]))
        user_dishes_list.append(data["dishes"])
    group_names = ["Гарниры", "Вторые блюда", "Добавки", "Блюда Завтрака (до 10:00)"]
    group_ids = await get_group_ids_by_names(session, group_names)

    group_map = {
        "garnish": group_ids["Гарниры"],
        "main_course": group_ids["Вторые блюда"],
        "addon": group_ids["Добавки"],
        "breakfast": group_ids["Блюда Завтрака (до 10:00)"]
    }
    total_block = format_total_order(user_dishes_list, group_map)
    return "".join(result_lines) + "Общий заказ:\n\n" + Messages.CODE_OPEN_TAG + total_block + Messages.CODE_CLOSE_TAG


async def get_orders_with_dishes(session, date):
    order_repo = Order(session)
    items_order_repo = ItemsOrder(session)
    user_repo = User(session)

    orders = await order_repo.get_confirm_orders_by_date(date)
    results = []

    for order in orders:
        if order.amount < MIN_AMOUNT_ORDER:
            continue
        dishes_raw = await items_order_repo.get_dishes_for_order(order.id)
        user = await user_repo.get_user_by_tg_id(order.user_id)

        if not user:
            continue

        dish_counter = defaultdict(int)
        for item in dishes_raw:
            dish_counter[item["dish"]] += item["count"]

        results.append({
            "user": user,
            "dishes": dish_counter,
            "amount_order": order.amount
        })

    return results


def format_user_order(user, dishes: dict, amount_order) -> str:
    if not dishes:
        return ""
    text = f"{user.username} {user.phone_number} заказал на {amount_order}:\n"
    for dish, count in dishes.items():
        text += f"{dish.name} - {count}\n"
    return text + "\n"


async def get_group_ids_by_names(session: AsyncSession, names: list[str]) -> dict[str, int]:
    group_repo = Group(session)
    result = await group_repo.get_all_groups()
    name_to_id = {g.name.lower(): g.id for g in result}

    return {
        name: name_to_id[name.lower()]
        for name in names
        if name.lower() in name_to_id
    }


def format_total_order(dishes_by_user: list[dict], group_map: dict[str, int]) -> str:
    portion_counter = Counter()

    def distribute_portions(garnish, main, addon, breakfast_sausage):
        groups = [garnish, main, breakfast_sausage, addon]
        max_len = max(len(g) for g in groups) if groups else 0

        combos = []
        for i in range(max_len):
            combo = []
            for group in groups:
                if i < len(group):
                    combo.append(group[i][0])
            combos.append(tuple(sorted(combo)))
        return combos

    for dishes in dishes_by_user:
        garnish = []
        main = []
        addon = []
        breakfast_sausage = []
        leftovers = {}
        syrnik_count = 0
        sgushenka_count = 0

        for dish, count in dishes.items():
            name = dish.name
            group_id = dish.group_id
            lname = name.lower()

            if "сырник" in lname:
                syrnik_count += count
                continue
            elif "сгущ" in lname:
                sgushenka_count += count
                continue

            if group_id == group_map["garnish"]:
                garnish.extend([(name,)] * count)
            elif group_id == group_map["main_course"]:
                main.extend([(name,)] * count)
            elif group_id == group_map["addon"]:
                addon.extend([(name,)] * count)
            elif group_id == group_map["breakfast"] and lname.startswith("сосиска"):
                breakfast_sausage.extend([(name,)] * count)
            else:
                leftovers[name] = leftovers.get(name, 0) + count

        # сгущёнка + сырник
        if sgushenka_count > 0 and syrnik_count > 0:
            part = f"Сырник * {syrnik_count}" if syrnik_count > 1 else "Сырник"
            sgushenka_part = f"Сгущенка * {sgushenka_count}" if sgushenka_count > 1 else "Сгущенка"
            portion_counter[((sgushenka_part,), (part,),)] += 1
        else:
            if syrnik_count > 0:
                syrnik_part = f"Сырник * {syrnik_count}"
                portion_counter[((syrnik_part,),)] += 1
            if sgushenka_count > 0:
                sg_part = f"Сгущенка * {sgushenka_count}"
                portion_counter[((sg_part,),)] += 1

        # группируем гарнир + (второе|сосиска) + добавки отдельно, распределяя одинаковые блюда по разным порциям
        if garnish and (main or breakfast_sausage):
            combos = distribute_portions(garnish, main, addon, breakfast_sausage)
            for combo in combos:
                portion_counter[combo] += 1
        else:
            for lst in [garnish, main, addon, breakfast_sausage]:
                for (name,) in lst:
                    portion_counter[((name,),)] += 1

        # добавляем leftovers
        for name, count in leftovers.items():
            portion_counter[((name,),)] += count

    # форматируем итог
    lines = []
    for portion, count in portion_counter.items():
        seen = {}
        for name in portion:
            seen[name] = seen.get(name, 0) + 1

        parts = []
        for name, qty in seen.items():
            # name - кортеж, берем первый элемент
            dish_name = name[0] if isinstance(name, tuple) else name
            part = f"{dish_name} * {qty}" if qty > 1 else dish_name
            parts.append(part)

        line = " + ".join(parts)
        lines.append(f"{line} - {count}")

    return "\n".join(lines)

