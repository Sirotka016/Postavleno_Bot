from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from .core.config import Settings
from .core.logging import get_logger
from .handlers import router as handlers_router
from .middlewares.request_id import RequestIdMiddleware
from .middlewares.user_context import UserContextMiddleware

BOT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
]


async def _on_startup(bot: Bot) -> None:
    logger = get_logger(__name__).bind(action="startup")
    await bot.set_my_commands(commands=BOT_COMMANDS, scope=BotCommandScopeDefault())
    logger.info("Команды обновлены", commands=[command.command for command in BOT_COMMANDS])


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(RequestIdMiddleware())
    dispatcher.update.middleware(UserContextMiddleware())
    dispatcher.include_router(handlers_router)
    dispatcher.startup.register(_on_startup)
    return dispatcher


__all__ = ["create_bot", "create_dispatcher", "BOT_COMMANDS"]
