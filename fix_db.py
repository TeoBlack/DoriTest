import sqlite3

conn = sqlite3.connect("dori_bot.db")
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE StudentSession ADD COLUMN level TEXT CHECK(level IN ('A1', 'A2', 'B1'))")
    conn.commit()
    print("Колонка 'level' успешно добавлена.")
except sqlite3.OperationalError as e:
    print("Ошибка:", e)

conn.close()
