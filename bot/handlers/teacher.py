from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from bot.database.db_helpers import get_or_create_session, add_word, get_words, add_library_word
from bot.menus import teacher_main_menu, confirm_batch_upload_menu
import asyncio
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton



import sqlite3

router = Router()

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

@router.message(F.text.lower() == "/menu_teacher")
async def show_teacher_menu(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=teacher_main_menu())

# --- Single word add flow ---

@router.callback_query(F.data == "add_word")
async def teacher_start_add(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TeacherAddWord.waiting_for_text)
    await callback.message.answer("Введите английское слово, которое хотите добавить в общую базу:")

@router.message(TeacherAddWord.waiting_for_text)
async def teacher_get_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(TeacherAddWord.waiting_for_translation)
    await message.answer("Введите перевод этого слова:")

@router.message(TeacherAddWord.waiting_for_translation)
async def teacher_get_translation(message: types.Message, state: FSMContext):
    await state.update_data(translation=message.text)
    await state.set_state(TeacherAddWord.waiting_for_part_of_speech)
    await message.answer(
        "Укажите часть речи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="noun", callback_data="pos_noun")],
            [InlineKeyboardButton(text="verb", callback_data="pos_verb")],
            [InlineKeyboardButton(text="adjective", callback_data="pos_adjective")],
            [InlineKeyboardButton(text="adverb", callback_data="pos_adverb")],
            [InlineKeyboardButton(text="phrase", callback_data="pos_phrase")],
            [InlineKeyboardButton(text="phrasal verb", callback_data="pos_phrasal")]
        ])
    )


@router.callback_query(F.data.startswith("pos_"))
async def teacher_receive_pos(callback: types.CallbackQuery, state: FSMContext):
    part_of_speech = callback.data.split("_")[1]
    await state.update_data(part_of_speech=part_of_speech)
    await state.set_state(TeacherAddWord.waiting_for_level)

    await callback.message.answer(
        "Выберите уровень сложности:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="A1", callback_data="level_A1")],
            [InlineKeyboardButton(text="A2", callback_data="level_A2")],
            [InlineKeyboardButton(text="B1", callback_data="level_B1")]
        ])
    )



@router.callback_query(F.data.startswith("level_"))
async def teacher_get_module(callback: types.CallbackQuery, state: FSMContext):
    level = callback.data.split("_")[1]
    await state.update_data(level=level)
    await state.set_state(TeacherAddWord.waiting_for_module)
    await callback.message.answer("Введите номер модуля (только цифру, например: 4):")

@router.message(TeacherAddWord.waiting_for_module)
async def teacher_save_word(message: types.Message, state: FSMContext):
    module_input = message.text.strip()
    if not module_input.isdigit():
        await message.answer("Пожалуйста, введите только номер модуля (например: 4).")
        return
    await state.update_data(module=module_input)

    data = await state.get_data()
    session_id = get_or_create_session(message.from_user.id)

    add_word(
        session_id=session_id,
        text=data['text'],
        translation=data['translation'],
        level=data['level'],
        part_of_speech=data['part_of_speech'],  # Add this
        added_by="teacher",
        module=data['module']
    )


    with sqlite3.connect("dori_bot.db") as db:
        cursor = db.cursor()
        cursor.execute("SELECT last_insert_rowid()")
        word_id = cursor.fetchone()[0]

    add_library_word(session_id=session_id, word_id=word_id, can_edit=True)

    await message.answer(f"Слово '{data['text']}' добавлено с уровнем {data['level']} и модулем {data['module']} и помещено в библиотеку.")
    await state.clear()


@router.callback_query(F.data == "edit_synonyms")
async def teacher_prompt_edit_synonyms(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TeacherEditSynonyms.waiting_for_word_id)
    await callback.message.answer("Введите ID слова, для которого хотите изменить синонимы:")


@router.message(TeacherEditSynonyms.waiting_for_word_id)
async def teacher_receive_word_id_synonyms(message: types.Message, state: FSMContext):
    try:
        word_id = int(message.text.strip())
        await state.update_data(word_id=word_id)
        await state.set_state(TeacherEditSynonyms.waiting_for_new_synonyms)
        await message.answer("Введите новые синонимы через запятую (или '-' если хотите очистить):")
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите числовой ID слова.")

# --- Batch word add flow ---

@router.callback_query(F.data == "add_batch")
async def teacher_start_batch_add(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TeacherBatchAdd.waiting_for_batch_input)
    await callback.message.answer(
        "Отправьте список слов для добавления в формате:\n"
        "`english_word - russian_translation - synonym1, synonym2 - module_number`\n"
        "Каждое слово с новой строки.\n\n"
        "Пример:\ncat - кот - feline, kitty - 4\nсобака - dog - canine, pooch - 4"
    )

@router.message(TeacherBatchAdd.waiting_for_batch_input)
async def teacher_receive_batch_input(message: types.Message, state: FSMContext):
    batch_text = message.text.strip()
    if not batch_text:
        await message.answer("Пожалуйста, отправьте хотя бы одно слово.")
        return

    await state.update_data(batch_text=batch_text)
    await state.set_state(TeacherBatchAdd.waiting_for_confirm)
    await message.answer("Вы уверены, что хотите добавить эти слова?", reply_markup=confirm_batch_upload_menu())

@router.callback_query(F.data == "confirm_batch")
async def teacher_confirm_batch(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    batch_text = data.get("batch_text", "")
    session_id = get_or_create_session(callback.from_user.id)

    success_count = 0
    fail_lines = []

    for line in batch_text.split("\n"):
        parts = [part.strip() for part in line.split("-")]
        if len(parts) != 4:
            fail_lines.append(line)
            continue

        text = parts[0]
        translation = parts[1]
        synonyms = parts[2]
        module = parts[3]

        if not module.isdigit():
            fail_lines.append(line)
            continue

        try:
            add_word(
                session_id=session_id,
                text=text,
                translation=translation,
                level="A1",  # default level; you can extend later to specify level per batch line
                added_by="teacher",
                module=module,
                synonyms=synonyms
            )
            success_count += 1
        except Exception:
            fail_lines.append(line)

    reply = f"Успешно добавлено слов: {success_count}."
    if fail_lines:
        reply += "\nНе удалось добавить следующие строки:\n" + "\n".join(fail_lines)

    await callback.message.answer(reply)
    await state.clear()

@router.callback_query(F.data == "cancel_batch")
async def teacher_cancel_batch(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Добавление слов отменено.")

# --- Existing word viewing and editing handlers ---

@router.callback_query(F.data == "view_words")
async def teacher_view_words(callback: types.CallbackQuery):
    conn = sqlite3.connect("dori_bot.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT Word_ID, Text, translation, synonyms
        FROM Word
        WHERE added_by = 'teacher'
        ORDER BY Word_ID
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await callback.message.answer("База слов пуста.")
    else:
        word_lines = [f"{row[0]}. {row[1]} – {row[2]}" for row in rows]
        await callback.message.answer("Слова, добавленные всеми преподавателями:\n" + "\n".join(word_lines))


@router.callback_query(F.data == "start_edit")
async def teacher_prompt_edit(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TeacherEditWord.waiting_for_word_id)
    await callback.message.answer("Введите ID слова, которое хотите изменить:")

@router.message(TeacherEditWord.waiting_for_word_id)
async def teacher_start_edit(message: types.Message, state: FSMContext):
    user_input = message.text.strip()
    session_id = get_or_create_session(message.from_user.id)

    # Try parsing as integer id
    word_id = None
    word_text = None
    try:
        word_id = int(user_input)
    except ValueError:
        word_text = user_input.lower()

    if word_id:
        # Check if word_id exists for this teacher
        words = get_words(session_id)
        if not any(w['Word_ID'] == word_id for w in words):
            await message.answer("Слово с таким ID не найдено. Попробуйте снова.")
            return
    else:
        # Try to find word by text
        words = get_words(session_id)
        matching = [w for w in words if w['Text'].lower() == word_text]
        if not matching:
            await message.answer("Слово не найдено. Попробуйте снова.")
            return
        word_id = matching[0]['Word_ID']

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
    word_id = data['word_id']
    new_text = data['new_text']
    new_translation = message.text

    with sqlite3.connect("dori_bot.db") as db:
        cursor = db.cursor()
        cursor.execute("""
            UPDATE Word SET Text = ?, translation = ? WHERE Word_ID = ?
        """, (new_text, new_translation, word_id))
        db.commit()

    await message.answer(f"Слово {word_id} обновлено: {new_text} – {new_translation}")
    await state.clear()



async def delete_message_later(bot, chat_id, message_id, delay=180):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass  # Ignore if already deleted or no permissions

@router.message(Command("help"))
async def teacher_help(message: types.Message):
    help_text = "👨‍🏫 <b>Справка для преподавателя:</b>\n\n"
    help_text += "<b>Основные команды:</b>\n"
    help_text += "/menu_teacher - Показать меню преподавателя\n"
    help_text += "/help - Показать эту справку\n\n"
    
    help_text += "<b>Функции меню:</b>\n"
    help_text += "• <b>Добавить слово</b> - Добавить новое слово в базу\n"
    help_text += "• <b>Добавить пакет слов</b> - Добавить несколько слов за раз\n"
    help_text += "• <b>Просмотреть все слова</b> - Посмотреть все слова в базе\n"
    help_text += "• <b>Редактировать слово</b> - Изменить существующее слово\n"
    help_text += "• <b>Редактировать синонимы</b> - Изменить синонимы слова\n"
    help_text += "• <b>Мои модули</b> - Просмотреть учебные модули\n"
    
    await message.answer(help_text, parse_mode="HTML")


def register(dp):
    dp.include_router(router)
