import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from config import ADMIN, MANAGER, TOKEN
from tg_bot.essence.dishes import Dish
from tg_bot.essence.groups import Group
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.orders import Order
from tg_bot.essence.users import User
from tg_bot.services.days_operations import next_work_day_string, create_matrices, download_calendar_excel, \
    parse_calendar
from tg_bot.services.handler_dishes import dishes_in_side_items
from tg_bot.services.markups_keyboards import groups_markup, request_contact
from tg_bot.services.resources import Messages
from tg_bot.services.statuses import StatusOrder, StatusEmployee
from tg_bot.services.timer_schedule import get_menu_by_kind, lunch_picker
from tg_bot.services.work_with_log import tail

router = Router()


@router.message(Command("clear"))
async def clear(message: Message, state: FSMContext):
    await state.clear()
    await message.answer_sticker(sticker="CAACAgIAAxkBAAIBZmXTPPzuBeK3Q1faFSbEk3xv9JH2AAJABgACU7H3A9q1WauGxd5MNAQ")


@router.message(Command("refresh"))
async def reload_menu(message: Message):
    if int(message.from_user.id) in (ADMIN, MANAGER):
        await message.answer("Пришли pdf файл с меню.")


@router.message(Command("start"))
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
        if re.fullmatch(r"[+]?\d{11}", phone_number):
            phone_number = int(phone_number[2:])
            user_table = User(session)
            user = await user_table.get_user_by_phone(phone_number)
            if user and not user.telegram_id:
                await user_table.update_user(phone_number, telegram_id=user_id, username=user_name)
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


@router.message(Command("menu"))
async def menu_command(message: Message, session: AsyncSession):
    user_table = User(session)
    user_id = message.from_user.id
    user_data = await user_table.get_user_by_tg_id(user_id)
    date_tomorrow = await next_work_day_string()
    if user_data:
        if user_data.status == StatusEmployee.WORK.value:
            date = await next_work_day_string()
            if date:
                order_table = Order(session)
                order = await order_table.get_order_by_user_id_and_date(user_id, date)
                if not order:
                    await order_table.create_order(user_id, date)
                await message.answer(f"Выбор обеда на {date_tomorrow}",
                                     reply_markup=await groups_markup(session, user_id))
            else:
                await message.answer("Технические неполадки сообщите администратору бота.")
        else:
            await message.answer("Попросите администратора поменять ваш статус для заказа обеда.")


@router.message(Command("calendar"))
async def calendar_load(message: Message, command: CommandObject):
    if int(message.from_user.id) in (ADMIN, MANAGER):
        arguments = command.args
        data = arguments.split(" ")
        year = data[0]
        url_calendar = data[1]
        months_matrix = create_matrices()
        file_calendar = download_calendar_excel(url_calendar)
        # Получение списков
        parse_calendar(file_calendar, "Лист1", year, months_matrix)
        await message.answer(f"{year} г. - календарь загружен")


@router.message(Command("my_order"))
async def my_order(message: Message, session: AsyncSession):
    result_lines = []
    combined_dish_counter = defaultdict(int)
    user_table = User(session)
    user_id = message.from_user.id
    user_data = await user_table.get_user_by_tg_id(user_id)
    if user_data:
        current_date = datetime.now()
        current_date_str = current_date.strftime('%Y-%m-%d')
        date_for_txt = current_date.strftime('%d.%m.%Y')
        user_id = message.from_user.id
        order_table = Order(session)
        order = await order_table.get_order_by_user_id_and_date_status(user_id, current_date_str,
                                                                       StatusOrder.CLOSE.value)
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


@router.message(Command("add_user"))
async def add_users(message: Message, command: CommandObject, session: AsyncSession):
    if int(message.from_user.id) in (ADMIN, MANAGER):
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
        await message.answer("Нет прав на данную команду.")


@router.message(Command("del_user"))
async def delete_users(message: Message, command: CommandObject, session: AsyncSession):
    if int(message.from_user.id) in (ADMIN, MANAGER):
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
        await message.answer("Нет прав на данную команду.")


@router.message(Command("commands"))
async def commands_admin(message: Message):
    text_commands = ("/menu - меню\n"
                     "/my_order - мой заказ на сегодня\n")
    if int(message.from_user.id) in (ADMIN, MANAGER):
        text_commands += ("/refresh - обновление меню, использовать, если меню на сайте обновилось.\n"
                          "/set_status 9991234455 отпуск/больничный/работа - установка статуса\n"
                          "/add_user 9991234455 - добавление, можно несколько сразу, через пробел\n"
                          "/del_user 9991234455 - удаление, можно несколько сразу, через пробел\n"
                          "/calendar 2025[год] https://mtsz.tatarstan.ru/file/pub/pub_4334893.xlsx [ссылка на файл "
                          "производственного календаря]"
                          "/add_bread 3[цена] - добавление хлеба в выпечку")
    await message.answer(text_commands)


@router.message(Command("add_bread"))
async def add_bread(message: Message, command: CommandObject, session: AsyncSession):
    if int(message.from_user.id) in (ADMIN, MANAGER):
        dish_table = Dish(session)
        arguments = command.args
        data = arguments.split(" ")
        amount = int(data[-1])
        group_table = Group(session)
        bread_group = await group_table.get_group_by_name("Выпечка")
        # print(bread_group)
        if not bread_group:
            await message.answer("Группа 'Выпечка' не найдена")
            return
        dish_id = await dish_table.create_dish(
            name="Хлеб",
            weight="5 гр.",
            amount=amount,
            compound="мука, вода, яйцо",
            image_url="",
            calories="40",
            group_id=bread_group.id
        )

        if dish_id:
            await message.answer(f"Хлеб добавлен в количестве {amount} шт.")
        else:
            await message.answer("Ошибка при добавлении хлеба")


@router.message(Command("set_status"))
async def set_status(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role not in ("admin", "manager"):
        return await message.answer(Messages.NO_ACCESS)

    user_table = User(session)
    arguments = command.args
    data = arguments.split(" ")
    phone_num = int(data[0])
    try:
        if re.fullmatch(r"\d{10}", data[0]):
            if data[1].lower() in ("отдых", "больничный", "отпуск"):
                status = "relax"
            else:
                status = "office"
            await user_table.update_user(phone_num, status=status)
            await message.answer(f"Статус {phone_num} обновлён на {data[1]}")
    except Exception as e:
        await message.answer(f"Ошибка обновления статуса: {e}")


@router.message(Command("lunch_picker"))
async def lunch_picker_command(message: Message, session: AsyncSession, role: str):
    if role not in ("admin", "manager"):
        return await message.answer(Messages.NO_ACCESS)
    try:
        text = await lunch_picker(session)
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logging.error(e)
        await message.answer("Произошла ошибка при формировании заказов")


@router.message(Command("get_users"))
async def get_status_users(message: Message, session: AsyncSession, role: str):
    if role not in ("admin", "manager"):
        return await message.answer(Messages.NO_ACCESS)
    text = ""
    user_table = User(session)
    users_data = await user_table.get_all_users()
    for user in users_data:
        text += f"{user.phone_number} - {user.username} - {user.status}\n"

    await message.answer(text)


@router.message(Command("read_log"))
async def read_logfile(message: Message, role: str):
    if role not in "admin":
        return await message.answer(Messages.NO_ACCESS)
    log_dir = "logs"
    log_file = os.path.join(log_dir, "bot.log")
    file_size = os.path.getsize(log_file)
    last_lines = await tail(log_file, 10)
    await message.answer(f'Размер {log_file}: {round(file_size / 1024, 2)} килобайт\n'
                         f'{last_lines}')


@router.message(Command("clear_next_day"))
async def clear_next_day_orders(message: Message, session: AsyncSession, role: str):
    if role not in ("admin", "manager"):
        return await message.answer(Messages.NO_ACCESS)
    next_work_day = await next_work_day_string()
    order_table = Order(session)
    await order_table.delete_orders_by_date(next_work_day)
    await message.answer(f"Заказы на {next_work_day} очищены.")


@router.message(Command("set_name"))
async def set_name_user(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role not in ("admin", "manager"):
        return await message.answer(Messages.NO_ACCESS)
    user_table = User(session)
    arguments = command.args
    data = arguments.split(" ")
    phone_num = int(data[0])
    await user_table.update_user(phone_number=phone_num, username=data[-1])
    await message.answer(f"Пользователю с номером {phone_num} присвоен username = {data[-1]}")


@router.message(Command("update_price"))
async def update_price_item(message: Message, command: CommandObject, session: AsyncSession, role: str):
    if role not in ("admin", "manager"):
        return await message.answer(Messages.NO_ACCESS)
    dishes_table = Dish(session)
    arguments = command.args
    data = arguments.split(" ")
    amount = data[-1]
    name_item = data[0]
    if amount.isdigit():
        try:
            await dishes_table.update_dish(name=name_item, amount=int(amount))
            await message.answer(f"У {name_item} цена обновлена на {int(amount)}.")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
    else:
        await message.answer("Некорректное исправление")


@router.message(F.document)
async def any_msg(message: Message, session: AsyncSession, role: str):
    if role not in ("admin", "manager"):
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

if __name__ == "__main__":
    # phone = "+79998887766"
    # if re.fullmatch(r"[+]?\d{11}", phone):
    #     print(phone)
    pass
