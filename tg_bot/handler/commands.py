import re
from collections import defaultdict
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from config import ADMIN, MANAGER
from tg_bot.essence.dishes import Dish
from tg_bot.essence.groups import Group
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.orders import Order
from tg_bot.essence.users import User
from tg_bot.services.days_operations import next_work_day_string, create_matrices, download_calendar_excel, \
    parse_calendar
from tg_bot.services.handler_dishes import dishes_in_side_items
from tg_bot.services.markups_keyboards import groups_markup, request_contact
from tg_bot.services.statuses import StatusOrder, StatusEmployee
from tg_bot.services.timer_schedule import get_menu_by_kind, lunch_picker

router = Router()


@router.message(Command("clear"))
async def clear(message: Message, state: FSMContext):
    await state.clear()
    await message.answer_sticker(sticker="CAACAgIAAxkBAAIBZmXTPPzuBeK3Q1faFSbEk3xv9JH2AAJABgACU7H3A9q1WauGxd5MNAQ")


@router.message(Command("refresh"))
async def reload_menu(message: Message, session: AsyncSession):
    if message.from_user.id == ADMIN or MANAGER:
        await get_menu_by_kind(session)
        await message.answer("Меню обновлено!")


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
    if user_data:
        if user_data.status == StatusEmployee.WORK.value:
            date = await next_work_day_string()
            if date:
                order_table = Order(session)
                order = await order_table.get_order_by_user_id_and_date(user_id, date)
                if not order:
                    await order_table.create_order(user_id, date)
                await message.answer("Выбери обед на следующий рабочий день",
                                     reply_markup=await groups_markup(session, user_id))
            else:
                await message.answer("Технические неполадки сообщите администратору бота.")
        else:
            await message.answer("Попросите администратора поменять ваш статус для заказа обеда.")


@router.message(Command("calendar"))
async def calendar_load(message: Message, command: CommandObject):
    if int(message.from_user.id) == ADMIN:
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
    if int(message.from_user.id) == ADMIN or MANAGER:
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
    if int(message.from_user.id) == ADMIN or MANAGER:
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
    if int(message.from_user.id) == ADMIN or MANAGER:
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
    if int(message.from_user.id) == ADMIN or MANAGER:
        dish_table = Dish(session)
        arguments = command.args
        data = arguments.split(" ")
        group_table = Group(session)
        groups = await group_table.get_all_groups()
        amount = int(data[-1])
        group_id = ""
        for group in groups:
            if group.name.lower() == "выпечка":
                group_id = group.id
                break
        await dish_table.create_dish("Хлеб", "5 гр.", amount, "мука, вода, яйцо", "",
                                     "40", group_id)


@router.message(Command("set_status"))
async def set_status(message: Message, command: CommandObject, session: AsyncSession):
    if int(message.from_user.id) == ADMIN or MANAGER:
        user_table = User(session)
        arguments = command.args
        data = arguments.split(" ")
        phone_num = int(data[0])
        try:
            if re.fullmatch(r"\d{10}", data[0]):
                if data[1].lower() == "отдых" or "больничный":
                    status = "relax"
                else:
                    status = "office"
                await user_table.update_user(phone_num, status=status)
                await message.answer(f"Статус {phone_num} обновлён на {data[1]}")
        except Exception as e:
            await message.answer(f"Ошибка обновления статуса: {e}")


@router.message(Command("lunch_picker"))
async def lunch_picker_command(message: Message, session: AsyncSession):
    try:
        text = await lunch_picker(session)
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer("Произошла ошибка при формировании заказов")


if __name__ == "__main__":
    # phone = "+79998887766"
    # if re.fullmatch(r"[+]?\d{11}", phone):
    #     print(phone)
    pass
