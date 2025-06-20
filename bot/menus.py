from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def teacher_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить слово", callback_data="add_word")],
        [InlineKeyboardButton(text="Добавить пакет слов", callback_data="add_batch")],  # Batch add button
        [InlineKeyboardButton(text="Посмотреть все слова", callback_data="view_words")],
        [InlineKeyboardButton(text="Редактировать слово", callback_data="start_edit")],
        [InlineKeyboardButton(text="Мои модули", callback_data="view_modules")]
    ])


def student_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Флеш-карты", callback_data="flashcards_start")],
        [InlineKeyboardButton(text="✏️ Редактировать слово", callback_data="student_start_edit")],
        [InlineKeyboardButton(text="📚 Мои модули", callback_data="view_modules")],
        [InlineKeyboardButton(text="📖 Мои слова", callback_data="view_student_words")],
        [InlineKeyboardButton(text="📓 Личный словарь", callback_data="personal_dict_menu")]  # ✅ fixed with comma
    ])


def module_selection_menu(modules: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=mod, callback_data=f"module_{mod}")] for mod in modules
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_batch_upload_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить загрузку", callback_data="confirm_batch")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_batch")]
    ])


def start_choice_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Преподаватель", callback_data="choose_teacher")],
        [InlineKeyboardButton(text="Студент", callback_data="choose_student")]
    ])


def back_to_start_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вернуться к выбору роли", callback_data="back_to_start")]
    ])


def teacher_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить слово", callback_data="add_word")],
        [InlineKeyboardButton(text="Добавить пакет слов", callback_data="add_batch")],
        [InlineKeyboardButton(text="Посмотреть все слова", callback_data="view_words")],
        [InlineKeyboardButton(text="Редактировать слово", callback_data="start_edit")],
        [InlineKeyboardButton(text="Редактировать синонимы", callback_data="edit_synonyms")],  # New button
        [InlineKeyboardButton(text="Мои модули", callback_data="view_modules")]
    ])


def student_word_view_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Все доступные", callback_data="student_words_all")],
        [InlineKeyboardButton(text="Только мои", callback_data="student_words_personal")],
        [InlineKeyboardButton(text="Только учителя", callback_data="student_words_teacher")],
        [InlineKeyboardButton(text="Сортировать по модулю", callback_data="student_words_by_module")]
    ])


def personal_dict_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить слово", callback_data="personal_add")],
        [InlineKeyboardButton(text="❌ Удалить слово", callback_data="personal_delete")],
        [InlineKeyboardButton(text="📖 Показать словарь", callback_data="personal_view")],
    ])
