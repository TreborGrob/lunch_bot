from aiogram import types

from tg_bot.services.collection_titles import CommandsTitle


async def set_default_commands(bot):
    await bot.set_my_commands(commands=[
        types.BotCommand(command=CommandsTitle.MENU.value, description="Меню на след. раб. день"),
        types.BotCommand(command=CommandsTitle.MY_ORDER.value, description="Посмотреть свой заказ на сегодня"),
        types.BotCommand(command=CommandsTitle.BALANCE.value, description="Заказал(а) за этот месяц"),
        types.BotCommand(command=CommandsTitle.COMMANDS.value, description="Доступные команды")
    ]
    )
