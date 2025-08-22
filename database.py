# database.py
# Этот файл отвечает за работу с базой данных
import sqlite3
import logging
from typing import List, Optional, Tuple, Any

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Имя файла базы данных
DB_NAME = "baraholka.db"

def get_db_connection():
    """Создает и возвращает соединение с базой данных."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # ← ЭТА СТРОКА ВАЖНА! Теперь результаты будут как словари
    return conn

def init_db():
    """Инициализирует базу данных, создает таблицы, если они не существуют."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Таблица для объявлений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT,
            text TEXT,
            contact TEXT,
            photos TEXT, -- Будем хранить ID фотографий через запятую
            is_paid BOOLEAN DEFAULT FALSE,
            is_published BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица для рефералов (для будущей системы бонусов)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL, -- Кто пригласил
            new_user_id INTEGER NOT NULL UNIQUE, -- Кого пригласили
            bonus_paid BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица для акций (для будущего функционала)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            photo_id TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            start_date DATETIME,
            end_date DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована (таблицы созданы/проверены)")

# Вспомогательные функции для работы с объявлениями
def create_ad(user_id: int, category: str) -> int:
    """Создает новую запись объявления в БД и возвращает его ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO ads (user_id, category) VALUES (?, ?)',
        (user_id, category)
    )
    ad_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Создано новое объявление ID {ad_id} для пользователя {user_id}")
    return ad_id

def get_ad(ad_id: int, user_id: int) -> Optional[sqlite3.Row]:
    """Получает объявление по его ID и ID пользователя (для безопасности)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM ads WHERE id = ? AND user_id = ?',
        (ad_id, user_id)
    )
    ad = cursor.fetchone()
    conn.close()
    return ad

def update_ad_text(ad_id: int, user_id: int, text: str) -> bool:
    """Обновляет текст объявления."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE ads SET text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?',
        (text, ad_id, user_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    if success:
        logger.info(f"Обновлен текст для объявления {ad_id}")
    else:
        logger.warning(f"Не удалось обновить текст для объявления {ad_id} (пользователь {user_id})")
    return success

# ... (здесь будут другие функции для обновления фото, контактов и т.д.) ...

def set_ad_photos(ad_id: int, user_id: int, photo_ids: List[str]) -> bool:
    """Обновляет список фото для объявления."""
    # Сохраняем ID фото как строку, разделенную запятыми
    photos_str = ",".join(photo_ids)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE ads SET photos = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?',
        (photos_str, ad_id, user_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def set_ad_contact(ad_id: int, user_id: int, contact: str) -> bool:
    """Обновляет контакт для объявления."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE ads SET contact = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?',
        (contact, ad_id, user_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def set_ad_paid(ad_id: int, user_id: int) -> bool:
    """Отмечает объявление как оплаченное."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE ads SET is_paid = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?',
        (ad_id, user_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def set_ad_published(ad_id: int) -> bool:
    """Отмечает объявление как опубликованное в канале."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE ads SET is_published = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (ad_id,)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def delete_ad(ad_id: int, user_id: int) -> bool:
    """Удаляет объявление."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM ads WHERE id = ? AND user_id = ?',
        (ad_id, user_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

# Запустим инициализацию БД при импорте этого файла
init_db()

def get_user_last_ad(user_id: int):
    """Получает данные последнего объявления пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM ads WHERE user_id = ? ORDER BY id DESC LIMIT 1',
        (user_id,)
    )
    ad = cursor.fetchone()
    conn.close()
    return ad


def set_ad_paid(ad_id: int, user_id: int) -> bool:
    """Отмечает объявление как оплаченное."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE ads SET is_paid = TRUE WHERE id = ? AND user_id = ?',
        (ad_id, user_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success
