"""
Общие константы и функции для обработчиков.
"""

from typing import Optional
from app.services import schedule_service

# Состояния диалога
STATE_AWAITING_LOGIN = "AWAITING_LOGIN"
STATE_AWAITING_PASSWORD = "AWAITING_PASSWORD"
STATE_AWAITING_SEARCH_TYPE = "AWAITING_SEARCH_TYPE"
STATE_AWAITING_SEARCH_QUERY = "AWAITING_SEARCH_QUERY"
STATE_AWAITING_SELECTION = "AWAITING_SELECTION"
STATE_AWAITING_DATE = "AWAITING_DATE"

MAX_SEARCH_RESULTS = 10

# Типы поиска и функции получения списков
SEARCH_TYPES = {
    'group': {'name': 'группа', 'get_list': schedule_service.get_groups},
    'room': {'name': 'аудитория', 'get_list': schedule_service.get_rooms},
    'teacher': {'name': 'преподаватель', 'get_list': schedule_service.get_teachers}
}

# Формы множественного числа
PLURAL_FORMS = {
    'group': {'one': 'группа', 'few': 'группы', 'many': 'групп'},
    'room': {'one': 'аудитория', 'few': 'аудитории', 'many': 'аудиторий'},
    'teacher': {'one': 'преподаватель', 'few': 'преподавателя', 'many': 'преподавателей'}
}

def get_plural_form(search_type: str, count: int) -> str:
    """Возвращает правильную форму существительного в зависимости от числа."""
    forms = PLURAL_FORMS[search_type]
    if count % 10 == 1 and count % 100 != 11:
        return forms['one']
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return forms['few']
    else:
        return forms['many']

def send_or_edit(chat_id: int, user_id: int, text: str, keyboard=None, format=None) -> Optional[str]:
    """Обёртка для редактирования или отправки нового сообщения."""
    from app.services import cleanup
    return cleanup.edit_or_send_message(chat_id, user_id, text, keyboard, format)