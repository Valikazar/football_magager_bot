import os
import sys
from aiogram import Bot, Dispatcher
from persistent_storage import MySQLStorage
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN not found in .env")
    sys.exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MySQLStorage())
