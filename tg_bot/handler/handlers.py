from asyncio.log import logger

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import FIX_SUM, currency
from tg_bot.essence.dishes import Dish
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.orders import Order
from tg_bot.services.days_operations import next_work_day_string
from tg_bot.services.markups_keyboards import groups_markup, items_group_markup, cart_items_markup, back_menu_markup
from tg_bot.services.statuses import StatusOrder

router = Router()


@router.callback_query(F.data.startswith("group_"))
async def group_menu(
        callback: CallbackQuery,
        session: AsyncSession,
        user_id: int = None  # user_id будет автоматически извлекаться из callback
):
    if user_id is None:
        user_id = callback.from_user.id

    group_id = int(callback.data.split("_")[-1])
    try:
        await callback.message.edit_text(
            "Выберите из блюд",
            reply_markup=await items_group_markup(group_id, session, user_id)
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            "Выбери обед на завтра",
            reply_markup=await groups_markup(session, user_id)
        )


@router.callback_query(F.data.startswith("add_cart_"))
async def add_item_in_cart(
        callback: CallbackQuery,
        session: AsyncSession,
        user_id: int = None
):
    if user_id is None:
        user_id = callback.from_user.id

    date_tomorrow = await next_work_day_string()
    if not date_tomorrow:
        await callback.answer("Нужно обновление календаря")
        return

    id_dish = int(callback.data.split("_")[-1])
    items_order_table = ItemsOrder(session)
    order_table = Order(session)
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer("Блюдо не найдено")
            return

        order_id = await order_table.create_order(user_id, date_tomorrow)
        order_amount = await items_order_table.get_amount_for_order(order_id)

        if (order_amount + item.amount) > FIX_SUM:
            await callback.answer('С этим блюдом сумма заказа превысит допустимую.', show_alert=True)
        else:
            await items_order_table.add_dish_to_order(order_id, id_dish, 1)
            await order_table.update_order(user_id, date_tomorrow, amount=order_amount + item.amount)
            await callback.message.edit_reply_markup(
                reply_markup=await items_group_markup(item.group_id, session, user_id)
            )
            await callback.answer()
    except Exception as e:
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data.startswith("item_"))
async def view_item(
        callback: CallbackQuery,
        session: AsyncSession,
        user_id: int = None
):
    if user_id is None:
        user_id = callback.from_user.id

    id_dish = int(callback.data.split("_")[-1])
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer("Блюдо не найдено")
            return

        description = (f"{item.name}\n\n"
                       f"{item.compound}\n\n"
                       f"Вес: {item.weight}\n\n"
                       f"Ккал: {item.calories}\n\n"
                       f"Цена: {item.amount} {currency}")

        await callback.message.edit_text(
            description,
            reply_markup=await back_menu_markup(item.id, item.group_id, session, user_id)
        )
        await callback.answer()
    except Exception as e:
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data.startswith("del_cart_"))
async def remove_item_in_cart(
        callback: CallbackQuery,
        session: AsyncSession,  # Сессия будет автоматически инжектиться
        user_id: int = None  # Можно добавить user_id как параметр
):
    if user_id is None:
        user_id = callback.from_user.id

    date_tomorrow = await next_work_day_string()
    if not date_tomorrow:
        await callback.answer("Нужно обновление календаря")
        return

    id_dish = int(callback.data.split("_")[-1])
    items_order_table = ItemsOrder(session)  # Передаем сессию вместо connect
    order_table = Order(session)
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer("Блюдо не найдено")
            return

        order_id = await order_table.create_order(user_id, date_tomorrow)
        await items_order_table.remove_dish_from_order(order_id, item.id)
        order_amount = await items_order_table.get_amount_for_order(order_id)
        await order_table.update_order(user_id, date_tomorrow, amount=order_amount)

        await callback.message.edit_reply_markup(
            reply_markup=await items_group_markup(item.group_id, session, user_id)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in remove_item_in_cart: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data.startswith("cart_"))
async def view_cart(
        callback: CallbackQuery,
        session: AsyncSession,
        user_id: int = None
):
    if user_id is None:
        user_id = callback.from_user.id

    date = await next_work_day_string()
    if not date:
        await callback.answer("Нужно обновление календаря")
        return

    order_table = Order(session)
    items_order_table = ItemsOrder(session)

    try:
        order_id = await order_table.get_id_order_by_user_id_and_date(user_id, date)
        if not order_id:
            await callback.answer('Заказ пуст')
            return

        dishes_in_order = await items_order_table.get_dishes_for_order(order_id)
        if dishes_in_order:
            await callback.message.edit_text(
                "Заказ",
                reply_markup=await cart_items_markup(dishes_in_order, session)
            )
        else:
            await callback.answer('Заказ пуст')
    except Exception as e:
        logger.error(f"Error in view_cart: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data == "menu_main")
async def give_menu(
        callback: CallbackQuery,
        session: AsyncSession,
        user_id: int = None
):
    if user_id is None:
        user_id = callback.from_user.id

    try:
        await callback.message.edit_text(
            "Выбери обед на завтра",
            reply_markup=await groups_markup(session, user_id)
        )
    except Exception as e:
        logger.error(f"Error in give_menu: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data.startswith("plus_cart_"))
async def plus_item_in_cart(
        callback: CallbackQuery,
        session: AsyncSession,
        user_id: int = None
):
    if user_id is None:
        user_id = callback.from_user.id

    date_tomorrow = await next_work_day_string()
    if not date_tomorrow:
        await callback.answer("Нужно обновление календаря")
        return

    id_dish = int(callback.data.split("_")[-1])
    items_order_table = ItemsOrder(session)
    order_table = Order(session)
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer("Блюдо не найдено")
            return

        order_id = await order_table.get_id_order_by_user_id_and_date(user_id, date_tomorrow)
        if not order_id:
            await callback.answer("Заказ не найден")
            return

        order_amount = await items_order_table.get_amount_for_order(order_id)
        if (order_amount + item.amount) > FIX_SUM:
            await callback.answer('С этим блюдом сумма заказа превысит допустимую.', show_alert=True)
        else:
            await items_order_table.add_dish_to_order(order_id, id_dish, 1)
            await order_table.update_order(user_id, date_tomorrow, amount=order_amount + item.amount)
            order_dishes = await items_order_table.get_dishes_for_order(order_id)
            await callback.message.edit_reply_markup(
                reply_markup=await cart_items_markup(order_dishes, session)
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in plus_item_in_cart: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data.startswith("minus_cart_"))
async def minus_item_in_cart(
        callback: CallbackQuery,
        session: AsyncSession,
        user_id: int = None
):
    if user_id is None:
        user_id = callback.from_user.id

    date_tomorrow = await next_work_day_string()
    if not date_tomorrow:
        await callback.answer("Нужно обновление календаря")
        return

    id_dish = int(callback.data.split("_")[-1])
    items_order_table = ItemsOrder(session)
    order_table = Order(session)
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer("Блюдо не найдено")
            return

        order_id = await order_table.get_id_order_by_user_id_and_date(user_id, date_tomorrow)
        if not order_id:
            await callback.answer("Заказ не найден")
            return

        await items_order_table.remove_dish_from_order(order_id, item.id)
        order_amount = await items_order_table.get_amount_for_order(order_id)
        await order_table.update_order(user_id, date_tomorrow, amount=order_amount)
        order_dishes = await items_order_table.get_dishes_for_order(order_id)
        await callback.message.edit_reply_markup(
            reply_markup=await cart_items_markup(order_dishes, session)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in minus_item_in_cart: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data == "confirm_order")
async def confirm_order(
        callback: CallbackQuery,
        session: AsyncSession,
        user_id: int = None
):
    if user_id is None:
        user_id = callback.from_user.id

    date = await next_work_day_string()
    if not date:
        await callback.answer("Нужно обновление календаря")
        return

    order_table = Order(session)

    try:
        await order_table.update_order(user_id, date, status=StatusOrder.CONFIRM.value)
        await callback.answer("Заказ оформлен!", show_alert=True)
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Error in confirm_order: {e}")
        await callback.answer("Произошла ошибка при оформлении заказа")
