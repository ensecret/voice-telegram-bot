import uuid
import logging
import os
import sqlite3
import sys  # Добавлено для использования sys.exit()
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultCachedVoice
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackContext,
    InlineQueryHandler,
    MessageHandler,
    filters,
)
import telegram  # Добавлено для доступа к telegram.error.TimedOut

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    print("Ошибка: Не найден токен бота в переменных окружения.")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Инициализация базы данных
def initialize_db():
    conn = sqlite3.connect('voices.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_id TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


# Функции для работы с базой данных
def add_voice(name: str, file_id: str):
    conn = sqlite3.connect('voices.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO voices (name, file_id) VALUES (?, ?)', (name, file_id))
    conn.commit()
    conn.close()


def search_voices(query: str):
    conn = sqlite3.connect('voices.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, file_id FROM voices WHERE name LIKE ?', (f'%{query}%',))
    results = cursor.fetchall()
    conn.close()
    return results


def remove_voice_by_name(name: str):
    conn = sqlite3.connect('voices.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM voices WHERE name = ?', (name,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted


# Функция обработки голосового сообщения для сохранения
async def save_voice(update: Update, context: CallbackContext):
    voice = update.message.voice
    if not voice:
        await update.message.reply_text('Пожалуйста, отправьте голосовое сообщение.')
        return

    # Извлечение имени файла из подписи, если есть, иначе использовать стандартное название
    file_name = update.message.caption if update.message.caption else "Голосовое сообщение"

    file_id = voice.file_id

    # Сохраняем голосовое сообщение в базе данных
    add_voice(file_name, file_id)
    await update.message.reply_text(f'Голосовое сообщение "{file_name}" сохранено!')


# Функция обработки команды /cancel
async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text('Добавление голосового сообщения отменено.')


# Функция обработки команды /removevoice
async def remove_voice(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        await update.message.reply_text(
            'Пожалуйста, укажите имя голосового сообщения для удаления. Используйте: /removevoice <имя>'
        )
        return
    name = ' '.join(args)

    deleted = remove_voice_by_name(name)
    if deleted > 0:
        await update.message.reply_text(f'Голосовое сообщение "{name}" удалено.')
    else:
        await update.message.reply_text(f'Голосовое сообщение "{name}" не найдено.')


# Функция обработки инлайн-запросов
async def inline_query(update: Update, context: CallbackContext):
    query = update.inline_query.query
    user = update.inline_query.from_user
    logger.info(f"Получен инлайн-запрос от пользователя {user.id}: {query}")

    # Поиск голосовых сообщений по имени
    matched_voices = search_voices(query)

    logger.info(f"Найдено {len(matched_voices)} голосовых сообщений для пользователя {user.id}.")

    results = []
    for voice in matched_voices[:50]:  # Ограничиваем до 50 результатов
        name, file_id = voice
        # Заполняем title корректным значением, чтобы избежать ошибки Audio_title_empty
        results.append(
            InlineQueryResultCachedVoice(
                id=str(uuid.uuid4()),
                voice_file_id=file_id,
                title=name or "Голосовое сообщение"  # Используем название или дефолтное значение
            )
        )

    # Отправка результатов
    try:
        await update.inline_query.answer(results, cache_time=1)
    except Exception as e:
        logger.error(f"Ошибка при отправке результатов инлайн-запроса: {e}")


# Функция обработчика ошибок
async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error(msg="Исключение при обработке обновления:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text('Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.')
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


if __name__ == '__main__':
    try:
        # Инициализация базы данных
        initialize_db()

        # Создаем объект приложения
        application = ApplicationBuilder().token(TOKEN).build()

        # Добавляем обработчики
        voice_handler = MessageHandler(filters.VOICE, save_voice)
        application.add_handler(voice_handler)

        remove_voice_handler = CommandHandler('removevoice', remove_voice)
        application.add_handler(remove_voice_handler)

        inline_query_handler = InlineQueryHandler(inline_query)
        application.add_handler(inline_query_handler)

        # Добавляем обработчик ошибок
        application.add_error_handler(error_handler)

        # Запускаем бота
        logger.info("Бот запущен...")
        application.run_polling()
    except telegram.error.TimedOut:
        logger.error("Не удалось подключиться к серверам Telegram: Тайм-аут.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        sys.exit(1)
