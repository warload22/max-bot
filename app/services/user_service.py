"""
Модуль для работы с локальной базой данных пользователей и состояний диалога.
Использует таблицы users, dialog_states, user_settings и user_actions в PostgreSQL.
"""

import logging
import json
from typing import Optional, Dict
from datetime import datetime
from app.core.database import get_local_connection

logger = logging.getLogger(__name__)

# ---------- Работа с пользователями ----------

def get_user_by_max_id(max_user_id: int) -> Optional[Dict]:
    """
    Возвращает запись пользователя из таблицы users по его max_user_id.
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, max_user_id, moodle_username, moodle_user_id, is_authenticated, "
                "authenticated_at, last_interaction FROM users WHERE max_user_id = %s",
                (str(max_user_id),)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя {max_user_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def create_user(max_user_id: int, moodle_username: str, moodle_user_id: int) -> bool:
    """
    Создаёт новую запись пользователя после успешной авторизации.
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (max_user_id, moodle_username, moodle_user_id, is_authenticated, authenticated_at) "
                "VALUES (%s, %s, %s, TRUE, %s)",
                (str(max_user_id), moodle_username, moodle_user_id, datetime.now())
            )
        conn.commit()
        logger.info(f"Пользователь {max_user_id} создан (Moodle ID: {moodle_user_id}, username: {moodle_username})")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании пользователя {max_user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_user_authentication(max_user_id: int, moodle_username: str, moodle_user_id: int) -> bool:
    """
    Обновляет статус аутентификации существующего пользователя.
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET is_authenticated = TRUE, moodle_username = %s, moodle_user_id = %s, "
                "authenticated_at = %s, last_interaction = %s WHERE max_user_id = %s",
                (moodle_username, moodle_user_id, datetime.now(), datetime.now(), str(max_user_id))
            )
        conn.commit()
        logger.info(f"Пользователь {max_user_id} обновлён (аутентифицирован)")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя {max_user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def set_user_authenticated(max_user_id: int, moodle_username: str, moodle_user_id: int) -> bool:
    """
    Создаёт или обновляет запись пользователя после успешной авторизации.
    """
    user = get_user_by_max_id(max_user_id)
    if user:
        return update_user_authentication(max_user_id, moodle_username, moodle_user_id)
    else:
        return create_user(max_user_id, moodle_username, moodle_user_id)

# ---------- Логирование действий ----------

def log_user_action(max_user_id: int, action_type: str, moodle_user_id: int = None, details: Optional[Dict] = None) -> bool:
    """
    Записывает действие пользователя в таблицу user_actions.
    Если передан moodle_user_id, сохраняет его.
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO user_actions (user_id, action_type, moodle_user_id, details, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (str(max_user_id), action_type, moodle_user_id, 
                 json.dumps(details, ensure_ascii=False) if details else None, 
                 datetime.now())
            )
        conn.commit()
        logger.debug(f"Действие {action_type} от {max_user_id} залогировано (moodle={moodle_user_id})")
        return True
    except Exception as e:
        logger.error(f"Ошибка при логировании действия {action_type} для {max_user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ---------- Работа с состояниями диалога ----------

def get_dialog_state(max_user_id: int) -> Optional[Dict]:
    """
    Возвращает состояние диалога для пользователя.
    Возвращает словарь с полями state и data.
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT state, data FROM dialog_states WHERE max_user_id = %s",
                (str(max_user_id),)
            )
            row = cursor.fetchone()
            if row:
                return {"state": row["state"], "data": row["data"]}
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении состояния диалога для {max_user_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def set_dialog_state(max_user_id: int, state: str, data: Optional[Dict] = None) -> bool:
    """
    Устанавливает состояние диалога для пользователя.
    Если состояние уже существует, обновляет его.
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO dialog_states (max_user_id, state, data, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (max_user_id) DO UPDATE
                SET state = EXCLUDED.state,
                    data = EXCLUDED.data,
                    updated_at = EXCLUDED.updated_at
            """, (str(max_user_id), state, json.dumps(data) if data else None, datetime.now()))
        conn.commit()
        logger.info(f"Состояние диалога для {max_user_id} установлено: {state}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке состояния диалога для {max_user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def clear_dialog_state(max_user_id: int) -> bool:
    """
    Удаляет состояние диалога для пользователя.
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM dialog_states WHERE max_user_id = %s",
                (str(max_user_id),)
            )
        conn.commit()
        logger.info(f"Состояние диалога для {max_user_id} удалено")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении состояния диалога для {max_user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ---------- Работа с настройками пользователя ----------

def get_user_settings(max_user_id: int) -> Optional[Dict]:
    """
    Возвращает настройки пользователя из таблицы user_settings.
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT selected_type, selected_id FROM user_settings WHERE max_user_id = %s",
                (str(max_user_id),)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении настроек пользователя {max_user_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def set_user_setting(max_user_id: int, selected_type: str, selected_id: int) -> bool:
    """
    Сохраняет или обновляет настройки пользователя (выбранную группу/преподавателя/аудиторию).
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_settings (max_user_id, selected_type, selected_id, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (max_user_id) DO UPDATE
                SET selected_type = EXCLUDED.selected_type,
                    selected_id = EXCLUDED.selected_id,
                    updated_at = EXCLUDED.updated_at
            """, (str(max_user_id), selected_type, selected_id, datetime.now()))
        conn.commit()
        logger.info(f"Настройки для {max_user_id} сохранены: {selected_type}={selected_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении настроек для {max_user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ---------- Выход из аккаунта ----------

def logout_user(max_user_id: int) -> bool:
    """
    Удаляет данные пользователя и его настройки (выход из аккаунта).
    """
    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            # Удаляем настройки
            cursor.execute("DELETE FROM user_settings WHERE max_user_id = %s", (str(max_user_id),))
            # Удаляем пользователя
            cursor.execute("DELETE FROM users WHERE max_user_id = %s", (str(max_user_id),))
        conn.commit()
        logger.info(f"Пользователь {max_user_id} вышел из аккаунта (данные удалены)")
        return True
    except Exception as e:
        logger.error(f"Ошибка при выходе пользователя {max_user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()