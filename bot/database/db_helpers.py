import sqlite3
from datetime import datetime
import random
from typing import Dict, Optional, List

DB_PATH = "dori_bot.db"


def get_connection():
    return sqlite3.connect(DB_PATH)

# --- Session & User Management ---

def get_or_create_session(telegram_id, local_id=None, role="student", level=None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT StudentSession_ID FROM StudentSession WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("""
            INSERT INTO StudentSession (telegram_id, localID, role, level)
            VALUES (?, ?, ?, ?)
        """, (telegram_id, local_id, role, level or "A1"))
        return cur.lastrowid

def get_user_role(telegram_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM StudentSession WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        return row[0] if row else "student"

def set_user_session(telegram_id, role=None, level=None):
    with get_connection() as conn:
        cur = conn.cursor()
        if role and level:
            cur.execute("UPDATE StudentSession SET role = ?, level = ? WHERE telegram_id = ?", (role, level, telegram_id))
        elif role:
            cur.execute("UPDATE StudentSession SET role = ? WHERE telegram_id = ?", (role, telegram_id))
        elif level:
            cur.execute("UPDATE StudentSession SET level = ? WHERE telegram_id = ?", (level, telegram_id))

def update_user_role(telegram_id, role):
    set_user_session(telegram_id, role=role)

def update_user_level_and_role(telegram_id, level):
    set_user_session(telegram_id, role="student", level=level)

# --- Word Management ---

def add_word(session_id, text, translation, level="A1", part_of_speech=None, added_by="student", synonyms=None, module=None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Word (Text, translation, level, part_of_speech, added_by, created_at, StudentSession_ID, synonyms, module)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (text, translation, level, part_of_speech, added_by, datetime.now(), session_id, synonyms, module))

def get_words(session_id, module=None):
    with get_connection() as conn:
        cur = conn.cursor()
        query = """
            SELECT Word_ID, Text, translation, synonyms
            FROM Word
            WHERE added_by = 'teacher' OR StudentSession_ID = ?
        """
        params = [session_id]
        if module:
            query += " AND LOWER(module) = LOWER(?)"
            params.append(module)
        cur.execute(query, params)
        return [{
            "Word_ID": row[0],
            "Text": row[1],
            "translation": row[2],
            "synonyms": row[3] or "не указаны"
        } for row in cur.fetchall()]

def get_weighted_words(session_id, module=None):
    with get_connection() as conn:
        cur = conn.cursor()
        query = """
            SELECT w.Word_ID, w.Text, w.translation, w.synonyms,
                   IFNULL(p.correct_count, 0), IFNULL(p.incorrect_count, 0)
            FROM Word w
            LEFT JOIN PracticeProgress p ON w.Word_ID = p.Word_ID AND p.StudentSession_ID = ?
            WHERE w.StudentSession_ID = ?
        """
        params = [session_id, session_id]
        if module:
            query += " AND w.module = ?"
            params.append(module)
        cur.execute(query, params)
        words = []
        for row in cur.fetchall():
            correct, incorrect = row[4], row[5]
            weight = max(1, 1 + incorrect - correct)
            words.append({
                "Word_ID": row[0],
                "Text": row[1],
                "translation": row[2],
                "synonyms": row[3] or "не указаны",
                "weight": weight
            })
        return words

# --- Progress & Achievements ---

def update_progress(session_id, word_id, is_correct):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT PracticeProgress_ID, correct_count, incorrect_count
            FROM PracticeProgress
            WHERE StudentSession_ID = ? AND Word_ID = ?
        """, (session_id, word_id))
        row = cur.fetchone()
        if row:
            correct = row[1] + int(is_correct)
            incorrect = row[2] + int(not is_correct)
            cur.execute("""
                UPDATE PracticeProgress
                SET correct_count = ?, incorrect_count = ?, last_practiced = CURRENT_TIMESTAMP
                WHERE PracticeProgress_ID = ?
            """, (correct, incorrect, row[0]))
        else:
            cur.execute("""
                INSERT INTO PracticeProgress (StudentSession_ID, Word_ID, correct_count, incorrect_count, last_practiced)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (session_id, word_id, int(is_correct), int(not is_correct)))

def assign_achievement(session_id, achievement_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO UserAchievement (StudentSession_ID, Achievement_ID, timestamp)
            VALUES (?, ?, ?)
        """, (session_id, achievement_id, datetime.now()))

def get_achievements(session_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.name, a.description, ua.timestamp
            FROM UserAchievement ua
            JOIN Achievement a ON ua.Achievement_ID = a.Achievement_ID
            WHERE ua.StudentSession_ID = ?
        """, (session_id,))
        return cur.fetchall()

# --- Library & Module Utilities ---

def add_library_word(session_id, word_id, can_edit=True):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO LibraryWord (Word_ID, StudentSession_ID, can_edit, added_at)
            VALUES (?, ?, ?, ?)
        """, (word_id, session_id, int(can_edit), datetime.now()))

def get_editable_library_words(session_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT w.Word_ID, w.Text, w.translation
            FROM LibraryWord lw
            JOIN Word w ON lw.Word_ID = w.Word_ID
            WHERE lw.StudentSession_ID = ? AND lw.can_edit = 1
        """, (session_id,))
        return cur.fetchall()

def can_user_edit_word(session_id, word_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM LibraryWord
            WHERE StudentSession_ID = ? AND Word_ID = ? AND can_edit = 1
        """, (session_id, word_id))
        return cur.fetchone() is not None

def get_all_modules():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT module FROM Word
            WHERE module IS NOT NULL AND module != ''
            ORDER BY module
        """)
        return [row[0] for row in cur.fetchall()]

def get_teacher_words(module=None):
    with get_connection() as conn:
        cur = conn.cursor()
        query = "SELECT Word_ID, Text, translation, module FROM Word WHERE added_by = 'teacher'"
        params = []
        if module:
            query += " AND LOWER(module) = LOWER(?)"
            params.append(module)
        cur.execute(query, params)
        return [dict(zip(["Word_ID", "Text", "translation", "module"], row)) for row in cur.fetchall()]

def get_personal_words_by_session(session_id, module=None):
    with get_connection() as conn:
        cur = conn.cursor()
        query = "SELECT Word_ID, Text, translation, module FROM Word WHERE StudentSession_ID = ?"
        params = [session_id]
        if module:
            query += " AND LOWER(module) = LOWER(?)"
            params.append(module)
        cur.execute(query, params)
        return [dict(zip(["Word_ID", "Text", "translation", "module"], row)) for row in cur.fetchall()]

def get_random_word(level: str = None) -> Optional[Dict]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM Word WHERE 1=1"
            params = []
            if level and level != "all":
                query += " AND level = ?"
                params.append(level)
            query += " ORDER BY RANDOM() LIMIT 1"
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Database error in get_random_word: {e}")
        return None

def get_word_definition(word_id: int) -> Optional[str]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT translation FROM Word WHERE Word_ID = ?", (word_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        print(f"Database error in get_word_definition: {e}")
        return None

def get_personal_words(user_id: int) -> list:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT w.* 
                FROM Word w
                JOIN StudentSession ss ON ss.telegram_id = ?
                WHERE w.StudentSession_ID = ss.StudentSession_ID
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error in get_personal_words: {e}")
        return []

def add_personal_word(user_id: int, word: str, translation: str) -> bool:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO StudentSession (telegram_id) VALUES (?)", (user_id,))
            cursor.execute("SELECT StudentSession_ID FROM StudentSession WHERE telegram_id = ?", (user_id,))
            session_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO Word (Text, translation, added_by, StudentSession_ID)
                VALUES (?, ?, 'student', ?)
            """, (word, translation, session_id))
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"Database error in add_personal_word: {e}")
        return False

def delete_personal_word(word_id: int) -> bool:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Word WHERE Word_ID = ?", (word_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Database error in delete_personal_word: {e}")
        return False
