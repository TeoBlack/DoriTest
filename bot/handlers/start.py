import os
import random
import asyncio
import sqlite3

from dotenv import load_dotenv
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from bot.menus import student_main_menu, teacher_main_menu, start_choice_menu
from bot.database.db_helpers import (
    get_connection, get_or_create_session, get_user_role,
    get_all_modules, add_word, get_words,
    add_library_word, can_user_edit_word, update_progress, set_user_session
)
from bot.handlers.teacher import delete_message_later, teacher_help
from bot.services.card_generator import generate_flashcard_image

load_dotenv()
TEACHER_PASS = os.getenv("TEACHER_PASS")

router = Router()

class RoleSelection(StatesGroup):
    waiting_for_teacher_password = State()
    waiting_for_student_level = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    session_id = get_or_create_session(message.from_user.id)
    role = get_user_role(message.from_user.id)

    if role not in ("teacher", "student"):
        await message.answer("Выберите роль:", reply_markup=start_choice_menu())
    elif role == "teacher":
        await message.answer("Добро пожаловать, преподаватель!", reply_markup=teacher_main_menu())
    else:
        await message.answer("Добро пожаловать, студент!", reply_markup=student_main_menu())


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
        await state.clear()
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


@router.message(StateFilter("*"), Command("back"))
@router.message(StateFilter("*"), F.text.lower() == "back")
async def handle_back_command(message: types.Message, state: FSMContext):
    await state.clear()
    role = get_user_role(message.from_user.id)

    if role == "teacher":
        await message.answer("Вы вернулись в меню преподавателя.", reply_markup=teacher_main_menu())
    else:
        await message.answer("Вы вернулись в меню студента.", reply_markup=student_main_menu())


@router.message(Command("levelSwitch"))
async def level_switch_command(message: types.Message, state: FSMContext):
    await message.answer(
        "Выберите новый уровень:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="A1", callback_data="switch_A1")],
            [InlineKeyboardButton(text="A2", callback_data="switch_A2")],
            [InlineKeyboardButton(text="B1", callback_data="switch_B1")]
        ])
    )


@router.callback_query(F.data.startswith("switch_"))
async def process_level_switch(callback: types.CallbackQuery):
    new_level = callback.data.split("_")[1]
    set_user_session(callback.from_user.id, level=new_level)
    await callback.message.edit_text(f"Ваш уровень успешно изменён на {new_level}.")


# ----------------- Флеш-карты и редактирование --------------------

class StudentEditWord(StatesGroup):
    waiting_for_word_id = State()
    waiting_for_new_text = State()
    waiting_for_new_translation = State()

class FlashcardState(StatesGroup):
    selecting_module = State()
    awaiting_input = State()

user_flashcards = {}


@router.message(F.text.lower() == "/menu_student")
async def show_student_menu(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=student_main_menu())


@router.callback_query(F.data == "student_start_edit")
async def student_prompt_edit(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(StudentEditWord.waiting_for_word_id)
    await callback.message.answer("Введите ID слова из вашей библиотеки, которое хотите изменить:")


@router.message(StudentEditWord.waiting_for_word_id)
async def student_check_edit_permission(message: types.Message, state: FSMContext):
    session_id = get_or_create_session(message.from_user.id)
    try:
        word_id = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите корректный числовой ID слова.")
        return

    if not can_user_edit_word(session_id, word_id):
        await message.answer("Вы не можете редактировать это слово. Оно не принадлежит вашему словарю.")
        await state.clear()
        return

    await state.update_data(word_id=word_id)
    await state.set_state(StudentEditWord.waiting_for_new_text)
    await message.answer("Введите новое значение слова:")


@router.message(StudentEditWord.waiting_for_new_text)
async def student_edit_text(message: types.Message, state: FSMContext):
    await state.update_data(new_text=message.text)
    await state.set_state(StudentEditWord.waiting_for_new_translation)
    await message.answer("Введите новый перевод:")


@router.message(StudentEditWord.waiting_for_new_translation)
async def student_edit_translation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    word_id = data['word_id']
    new_text = data['new_text']
    new_translation = message.text

    with sqlite3.connect("dori_bot.db") as db:
        cursor = db.cursor()
        cursor.execute("UPDATE Word SET Text = ?, translation = ? WHERE Word_ID = ?", (new_text, new_translation, word_id))
        db.commit()

    await message.answer(f"Слово {word_id} обновлено: {new_text} – {new_translation}")
    await state.clear()


@router.callback_query(F.data == "flashcards_start")
async def start_flashcard_practice(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(FlashcardState.selecting_module)
    await callback.message.answer(
        "Режим флеш-карт активирован.\n\nВам будет показано слово на русском. Напишите его перевод на английский.\nПосле каждого ответа будут показаны синонимы и верный перевод, если вы ошиблись."
    )
    await callback.message.answer("Введите модуль (например: module 4) или 'все' для всех слов:")


@router.message(FlashcardState.selecting_module)
async def handle_module_selection(message: types.Message, state: FSMContext):
    module = message.text.strip().lower()
    session_id = get_or_create_session(message.from_user.id)
    words = get_words(session_id, module=module if module != "все" else None)

    if not words:
        await message.answer("Слов из этого модуля не найдено. Попробуйте другой модуль.")
        return

    random.shuffle(words)
    word = words[0]
    user_flashcards[message.from_user.id] = words[1:]

    await state.set_state(FlashcardState.awaiting_input)
    await state.update_data(current_word=word)

    image_path = generate_flashcard_image(word['translation'])
    sent_message: Message = await message.answer_photo(photo=types.FSInputFile(image_path))
    asyncio.create_task(delete_message_later(message.bot, message.chat.id, sent_message.message_id))
    await message.answer(f"Слово: {word['translation']}")


@router.message(FlashcardState.awaiting_input)
async def check_flashcard_answer(message: types.Message, state: FSMContext):
    session_id = get_or_create_session(message.from_user.id)
    data = await state.get_data()
    word = data["current_word"]

    user_input = message.text.strip().lower()
    correct = word['Text'].strip().lower()
    synonyms = [s.strip().lower() for s in (word.get('synonyms') or "").split(",")]
    is_correct = user_input == correct or user_input in synonyms

    update_progress(session_id, word['Word_ID'], is_correct)

    if user_input == correct:
        feedback = "✅ Верно!"
    elif user_input in synonyms:
        feedback = "✅ Верно (синоним)!"
    else:
        feedback = f"❌ Неверно.\nПравильный ответ: *{word['Text']}*"

    await message.answer(
        f"{feedback}\nСинонимы: {word.get('synonyms', 'не указаны')}",
        parse_mode="Markdown"
    )

    next_words = user_flashcards.get(message.from_user.id, [])
    if not next_words:
        await message.answer("Тренировка завершена")
        await state.clear()
        return

    if is_correct:
        next_word = next_words.pop(0)
    else:
        next_words.append(word)  # Push incorrect word to end of queue
        next_word = next_words.pop(0)
    user_flashcards[message.from_user.id] = next_words
    await state.update_data(current_word=next_word)

    image_path = generate_flashcard_image(next_word['translation'])
    sent_message: Message = await message.answer_photo(photo=types.FSInputFile(image_path))
    asyncio.create_task(delete_message_later(message.bot, message.chat.id, sent_message.message_id))
    await message.answer(f"Слово: {next_word['translation']}")


@router.callback_query(F.data == "view_modules")
async def student_view_modules(callback: types.CallbackQuery):
    modules = get_all_modules()
    if not modules:
        await callback.message.answer("Модули пока не найдены.")
        return

    modules_list = "\n".join(modules)
    await callback.message.answer(f"Доступные модули:\n{modules_list}")


@router.callback_query(F.data == "student_switch_level")
async def student_switch_level(callback: types.CallbackQuery):
    await callback.message.answer(
        "Выберите новый уровень:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="A1", callback_data="switch_A1")],
            [InlineKeyboardButton(text="A2", callback_data="switch_A2")],
            [InlineKeyboardButton(text="B1", callback_data="switch_B1")]
        ])
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    role = get_user_role(message.from_user.id)
    
    help_text = "📚 <b>Список доступных команд:</b>\n\n"
    
    # Общие команды для всех пользователей
    help_text += "🛠 <b>Общие команды:</b>\n"
    help_text += "/start - Начать работу с ботом\n"
    help_text += "/help - Показать эту справку\n"
    help_text += "/role - Выбрать или изменить роль\n"
    help_text += "/cancel - Отменить текущее действие\n\n"
    
    if role == "teacher":
        help_text += "👨‍🏫 <b>Команды для преподавателя:</b>\n"
        help_text += "/menu_teacher - Показать меню преподавателя\n"
        help_text += "Доступные действия в меню:\n"
        help_text += "• Добавить слово\n"
        help_text += "• Добавить пакет слов\n"
        help_text += "• Просмотреть все слова\n"
        help_text += "• Редактировать слово\n"
        help_text += "• Редактировать синонимы\n"
        help_text += "• Просмотреть модули\n"
    elif role == "student":
        help_text += "🎓 <b>Команды для студента:</b>\n"
        help_text += "/levelSwitch Изменить уровень сложности (A1/A2/B1)\n"
        help_text += "/menu_student - Показать меню студента\n"
        help_text += "Доступные действия в меню:\n"
        help_text += "• Флеш-карты\n"
        help_text += "• Редактировать слово\n"
        help_text += "• Просмотреть модули\n"
        help_text += "• /stopCard - Завершить тренировку с флеш-картами\n"
    else:
        help_text += "🤔 <b>Выберите роль для доступа к дополнительным функциям:</b>\n"
        help_text += "Используйте /start для выбора роли\n"
    
    await message.answer(help_text, parse_mode="HTML")


@router.callback_query(F.data == "help_command")
async def handle_help_callback(callback: types.CallbackQuery):
    await teacher_help(callback.message)
    await callback.answer()


def register(dp):
    dp.include_router(router)
