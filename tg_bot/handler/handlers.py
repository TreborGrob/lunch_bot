import datetime
import logging
from asyncio.log import logger
from collections import Counter
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from pytz import timezone
from sqlalchemy.ext.asyncio import AsyncSession
from config import FIX_SUM, LAST_HOUR_FOR_ORDER, HOUR_OPEN_ORDER, TIMEZONE
from tg_bot.essence.balance import Balance
from tg_bot.essence.dishes import Dish
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.orders import Order
from tg_bot.services.days_operations import next_work_day_string, get_day_of_week
from tg_bot.services.handler_dishes import dishes_in_side_items
from tg_bot.services.markups_keyboards import groups_markup, items_group_markup, cart_items_markup, back_menu_markup
from tg_bot.services.resources import Messages, create_description_for_dish
from tg_bot.services.collection_titles import StatusOrder

router = Router()


@router.callback_query(F.data.startswith("group_"))
async def group_menu(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    date_tomorrow = await next_work_day_string()
    group_id = int(callback.data.split("_")[-1])
    try:
        await callback.message.edit_text(
            Messages.SELECT_DISHES,
            reply_markup=await items_group_markup(group_id, session, user_id, date_tomorrow)
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            Messages.SELECT_LUNCH.format(date_tomorrow=date_tomorrow),
            reply_markup=await groups_markup(session, user_id, date_tomorrow)
        )


@router.callback_query(F.data.startswith("add_cart_"))
async def add_item_in_cart(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    date_tomorrow = await next_work_day_string()
    if not date_tomorrow:
        await callback.answer(Messages.NEED_UPDATE_CALENDAR)
        return

    id_dish = int(callback.data.split("_")[-1])
    items_order_table = ItemsOrder(session)
    order_table = Order(session)
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer(Messages.DISH_NOT_FOUND)
            return
        order_id = await order_table.create_order(user_id, date_tomorrow)
        order_amount = await items_order_table.get_amount_for_order(order_id)

        if (order_amount + item.amount) > FIX_SUM:
            await callback.answer(Messages.ORDER_OVER_SUM, show_alert=True)
        else:
            await items_order_table.add_dish_to_order(order_id, id_dish, 1)
            await order_table.update_order(user_id, date_tomorrow, amount=order_amount + item.amount)
            await callback.message.edit_reply_markup(
                reply_markup=await items_group_markup(item.group_id, session, user_id, date_tomorrow)
            )
            await callback.answer()
    except Exception as e:
        logging.error(e)
        await callback.answer(Messages.ERROR)


@router.callback_query(F.data.startswith("item_"))
async def view_item(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    id_dish = int(callback.data.split("_")[-1])
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer(Messages.DISH_NOT_FOUND)
            return

        description = await create_description_for_dish(item)

        await callback.message.edit_text(
            description,
            reply_markup=await back_menu_markup(item.id, item.group_id, session, user_id)
        )
        await callback.answer()
    except Exception as e:
        logging.error(e)
        await callback.answer(Messages.ERROR)


@router.callback_query(F.data.startswith("del_cart_"))
async def remove_item_in_cart(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    date_tomorrow = await next_work_day_string()
    if not date_tomorrow:
        await callback.answer(Messages.NEED_UPDATE_CALENDAR)
        return

    id_dish = int(callback.data.split("_")[-1])
    items_order_table = ItemsOrder(session)
    order_table = Order(session)
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer(Messages.DISH_NOT_FOUND)
            return

        order_id = await order_table.create_order(user_id, date_tomorrow)
        await items_order_table.remove_dish_from_order(order_id, item.id)
        order_amount = await items_order_table.get_amount_for_order(order_id)
        await order_table.update_order(user_id, date_tomorrow, amount=order_amount)

        await callback.message.edit_reply_markup(
            reply_markup=await items_group_markup(item.group_id, session, user_id, date_tomorrow)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in remove_item_in_cart: {e}")
        await callback.answer(Messages.ERROR)


@router.callback_query(F.data.startswith("cart_"))
async def view_cart(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    date = await next_work_day_string()
    if not date:
        await callback.answer(Messages.NEED_UPDATE_CALENDAR)
        return

    order_table = Order(session)
    items_order_table = ItemsOrder(session)

    try:
        order_id = await order_table.get_id_order_by_user_id_and_date(user_id, date)
        if not order_id:
            await callback.answer(Messages.ORDER_VOID)
            return

        dishes_in_order = await items_order_table.get_dishes_for_order(order_id)
        if dishes_in_order:
            await callback.message.edit_text(
                Messages.ORDER,
                reply_markup=await cart_items_markup(dishes_in_order)
            )
        else:
            await callback.answer(Messages.ORDER_VOID)
    except Exception as e:
        logger.error(f"Error in view_cart: {e}")
        await callback.answer(Messages.ERROR)


@router.callback_query(F.data == "menu_main")
async def give_menu(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    date_tomorrow = await next_work_day_string()
    try:
        await callback.message.edit_text(
            Messages.SELECT_LUNCH.format(date_tomorrow=date_tomorrow),
            reply_markup=await groups_markup(session, user_id, date_tomorrow)
        )
    except Exception as e:
        logger.error(f"Error in give_menu: {e}")
        await callback.answer(Messages.ERROR)


@router.callback_query(F.data.startswith("plus_cart_"))
async def plus_item_in_cart(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    date_tomorrow = await next_work_day_string()
    if not date_tomorrow:
        await callback.answer(Messages.NEED_UPDATE_CALENDAR)
        return

    id_dish = int(callback.data.split("_")[-1])
    items_order_table = ItemsOrder(session)
    order_table = Order(session)
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer(Messages.DISH_NOT_FOUND)
            return

        order_id = await order_table.get_id_order_by_user_id_and_date(user_id, date_tomorrow)
        if not order_id:
            await callback.answer(Messages.ORDER_NOT_FOUND)
            return

        order_amount = await items_order_table.get_amount_for_order(order_id)
        if (order_amount + item.amount) > FIX_SUM:
            await callback.answer(Messages.ORDER_OVER_SUM, show_alert=True)
        else:
            await items_order_table.add_dish_to_order(order_id, id_dish, 1)
            await order_table.update_order(user_id, date_tomorrow, amount=order_amount + item.amount)
            order_dishes = await items_order_table.get_dishes_for_order(order_id)
            await callback.message.edit_reply_markup(
                reply_markup=await cart_items_markup(order_dishes)
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in plus_item_in_cart: {e}")
        await callback.answer(Messages.ERROR)


@router.callback_query(F.data.startswith("minus_cart_"))
async def minus_item_in_cart(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    date_tomorrow = await next_work_day_string()
    if not date_tomorrow:
        await callback.answer(Messages.NEED_UPDATE_CALENDAR)
        return

    id_dish = int(callback.data.split("_")[-1])
    items_order_table = ItemsOrder(session)
    order_table = Order(session)
    dish_table = Dish(session)

    try:
        item = await dish_table.get_dish_by_id(id_dish)
        if not item:
            await callback.answer(Messages.DISH_NOT_FOUND)
            return

        order_id = await order_table.get_id_order_by_user_id_and_date(user_id, date_tomorrow)
        if not order_id:
            await callback.answer(Messages.ORDER_NOT_FOUND)
            return

        await items_order_table.remove_dish_from_order(order_id, item.id)
        order_amount = await items_order_table.get_amount_for_order(order_id)
        await order_table.update_order(user_id, date_tomorrow, amount=order_amount)
        order_dishes = await items_order_table.get_dishes_for_order(order_id)
        await callback.message.edit_reply_markup(
            reply_markup=await cart_items_markup(order_dishes)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in minus_item_in_cart: {e}")
        await callback.answer(Messages.ERROR)


@router.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    date = await next_work_day_string()
    moscow_tz = timezone(TIMEZONE)
    if date is False:
        await callback.answer(Messages.NEED_UPDATE_CALENDAR)
    time_now = datetime.datetime.now(tz=moscow_tz)
    order_table = Order(session)
    next_work_day_week_int = await get_day_of_week(date)
    time_now_week_int = time_now.isoweekday()
    if next_work_day_week_int - time_now_week_int > HOUR_OPEN_ORDER or time_now.time().hour < LAST_HOUR_FOR_ORDER:
        order = await order_table.get_order_by_user_id_and_date(user_id, date)
        await order_table.update_order(user_id, date, status=StatusOrder.CONFIRM.value)
        items_order_table = ItemsOrder(session)
        user_dish_counter = Counter()
        user_lines = []
        dishes = await items_order_table.get_dishes_for_order(order.id)
        text_user = Messages.ORDER_YOUR_FOR_DATE.format(date=date)
        if dishes:
            dish_counter = await dishes_in_side_items(dishes, session)
            for dish, count in dish_counter.items():
                user_dish_counter[dish] += count
            for dish, count in user_dish_counter.items():
                user_lines.append(f"{dish} - {count}")
            text_user += Messages.CODE_OPEN_TAG
            text_user += "\n".join(user_lines)
            text_user += Messages.CODE_CLOSE_TAG
        balance_table = Balance(session)
        balance_user = await balance_table.get_balance_by_user_id(user_id)
        if balance_user:
            await balance_table.update_balance(user_id, balance=balance_user.balance + order.amount)
        await callback.message.delete()
        await callback.message.answer(text_user)
    else:
        await callback.answer(Messages.BEING_LATE)
        order_data = await order_table.get_order_by_user_id_and_date(user_id, date)
        if order_data:
            await order_table.delete_order(order_data.id)
