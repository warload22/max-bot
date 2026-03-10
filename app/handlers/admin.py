"""
Обработчики для административной панели.
"""

import logging
from app.services import admin_service, user_service
from app.handlers.common import send_or_edit

logger = logging.getLogger(__name__)

def handle_admin_panel(chat_id, user_id, user, callback_data, message_id):
    """Показывает главное меню админ-панели."""
    user_service.log_user_action(user_id, 'admin_panel_open', user['moodle_user_id'])
    admin_text = (
        "🛠 <b>Панель администратора</b>\n\n"
        "Выберите раздел:"
    )
    admin_keyboard = [
        [{"type": "callback", "text": "📊 Статистика", "intent": "default", "payload": "admin_stats_menu"}],
        [{"type": "callback", "text": "📋 Логи сервера", "intent": "default", "payload": "admin_logs"}],
        [{"type": "callback", "text": "🖥 Статус сервера", "intent": "default", "payload": "admin_status"}],
        [{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]
    ]
    send_or_edit(chat_id, user_id, admin_text, keyboard=admin_keyboard, format="html")

def handle_admin_stats_menu(chat_id, user_id, callback_data, message_id):
    """Меню выбора периода статистики."""
    stats_menu_text = "📊 Выберите период статистики:"
    stats_menu_keyboard = [
        [{"type": "callback", "text": "📅 Сегодня", "intent": "default", "payload": "admin_stats_day"}],
        [{"type": "callback", "text": "📆 7 дней", "intent": "default", "payload": "admin_stats_week"}],
        [{"type": "callback", "text": "📆 30 дней", "intent": "default", "payload": "admin_stats_month"}],
        [{"type": "callback", "text": "🔙 Назад", "intent": "default", "payload": "admin_panel"}]
    ]
    send_or_edit(chat_id, user_id, stats_menu_text, keyboard=stats_menu_keyboard, format="html")

def handle_admin_stats(chat_id, user_id, moodle_user_id, period, callback_data, message_id):
    """
    Универсальный обработчик статистики за указанный период.
    period: 'day', 'week', 'month'
    """
    # Определяем тип действия для логирования
    action_map = {'day': 'admin_stats_day', 'week': 'admin_stats_week', 'month': 'admin_stats_month'}
    action_type = action_map.get(period, 'admin_stats_day')
    user_service.log_user_action(user_id, action_type, moodle_user_id)

    stats_text = admin_service.get_stats(period)
    keyboard = [[{"type": "callback", "text": "🔙 Назад", "intent": "default", "payload": "admin_stats_menu"}]]
    send_or_edit(chat_id, user_id, stats_text, keyboard=keyboard, format="html")

def handle_admin_logs(chat_id, user_id, moodle_user_id, callback_data, message_id):
    """Показывает последние строки лога."""
    user_service.log_user_action(user_id, 'admin_logs', moodle_user_id)
    logs_text = admin_service.get_logs(lines=50)
    keyboard = [[{"type": "callback", "text": "🔙 Назад", "intent": "default", "payload": "admin_panel"}]]
    send_or_edit(chat_id, user_id, logs_text, keyboard=keyboard, format="html")

def handle_admin_status(chat_id, user_id, moodle_user_id, callback_data, message_id):
    """Показывает статус сервера."""
    user_service.log_user_action(user_id, 'admin_status', moodle_user_id)
    status_text = admin_service.get_server_status()
    keyboard = [[{"type": "callback", "text": "🔙 Назад", "intent": "default", "payload": "admin_panel"}]]
    send_or_edit(chat_id, user_id, status_text, keyboard=keyboard, format="html")