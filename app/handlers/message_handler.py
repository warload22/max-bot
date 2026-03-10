"""
Модуль-диспетчер для обработки входящих обновлений.
Вызывает соответствующие обработчики из подмодулей.
"""

import logging
from typing import Optional

from app.services import user_service, auth_service, cleanup
from app.handlers.common import (
    send_or_edit,
    SEARCH_TYPES,
    STATE_AWAITING_LOGIN,
    STATE_AWAITING_PASSWORD,
    STATE_AWAITING_SEARCH_TYPE,
    STATE_AWAITING_SEARCH_QUERY,
    STATE_AWAITING_SELECTION,
    STATE_AWAITING_DATE,
)
from app.handlers import auth as auth_handler
from app.handlers import schedule as schedule_handler
from app.handlers import admin as admin_handler

logger = logging.getLogger(__name__)

def handle_update(update: dict) -> None:
    """Основная точка входа для обработки обновления."""
    update_type = update.get('update_type')
    chat_id = update.get('chat_id')
    user_id = update.get('user_id')
    text = update.get('text')
    callback_data = update.get('callback_data')
    message_id = update.get('message_id')

    if not chat_id or not user_id:
        logger.warning("Нет chat_id или user_id в обновлении")
        return

    logger.info(f"handle_update: тип={update_type}, user_id={user_id}, text={text}, callback={callback_data}")

    if update_type == 'bot_started':
        handle_bot_started(chat_id, user_id, update.get('payload'))
    elif update_type == 'message_created' and text is not None:
        handle_text_message(chat_id, user_id, text, message_id)
    elif update_type == 'message_callback' and callback_data is not None:
        handle_callback(chat_id, user_id, callback_data, message_id)
    else:
        logger.info(f"Необрабатываемый тип обновления: {update_type}")

def handle_bot_started(chat_id: int, user_id: int, payload: str = None):
    """Обрабатывает событие bot_started (первый запуск или возврат)."""
    user = user_service.get_user_by_max_id(user_id)
    if user and user['is_authenticated']:
        show_main_menu(chat_id, user_id)
    else:
        welcome_text = (
            "👋 Добро пожаловать в бот расписания АГЗ МЧС России!\n\n"
            "🔐 <b>Ваша безопасность:</b>\n"
            "Мы не храним ваш пароль. При входе он сразу превращается в защищённый цифровой отпечаток и сравнивается с тем, который хранится на портале Moodle. "
            "Даже мы не сможем его восстановить — он остаётся только у вас.\n\n"
            "Для доступа к расписанию необходимо авторизоваться.\n"
            "Нажмите кнопку ниже, чтобы начать."
        )
        keyboard = [
            [{"type": "callback", "text": "🔐 Авторизация", "intent": "default", "payload": "start_auth"}],
            [{"type": "callback", "text": "ℹ️ О боте", "intent": "default", "payload": "info"}]
        ]
        send_or_edit(chat_id, user_id, welcome_text, keyboard=keyboard, format="html")

def handle_text_message(chat_id: int, user_id: int, text: str, message_id: Optional[str] = None):
    """Обрабатывает текстовое сообщение."""
    text_lower = text.lower().strip()

    if text_lower in ['/start', 'меню', 'menu']:
        show_main_menu(chat_id, user_id)
        return
    if text_lower in ['/schedule', 'моё расписание', 'расписание']:
        handle_my_schedule(chat_id, user_id)
        return
    if text_lower in ['/logout', 'выйти', 'выход', 'разлогиниться']:
        handle_logout(chat_id, user_id)
        return
    if text_lower in ['/date', 'поиск по дате', 'дата']:
        start_date_search(chat_id, user_id)
        return
    if text_lower in ['отмена', 'назад', 'cancel']:
        show_main_menu(chat_id, user_id)
        return

    state_data = user_service.get_dialog_state(user_id)
    if not state_data:
        show_main_menu(chat_id, user_id)
        return

    state = state_data['state']
    data = state_data['data'] or {}

    if state == STATE_AWAITING_LOGIN:
        auth_handler.handle_login_input(chat_id, user_id, text, message_id, data)
    elif state == STATE_AWAITING_PASSWORD:
        auth_handler.handle_password_input(chat_id, user_id, text, message_id, data)
    elif state == STATE_AWAITING_SEARCH_TYPE:
        send_or_edit(chat_id, user_id, "Пожалуйста, выберите тип расписания, нажав на кнопку.",
                     keyboard=[[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]])
    elif state == STATE_AWAITING_SEARCH_QUERY:
        schedule_handler.handle_search_query(chat_id, user_id, text, data)
    elif state == STATE_AWAITING_SELECTION:
        send_or_edit(chat_id, user_id, "Пожалуйста, выберите из списка, нажав на кнопку.",
                     keyboard=[[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]])
    elif state == STATE_AWAITING_DATE:
        schedule_handler.handle_date_input(chat_id, user_id, text, data)
    else:
        logger.warning(f"Неизвестное состояние {state}, сбрасываем")
        user_service.clear_dialog_state(user_id)
        show_main_menu(chat_id, user_id)

def handle_callback(chat_id: int, user_id: int, callback_data: str, message_id: str = None):
    """Обрабатывает нажатия на callback-кнопки."""
    logger.info(f"Callback: {callback_data}")

    # Обработка общих callback'ов
    if callback_data == "start_auth":
        auth_handler.handle_start_auth(chat_id, user_id, callback_data, message_id)
        return

    if callback_data == "info":
        info_text = (
            "🤖 Чат-бот «Расписание АГЗ МЧС России» разработан отделом (современных средств обучения) "
            "центра (учебно-методического) Академии гражданской защиты МЧС России.\n\n"
            "По всем вопросам и предложениям обращайтесь:\n"
            "📞 телефон: 8 (498) 699-04-05\n\n"
            "Мы всегда рады помочь!"
        )
        keyboard = [[{"type": "callback", "text": "🔙 Назад", "intent": "default", "payload": "back_to_start"}]]
        send_or_edit(chat_id, user_id, info_text, keyboard=keyboard, format="html")
        return

    if callback_data == "back_to_start":
        handle_bot_started(chat_id, user_id)
        return

    if callback_data == "menu":
        user_service.clear_dialog_state(user_id)
        show_main_menu(chat_id, user_id)
        return

    if callback_data == "cancel_input":
        state_data = user_service.get_dialog_state(user_id)
        if not state_data:
            show_main_menu(chat_id, user_id)
            return
        current_state = state_data.get('state')
        if current_state == STATE_AWAITING_PASSWORD:
            user_service.set_dialog_state(user_id, STATE_AWAITING_LOGIN)
            keyboard = [[{"type": "callback", "text": "❌ Отмена", "intent": "default", "payload": "cancel_input"}]]
            send_or_edit(chat_id, user_id, "Введите ваш логин от Moodle:", keyboard=keyboard)
        elif current_state == STATE_AWAITING_LOGIN:
            user_service.clear_dialog_state(user_id)
            handle_bot_started(chat_id, user_id)
        else:
            show_main_menu(chat_id, user_id)
        return

    if callback_data == "change_schedule_type":
        show_search_type_menu(chat_id, user_id)
        return

    if callback_data == "search_by_date":
        start_date_search(chat_id, user_id)
        return

    if callback_data.startswith("select_type|"):
        schedule_handler.handle_select_type(chat_id, user_id, callback_data)
        return

    if callback_data.startswith("select_item|"):
        schedule_handler.handle_select_item(chat_id, user_id, callback_data)
        return

    if callback_data.startswith("week|"):
        schedule_handler.handle_week_navigation(chat_id, user_id, callback_data)
        return

    if callback_data == "search_more" or callback_data == "group_more":
        send_or_edit(chat_id, user_id, "Функция 'показать ещё' пока не реализована.")
        return

    if callback_data == "my_schedule":
        handle_my_schedule(chat_id, user_id)
        return

    if callback_data == "logout":
        handle_logout(chat_id, user_id)
        return

    # Админ-панель
    if callback_data == "admin_panel":
        user = user_service.get_user_by_max_id(user_id)
        if not user or not user.get('moodle_user_id'):
            send_or_edit(chat_id, user_id, "Не удалось проверить права администратора.")
            return

        if not auth_service.is_user_admin(user['moodle_user_id']):
            user_service.log_user_action(user_id, 'admin_unauthorized_attempt', user['moodle_user_id'])
            send_or_edit(chat_id, user_id, "У вас нет прав доступа к панели администратора.")
            return

        admin_handler.handle_admin_panel(chat_id, user_id, user, callback_data, message_id)
        return

    if callback_data == "admin_stats_menu":
        admin_handler.handle_admin_stats_menu(chat_id, user_id, callback_data, message_id)
        return

    if callback_data in ('admin_stats_day', 'admin_stats_week', 'admin_stats_month'):
        user = user_service.get_user_by_max_id(user_id)
        moodle_user_id = user.get('moodle_user_id') if user else None
        period = {'admin_stats_day': 'day', 'admin_stats_week': 'week', 'admin_stats_month': 'month'}[callback_data]
        admin_handler.handle_admin_stats(chat_id, user_id, moodle_user_id, period, callback_data, message_id)
        return

    if callback_data == "admin_logs":
        user = user_service.get_user_by_max_id(user_id)
        moodle_user_id = user.get('moodle_user_id') if user else None
        admin_handler.handle_admin_logs(chat_id, user_id, moodle_user_id, callback_data, message_id)
        return

    if callback_data == "admin_status":
        user = user_service.get_user_by_max_id(user_id)
        moodle_user_id = user.get('moodle_user_id') if user else None
        admin_handler.handle_admin_status(chat_id, user_id, moodle_user_id, callback_data, message_id)
        return

    send_or_edit(chat_id, user_id, f"Неизвестная команда.")

def show_main_menu(chat_id: int, user_id: int):
    """Показывает главное меню."""
    user = user_service.get_user_by_max_id(user_id)
    if not user or not user['is_authenticated']:
        handle_bot_started(chat_id, user_id)
        return

    settings = user_service.get_user_settings(user_id)
    text, keyboard = get_main_menu_content(user, settings)
    send_or_edit(chat_id, user_id, text, keyboard=keyboard, format="html")

def get_main_menu_content(user: dict, settings: dict) -> tuple:
    """Возвращает текст и клавиатуру для главного меню."""
    if settings and settings.get('selected_type') and settings.get('selected_id'):
        search_type = settings['selected_type']
        entity_id = settings['selected_id']
        items = SEARCH_TYPES[search_type]['get_list']()
        selected_item = next((item for item in items if item['id'] == entity_id), None)
        if selected_item:
            display_name = selected_item['name']
            if search_type == 'group' and 'course' in selected_item:
                display_name += f" (курс {selected_item['course']})"
            entity_display = f"{SEARCH_TYPES[search_type]['name']} «{display_name}»"
        else:
            entity_display = f"{SEARCH_TYPES[search_type]['name']} (ID {entity_id})"

        text = f"Вы авторизованы как {user['moodle_username']}.\nВыбрано: {entity_display}.\nЧто хотите сделать?"

        buttons = [
            [{"type": "callback", "text": "📅 Моё расписание", "intent": "default", "payload": "my_schedule"}],
            [{"type": "callback", "text": "🔄 Сменить расписание", "intent": "default", "payload": "change_schedule_type"}],
            [{"type": "callback", "text": "🚪 Выйти", "intent": "default", "payload": "logout"}]
        ]

        if user.get('moodle_user_id') and auth_service.is_user_admin(user['moodle_user_id']):
            buttons.insert(0, [{"type": "callback", "text": "👨‍💼 Панель администратора", "intent": "default", "payload": "admin_panel"}])

        keyboard = buttons
    else:
        text = "Выберите, по какому критерию искать расписание:"
        keyboard = [
            [{"type": "callback", "text": "👥 По группе", "intent": "default", "payload": "select_type|group"}],
            [{"type": "callback", "text": "🏛 По аудитории", "intent": "default", "payload": "select_type|room"}],
            [{"type": "callback", "text": "👨‍🏫 По преподавателю", "intent": "default", "payload": "select_type|teacher"}],
            [{"type": "callback", "text": "🚪 Выйти", "intent": "default", "payload": "logout"}]
        ]

    return text, keyboard

def show_search_type_menu(chat_id: int, user_id: int):
    """Показывает меню выбора типа расписания."""
    keyboard = [
        [{"type": "callback", "text": "👥 По группе", "intent": "default", "payload": "select_type|group"}],
        [{"type": "callback", "text": "🏛 По аудитории", "intent": "default", "payload": "select_type|room"}],
        [{"type": "callback", "text": "👨‍🏫 По преподавателю", "intent": "default", "payload": "select_type|teacher"}],
        [{"type": "callback", "text": "🚪 Выйти", "intent": "default", "payload": "logout"}]
    ]
    send_or_edit(chat_id, user_id, "Выберите, по какому критерию искать расписание:", keyboard=keyboard)
    user_service.set_dialog_state(user_id, STATE_AWAITING_SEARCH_TYPE)

def start_date_search(chat_id: int, user_id: int):
    """Запускает режим поиска по дате."""
    user_service.set_dialog_state(user_id, STATE_AWAITING_DATE, {})
    keyboard = [[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]]
    send_or_edit(
        chat_id,
        user_id,
        "📅 Введите дату в формате ДД.ММ.ГГ или ДД.ММ.ГГГГ (например, 24.04.26 или 24.04.2026).\n"
        "Я покажу расписание на неделю, содержащую эту дату.",
        keyboard=keyboard
    )

def handle_logout(chat_id: int, user_id: int):
    """Обрабатывает выход из аккаунта."""
    user_service.logout_user(user_id)
    user_service.clear_dialog_state(user_id)
    cleanup.clear_last_message(user_id)
    handle_bot_started(chat_id, user_id)

def handle_my_schedule(chat_id: int, user_id: int):
    """Показывает расписание пользователя на текущую неделю."""
    user = user_service.get_user_by_max_id(user_id)
    if not user or not user['is_authenticated']:
        send_or_edit(chat_id, user_id, "Сначала авторизуйтесь. Введите логин:")
        user_service.set_dialog_state(user_id, STATE_AWAITING_LOGIN)
        return

    settings = user_service.get_user_settings(user_id)
    if not settings or not settings.get('selected_type') or not settings.get('selected_id'):
        send_or_edit(chat_id, user_id, "Сначала выберите расписание (группу, аудиторию или преподавателя).")
        show_search_type_menu(chat_id, user_id)
        return

    search_type = settings['selected_type']
    entity_id = settings['selected_id']
    moodle_user_id = user.get('moodle_user_id')
    user_service.log_user_action(user_id, 'view_schedule', moodle_user_id, {'type': search_type, 'id': entity_id})
    schedule_handler.show_schedule_for_week(chat_id, user_id, search_type, entity_id, week_offset=0)