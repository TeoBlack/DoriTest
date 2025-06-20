import random
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from bot.database.db_helpers import get_all_modules, get_connection, get_or_create_session, add_word, get_words, add_library_word, can_user_edit_word, update_progress
from bot.handlers.teacher import delete_message_later
from bot.menus import personal_dict_menu, student_main_menu, student_word_view_menu
from bot.services.card_generator import generate_flashcard_image
import asyncio
import sqlite3
from aiogram.types import Message
from aiogram.filters import Command


router = Router()


def pick_weighted_word(words):
    total = sum(word["weight"] for word in words)
    r = random.uniform(0, total)
    upto = 0
    for word in words:
        if upto + word["weight"] >= r:
            return word
        upto += word["weight"]
    return words[-1]  # fallback


class StudentEditWord(StatesGroup):
    waiting_for_word_id = State()
    waiting_for_new_text = State()
    waiting_for_new_translation = State()

class FlashcardState(StatesGroup):
    selecting_module = State()
    awaiting_input = State()

class PersonalDictFSM(StatesGroup):
    adding_word = State()
    adding_translation = State()
    deleting_word_id = State()


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
        cursor.execute("""
            UPDATE Word SET Text = ?, translation = ? WHERE Word_ID = ?
        """, (new_text, new_translation, word_id))
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

    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT Word_ID, Text, translation, synonyms
        FROM Word
        WHERE added_by = 'teacher'
    """
    params = []

    if module != "все":
        query += " AND LOWER(module) = LOWER(?)"
        params.append(module)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    words = [
        {"Word_ID": row[0], "Text": row[1], "translation": row[2], "synonyms": row[3] or "не указаны"}
        for row in rows
    ]

    if not words:
        await message.answer("Слов из этого модуля не найдено. Попробуйте другой модуль.")
        return

    random.shuffle(words)
    word = words[0]
    user_flashcards[message.from_user.id] = words[1:]

    await state.set_state(FlashcardState.awaiting_input)
    await state.update_data(current_word=word)

    image_path = generate_flashcard_image(word['translation'])
    sent_message = await message.answer_photo(photo=types.FSInputFile(image_path))
    asyncio.create_task(delete_message_later(message.bot, message.chat.id, sent_message.message_id))
    await message.answer(f"Слово: {word['translation']}")


@router.callback_query(F.data == "view_modules")
async def student_view_modules(callback: types.CallbackQuery):
    modules = get_all_modules()
    if not modules:
        await callback.message.answer("Модули пока не найдены.")
        return

    modules_list = "\n".join(modules)
    await callback.message.answer(f"Доступные модули:\n{modules_list}")

@router.message(Command("stopcard"))
async def stop_flashcard_session(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    await state.clear()

    # Safely remove if it exists
    if user_id in user_flashcards:
        user_flashcards.pop(user_id, None)

    await message.answer("⛔️ Режим флеш-карт остановлен.")

@router.message(FlashcardState.awaiting_input)
async def check_flashcard_answer(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/stopcard":
        await stop_flashcard_session(message, state)
        return

    session_id = get_or_create_session(message.from_user.id)
    data = await state.get_data()
    word = data["current_word"]

    user_input = message.text.strip().lower()
    correct = word['Text'].strip().lower()
    is_correct = user_input == correct

    update_progress(session_id, word['Word_ID'], is_correct)

    if is_correct:
        await message.answer("✅ Верно!")
    else:
        part = word.get("part_of_speech", "не указана")
        await message.answer(
            f"❌ Неверно.\n\n"
            f"Правильный ответ: <b>{word['Text']}</b>\n"
            f"Перевод: {word['translation']}\n"
            f"Синонимы: {word.get('synonyms', 'не указаны')}\n"
            f"Часть речи: {part}"
        )
        # Добавить в конец очереди
        user_flashcards.setdefault(message.from_user.id, []).append(word)

    next_words = user_flashcards.get(message.from_user.id, [])
    if not next_words:
        await message.answer("🎉 Тренировка завершена")
        await state.clear()
        return

    next_word = next_words.pop(0)
    user_flashcards[message.from_user.id] = next_words
    await state.update_data(current_word=next_word)

    image_path = generate_flashcard_image(next_word['translation'])
    sent_message: Message = await message.answer_photo(photo=types.FSInputFile(image_path))
    await message.answer(f"Слово: {next_word['translation']}")
    asyncio.create_task(delete_message_later(message.bot, message.chat.id, sent_message.message_id))


@router.message(Command("help"))
async def student_help(message: types.Message):
    help_text = "🎓 <b>Справка для студента:</b>\n\n"
    help_text += "<b>Основные команды:</b>\n"
    help_text += "/menu_student - Показать меню студента\n"
    help_text += "/levelSwitch Изменить уровень сложности (A1/A2/B1)\n"
    help_text += "/help - Показать эту справку\n\n"
    
    help_text += "<b>Функции меню:</b>\n"
    help_text += "• <b>Флеш-карты</b> - Тренировка перевода слов\n"
    help_text += "• <b>Редактировать слово</b> - Изменить слова из вашей библиотеки\n"
    help_text += "• <b>Мои модули</b> - Просмотреть доступные учебные модули\n"
    
    await message.answer(help_text, parse_mode="HTML")


@router.callback_query(F.data == "view_student_words")
async def student_words_entry(callback: types.CallbackQuery):
    await callback.message.answer("Что вы хотите просмотреть?", reply_markup=student_word_view_menu())


@router.callback_query(F.data == "student_words_all")
async def view_all_words(callback: types.CallbackQuery):
    session_id = get_or_create_session(callback.from_user.id)
    words = get_words(session_id=session_id)  # already returns all available to student
    if not words:
        await callback.message.answer("Слов не найдено.")
        return

    word_lines = [
    f"{w['Word_ID']}. {w['Text']} – {w['translation']}"
    for w in words
]

    await callback.message.answer("📚 Все доступные слова:\n" + "\n".join(word_lines))


@router.callback_query(F.data == "personal_dict_menu")
async def open_personal_dict_menu(callback: types.CallbackQuery):
    await callback.message.answer("Личный словарь: выберите действие", reply_markup=personal_dict_menu())


@router.callback_query(F.data == "personal_add")
async def personal_add_word_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PersonalDictFSM.adding_word)
    await callback.message.answer("Введите английское слово, которое хотите добавить:")

@router.message(PersonalDictFSM.adding_word)
async def personal_add_word_text(message: types.Message, state: FSMContext):
    await state.update_data(word=message.text.strip())
    await state.set_state(PersonalDictFSM.adding_translation)
    await message.answer("Введите перевод этого слова:")

@router.message(PersonalDictFSM.adding_translation)
async def personal_add_word_translation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    word = data["word"]
    translation = message.text.strip()
    session_id = get_or_create_session(message.from_user.id)

    add_word(
        session_id=session_id,
        text=word,
        translation=translation,
        level="A1",
        added_by="student"
    )

    await message.answer(f"✅ Слово <b>{word}</b> добавлено в ваш личный словарь.", parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "personal_view")
async def personal_view(callback: types.CallbackQuery):
    session_id = get_or_create_session(callback.from_user.id)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT Word_ID, Text, translation FROM Word
        WHERE added_by = 'student' AND StudentSession_ID = ?
    """, (session_id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await callback.message.answer("🕵️ Ваш личный словарь пока пуст.")
        return

    lines = [f"{row[0]}. {row[1]} – {row[2]}" for row in rows]
    await callback.message.answer("📓 Ваши слова:\n" + "\n".join(lines))

@router.callback_query(F.data == "personal_delete")
async def personal_delete_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PersonalDictFSM.deleting_word_id)
    await callback.message.answer("Введите ID слова из вашего словаря, которое хотите удалить:")

@router.message(PersonalDictFSM.deleting_word_id)
async def personal_delete_confirm(message: types.Message, state: FSMContext):
    session_id = get_or_create_session(message.from_user.id)
    try:
        word_id = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите числовой ID.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM Word
        WHERE Word_ID = ? AND added_by = 'student' AND StudentSession_ID = ?
    """, (word_id, session_id))
    deleted = cur.rowcount
    conn.commit()
    conn.close()

    if deleted:
        await message.answer("✅ Слово удалено.")
    else:
        await message.answer("❌ Не удалось удалить слово. Убедитесь, что оно существует и принадлежит вам.")
    await state.clear()



def register(dp):
    dp.include_router(router)