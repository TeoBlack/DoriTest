import sqlite3
import random
from typing import Dict, Optional

DB_PATH = "dori_bot.db"

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
            
            if row:
                return dict(row)
            return None
            
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

def get_college_words() -> list:

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT w.* 
                FROM Word w
                WHERE w.added_by = 'teacher'
            """)
            return [dict(row) for row in cursor.fetchall()]
            
    except sqlite3.Error as e:
        print(f"Database error in get_college_words: {e}")
        return []

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
            
            # Получаем StudentSession_ID для пользователя
            cursor.execute("""
                INSERT OR IGNORE INTO StudentSession (telegram_id) 
                VALUES (?)
            """, (user_id,))
            
            cursor.execute("""
                SELECT StudentSession_ID 
                FROM StudentSession 
                WHERE telegram_id = ?
            """, (user_id,))
            session_id = cursor.fetchone()[0]
            
            # Добавляем слово
            cursor.execute("""
                INSERT INTO Word (
                    Text, 
                    translation, 
                    added_by, 
                    StudentSession_ID
                ) VALUES (?, ?, 'student', ?)
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