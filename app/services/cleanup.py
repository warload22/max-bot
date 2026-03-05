"""
Модуль для управления историей сообщений в чате.
Позволяет сохранять ID последнего отправленного сообщения бота для пользователя,
удалять предыдущее сообщение или редактировать его.
"""

import logging
from typing import Optional, List, Dict
from app.services import max_api
from app.services.user_service import get_dialog_state, set_dialog_state

logger = logging.getLogger(__name__)

LAST_MSG_KEY = "last_bot_message_id"

def save_last_message(user_id: int, message_id: str) -> None:
    """
    Сохраняет ID последнего отправленного сообщения бота для пользователя.
    Если состояния нет, создаёт новое с пустыми данными.
    """
    state_data = get_dialog_state(user_id)
    if state_data is None:
        # Создаём новое состояние без конкретного state, просто для хранения last_message
        state_data = {'state': None, 'data': {}}
    data = state_data.get('data') or {}
    data[LAST_MSG_KEY] = message_id
    set_dialog_state(user_id, state_data.get('state'), data)

def get_last_message(user_id: int) -> Optional[str]:
    """
    Возвращает ID последнего отправленного сообщения бота для пользователя.
    """
    state_data = get_dialog_state(user_id)
    if not state_data:
        return None
    data = state_data.get('data')
    if not data:
        return None
    return data.get(LAST_MSG_KEY)

def clear_last_message(user_id: int) -> None:
    """
    Удаляет информацию о последнем сообщении из состояния.
    """
    state_data = get_dialog_state(user_id)
    if not state_data:
        return
    data = state_data.get('data')
    if data and LAST_MSG_KEY in data:
        del data[LAST_MSG_KEY]
        set_dialog_state(user_id, state_data['state'], data)

def delete_previous_bot_message(chat_id: int, user_id: int) -> None:
    """
    Удаляет предыдущее сообщение бота для данного пользователя, если оно существует.
    """
    prev_msg_id = get_last_message(user_id)
    if prev_msg_id:
        logger.info(f"Удаление предыдущего сообщения {prev_msg_id} для пользователя {user_id}")
        max_api.delete_message(prev_msg_id)
        clear_last_message(user_id)

def edit_or_send_message(chat_id: int, user_id: int, text: str, keyboard=None, format=None) -> Optional[str]:
    """
    Пытается отредактировать последнее сообщение бота. Если это не удаётся (нет последнего сообщения
    или ошибка редактирования), отправляет новое сообщение.
    Возвращает ID нового сообщения (или ID отредактированного, если редактирование удалось).
    """
    last_msg_id = get_last_message(user_id)
    if last_msg_id:
        # Пытаемся отредактировать последнее сообщение
        result = max_api.edit_message(last_msg_id, text, keyboard, format)
        # Проверяем, что результат не None и что success = True (если есть поле success)
        if result is not None and (not isinstance(result, dict) or result.get('success', True)):
            logger.info(f"Сообщение {last_msg_id} отредактировано для пользователя {user_id}")
            return last_msg_id
        else:
            logger.warning(f"Не удалось отредактировать сообщение {last_msg_id}, отправляем новое")
            # Очищаем запись о последнем сообщении, чтобы не пытаться редактировать его снова
            clear_last_message(user_id)

    # Отправляем новое сообщение
    result = max_api.send_message(chat_id, text, keyboard, format)
    if result and 'message' in result and 'mid' in result['message']:
        new_msg_id = result['message']['mid']
        save_last_message(user_id, new_msg_id)
        return new_msg_id
    return None