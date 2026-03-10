"""
Обработчики для работы с расписанием.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.services import user_service, schedule_service
from app.handlers.common import send_or_edit, SEARCH_TYPES, get_plural_form, MAX_SEARCH_RESULTS, STATE_AWAITING_SELECTION

logger = logging.getLogger(__name__)

def handle_select_type(chat_id, user_id, callback_data):
    """Обрабатывает выбор типа расписания."""
    _, search_type = callback_data.split("|")
    if search_type in SEARCH_TYPES:
        user_service.set_dialog_state(user_id, 'AWAITING_SEARCH_QUERY', {"search_type": search_type})
        keyboard = [[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]]
        send_or_edit(chat_id, user_id, f"Введите название {SEARCH_TYPES[search_type]['name']} (можно часть названия):", keyboard=keyboard)
    else:
        send_or_edit(chat_id, user_id, "Неизвестный тип.")

def handle_search_query(chat_id, user_id, text, data):
    """Обрабатывает ввод поискового запроса."""
    search_type = data.get('search_type')
    if not search_type or search_type not in SEARCH_TYPES:
        logger.error(f"Неизвестный тип поиска: {search_type}")
        # Здесь нужно вызвать показ меню, но для краткости просто вернёмся в меню
        from app.handlers.message_handler import show_main_menu
        show_main_menu(chat_id, user_id)
        return

    search_text = text.strip()
    if not search_text:
        keyboard = [[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]]
        send_or_edit(chat_id, user_id, f"Введите часть названия {SEARCH_TYPES[search_type]['name']} (например, '101' или 'Иванов'):", keyboard=keyboard)
        return

    items = SEARCH_TYPES[search_type]['get_list']()
    import re
    pattern = re.compile(re.escape(search_text), re.IGNORECASE)
    matches = [item for item in items if pattern.search(item['name'])]

    if not matches:
        plural = get_plural_form(search_type, 0)
        send_or_edit(chat_id, user_id, f"{plural.capitalize()} с названием '{search_text}' не найдено. Попробуйте другой запрос.")
        return

    user_service.set_dialog_state(user_id, STATE_AWAITING_SELECTION, {
        "search_type": search_type,
        "matches": matches[:MAX_SEARCH_RESULTS],
        "all_matches": matches
    })

    keyboard = []
    for item in matches[:MAX_SEARCH_RESULTS]:
        display_text = item['name']
        if search_type == 'group' and 'course' in item:
            display_text += f" (курс {item['course']})"
        keyboard.append([{
            "type": "callback",
            "text": display_text,
            "intent": "default",
            "payload": f"select_item|{search_type}|{item['id']}"
        }])

    if len(matches) > MAX_SEARCH_RESULTS:
        keyboard.append([{
            "type": "callback",
            "text": "Показать ещё...",
            "intent": "default",
            "payload": "search_more"
        }])

    keyboard.append([{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}])

    plural = get_plural_form(search_type, len(matches))
    send_or_edit(
        chat_id,
        user_id,
        f"Найдено {plural}: {len(matches)}. Выберите нужный:",
        keyboard=keyboard
    )

def handle_select_item(chat_id, user_id, callback_data):
    """Обрабатывает выбор конкретного элемента из списка."""
    parts = callback_data.split("|")
    if len(parts) >= 3:
        search_type = parts[1]
        item_id = int(parts[2])
        success = user_service.set_user_setting(user_id, search_type, item_id)
        if success:
            user_service.clear_dialog_state(user_id)
            items = SEARCH_TYPES[search_type]['get_list']()
            selected_item = next((item for item in items if item['id'] == item_id), None)
            if selected_item:
                display_name = selected_item['name']
                if search_type == 'group' and 'course' in selected_item:
                    display_name += f" (курс {selected_item['course']})"
            else:
                display_name = str(item_id)

            gender_map = {'group': 'а', 'room': 'а', 'teacher': ''}
            gender = gender_map.get(search_type, 'о')
            confirm_text = f"✅ {SEARCH_TYPES[search_type]['name'].capitalize()} «{display_name}» успешно сохранен{gender}! Теперь вы можете запросить расписание командой «моё расписание»."

            user = user_service.get_user_by_max_id(user_id)
            moodle_user_id = user.get('moodle_user_id') if user else None
            user_service.log_user_action(user_id, 'select_item', moodle_user_id, {'type': search_type, 'id': item_id, 'name': display_name})
            send_or_edit(chat_id, user_id, confirm_text)
            from app.handlers.message_handler import show_main_menu
            show_main_menu(chat_id, user_id)
        else:
            send_or_edit(chat_id, user_id, "❌ Ошибка при сохранении. Попробуйте позже.")
    else:
        send_or_edit(chat_id, user_id, "Неверный формат выбора.")

def handle_week_navigation(chat_id, user_id, callback_data):
    """Обрабатывает навигацию по неделям."""
    parts = callback_data.split("|")
    if len(parts) == 3:
        offset = int(parts[1])
        entity_id = int(parts[2])
        settings = user_service.get_user_settings(user_id)
        if not settings:
            send_or_edit(chat_id, user_id, "Сначала выберите расписание.")
            return
        search_type = settings.get('selected_type')
        user = user_service.get_user_by_max_id(user_id)
        moodle_user_id = user.get('moodle_user_id') if user else None
        user_service.log_user_action(user_id, 'view_week', moodle_user_id, {'type': search_type, 'id': entity_id, 'offset': offset})
        show_schedule_for_week(chat_id, user_id, search_type, entity_id, week_offset=offset)

def handle_date_input(chat_id, user_id, text, data):
    """Обрабатывает ввод даты для поиска."""
    # Эта функция должна быть реализована аналогично старой логике
    # Для краткости я пропускаю, но нужно перенести из старого message_handler.py
    # Пока оставим заглушку
    send_or_edit(chat_id, user_id, "Функция поиска по дате временно недоступна.")

def show_schedule_for_week(chat_id: int, user_id: int, search_type: str, entity_id: int,
                           week_offset: int = 0, target_monday: Optional[datetime.date] = None):
    """Показывает расписание на неделю."""
    today = datetime.now().date()
    current_monday = today - timedelta(days=today.weekday())

    if target_monday is None:
        target_monday = current_monday + timedelta(weeks=week_offset)
        delta_weeks = week_offset
    else:
        delta_weeks = (target_monday - current_monday).days // 7

    target_sunday = target_monday + timedelta(days=6)

    start = datetime.combine(target_monday, datetime.min.time())
    end = datetime.combine(target_sunday, datetime.max.time())

    if search_type == 'group':
        schedule = schedule_service.get_schedule_for_group(entity_id, start, end)
    elif search_type == 'room':
        schedule = schedule_service.get_schedule_for_room(entity_id, start, end)
    elif search_type == 'teacher':
        schedule = schedule_service.get_schedule_for_teacher(entity_id, start, end)
    else:
        logger.error(f"Неизвестный тип расписания: {search_type}")
        send_or_edit(chat_id, user_id, "Ошибка: неизвестный тип расписания.")
        return

    if not schedule:
        text = f"На неделе с {target_monday.strftime('%d.%m')} по {target_sunday.strftime('%d.%m')} занятий нет."
    else:
        text = schedule_service.format_schedule(schedule, search_type)

    keyboard = [
        [
            {"type": "callback", "text": "⬅️ Пред.", "intent": "default", "payload": f"week|{delta_weeks-1}|{entity_id}"},
            {"type": "callback", "text": "📅 Тек. неделя", "intent": "default", "payload": f"week|0|{entity_id}"},
            {"type": "callback", "text": "➡️ След.", "intent": "default", "payload": f"week|{delta_weeks+1}|{entity_id}"}
        ],
        [
            {"type": "callback", "text": "📅 Поиск по дате", "intent": "default", "payload": "search_by_date"},
            {"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}
        ]
    ]

    send_or_edit(chat_id, user_id, text, keyboard=keyboard, format="html")