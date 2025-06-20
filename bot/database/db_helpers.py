import sqlite3
from datetime import datetime
import random

DB_PATH = "dori_bot.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_or_create_session(telegram_id, local_id=None, role="student", level=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT StudentSession_ID FROM StudentSession WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()

    if row:
        session_id = row[0]
    else:
        cur.execute("""
            INSERT INTO StudentSession (telegram_id, localID, role, level)
            VALUES (?, ?, ?, ?)
        """, (telegram_id, local_id, role, level or "A1"))
        session_id = cur.lastrowid
        conn.commit()

    conn.close()
    return session_id

def get_user_role(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT role FROM StudentSession WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "student"

def set_user_session(telegram_id, role=None, level=None):
    conn = get_connection()
    cur = conn.cursor()
    if role and level:
        cur.execute("UPDATE StudentSession SET role = ?, level = ? WHERE telegram_id = ?", (role, level, telegram_id))
    elif role:
        cur.execute("UPDATE StudentSession SET role = ? WHERE telegram_id = ?", (role, telegram_id))
    elif level:
        cur.execute("UPDATE StudentSession SET level = ? WHERE telegram_id = ?", (level, telegram_id))
    conn.commit()
    conn.close()


def update_user_role(telegram_id, role):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE StudentSession
        SET role = ?
        WHERE telegram_id = ?
    """, (role, telegram_id))
    conn.commit()
    conn.close()

def update_user_level_and_role(telegram_id, level):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE StudentSession
        SET level = ?, role = 'student'
        WHERE telegram_id = ?
    """, (level, telegram_id))
    conn.commit()
    conn.close()

def add_word(session_id, text, translation, level="A1", part_of_speech=None, added_by="student", synonyms=None, module=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO Word (Text, translation, level, part_of_speech, added_by, created_at, StudentSession_ID, synonyms, module)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (text, translation, level, part_of_speech, added_by, datetime.now(), session_id, synonyms, module))
    conn.commit()
    conn.close()

def get_words(session_id, module=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT Word_ID, Text, translation, synonyms
        FROM Word
        WHERE added_by = 'teacher'
           OR StudentSession_ID = ?
    """
    params = [session_id]

    if module:
        query += " AND LOWER(module) = LOWER(?)"
        params.append(module)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "Word_ID": row[0],
            "Text": row[1],
            "translation": row[2],
            "synonyms": row[3] or "не указаны"
        }
        for row in rows
    ]

def update_progress(session_id, word_id, is_correct):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT PracticeProgress_ID, correct_count, incorrect_count FROM PracticeProgress
        WHERE StudentSession_ID = ? AND Word_ID = ?
    """, (session_id, word_id))
    row = cur.fetchone()

    if row:
        progress_id, correct, incorrect = row
        if is_correct:
            correct += 1
        else:
            incorrect += 1
        cur.execute("""
            UPDATE PracticeProgress
            SET correct_count = ?, incorrect_count = ?, last_practiced = CURRENT_TIMESTAMP
            WHERE PracticeProgress_ID = ?
        """, (correct, incorrect, progress_id))
    else:
        cur.execute("""
            INSERT INTO PracticeProgress (StudentSession_ID, Word_ID, correct_count, incorrect_count, last_practiced)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (session_id, word_id, 1 if is_correct else 0, 0 if is_correct else 1))

    conn.commit()
    conn.close()

def assign_achievement(session_id, achievement_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO UserAchievement (StudentSession_ID, Achievement_ID, timestamp)
        VALUES (?, ?, ?)
    """, (session_id, achievement_id, datetime.now()))
    conn.commit()
    conn.close()

def get_achievements(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.name, a.description, ua.timestamp
        FROM UserAchievement ua
        JOIN Achievement a ON ua.Achievement_ID = a.Achievement_ID
        WHERE ua.StudentSession_ID = ?
    """, (session_id,))
    achievements = cur.fetchall()
    conn.close()
    return achievements

def add_library_word(session_id, word_id, can_edit=True):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO LibraryWord (Word_ID, StudentSession_ID, can_edit, added_at)
        VALUES (?, ?, ?, ?)
    """, (word_id, session_id, int(can_edit), datetime.now()))
    conn.commit()
    conn.close()

def get_editable_library_words(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.Word_ID, w.Text, w.translation
        FROM LibraryWord lw
        JOIN Word w ON lw.Word_ID = w.Word_ID
        WHERE lw.StudentSession_ID = ? AND lw.can_edit = 1
    """, (session_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def can_user_edit_word(session_id, word_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM LibraryWord
        WHERE StudentSession_ID = ? AND Word_ID = ? AND can_edit = 1
    """, (session_id, word_id))
    result = cur.fetchone()
    conn.close()
    return result is not None

def get_all_modules():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT module FROM Word
        WHERE module IS NOT NULL AND module != ''
        ORDER BY module
    """)
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_weighted_words(session_id, module=None):
    conn = get_connection()
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
    rows = cur.fetchall()
    conn.close()

    words = []
    for row in rows:
        word_id, text, translation, synonyms, correct, incorrect = row
        weight = 1 + incorrect - correct
        if weight < 1:
            weight = 1
        words.append({
            "Word_ID": word_id,
            "Text": text,
            "translation": translation,
            "synonyms": synonyms or "не указаны",
            "weight": weight
        })
    return words


def get_teacher_words(module=None):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT Word_ID, Text, translation, module FROM Word WHERE added_by = 'teacher'"
    params = []
    if module:
        query += " AND LOWER(module) = LOWER(?)"
        params.append(module)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(zip(["Word_ID", "Text", "translation", "module"], row)) for row in rows]

def get_personal_words_by_session(session_id, module=None):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT Word_ID, Text, translation, module FROM Word WHERE StudentSession_ID = ?"
    params = [session_id]
    if module:
        query += " AND LOWER(module) = LOWER(?)"
        params.append(module)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(zip(["Word_ID", "Text", "translation", "module"], row)) for row in rows]
