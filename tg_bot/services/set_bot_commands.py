from aiogram import types


async def set_default_commands(bot):
    await bot.set_my_commands(commands=[
        types.BotCommand(command="menu", description="Меню на завтра"),
        types.BotCommand(command="my_order", description="Посмотреть свой заказ на сегодня"),
        types.BotCommand(command="commands", description="Доступные команды")
    ]
    )
