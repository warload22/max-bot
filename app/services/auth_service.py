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

def is_user_admin(moodle_user_id: int) -> bool:
    """
    Проверяет, является ли пользователь с данным ID администратором Moodle.
    Администраторы определяются параметром siteadmins в таблице mdl_config.
    """
    try:
        logger.info(f"is_user_admin: проверка для moodle_user_id={moodle_user_id}")
        conn = get_moodle_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT value FROM mdl_config WHERE name = 'siteadmins'")
            result = cursor.fetchone()
            logger.info(f"is_user_admin: result = {result}")
        conn.close()
        
        if not result or not result['value']:
            logger.debug(f"siteadmins не найден или пуст")
            return False
        
        # Парсим строку вида "7,6,33,17021,9123,..." в список целых чисел
        admin_ids_str = result['value'].strip()
        admin_ids = []
        for part in admin_ids_str.split(','):
            part = part.strip()
            if part.isdigit():
                admin_ids.append(int(part))
            else:
                logger.warning(f"Некорректный ID в siteadmins: '{part}'")
        
        is_admin = moodle_user_id in admin_ids
        logger.info(f"is_user_admin: moodle_user_id={moodle_user_id} в списке? {is_admin}")
        return is_admin
    
    except Exception as e:
        logger.error(f"Ошибка при проверке прав администратора для user_id {moodle_user_id}: {e}", exc_info=True)
        return False