from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import currency
from tg_bot.essence.groups import Group
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.orders import Order
from tg_bot.essence.weekly_menu import WeeklyMenu
from tg_bot.services.days_operations import next_work_day_string
from tg_bot.services.statuses import StatusOrder


def menu_markup(tg_id: int) -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Меню на след.рабочий день", callback_data='menu_tomorrow'),
        InlineKeyboardButton(text=f'Заказ ({currency})', callback_data=f'cart_{tg_id}')
    )
    return builder.as_markup()


async def groups_markup(session: AsyncSession, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура групп блюд"""
    builder = InlineKeyboardBuilder()
    group_table = Group(session)
    orders_table = Order(session)

    groups = await group_table.get_all_groups()
    date = await next_work_day_string()

    if date:
        order = await orders_table.get_order_by_user_id_and_date_status(user_id, date)

        for group in groups:
            builder.add(InlineKeyboardButton(text=group.name, callback_data=f"group_{group.id}"))

        if order and order.amount:
            builder.row(
                InlineKeyboardButton(
                    text=f"Заказ ({order.amount} {currency}) 🛒",
                    callback_data=f'cart_{user_id}'
                )
            )

    builder.adjust(1)
    return builder.as_markup()


async def items_group_markup(group_id: int, session: AsyncSession, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура блюд в группе"""
    builder = InlineKeyboardBuilder()
    date = await next_work_day_string()

    if not date:
        return builder.as_markup()

    weekly_menu_table = WeeklyMenu(session)
    items_order_table = ItemsOrder(session)
    order_table = Order(session)

    order_id = await order_table.get_id_order_by_user_id_and_date(user_id, date)
    items_in_order = []
    order = None

    if order_id:
        order = await order_table.get_order_by_id(order_id)
        dishes_in_order = await items_order_table.get_dishes_for_order(order_id)
        items_in_order = [item["dish"].id for item in dishes_in_order]

    current_datetime = datetime.now()
    day_id = current_datetime.weekday() + 2
    dishes = await weekly_menu_table.get_dishes_for_day_by_group(day_id, group_id)

    for dish in dishes:
        builder.row(
            InlineKeyboardButton(text=dish.name, callback_data=f'item_{dish.id}'),
            InlineKeyboardButton(text=f"{dish.amount} {currency}", callback_data=f'item_{dish.id}')
        )

        if order and order.status == StatusOrder.CREATE.value:
            builder.add(InlineKeyboardButton(text="✅", callback_data=f'add_cart_{dish.id}'))

        if dish.id in items_in_order:
            builder.add(InlineKeyboardButton(text="❌", callback_data=f'del_cart_{dish.id}'))

    order_amount = await items_order_table.get_amount_for_order(order_id) if order_id else 0

    builder.row(
        InlineKeyboardButton(text="🔙Назад", callback_data=f"group_{group_id}"),
        InlineKeyboardButton(
            text=f"Заказ ({order_amount} {currency}) 🛒",
            callback_data=f'cart_{user_id}'
        )
    )

    return builder.as_markup()


async def cart_items_markup(dishes: list, session: AsyncSession) -> InlineKeyboardMarkup:
    """Клавиатура корзины"""
    builder = InlineKeyboardBuilder()

    for dish in dishes:
        name = dish["dish"].name
        id_item = dish["dish"].id
        amount = dish["dish"].amount
        count = dish["count"]

        builder.row(
            InlineKeyboardButton(text=name, callback_data=f'item_{id_item}'),
            InlineKeyboardButton(text=f"{count} ед. - {count * amount} {currency}", callback_data=f'item_{id_item}'),
            InlineKeyboardButton(text="✅", callback_data=f'plus_cart_{id_item}'),
            InlineKeyboardButton(text="❌", callback_data=f'minus_cart_{id_item}')
        )

    if dishes:
        builder.row(
            InlineKeyboardButton(
                text="Заказать на след.рабочий день",
                callback_data="confirm_order"
            )
        )

    builder.row(
        InlineKeyboardButton(text="📝В меню", callback_data="menu_main")
    )

    return builder.as_markup()


async def back_menu_markup(item_id: int, group_id: int, session: AsyncSession, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура возврата в меню"""
    builder = InlineKeyboardBuilder()
    date = await next_work_day_string()

    if not date:
        return builder.as_markup()

    order_table = Order(session)
    items_order_table = ItemsOrder(session)

    order_id = await order_table.get_id_order_by_user_id_and_date(user_id, date)

    if order_id:
        order = await order_table.get_order_by_id(order_id)
        dishes_in_order = await items_order_table.get_dishes_for_order(order_id)
        items_in_order = [item["dish"].id for item in dishes_in_order]

        if order and order.status == StatusOrder.CREATE.value:
            builder.row(
                InlineKeyboardButton(text="✅", callback_data=f'add_cart_{item_id}')
            )

        if item_id in items_in_order:
            builder.add(
                InlineKeyboardButton(text="❌", callback_data=f'del_cart_{item_id}')
            )

    builder.row(
        InlineKeyboardButton(text="🔙Назад", callback_data=f"group_{group_id}"),
        InlineKeyboardButton(text="📝В меню", callback_data="menu_main")
    )

    return builder.as_markup()


def request_contact() -> ReplyKeyboardMarkup:
    """Клавиатура запроса контакта"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="Отправить контакт", request_contact=True)
    )
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=True
    )
