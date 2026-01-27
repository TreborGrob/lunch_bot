import logging
import os
import re
from collections import Counter
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from config import TOKEN, ACCESS_ARRAY, currency
from tg_bot.essence.balance import BalanceModel, Balance
from tg_bot.essence.dishes import Dish
from tg_bot.essence.groups import Group
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.orders import Order
from tg_bot.essence.users import User
from tg_bot.essence.weekly_menu import WeeklyMenu
from tg_bot.services.days_operations import next_work_day_string, create_matrices, download_calendar_excel, \
    parse_calendar
from tg_bot.services.handler_dishes import dishes_in_side_items
from tg_bot.services.markups_keyboards import groups_markup, request_contact
from tg_bot.services.resources import Messages, create_dish_for_menu
from tg_bot.services.collection_titles import StatusEmployee, CommandsTitle
from tg_bot.services.timer_schedule import get_menu_by_kind, lunch_picker
from tg_bot.services.work_with_log import tail

router = Router()


@router.message(Command(CommandsTitle.CLEAR.value))
async def clear(message: Message, state: FSMContext):
    await state.clear()
    await message.answer_sticker(sticker="CAACAgIAAxkBAAIBZmXTPPzuBeK3Q1faFSbEk3xv9JH2AAJABgACU7H3A9q1WauGxd5MNAQ")


@router.message(Command(CommandsTitle.REFRESH.value))
async def reload_menu(message: Message, role: str):
    if role in ACCESS_ARRAY:
        await message.answer("Пришли pdf файл с меню.")


@router.message(Command(CommandsTitle.START.value))
async def start_bot(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    user_table = User(session)
    user_data = await user_table.get_user_by_tg_id(user_id)
    if user_data:
        await message.answer("Бот для заказа обеда организации ООО'РАНДЕМ'\nВведи команду /menu,"
                             " чтобы заказать обед на следующий рабочий день.")
    else:
        await message.answer("⬇Отправь контакт по кнопке⬇", reply_markup=request_contact())


@router.message(F.contact)
async def contact_getter(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    user_name = message.from_user.first_name if message.from_user.first_name else message.from_user.last_name
    if message.contact.user_id == user_id:
        phone_number = message.contact.phone_number
        if re.fullmatch(r"(\+7|7|8)\d{10}", phone_number):
            phone_number = int(phone_number[-10:])
            logging.error(f"{phone_number}")
            user_table = User(session)
            # balance_table = Balance(session)
            user = await user_table.get_user_by_phone(phone_number)
            if user and not user.telegram_id:
                await user_table.update_user(phone_number, telegram_id=user_id, username=user_name)
                # await balance_table.create_or_get_balance(user_id=user_id)
                await message.answer("Теперь можно делать заказ с помощью команды /menu",
                                     reply_markup=ReplyKeyboardRemove())
            elif not user:
                await message.answer("О вас нет данных, обратитесь к администратору",
                                     reply_markup=ReplyKeyboardRemove())
            else:
                await message.answer("Вы зарегистрированы, можно делать заказ с помощью команды /menu",
                                     reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("Принимается только ваш номер.")


@router.message(Command(CommandsTitle.MENU.value))
async def menu_command(message: Message, session: AsyncSession):
    user_table = User(session)
    user_id = message.from_user.id
    user_data = await user_table.get_user_by_tg_id(user_id)
    if user_data:
        if user_data.status == StatusEmployee.WORK.value:
            date = await next_work_day_string()
            if date:
                order_table = Order(session)
                order = await order_table.get_order_by_user_id_and_date(user_id, date)
                if not order:
                    await order_table.create_order(user_id, date)
                await message.answer(f"Выбор обеда на {date}",
                                     reply_markup=await groups_markup(session, user_id, date))
            else:
                await message.answer("Технические неполадки сообщите администратору бота.")
        else:
            await message.answer("Попросите администратора поменять ваш статус для заказа обеда.")


@router.message(Command(CommandsTitle.CALENDAR.value))
async def calendar_load(message: Message, command: CommandObject, role: str):
    if role in ACCESS_ARRAY:
        arguments = command.args
        data = arguments.split(" ")
        year = data[0]
        url_calendar = data[1]
        months_matrix = create_matrices()
        file_calendar = download_calendar_excel(url_calendar)
        # Получение списков
        parse_calendar(file_calendar, "Лист1", year, months_matrix)
        await message.answer(f"{year} г. - календарь загружен")


@router.message(Command(CommandsTitle.MY_ORDER.value))
async def my_order(message: Message, session: AsyncSession):
    result_lines = []
    combined_dish_counter = Counter()
    user_table = User(session)
    user_id = message.from_user.id
    user_data = await user_table.get_user_by_tg_id(user_id)
    if user_data:
        current_date = datetime.now()
        current_date_str = current_date.strftime('%Y-%m-%d')
        date_for_txt = current_date.strftime('%d.%m.%Y')
        user_id = message.from_user.id
        order_table = Order(session)
        order = await order_table.get_order_by_user_id_and_date(user_id, current_date_str)
        text_msg = f"Обед на {date_for_txt}\n\n"
        if order:
            items_order_table = ItemsOrder(session)
            items = await items_order_table.get_dishes_for_order(order.id)

            if items:
                dish_counter = await dishes_in_side_items(items, session)
                for dish, count in dish_counter.items():
                    combined_dish_counter[dish] += count
            for dish, count in combined_dish_counter.items():
                result_lines.append(f"{dish} - {count}")

            text_msg += "\n".join(result_lines)
        else:
            text_msg += "Не найден."

        await message.answer(text_msg)


@router.message(Command(CommandsTitle.ADD_USER.value))
async def add_users(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role in ACCESS_ARRAY:
        arguments = command.args
        data_phones = arguments.split(" ")
        user_table = User(session)
        text_msg = "Пользователи: "
        for phone in data_phones:
            if phone.isdigit():
                text_msg += "\n" + phone
                await user_table.add_user(int(phone))
            text_msg += "\nдобавлены."
        await message.answer(text_msg)
    else:
        await message.answer(Messages.NO_ACCESS)


@router.message(Command(CommandsTitle.DEL_USER.value))
async def delete_users(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role in ACCESS_ARRAY:
        arguments = command.args
        data_phones = arguments.split(" ")
        user_table = User(session)
        text_msg = "Пользователи: "
        for phone in data_phones:
            if phone.isdigit():
                text_msg += "\n" + phone
                await user_table.delete_user(int(phone))
            text_msg += "\nудалены."
        await message.answer(text_msg)
    else:
        await message.answer(Messages.NO_ACCESS)


@router.message(Command(CommandsTitle.COMMANDS.value))
async def commands_admin(message: Message, role: str):
    next_day = await next_work_day_string()
    text_commands = (f"/{CommandsTitle.MENU.value} - меню\n"
                     f"/{CommandsTitle.MY_ORDER.value} - мой заказ на сегодня\n"
                     f"/{CommandsTitle.BALANCE.value} - мой баланс\n")
    if role in ACCESS_ARRAY:
        text_commands += (f"/{CommandsTitle.REFRESH.value} - обновление меню, использовать, "
                          f"если меню на сайте обновилось.\n"
                          f"/{CommandsTitle.SET_STATUS.value} 9991234455 отпуск/больничный/работа - установка статуса\n"
                          f"/{CommandsTitle.ADD_USER.value} 9991234455 - "
                          f"добавление, можно несколько сразу, через пробел\n"
                          f"/{CommandsTitle.DEL_USER.value} 9991234455 - "
                          f"удаление, можно несколько сразу, через пробел\n"
                          f"/{CommandsTitle.CALENDAR.value} 2026 https://mtsz.tatarstan.ru/file/pub/pub_4757062.xlsx\n"
                          f"/{CommandsTitle.ADD_DISH.value} [категория] [наименование] "
                          f"[цена] - добавление блюда в категорию\n")
        text_commands += f"/{CommandsTitle.LUNCH_PICKER.value} - просмотр заказа на {next_day}\n"
    await message.answer(text_commands)


@router.message(Command(CommandsTitle.ADD_DISH.value))
async def add_dish_for_menu(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role in ACCESS_ARRAY:

        weekly_menu = WeeklyMenu(session)
        arguments = command.args
        arg_pack = arguments.split()
        amount = int(arg_pack[-1])
        group_name = arg_pack[0]
        dish_name = arg_pack[1]
        group_table = Group(session)
        group_id = await group_table.get_group_by_name(group_name)
        if not group_id:
            await message.answer(f"Категория {group_name} не найдена")
            return
        dish_id = await create_dish_for_menu(dish_name, amount, session, group_id)
        if dish_id:
            await message.answer(f"{dish_name} добавлен стоимостью {amount} за шт. в категорию {group_name}")
            for day_id in range(1, 7):
                await weekly_menu.add_dish_to_day(day_id, dish_id)
        else:
            await message.answer(f"Ошибка при добавлении, либо уже существует.")


@router.message(Command(CommandsTitle.SET_STATUS.value))
async def set_status(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role not in ACCESS_ARRAY:
        return await message.answer(Messages.NO_ACCESS)
    relax_statuses = ("отдых", "больничный", "отпуск")
    user_table = User(session)
    arguments = command.args
    data = arguments.split(" ")
    phone_num = int(data[0])
    try:
        if re.fullmatch(r"\d{10}", data[0]):
            if data[1].lower() in relax_statuses:
                status = StatusEmployee.RELAX.value
            else:
                status = StatusEmployee.WORK.value
            await user_table.update_user(phone_num, status=status)
            await message.answer(f"Статус {phone_num} обновлён на {data[1]}")
    except Exception as e:
        await message.answer(f"Ошибка обновления статуса: {e}")


@router.message(Command(CommandsTitle.LUNCH_PICKER.value))
async def lunch_picker_command(message: Message, session: AsyncSession, role: str):
    if role not in ACCESS_ARRAY:
        return await message.answer(Messages.NO_ACCESS)
    try:
        text = await lunch_picker(session)
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logging.error(e)
        await message.answer("Произошла ошибка при формировании заказов")


@router.message(Command(CommandsTitle.GET_USERS.value))
async def get_status_users(message: Message, session: AsyncSession, role: str):
    if role not in ACCESS_ARRAY:
        return await message.answer(Messages.NO_ACCESS)
    text = ""
    user_table = User(session)
    users_data = await user_table.get_all_users()
    for user in users_data:
        text += f"{user.phone_number} - {user.username} - {user.status}\n"

    await message.answer(text)


@router.message(Command(CommandsTitle.READ_LOG.value))
async def read_logfile(message: Message, role: str):
    if role != "admin":
        return await message.answer(Messages.NO_ACCESS)
    log_dir = "logs"
    log_file = os.path.join(log_dir, "bot.log")
    file_size = os.path.getsize(log_file)
    last_lines = await tail(log_file, 10)
    await message.answer(f'Размер {log_file}: {round(file_size / 1024, 2)} килобайт\n'
                         f'{last_lines}')


@router.message(Command(CommandsTitle.CLEAR_NEXT_DAY.value))
async def clear_next_day_orders(message: Message, session: AsyncSession, role: str):
    if role not in ACCESS_ARRAY:
        return await message.answer(Messages.NO_ACCESS)
    next_work_day = await next_work_day_string()
    order_table = Order(session)
    await order_table.delete_orders_by_date(next_work_day)
    await message.answer(f"Заказы на {next_work_day} очищены.")


@router.message(Command(CommandsTitle.SET_NAME.value))
async def set_name_user(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role not in ACCESS_ARRAY:
        return await message.answer(Messages.NO_ACCESS)
    user_table = User(session)
    arguments = command.args
    data = arguments.split(" ")
    phone_num = int(data[0])
    await user_table.update_user(phone_number=phone_num, username=data[-1])
    await message.answer(f"Пользователю с номером {phone_num} присвоен username = {data[-1]}")


@router.message(Command(CommandsTitle.UPDATE_PRICE.value))
async def update_price_item(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role not in ACCESS_ARRAY:
        return await message.answer(Messages.NO_ACCESS)
    dishes_table = Dish(session)
    arguments = command.args
    data = arguments.split(" ")
    amount = data[-1]
    name_item = data[0].split("_")
    name = " ".join(name_item)
    item = await dishes_table.get_dish_by_name(name)
    if item:
        if amount.isdigit():
            try:
                await dishes_table.update_dish(dish_id=item.id, amount=int(amount))
                await message.answer(f"У {name} цена обновлена на {int(amount)}.")
            except Exception as e:
                await message.answer(f"Ошибка: {e}")
        else:
            await message.answer("Некорректное исправление")


@router.message(F.document)
async def any_msg(message: Message, session: AsyncSession, role: str):
    if role not in ACCESS_ARRAY:
        return await message.answer(Messages.NO_ACCESS)
    pdf_name = "menu.pdf"
    file_id = message.document.file_id
    async with Bot(token=TOKEN).context(True) as bot:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        await bot.download_file(file_path, pdf_name)
    update_result = await get_menu_by_kind(session, pdf_name)
    if update_result:
        result_text = "Меню обновилось"
    else:
        result_text = "Возникла ошибка, меню не обновилось, попробуй ещё раз."
    if os.path.exists(pdf_name):
        os.remove(pdf_name)
    await message.answer(result_text)


@router.message(Command(CommandsTitle.CREATE_BALANCE_ALL.value))
async def create_balance_all_users(message: Message, session: AsyncSession, role: str):
    if role not in ACCESS_ARRAY:
        return await message.answer(Messages.NO_ACCESS)
    user_table = User(session)
    count_create_balances = await user_table.create_balance_records_for_all_users(BalanceModel)
    await message.answer(f"Кол-во созданных кошельков = {count_create_balances} шт.")


@router.message(Command(CommandsTitle.BALANCE.value))
async def my_balance(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    balance_table = Balance(session)
    balance_data = await balance_table.get_balance_by_user_id(user_id)
    if balance_data:
        await message.answer(f"В этом месяце заказал на: {balance_data.balance} {currency}.")

if __name__ == "__main__":
    # phone = "+79998887766"
    # if re.fullmatch(r"[+]?\d{11}", phone):
    #     print(phone)
    pass
