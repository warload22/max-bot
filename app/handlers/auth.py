"""
Модуль для обработки авторизации пользователей.
"""

import logging
import time
from typing import Optional

from app.services import max_api, auth_service, user_service
from app.handlers.common import (
    STATE_AWAITING_LOGIN, STATE_AWAITING_PASSWORD,
    send_or_edit
)

logger = logging.getLogger(__name__)

def handle_start_auth(chat_id: int, user_id: int) -> None:
    """Начинает процесс авторизации: запрашивает логин."""
    user_service.set_dialog_state(user_id, STATE_AWAITING_LOGIN)
    keyboard = [[{"type": "callback", "text": "❌ Отмена", "intent": "default", "payload": "cancel_input"}]]
    send_or_edit(chat_id, user_id, "Введите ваш логин от Moodle:", keyboard=keyboard)
    user_service.log_user_action(user_id, 'start_auth', None)

def handle_login_input(chat_id: int, user_id: int, text: str, message_id: Optional[str] = None) -> None:
    """Обрабатывает ввод логина."""
    login = text.strip()
    if not login:
        send_or_edit(chat_id, user_id, "Логин не может быть пустым. Введите логин:")
        return
    user_service.set_dialog_state(user_id, STATE_AWAITING_PASSWORD, {
        "login": login,
        "login_msg_id": message_id
    })
    keyboard = [[{"type": "callback", "text": "❌ Отмена", "intent": "default", "payload": "cancel_input"}]]
    send_or_edit(chat_id, user_id, "Теперь введите пароль:", keyboard=keyboard)

def handle_password_input(chat_id: int, user_id: int, text: str, message_id: Optional[str] = None) -> None:
    """Обрабатывает ввод пароля, проверяет авторизацию."""
    state_data = user_service.get_dialog_state(user_id)
    if not state_data:
        # Странно, но сбросим в главное меню
        from app.handlers.message_handler import show_main_menu
        show_main_menu(chat_id, user_id)
        return
    data = state_data.get('data') or {}
    login = data.get('login')
    login_msg_id = data.get('login_msg_id')

    if not login:
        user_service.set_dialog_state(user_id, STATE_AWAITING_LOGIN)
        send_or_edit(chat_id, user_id, "Ошибка. Введите логин заново:")
        return

    password = text
    moodle_user = auth_service.authenticate_user(login, password)

    if moodle_user:
        # Успешная авторизация
        user_service.set_user_authenticated(user_id, login, moodle_user['id'])
        user_service.log_user_action(user_id, 'auth_success', moodle_user['id'], {'username': login})
        user_service.clear_dialog_state(user_id)

        welcome = f"✅ Авторизация успешна! Добро пожаловать, {moodle_user['firstname']} {moodle_user['lastname']}."
        send_or_edit(chat_id, user_id, welcome, format="html")

        time.sleep(0.5)
        if login_msg_id:
            max_api.delete_message_with_retry(login_msg_id, retries=3, delay=0.5)
        if message_id:
            max_api.delete_message_with_retry(message_id, retries=3, delay=0.5)

        from app.handlers.message_handler import show_main_menu
        show_main_menu(chat_id, user_id)
    else:
        # Неверный пароль
        if message_id:
            time.sleep(0.5)
            max_api.delete_message_with_retry(message_id, retries=3, delay=0.5)
        send_or_edit(chat_id, user_id, "❌ Неверный логин или пароль. Попробуйте ещё раз.\nВведите логин:")
        user_service.set_dialog_state(user_id, STATE_AWAITING_LOGIN)