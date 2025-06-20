# main.py — entry point for Dori Bot
import os
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from bot.services.card_generator import generate_flashcard_image
from bot.handlers import teacher, student, start

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Register all handlers and routers
start.register(dp)
student.register(dp)
teacher.register(dp)

async def main():
    initialize_db()
    await dp.start_polling(bot)

def initialize_db(db_path="dori_bot.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
    -- Table: StudentSession
    CREATE TABLE IF NOT EXISTS StudentSession (
        StudentSession_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL UNIQUE,
        localID TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Table: Word
    CREATE TABLE IF NOT EXISTS Word (
        Word_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Text TEXT NOT NULL,
        translation TEXT NOT NULL,
        part_of_speech TEXT,
        added_by TEXT CHECK(added_by IN ('teacher', 'student')) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        localID TEXT,
        level TEXT CHECK(level IN ('A1', 'A2', 'B1')),
        StudentSession_ID INTEGER,
        synonyms TEXT,
        module TEXT
    );

    -- Table: LibraryWord
    CREATE TABLE IF NOT EXISTS LibraryWord (
        LibraryWord_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        can_edit BOOLEAN DEFAULT FALSE,
        StudentSession_ID INTEGER,
        Word_ID INTEGER
    );

    -- Table: PracticeProgress
    CREATE TABLE IF NOT EXISTS PracticeProgress (
        PracticeProgress_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        StudentSession_ID INTEGER,
        Word_ID INTEGER,
        correct_count INTEGER DEFAULT 0,
        incorrect_count INTEGER DEFAULT 0,
        last_practiced DATETIME
    );

    -- Table: Achievement
    CREATE TABLE IF NOT EXISTS Achievement (
        Achievement_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        criteria TEXT
    );

    -- Table: UserAchievement
    CREATE TABLE IF NOT EXISTS UserAchievement (
        UserAchievement_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        StudentSession_ID INTEGER,
        Achievement_ID INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())