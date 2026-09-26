BOT_TOKEN=8628819274:AAGm3SohIIEio6GX9DRm7Pors47XQoBsYBg

ADMIN_IDS=7365030714

CHANNEL_USERNAME=@afsungarmerlinkinokanal
CHANNEL_USERNAME=@afsungarmerlinkinokanal

import asyncio
import logging
import os

import aiosqlite
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ChatMemberStatus

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
DB_NAME = "kino_bot.db"

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan.")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Oddiy admin holatlari
admin_state = {}


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT
            )
        """)
        await db.commit()


async def save_user(message: Message):
    u = message.from_user
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users(user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (u.id, u.username, u.first_name))
        await db.commit()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def subscribed(user_id: int) -> bool:
    if not CHANNEL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
    except Exception:
        return False


def subscribe_keyboard():
    username = CHANNEL_USERNAME.lstrip("@")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Kanalga obuna bo'lish",
            url=f"https://t.me/{username}"
        )],
        [InlineKeyboardButton(
            text="✅ Obunani tekshirish",
            callback_data="check_sub"
        )]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="add_movie")],
        [InlineKeyboardButton(text="🗑 Kino o'chirish", callback_data="delete_movie")],
        [InlineKeyboardButton(text="🔎 Kino qidirish", callback_data="search_movie")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
    ])


@dp.message(CommandStart())
async def start(message: Message):
    await save_user(message)

    if not await subscribed(message.from_user.id):
        await message.answer(
            "🎬 Botdan foydalanish uchun avval kanalga obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    await message.answer(
        "🎬 <b>Kino botiga xush kelibsiz!</b>\n\n"
        "Kino kodini yuboring.\n"
        "Masalan: <code>123</code>\n\n"
        "Kino nomi bo'yicha ham qidirishingiz mumkin.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):
    if await subscribed(callback.from_user.id):
        await callback.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\nKino kodini yuboring."
        )
    else:
        await callback.answer(
            "❌ Hali kanalga obuna bo'lmagansiz.",
            show_alert=True
        )


@dp.message(Command("admin"))
async def admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz.")
        return

    await message.answer(
        "👨‍💼 <b>ADMIN PANEL</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "add_movie")
async def add_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "add", "step": "code"}
    await callback.message.answer(
        "➕ Kino qo'shish\n\n1️⃣ Kino kodini yuboring:"
    )


@dp.callback_query(F.data == "delete_movie")
async def delete_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "delete"}
    await callback.message.answer("🗑 O'chiriladigan kino kodini yuboring:")


@dp.callback_query(F.data == "search_movie")
async def search_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "search"}
    await callback.message.answer("🔎 Kino kodi yoki nomini yuboring:")


@dp.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT COUNT(*) FROM movies")
        movie_count = (await c.fetchone())[0]
        c = await db.execute("SELECT COUNT(*) FROM users")
        user_count = (await c.fetchone())[0]

    await callback.message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {user_count}\n"
        f"🎬 Kinolar: {movie_count}",
        parse_mode="HTML"
    )


@dp.message()
async def messages(message: Message):
    await save_user(message)
    uid = message.from_user.id

    # Admin amallari
    if is_admin(uid) and uid in admin_state:
        state = admin_state[uid]

        if state["action"] == "add":
            if state["step"] == "code":
                if not message.text:
                    await message.answer("❌ Kodni matn ko'rinishida yuboring.")
                    return

                code = message.text.strip()

                async with aiosqlite.connect(DB_NAME) as db:
                    c = await db.execute(
                        "SELECT id FROM movies WHERE code = ?", (code,)
                    )
                    exists = await c.fetchone()

                if exists:
                    await message.answer("❌ Bu kod allaqachon mavjud.")
                    return

                state["code"] = code
                state["step"] = "title"
                await message.answer("2️⃣ Kino nomini yuboring:")
                return

            if state["step"] == "title":
                if not message.text:
                    await message.answer("❌ Kino nomini yuboring.")
                    return

                state["title"] = message.text.strip()
                state["step"] = "video"
                await message.answer("3️⃣ Endi videoni yuboring:")
                return

            if state["step"] == "video":
                if not message.video:
                    await message.answer("❌ Video fayl yuboring.")
                    return

                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute(
                        "INSERT INTO movies(code, title, file_id) VALUES (?, ?, ?)",
                        (state["code"], state["title"], message.video.file_id)
                    )
                    await db.commit()

                code = state["code"]
                title = state["title"]
                del admin_state[uid]

                await message.answer(
                    f"✅ Kino qo'shildi!\n\n"
                    f"🎬 {title}\n"
                    f"🔢 Kod: <code>{code}</code>",
                    parse_mode="HTML"
                )
                return

        if state["action"] == "delete":
            if not message.text:
                return
            code = message.text.strip()

            async with aiosqlite.connect(DB_NAME) as db:
                c = await db.execute(
                    "DELETE FROM movies WHERE code = ?", (code,)
                )
                await db.commit()
                deleted = c.rowcount

            del admin_state[uid]
            await message.answer(
                f"✅ {code} kodli kino o'chirildi."
                if deleted else "❌ Bunday kod topilmadi."
            )
            return

        if state["action"] == "search":
            if not message.text:
                return
            query = message.text.strip()

            async with aiosqlite.connect(DB_NAME) as db:
                c = await db.execute("""
                    SELECT code, title FROM movies
                    WHERE code = ? OR title LIKE ?
                    ORDER BY id DESC LIMIT 20
                """, (query, f"%{query}%"))
                rows = await c.fetchall()

            del admin_state[uid]

            if not rows:
                await message.answer("❌ Kino topilmadi.")
                return

            text = "🔎 <b>Natijalar:</b>\n\n"
            for code, title in rows:
                text += f"🎬 {title}\n🔢 <code>{code}</code>\n\n"
            await message.answer(text, parse_mode="HTML")
            return

    # Oddiy foydalanuvchi
    if not await subscribed(uid):
        await message.answer(
            "❌ Avval kanalga obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    if not message.text:
        return

    query = message.text.strip()

    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("""
            SELECT code, title, file_id
            FROM movies
            WHERE code = ? OR title LIKE ?
            ORDER BY id DESC LIMIT 10
        """, (query, f"%{query}%"))
        rows = await c.fetchall()

    if not rows:
        await message.answer("❌ Kino topilmadi.")
        return

    for code, title, file_id in rows:
        await message.answer_video(
            video=file_id,
            caption=f"🎬 <b>{title}</b>\n🔢 Kod: <code>{code}</code>",
            parse_mode="HTML"
        )


async def main():
    await init_db()
    print("🤖 Kino bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

# Telegram Kino Bot

## O'rnatish

1. Python 3.10+ o'rnating.
2. Terminalda:
   pip install -r requirements.txt
3. `.env` faylini ochib:
   - BOT_TOKEN
   - ADMIN_IDS
   - CHANNEL_USERNAME
   qiymatlarini kiriting.
4. Botni Telegram kanalingizga admin qilib qo'ying.
5. Ishga tushiring:
   python main.py

## Admin
Telegramda:
 /admin

Admin panel orqali kino qo'shish, o'chirish, qidirish va statistika mavjud.

## Eslatma
Faqat tarqatish huquqiga ega bo'lgan videolardan foydalaning.

aiogram>=3.22,<4
aiosqlite>=0.20
python-dotenv>=1.0
# Telegram Kino Bot

## O'rnatish

1. Python 3.10+ o'rnating.
2. Terminalda:
   pip install -r requirements.txt
3. `.env` faylini ochib:
   - BOT_TOKEN
   - ADMIN_IDS
   - CHANNEL_USERNAME
   qiymatlarini kiriting.
4. Botni Telegram kanalingizga admin qilib qo'ying.
5. Ishga tushiring:
   python main.py

## Admin
Telegramda:
 /admin

Admin panel orqali kino qo'shish, o'chirish, qidirish va statistika mavjud.

## Eslatma
Faqat tarqatish huquqiga ega bo'lgan videolardan foydalaning.

aiogram>=3.22,<4
aiosqlite>=0.20
python-dotenv>=1.0

import asyncio
import logging
import os

import aiosqlite
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ChatMemberStatus

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
DB_NAME = "kino_bot.db"

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan.")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Oddiy admin holatlari
admin_state = {}


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT
            )
        """)
        await db.commit()


async def save_user(message: Message):
    u = message.from_user
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users(user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (u.id, u.username, u.first_name))
        await db.commit()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def subscribed(user_id: int) -> bool:
    if not CHANNEL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
    except Exception:
        return False


def subscribe_keyboard():
    username = CHANNEL_USERNAME.lstrip("@")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Kanalga obuna bo'lish",
            url=f"https://t.me/{username}"
        )],
        [InlineKeyboardButton(
            text="✅ Obunani tekshirish",
            callback_data="check_sub"
        )]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="add_movie")],
        [InlineKeyboardButton(text="🗑 Kino o'chirish", callback_data="delete_movie")],
        [InlineKeyboardButton(text="🔎 Kino qidirish", callback_data="search_movie")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
    ])


@dp.message(CommandStart())
async def start(message: Message):
    await save_user(message)

    if not await subscribed(message.from_user.id):
        await message.answer(
            "🎬 Botdan foydalanish uchun avval kanalga obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    await message.answer(
        "🎬 <b>Kino botiga xush kelibsiz!</b>\n\n"
        "Kino kodini yuboring.\n"
        "Masalan: <code>123</code>\n\n"
        "Kino nomi bo'yicha ham qidirishingiz mumkin.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):
    if await subscribed(callback.from_user.id):
        await callback.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\nKino kodini yuboring."
        )
    else:
        await callback.answer(
            "❌ Hali kanalga obuna bo'lmagansiz.",
            show_alert=True
        )


@dp.message(Command("admin"))
async def admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz.")
        return

    await message.answer(
        "👨‍💼 <b>ADMIN PANEL</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "add_movie")
async def add_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "add", "step": "code"}
    await callback.message.answer(
        "➕ Kino qo'shish\n\n1️⃣ Kino kodini yuboring:"
    )


@dp.callback_query(F.data == "delete_movie")
async def delete_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "delete"}
    await callback.message.answer("🗑 O'chiriladigan kino kodini yuboring:")


@dp.callback_query(F.data == "search_movie")
async def search_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "search"}
    await callback.message.answer("🔎 Kino kodi yoki nomini yuboring:")


@dp.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT COUNT(*) FROM movies")
        movie_count = (await c.fetchone())[0]
        c = await db.execute("SELECT COUNT(*) FROM users")
        user_count = (await c.fetchone())[0]

    await callback.message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {user_count}\n"
        f"🎬 Kinolar: {movie_count}",
        parse_mode="HTML"
    )


@dp.message()
async def messages(message: Message):
    await save_user(message)
    uid = message.from_user.id

    # Admin amallari
    if is_admin(uid) and uid in admin_state:
        state = admin_state[uid]

        if state["action"] == "add":
            if state["step"] == "code":
                if not message.text:
                    await message.answer("❌ Kodni matn ko'rinishida yuboring.")
                    return

                code = message.text.strip()

                async with aiosqlite.connect(DB_NAME) as db:
                    c = await db.execute(
                        "SELECT id FROM movies WHERE code = ?", (code,)
                    )
                    exists = await c.fetchone()

                if exists:
                    await message.answer("❌ Bu kod allaqachon mavjud.")
                    return

                state["code"] = code
                state["step"] = "title"
                await message.answer("2️⃣ Kino nomini yuboring:")
                return

            if state["step"] == "title":
                if not message.text:
                    await message.answer("❌ Kino nomini yuboring.")
                    return

                state["title"] = message.text.strip()
                state["step"] = "video"
                await message.answer("3️⃣ Endi videoni yuboring:")
                return

            if state["step"] == "video":
                if not message.video:
                    await message.answer("❌ Video fayl yuboring.")
                    return

                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute(
                        "INSERT INTO movies(code, title, file_id) VALUES (?, ?, ?)",
                        (state["code"], state["title"], message.video.file_id)
                    )
                    await db.commit()

                code = state["code"]
                title = state["title"]
                del admin_state[uid]

                await message.answer(
                    f"✅ Kino qo'shildi!\n\n"
                    f"🎬 {title}\n"
                    f"🔢 Kod: <code>{code}</code>",
                    parse_mode="HTML"
                )
                return

        if state["action"] == "delete":
            if not message.text:
                return
            code = message.text.strip()

            async with aiosqlite.connect(DB_NAME) as db:
                c = await db.execute(
                    "DELETE FROM movies WHERE code = ?", (code,)
                )
                await db.commit()
                deleted = c.rowcount

            del admin_state[uid]
            await message.answer(
                f"✅ {code} kodli kino o'chirildi."
                if deleted else "❌ Bunday kod topilmadi."
            )
            return

        if state["action"] == "search":
            if not message.text:
                return
            query = message.text.strip()

            async with aiosqlite.connect(DB_NAME) as db:
                c = await db.execute("""
                    SELECT code, title FROM movies
                    WHERE code = ? OR title LIKE ?
                    ORDER BY id DESC LIMIT 20
                """, (query, f"%{query}%"))
                rows = await c.fetchall()

            del admin_state[uid]

            if not rows:
                await message.answer("❌ Kino topilmadi.")
                return

            text = "🔎 <b>Natijalar:</b>\n\n"
            for code, title in rows:
                text += f"🎬 {title}\n🔢 <code>{code}</code>\n\n"
            await message.answer(text, parse_mode="HTML")
            return

    # Oddiy foydalanuvchi
    if not await subscribed(uid):
        await message.answer(
            "❌ Avval kanalga obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    if not message.text:
        return

    query = message.text.strip()

    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("""
            SELECT code, title, file_id
            FROM movies
            WHERE code = ? OR title LIKE ?
            ORDER BY id DESC LIMIT 10
        """, (query, f"%{query}%"))
        rows = await c.fetchall()

    if not rows:
        await message.answer("❌ Kino topilmadi.")
        return

    for code, title, file_id in rows:
        await message.answer_video(
            video=file_id,
            caption=f"🎬 <b>{title}</b>\n🔢 Kod: <code>{code}</code>",
            parse_mode="HTML"
        )


async def main():
    await init_db()
    print("🤖 Kino bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
aiogram>=3.22,<4
aiosqlite>=0.20
python-dotenv>=1.0

import asyncio
import logging
import os

import aiosqlite
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ChatMemberStatus

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
DB_NAME = "kino_bot.db"

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan.")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Oddiy admin holatlari
admin_state = {}


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT
            )
        """)
        await db.commit()


async def save_user(message: Message):
    u = message.from_user
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users(user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (u.id, u.username, u.first_name))
        await db.commit()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def subscribed(user_id: int) -> bool:
    if not CHANNEL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
    except Exception:
        return False


def subscribe_keyboard():
    username = CHANNEL_USERNAME.lstrip("@")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Kanalga obuna bo'lish",
            url=f"https://t.me/{username}"
        )],
        [InlineKeyboardButton(
            text="✅ Obunani tekshirish",
            callback_data="check_sub"
        )]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="add_movie")],
        [InlineKeyboardButton(text="🗑 Kino o'chirish", callback_data="delete_movie")],
        [InlineKeyboardButton(text="🔎 Kino qidirish", callback_data="search_movie")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
    ])


@dp.message(CommandStart())
async def start(message: Message):
    await save_user(message)

    if not await subscribed(message.from_user.id):
        await message.answer(
            "🎬 Botdan foydalanish uchun avval kanalga obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    await message.answer(
        "🎬 <b>Kino botiga xush kelibsiz!</b>\n\n"
        "Kino kodini yuboring.\n"
        "Masalan: <code>123</code>\n\n"
        "Kino nomi bo'yicha ham qidirishingiz mumkin.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):
    if await subscribed(callback.from_user.id):
        await callback.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\nKino kodini yuboring."
        )
    else:
        await callback.answer(
            "❌ Hali kanalga obuna bo'lmagansiz.",
            show_alert=True
        )


@dp.message(Command("admin"))
async def admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz.")
        return

    await message.answer(
        "👨‍💼 <b>ADMIN PANEL</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "add_movie")
async def add_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "add", "step": "code"}
    await callback.message.answer(
        "➕ Kino qo'shish\n\n1️⃣ Kino kodini yuboring:"
    )


@dp.callback_query(F.data == "delete_movie")
async def delete_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "delete"}
    await callback.message.answer("🗑 O'chiriladigan kino kodini yuboring:")


@dp.callback_query(F.data == "search_movie")
async def search_movie(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state[callback.from_user.id] = {"action": "search"}
    await callback.message.answer("🔎 Kino kodi yoki nomini yuboring:")


@dp.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT COUNT(*) FROM movies")
        movie_count = (await c.fetchone())[0]
        c = await db.execute("SELECT COUNT(*) FROM users")
        user_count = (await c.fetchone())[0]

    await callback.message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {user_count}\n"
        f"🎬 Kinolar: {movie_count}",
        parse_mode="HTML"
    )


@dp.message()
async def messages(message: Message):
    await save_user(message)
    uid = message.from_user.id

    # Admin amallari
    if is_admin(uid) and uid in admin_state:
        state = admin_state[uid]

        if state["action"] == "add":
            if state["step"] == "code":
                if not message.text:
                    await message.answer("❌ Kodni matn ko'rinishida yuboring.")
                    return

                code = message.text.strip()

                async with aiosqlite.connect(DB_NAME) as db:
                    c = await db.execute(
                        "SELECT id FROM movies WHERE code = ?", (code,)
                    )
                    exists = await c.fetchone()

                if exists:
                    await message.answer("❌ Bu kod allaqachon mavjud.")
                    return

                state["code"] = code
                state["step"] = "title"
                await message.answer("2️⃣ Kino nomini yuboring:")
                return

            if state["step"] == "title":
                if not message.text:
                    await message.answer("❌ Kino nomini yuboring.")
                    return

                state["title"] = message.text.strip()
                state["step"] = "video"
                await message.answer("3️⃣ Endi videoni yuboring:")
                return

            if state["step"] == "video":
                if not message.video:
                    await message.answer("❌ Video fayl yuboring.")
                    return

                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute(
                        "INSERT INTO movies(code, title, file_id) VALUES (?, ?, ?)",
                        (state["code"], state["title"], message.video.file_id)
                    )
                    await db.commit()

                code = state["code"]
                title = state["title"]
                del admin_state[uid]

                await message.answer(
                    f"✅ Kino qo'shildi!\n\n"
                    f"🎬 {title}\n"
                    f"🔢 Kod: <code>{code}</code>",
                    parse_mode="HTML"
                )
                return

        if state["action"] == "delete":
            if not message.text:
                return
            code = message.text.strip()

            async with aiosqlite.connect(DB_NAME) as db:
                c = await db.execute(
                    "DELETE FROM movies WHERE code = ?", (code,)
                )
                await db.commit()
                deleted = c.rowcount

            del admin_state[uid]
            await message.answer(
                f"✅ {code} kodli kino o'chirildi."
                if deleted else "❌ Bunday kod topilmadi."
            )
            return

        if state["action"] == "search":
            if not message.text:
                return
            query = message.text.strip()

            async with aiosqlite.connect(DB_NAME) as db:
                c = await db.execute("""
                    SELECT code, title FROM movies
                    WHERE code = ? OR title LIKE ?
                    ORDER BY id DESC LIMIT 20
                """, (query, f"%{query}%"))
                rows = await c.fetchall()

            del admin_state[uid]

            if not rows:
                await message.answer("❌ Kino topilmadi.")
                return

            text = "🔎 <b>Natijalar:</b>\n\n"
            for code, title in rows:
                text += f"🎬 {title}\n🔢 <code>{code}</code>\n\n"
            await message.answer(text, parse_mode="HTML")
            return

    # Oddiy foydalanuvchi
    if not await subscribed(uid):
        await message.answer(
            "❌ Avval kanalga obuna bo'ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    if not message.text:
        return

    query = message.text.strip()

    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("""
            SELECT code, title, file_id
            FROM movies
            WHERE code = ? OR title LIKE ?
            ORDER BY id DESC LIMIT 10
        """, (query, f"%{query}%"))
        rows = await c.fetchall()

    if not rows:
        await message.answer("❌ Kino topilmadi.")
        return

    for code, title, file_id in rows:
        await message.answer_video(
            video=file_id,
            caption=f"🎬 <b>{title}</b>\n🔢 Kod: <code>{code}</code>",
            parse_mode="HTML"
        )


async def main():
    await init_db()
    print("🤖 Kino bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

# Telegram Kino Bot

## O'rnatish

1. Python 3.10+ o'rnating.
2. Terminalda:
   pip install -r requirements.txt
3. `.env` faylini ochib:
   - BOT_TOKEN
   - ADMIN_IDS
   - CHANNEL_USERNAME
   qiymatlarini kiriting.
4. Botni Telegram kanalingizga admin qilib qo'ying.
5. Ishga tushiring:
   python main.py

## Admin
Telegramda:
 /admin

Admin panel orqali kino qo'shish, o'chirish, qidirish va statistika mavjud.

## Eslatma
Faqat tarqatish huquqiga ega bo'lgan videolardan foydalaning.
