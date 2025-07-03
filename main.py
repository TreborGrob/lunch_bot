import asyncio
import logging
import platform
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tg_bot.essence.base_model import Base
from config import TOKEN, DATABASE_URL
from tg_bot.essence.weekly_menu import WeeklyMenu
from tg_bot.middlewares.DatabaseMiddleware import register_global_middlewares
from tg_bot.handler import commands, handlers
from tg_bot.services.send_message_bot import send_report_admin
from tg_bot.services.set_bot_commands import set_default_commands
from tg_bot.services.timer_schedule import reminder, total_text_lunch_send_admin
from tg_bot.services.work_with_log import setup_logging
from pytz import timezone


async def on_startup(bot: Bot, scheduler: AsyncIOScheduler):
    # Создаем движок и сессии
    engine = create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # Создаем все таблицы одним запросом
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Инициализация данных и планировщика
    async with async_session() as session:
        # Устанавливаем команды бота
        await set_default_commands(bot)

        # Инициализируем данные (если нужно)
        weekly_menu_table = WeeklyMenu(session)
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
    scheduler = AsyncIOScheduler(timezone=timezone('Europe/Moscow'))
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
        setup_logging()
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot stopped!")
    finally:
        asyncio.run(send_report_admin(False))
