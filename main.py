import asyncio
import logging
import platform
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import TOKEN, DATABASE_URL
from tg_bot.essence.dishes import Dish
from tg_bot.essence.groups import Group
from tg_bot.essence.items_in_order import ItemsOrder
from tg_bot.essence.orders import Order
from tg_bot.essence.users import User
from tg_bot.essence.weekly_menu import WeeklyMenu
from tg_bot.middlewares.DatabaseMiddleware import register_global_middlewares
from tg_bot.handler import commands, handlers
from tg_bot.services.send_message_bot import send_report_admin
from tg_bot.services.set_bot_commands import set_default_commands
from tg_bot.services.timer_schedule import reminder, total_text_lunch_send_admin


async def on_startup(bot: Bot, scheduler: AsyncIOScheduler):
    engine = create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Устанавливаем команды бота
        await set_default_commands(bot)

        # Инициализируем таблицы
        dishes_table = Dish(session)
        await dishes_table.create_table()

        groups_table = Group(session)
        await groups_table.create_table()

        order_table = Order(session)
        await order_table.create_table()

        user_table = User(session)
        await user_table.create_table()

        items_order_table = ItemsOrder(session)
        await items_order_table.create_table()

        weekly_menu_table = WeeklyMenu(session)
        await weekly_menu_table.create_table()
        await weekly_menu_table.initialize_days()

        # Настраиваем планировщик задач
        scheduler.add_job(
            func=reminder,
            trigger='cron',
            day='*',
            hour='12',
            minute='30',
            kwargs={'session': session}
        )
        scheduler.add_job(
            func=total_text_lunch_send_admin,
            trigger='cron',
            day='*',
            hour='14',
            minute='00',
            kwargs={'session': session}
        )


async def main():
    # Настройка хранилища и логгирования
    storage = MemoryStorage()
    logging.basicConfig(level=logging.INFO)

    # Инициализация бота
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))

    # Создаем движок для основного пула соединений
    engine = create_async_engine(DATABASE_URL)
    session_pool = async_sessionmaker(engine, expire_on_commit=False)

    # Инициализация диспетчера
    dp = Dispatcher(storage=storage)

    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    dp['scheduler'] = scheduler
    dp['session_pool'] = session_pool

    # Инициализация бота
    await on_startup(bot, scheduler)

    # Подключаем роутеры
    dp.include_routers(commands.router, handlers.router)

    # Регистрируем middleware
    register_global_middlewares(dp, session_pool)

    # Запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        scheduler.start()
        await dp.start_polling(bot)
    finally:
        await dp.storage.close()
        await bot.session.close()
        scheduler.remove_all_jobs()
        scheduler.shutdown()
        await engine.dispose()


if __name__ == '__main__':
    try:
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot stopped!")
    finally:
        asyncio.run(send_report_admin(False))
