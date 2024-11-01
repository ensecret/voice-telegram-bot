import sqlite3

def create_initial_table():
    conn = sqlite3.connect('voices.db')
    cursor = conn.cursor()
    try:
        # Создаем таблицу, если она не существует
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voices (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                file_id TEXT NOT NULL,
                user_id INTEGER  -- Можно убрать после миграции
            )
        ''')
        conn.commit()
        print("Таблица voices создана или уже существует.")
    except sqlite3.OperationalError as e:
        print(f"Ошибка при создании таблицы voices: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_initial_table()