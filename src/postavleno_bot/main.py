from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault

from .core.config import get_settings
from .core.logging import get_logger, setup_logging
from .handlers.menu import MENU_ROUTER
from .middlewares.request_id import RequestIdMiddleware
from .middlewares.user_context import UserContextMiddleware


async def _on_startup(bot: Bot) -> None:
    logger = get_logger(__name__).bind(action="startup")
    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="help", description="Помощь"),
        ],
        scope=BotCommandScopeDefault(),
    )
    logger.info("Команды обновлены")


async def main() -> None:
    settings = get_settings()
    setup_logging(rich_enabled=settings.log_rich, json_enabled=settings.log_json)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.update.middleware(RequestIdMiddleware())
    dispatcher.update.middleware(UserContextMiddleware())
    dispatcher.include_router(MENU_ROUTER)
    dispatcher.startup.register(_on_startup)

    logger = get_logger(__name__).bind(action="run")
    logger.info("Бот запускается")

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
