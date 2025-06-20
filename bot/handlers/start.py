import os
import random
from dotenv import load_dotenv
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.menus import student_main_menu, teacher_main_menu, start_choice_menu
from bot.database.db_helpers import (
    get_or_create_session, get_user_role, set_user_session,
    get_all_modules, get_words, update_progress
)
from bot.handlers.teacher import delete_message_later, teacher_help
from bot.services.card_generator import generate_flashcard_image

load_dotenv()
TEACHER_PASS = os.getenv("TEACHER_PASS")

router = Router()
user_flashcards = {}

# --- FSM States ---
class RoleSelection(StatesGroup):
    waiting_for_teacher_password = State()
    waiting_for_student_level = State()

class FlashcardState(StatesGroup):
    selecting_module = State()
    awaiting_input = State()

# --- Role selection ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    get_or_create_session(message.from_user.id)
    role = get_user_role(message.from_user.id)
    if role not in ("teacher", "student"):
        await message.answer("Выберите роль:", reply_markup=start_choice_menu())
    elif role == "teacher":
        await message.answer("Добро пожаловать, преподаватель!", reply_markup=teacher_main_menu())
    else:
        await message.answer("Изменение2", reply_markup=student_main_menu())

@router.message(Command("role"))
async def cmd_role(message: types.Message):
    await message.answer("Выберите роль:", reply_markup=start_choice_menu())

@router.callback_query(F.data == "choose_teacher")
async def choose_teacher(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите пароль преподавателя:")
    await state.set_state(RoleSelection.waiting_for_teacher_password)

@router.message(RoleSelection.waiting_for_teacher_password)
async def process_teacher_password(message: types.Message, state: FSMContext):
    if message.text == TEACHER_PASS:
        set_user_session(message.from_user.id, role="teacher")
        await message.answer("Пароль верен! Добро пожаловать, преподаватель!", reply_markup=teacher_main_menu())
    else:
        await message.answer("Неверный пароль. Попробуйте ещё раз или выберите другую роль.")
    await state.clear()

@router.callback_query(F.data == "choose_student")
async def choose_student(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите ваш уровень английского:")
    await callback.message.answer(
        "Пожалуйста, выберите уровень:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="A1", callback_data="level_A1")],
            [InlineKeyboardButton(text="A2", callback_data="level_A2")],
            [InlineKeyboardButton(text="B1", callback_data="level_B1")]
        ])
    )
    await state.set_state(RoleSelection.waiting_for_student_level)

@router.callback_query(RoleSelection.waiting_for_student_level, F.data.startswith("level_"))
async def student_level_selected(callback: types.CallbackQuery, state: FSMContext):
    level = callback.data.split("_")[1]
    set_user_session(callback.from_user.id, role="student", level=level)
    await callback.message.edit_text(f"Ваш уровень установлен как {level}.")
    await callback.message.answer("Добро пожаловать, студент!", reply_markup=student_main_menu())
    await state.clear()

# --- Flashcard Mode ---
@router.callback_query(F.data == "flashcards_start")
async def start_flashcard(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(FlashcardState.selecting_module)
    await callback.message.answer(
        "Режим флеш-карт активирован.\n\nВведите модуль (например: module 4) или 'все' для всех слов:"
    )

@router.message(FlashcardState.selecting_module)
async def load_flashcard_words(message: types.Message, state: FSMContext):
    module = message.text.strip().lower()
    session_id = get_or_create_session(message.from_user.id)
    words = get_words(session_id, module if module != "все" else None)

    if not words:
        await message.answer("Слов из этого модуля не найдено.")
        return

    random.shuffle(words)
    user_flashcards[message.from_user.id] = words[1:]
    current_word = words[0]
    await state.set_state(FlashcardState.awaiting_input)
    await state.update_data(current_word=current_word)

    image = await generate_flashcard_image(current_word["translation"], is_question=True)
    sent = await message.answer_photo(photo=image)
    await message.answer(f"Слово: {current_word['translation']}")
    await delete_message_later(message.bot, message.chat.id, sent.message_id)

@router.message(FlashcardState.awaiting_input)
async def handle_flashcard_answer(message: types.Message, state: FSMContext):
    session_id = get_or_create_session(message.from_user.id)
    data = await state.get_data()
    word = data["current_word"]

    user_input = message.text.strip().lower()
    correct = word["Text"].strip().lower()
    synonyms = [s.strip().lower() for s in (word.get("synonyms") or "").split(",")]
    is_correct = user_input == correct or user_input in synonyms

    update_progress(session_id, word["Word_ID"], is_correct)

    feedback = (
        "✅ Верно!" if user_input == correct else
        "✅ Верно (синоним)!" if user_input in synonyms else
        f"❌ Неверно.\nПравильный ответ: <b>{word['Text']}</b>"
    )

    await message.answer(f"{feedback}\nСинонимы: {word.get('synonyms', 'не указаны')}", parse_mode="HTML")

    next_words = user_flashcards.get(message.from_user.id, [])
    if not next_words:
        await message.answer("🎉 Тренировка завершена")
        await state.clear()
        return

    if not is_correct:
        next_words.append(word)
    next_word = next_words.pop(0)
    user_flashcards[message.from_user.id] = next_words
    await state.update_data(current_word=next_word)

    image = await generate_flashcard_image(next_word["translation"], is_question=True)
    sent = await message.answer_photo(photo=image)
    await message.answer(f"Слово: {next_word['translation']}")
    await delete_message_later(message.bot, message.chat.id, sent.message_id)

# --- Help ---
@router.message(Command("help"))
async def cmd_help(message: types.Message):
    role = get_user_role(message.from_user.id)
    help_text = (
        "📚 <b>Список доступных команд:</b>\n\n"
        "🛠 <b>Общие команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/role - Выбрать или изменить роль\n"
        "/cancel - Отменить текущее действие\n\n"
    )
    if role == "teacher":
        help_text += (
            "👨‍🏫 <b>Команды для преподавателя:</b>\n"
            "/menu_teacher - Показать меню преподавателя\n"
            "• Добавить слово\n"
            "• Добавить пакет слов\n"
            "• Просмотреть все слова\n"
            "• Редактировать слово\n"
            "• Редактировать синонимы\n"
            "• Просмотреть модули\n"
        )
    elif role == "student":
        help_text += (
            "🎓 <b>Команды для студента:</b>\n"
            "/levelSwitch - Изменить уровень сложности (A1/A2/B1)\n"
            "/menu_student - Показать меню студента\n"
            "• Флеш-карты\n"
            "• Редактировать слово\n"
            "• Просмотреть модули\n"
            "• /stopcard - Завершить тренировку\n"
        )
    else:
        help_text += "🤔 Выберите роль с помощью /start."

    await message.answer(help_text, parse_mode="HTML")

@router.callback_query(F.data == "help_command")
async def handle_help_callback(callback: types.CallbackQuery):
    await teacher_help(callback.message)
    await callback.answer()

def register(dp):
    dp.include_router(router)
