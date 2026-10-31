import asyncio
import sqlite3
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Не найден BOT_TOKEN. Проверьте файл .env")

bot = Bot(token=TOKEN)
dp = Dispatcher()

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить задачу")],
        [KeyboardButton(text="📋 Мои задачи")],
    ],
    resize_keyboard=True,
)

db = sqlite3.connect("tasks.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0
)
""")
db.commit()


class AddTask(StatesGroup):
    waiting_text = State()


def get_tasks_view(user_id):
    """Собирает текст списка задач и кнопки под ним."""
    cursor.execute(
        "SELECT id, text, done FROM tasks WHERE user_id = ?",
        (user_id,),
    )
    rows = cursor.fetchall()

    if not rows:
        return "Пока задач нет", None

    lines = []
    buttons = []
    for number, (task_id, text, done) in enumerate(rows, start=1):
        mark = "✅" if done else "⬜"
        lines.append(f"{number}. {mark} {text}")
        buttons.append([
            InlineKeyboardButton(text=f"✅ {number}", callback_data=f"done:{task_id}"),
            InlineKeyboardButton(text=f"🗑 {number}", callback_data=f"del:{task_id}"),
        ])

    return "Твои задачи:\n" + "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def refresh_list(callback: CallbackQuery):
    """Обновляет сообщение со списком после действия."""
    text, markup = get_tasks_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass  # текст не изменился, ничего страшного
    await callback.answer()


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! Выбери действие:",
        reply_markup=menu,
    )


@dp.message(F.text == "➕ Добавить задачу")
async def add_task(message: Message, state: FSMContext):
    await message.answer("Напиши текст задачи:")
    await state.set_state(AddTask.waiting_text)


@dp.message(F.text == "📋 Мои задачи")
async def show_tasks(message: Message):
    text, markup = get_tasks_view(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@dp.message(AddTask.waiting_text)
async def save_task(message: Message, state: FSMContext):
    cursor.execute(
        "INSERT INTO tasks (user_id, text) VALUES (?, ?)",
        (message.from_user.id, message.text),
    )
    db.commit()
    await state.clear()
    await message.answer("Задача сохранена ✅", reply_markup=menu)


@dp.callback_query(F.data.startswith("done:"))
async def mark_done(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    cursor.execute(
        "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?",
        (task_id, callback.from_user.id),
    )
    db.commit()
    await refresh_list(callback)


@dp.callback_query(F.data.startswith("del:"))
async def delete_task(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    cursor.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, callback.from_user.id),
    )
    db.commit()
    await refresh_list(callback)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())