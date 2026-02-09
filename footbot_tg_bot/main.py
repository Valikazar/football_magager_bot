import logging
import asyncio
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats

import database as db
import translations as tr
from init_bot import bot, dp

# Import routers from modular handlers
import admin_handlers
import user_handlers

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def set_bot_commands(bot):
    commands_ru = [
        BotCommand(command="poll", description=tr.t("cmd_poll_desc", 1)),
        BotCommand(command="admin", description=tr.t("cmd_admin_desc", 1)),
        BotCommand(command="table", description=tr.t("cmd_table_desc", 1)),
        BotCommand(command="finish_draw", description=tr.t("cmd_finish_draw_desc", 1)),
        BotCommand(command="cancel", description=tr.t("cmd_cancel_desc", 1)),
        BotCommand(command="site", description=tr.t("cmd_site_desc", 1)),
        BotCommand(command="start", description=tr.t("cmd_start_desc", 1)),
    ]
    commands_en = [
        BotCommand(command="poll", description=tr.t("cmd_poll_desc", 2)),
        BotCommand(command="admin", description=tr.t("cmd_admin_desc", 2)),
        BotCommand(command="table", description=tr.t("cmd_table_desc", 2)),
        BotCommand(command="finish_draw", description=tr.t("cmd_finish_draw_desc", 2)),
        BotCommand(command="cancel", description=tr.t("cmd_cancel_desc", 2)),
        BotCommand(command="site", description=tr.t("cmd_site_desc", 2)),
        BotCommand(command="start", description=tr.t("cmd_start_desc", 2)),
    ]
    # Set for private chats
    await bot.set_my_commands(commands_ru, scope=BotCommandScopeAllPrivateChats(), language_code="ru")
    await bot.set_my_commands(commands_en, scope=BotCommandScopeAllPrivateChats(), language_code="en")
    # Set for group chats
    await bot.set_my_commands(commands_ru, scope=BotCommandScopeAllGroupChats(), language_code="ru")
    await bot.set_my_commands(commands_en, scope=BotCommandScopeAllGroupChats(), language_code="en")
    # Set default
    await bot.set_my_commands(commands_ru)

async def main():
    # Initialize DB
    db.init_db()
    
    # Load translations
    tr.load_translations()
    
    # Setup commands
    await set_bot_commands(bot)
    
    # Register routers
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    
    # Register middleware
    from utils import PMContextMiddleware
    dp.message.outer_middleware(PMContextMiddleware())
    
    logger.info("Bot started with modular handlers...")
    
    # Reset webhooks and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
