from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.database.db_helpers import get_or_create_session, add_word, get_words, add_library_word
from bot.menus import teacher_main_menu, confirm_batch_upload_menu

import sqlite3
import asyncio

router = Router()

# --- FSM States ---
class TeacherAddWord(StatesGroup):
    waiting_for_text = State()
    waiting_for_translation = State()
    waiting_for_part_of_speech = State()
    waiting_for_level = State()
    waiting_for_module = State()

class TeacherEditWord(StatesGroup):
    waiting_for_word_id = State()
    waiting_for_new_text = State()
    waiting_for_new_translation = State()

class TeacherEditSynonyms(StatesGroup):
    waiting_for_word_id = State()
    waiting_for_new_synonyms = State()

class TeacherBatchAdd(StatesGroup):
    waiting_for_batch_input = State()
    waiting_for_confirm = State()

# --- Commands ---
@router.message(Command("menu_teacher"))
async def show_teacher_menu(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=teacher_main_menu())
    

async def delete_message_later(bot, chat_id, message_id, delay=180):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass  # Ignore if already deleted or insufficient permissions


@router.message(Command("help"))
async def teacher_help(message: types.Message):
    help_text = (
        "👨‍🏫 <b>Справка для преподавателя:</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/menu_teacher - Показать меню преподавателя\n"
        "/help - Показать эту справку\n\n"
        "<b>Функции меню:</b>\n"
        "• <b>Добавить слово</b> - Добавить новое слово в базу\n"
        "• <b>Добавить пакет слов</b> - Добавить несколько слов за раз\n"
        "• <b>Просмотреть все слова</b> - Посмотреть все слова в базе\n"
        "• <b>Редактировать слово</b> - Изменить существующее слово\n"
        "• <b>Редактировать синонимы</b> - Изменить синонимы слова\n"
        "• <b>Мои модули</b> - Просмотреть учебные модули"
    )
    await message.answer(help_text, parse_mode="HTML")

# --- Add single word ---
@router.callback_query(F.data == "add_word")
async def teacher_start_add(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TeacherAddWord.waiting_for_text)
    await callback.message.answer("Введите английское слово:")

@router.message(TeacherAddWord.waiting_for_text)
async def teacher_get_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(TeacherAddWord.waiting_for_translation)
    await message.answer("Введите перевод:")

@router.message(TeacherAddWord.waiting_for_translation)
async def teacher_get_translation(message: types.Message, state: FSMContext):
    await state.update_data(translation=message.text)
    await state.set_state(TeacherAddWord.waiting_for_part_of_speech)
    await message.answer("Укажите часть речи:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"pos_{label}")]
        for label in ["noun", "verb", "adjective", "adverb", "phrase", "phrasal verb"]
    ]))

@router.callback_query(F.data.startswith("pos_"))
async def teacher_receive_pos(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(part_of_speech=callback.data.split("_", 1)[1])
    await state.set_state(TeacherAddWord.waiting_for_level)
    await callback.message.answer("Выберите уровень:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lvl, callback_data=f"level_{lvl}")]
        for lvl in ["A1", "A2", "B1"]
    ]))

@router.callback_query(F.data.startswith("level_"))
async def teacher_get_module(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(level=callback.data.split("_", 1)[1])
    await state.set_state(TeacherAddWord.waiting_for_module)
    await callback.message.answer("Введите номер модуля:")

@router.message(TeacherAddWord.waiting_for_module)
async def teacher_save_word(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("Введите только цифру модуля.")
        return
    await state.update_data(module=message.text.strip())
    data = await state.get_data()
    session_id = get_or_create_session(message.from_user.id)
    add_word(session_id, data['text'], data['translation'], data['level'], data['part_of_speech'], "teacher", None, data['module'])
    with sqlite3.connect("dori_bot.db") as db:
        word_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    add_library_word(session_id, word_id, can_edit=True)
    await message.answer(f"Слово '{data['text']}' добавлено.")
    await state.clear()

# --- Edit synonyms ---
@router.callback_query(F.data == "edit_synonyms")
async def teacher_prompt_edit_synonyms(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TeacherEditSynonyms.waiting_for_word_id)
    await callback.message.answer("Введите ID слова:")

@router.message(TeacherEditSynonyms.waiting_for_word_id)
async def teacher_receive_word_id_synonyms(message: types.Message, state: FSMContext):
    try:
        await state.update_data(word_id=int(message.text.strip()))
        await state.set_state(TeacherEditSynonyms.waiting_for_new_synonyms)
        await message.answer("Введите синонимы через запятую или '-' для удаления:")
    except ValueError:
        await message.answer("Введите числовой ID.")

# --- Batch add ---
@router.callback_query(F.data == "add_batch")
async def teacher_start_batch_add(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TeacherBatchAdd.waiting_for_batch_input)
    await callback.message.answer(
        "Формат: слово - перевод - синонимы - модуль\nПример:\ncat - кот - feline, kitty - 4"
    )

@router.message(TeacherBatchAdd.waiting_for_batch_input)
async def teacher_receive_batch_input(message: types.Message, state: FSMContext):
    await state.update_data(batch_text=message.text.strip())
    await state.set_state(TeacherBatchAdd.waiting_for_confirm)
    await message.answer("Подтвердите загрузку:", reply_markup=confirm_batch_upload_menu())

@router.callback_query(F.data == "confirm_batch")
async def teacher_confirm_batch(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    session_id = get_or_create_session(callback.from_user.id)
    success, failed = 0, []
    for line in data['batch_text'].splitlines():
        parts = [p.strip() for p in line.split("-")]
        if len(parts) != 4 or not parts[3].isdigit():
            failed.append(line)
            continue
        try:
            add_word(session_id, parts[0], parts[1], "A1", None, "teacher", parts[2], parts[3])
            success += 1
        except Exception:
            failed.append(line)
    summary = f"Добавлено: {success}"
    if failed:
        summary += "\nОшибки:\n" + "\n".join(failed)
    await callback.message.answer(summary)
    await state.clear()

@router.callback_query(F.data == "cancel_batch")
async def teacher_cancel_batch(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Добавление отменено.")

# --- View & Edit ---
@router.callback_query(F.data == "view_words")
async def teacher_view_words(callback: types.CallbackQuery):
    with sqlite3.connect("dori_bot.db") as db:
        rows = db.execute("SELECT Word_ID, Text, translation FROM Word WHERE added_by = 'teacher'").fetchall()
    if not rows:
        await callback.message.answer("База пуста.")
    else:
        await callback.message.answer("\n".join(f"{r[0]}. {r[1]} – {r[2]}" for r in rows))

@router.callback_query(F.data == "start_edit")
async def teacher_prompt_edit(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TeacherEditWord.waiting_for_word_id)
    await callback.message.answer("Введите ID или слово:")

@router.message(TeacherEditWord.waiting_for_word_id)
async def teacher_start_edit(message: types.Message, state: FSMContext):
    session_id = get_or_create_session(message.from_user.id)
    input_text = message.text.strip()
    word_id = None
    try:
        word_id = int(input_text)
    except ValueError:
        matches = [w for w in get_words(session_id) if w['Text'].lower() == input_text.lower()]
        if matches:
            word_id = matches[0]['Word_ID']
    if not word_id or not any(w['Word_ID'] == word_id for w in get_words(session_id)):
        await message.answer("Слово не найдено.")
        return
    await state.update_data(word_id=word_id)
    await state.set_state(TeacherEditWord.waiting_for_new_text)
    await message.answer("Введите новое английское слово:")

@router.message(TeacherEditWord.waiting_for_new_text)
async def teacher_edit_text(message: types.Message, state: FSMContext):
    await state.update_data(new_text=message.text)
    await state.set_state(TeacherEditWord.waiting_for_new_translation)
    await message.answer("Введите новый перевод:")

@router.message(TeacherEditWord.waiting_for_new_translation)
async def teacher_edit_translation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    with sqlite3.connect("dori_bot.db") as db:
        db.execute("UPDATE Word SET Text = ?, translation = ? WHERE Word_ID = ?", (data['new_text'], message.text, data['word_id']))
    await message.answer("Слово обновлено.")
    await state.clear()

def register(dp):
    dp.include_router(router)