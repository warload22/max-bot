"""
Модуль аутентификации пользователей через базу Moodle.
"""

import bcrypt
import logging
from typing import Optional, Dict
from app.core.database import get_moodle_connection

logger = logging.getLogger(__name__)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет пароль против хеша. Поддерживает только bcrypt ($2y$).
    """
    if hashed_password.startswith('$2y$'):
        # bcrypt требует байты
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    else:
        # Если вдруг другой формат (маловероятно), логируем и возвращаем False
        logger.warning(f"Неизвестный формат хеша: {hashed_password[:20]}...")
        return False

def get_user_by_username(username: str) -> Optional[Dict]:
    """
    Ищет пользователя в таблице mdl_user по username.
    Возвращает словарь с данными пользователя или None.
    """
    conn = None
    try:
        conn = get_moodle_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password, auth, firstname, lastname, email "
                "FROM mdl_user WHERE username = %s AND deleted = 0 AND suspended = 0",
                (username,)
            )
            user = cursor.fetchone()
        return user
    except Exception as e:
        logger.error(f"Ошибка при поиске пользователя {username}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Проверяет логин и пароль.
    Возвращает данные пользователя при успехе, иначе None.
    """
    user = get_user_by_username(username)
    if not user:
        logger.info(f"Пользователь {username} не найден")
        return None

    stored_hash = user['password']
    if verify_password(password, stored_hash):
        logger.info(f"Успешная авторизация: {username}")
        return user
    else:
        logger.warning(f"Неверный пароль для {username}")
        return None
