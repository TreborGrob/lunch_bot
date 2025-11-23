import asyncio
import logging
import platform
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tg_bot.essence.base_model import Base
from config import TOKEN, LAST_HOUR_FOR_ORDER, REMINDER_HOUR, REMINDER_MINUTES, TIMEZONE, \
    LAST_MINUTE_FOR_ORDER
from tg_bot.essence.weekly_menu import WeeklyMenu
from tg_bot.middlewares.database import register_global_middlewares
from tg_bot.handler import commands, handlers
from tg_bot.middlewares.roles import RoleMiddleware
from tg_bot.services.database_engine import get_session_pool
from tg_bot.services.send_message_bot import send_report_admin
from tg_bot.services.set_bot_commands import set_default_commands
from tg_bot.services.timer_schedule import reminder, total_text_lunch_send_admin, resetting_the_balance
from tg_bot.services.work_with_log import setup_logging
from pytz import timezone


async def on_startup(bot: Bot, scheduler: AsyncIOScheduler, async_session, engine):

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
            hour=f'{REMINDER_HOUR}',
            minute=f'{REMINDER_MINUTES}',
            kwargs={'session': session}
        )
        scheduler.add_job(
            func=total_text_lunch_send_admin,
            trigger='cron',
            day_of_week='mon-fri',
            hour=f'{LAST_HOUR_FOR_ORDER}',
            minute=f'{LAST_MINUTE_FOR_ORDER}',
            kwargs={'session': session}
        )
        scheduler.add_job(
            func=resetting_the_balance,
            trigger='cron',
            day_of_week=6,
            hour=17,
            minute=53,
            kwargs={'session': session}
        )


async def main():
    # Настройка хранилища и логгирования
    storage = MemoryStorage()
    logging.basicConfig(level=logging.INFO)

    # Инициализация бота
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))

    # Создаем движок для основного пула соединений
    session_pool, engine = get_session_pool()

    # Инициализация диспетчера
    dp = Dispatcher(storage=storage)

    # Настройка планировщика
    scheduler = AsyncIOScheduler(timezone=timezone(TIMEZONE))
    dp['scheduler'] = scheduler
    dp['session_pool'] = session_pool

    # Инициализация бота
    await on_startup(bot, scheduler, session_pool, engine)

    # Подключаем роутеры
    dp.include_routers(commands.router, handlers.router)

    # Регистрируем middleware
    register_global_middlewares(dp, session_pool)
    dp.message.middleware(RoleMiddleware())
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
