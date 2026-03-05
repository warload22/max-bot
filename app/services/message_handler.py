"""
Модуль для обработки входящих сообщений и управления диалогом.
Реализует авторизацию, выбор типа расписания, поиск по дате,
показ расписания и навигацию с редактированием сообщений.
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from app.services import max_api
from app.services import auth_service
from app.services import user_service
from app.services import schedule_service
from app.services import cleanup

logger = logging.getLogger(__name__)

STATE_AWAITING_LOGIN = "AWAITING_LOGIN"
STATE_AWAITING_PASSWORD = "AWAITING_PASSWORD"
STATE_AWAITING_SEARCH_TYPE = "AWAITING_SEARCH_TYPE"
STATE_AWAITING_SEARCH_QUERY = "AWAITING_SEARCH_QUERY"
STATE_AWAITING_SELECTION = "AWAITING_SELECTION"
STATE_AWAITING_DATE = "AWAITING_DATE"

MAX_SEARCH_RESULTS = 10

SEARCH_TYPES = {
    'group': {'name': 'группа', 'get_list': schedule_service.get_groups},
    'room': {'name': 'аудитория', 'get_list': schedule_service.get_rooms},
    'teacher': {'name': 'преподаватель', 'get_list': schedule_service.get_teachers}
}

PLURAL_FORMS = {
    'group': {'one': 'группа', 'few': 'группы', 'many': 'групп'},
    'room': {'one': 'аудитория', 'few': 'аудитории', 'many': 'аудиторий'},
    'teacher': {'one': 'преподаватель', 'few': 'преподавателя', 'many': 'преподавателей'}
}

def get_plural_form(search_type: str, count: int) -> str:
    forms = PLURAL_FORMS[search_type]
    if count % 10 == 1 and count % 100 != 11:
        return forms['one']
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return forms['few']
    else:
        return forms['many']

def send_or_edit(chat_id: int, user_id: int, text: str, keyboard=None, format=None) -> Optional[str]:
    return cleanup.edit_or_send_message(chat_id, user_id, text, keyboard, format)

def handle_update(update: dict) -> None:
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

    elif state == STATE_AWAITING_PASSWORD:
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
            user_service.set_user_authenticated(user_id, login)
            user_service.clear_dialog_state(user_id)

            # Отправляем приветствие
            welcome = f"✅ Авторизация успешна! Добро пожаловать, {moodle_user['firstname']} {moodle_user['lastname']}."
            send_or_edit(chat_id, user_id, welcome, format="html")

            # Небольшая задержка, чтобы сообщение точно дошло
            time.sleep(0.5)

            # Удаляем сообщение с логином (с повторными попытками)
            if login_msg_id:
                max_api.delete_message_with_retry(login_msg_id, retries=3, delay=0.5)

            # Удаляем сообщение с паролем (с повторными попытками)
            if message_id:
                max_api.delete_message_with_retry(message_id, retries=3, delay=0.5)

            # Показываем главное меню
            show_main_menu(chat_id, user_id)
        else:
            # Неудача – удаляем только сообщение с паролем
            if message_id:
                time.sleep(0.5)
                max_api.delete_message_with_retry(message_id, retries=3, delay=0.5)
            send_or_edit(chat_id, user_id, "❌ Неверный логин или пароль. Попробуйте ещё раз.\nВведите логин:")
            user_service.set_dialog_state(user_id, STATE_AWAITING_LOGIN)

    elif state == STATE_AWAITING_SEARCH_TYPE:
        keyboard = [[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]]
        send_or_edit(chat_id, user_id, "Пожалуйста, выберите тип расписания, нажав на кнопку.", keyboard=keyboard)

    elif state == STATE_AWAITING_SEARCH_QUERY:
        search_type = data.get('search_type')
        if not search_type or search_type not in SEARCH_TYPES:
            logger.error(f"Неизвестный тип поиска: {search_type}")
            show_search_type_menu(chat_id, user_id)
            return

        search_text = text.strip()
        if not search_text:
            keyboard = [[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]]
            send_or_edit(chat_id, user_id, f"Введите часть названия {SEARCH_TYPES[search_type]['name']} (например, '101' или 'Иванов'):", keyboard=keyboard)
            return

        items = SEARCH_TYPES[search_type]['get_list']()
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

    elif state == STATE_AWAITING_SELECTION:
        keyboard = [[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]]
        send_or_edit(chat_id, user_id, "Пожалуйста, выберите из списка, нажав на кнопку.", keyboard=keyboard)

    elif state == STATE_AWAITING_DATE:
        date_str = text.strip()
        keyboard = [[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]]
        try:
            parts = date_str.split('.')
            if len(parts) == 3:
                day = int(parts[0])
                month = int(parts[1])
                year_part = parts[2]
                if len(year_part) == 2:
                    year = 2000 + int(year_part) if int(year_part) < 50 else 1900 + int(year_part)
                else:
                    year = int(year_part)
                input_date = datetime(year, month, day).date()
            else:
                raise ValueError("Неверный формат")

            monday = input_date - timedelta(days=input_date.weekday())

            settings = user_service.get_user_settings(user_id)
            if not settings or not settings.get('selected_type') or not settings.get('selected_id'):
                send_or_edit(chat_id, user_id, "Сначала выберите расписание (группу, аудиторию или преподавателя).")
                show_search_type_menu(chat_id, user_id)
                user_service.clear_dialog_state(user_id)
                return

            search_type = settings['selected_type']
            entity_id = settings['selected_id']
            user_service.clear_dialog_state(user_id)
            show_schedule_for_week(chat_id, user_id, search_type, entity_id, target_monday=monday)

        except Exception as e:
            logger.warning(f"Ошибка парсинга даты: {e}")
            send_or_edit(chat_id, user_id, "❌ Не удалось распознать дату. Пожалуйста, введите в формате ДД.ММ.ГГ или ДД.ММ.ГГГГ.", keyboard=keyboard)
            return

    else:
        logger.warning(f"Неизвестное состояние {state}, сбрасываем")
        user_service.clear_dialog_state(user_id)
        show_main_menu(chat_id, user_id)

def handle_callback(chat_id: int, user_id: int, callback_data: str, message_id: str = None):
    logger.info(f"Callback: {callback_data}")

    if callback_data == "start_auth":
        user_service.set_dialog_state(user_id, STATE_AWAITING_LOGIN)
        keyboard = [[{"type": "callback", "text": "❌ Отмена", "intent": "default", "payload": "cancel_input"}]]
        send_or_edit(chat_id, user_id, "Введите ваш логин от Moodle:", keyboard=keyboard)
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
        _, search_type = callback_data.split("|")
        if search_type in SEARCH_TYPES:
            user_service.set_dialog_state(user_id, STATE_AWAITING_SEARCH_QUERY, {"search_type": search_type})
            keyboard = [[{"type": "callback", "text": "📋 Меню", "intent": "default", "payload": "menu"}]]
            send_or_edit(chat_id, user_id, f"Введите название {SEARCH_TYPES[search_type]['name']} (можно часть названия):", keyboard=keyboard)
        else:
            send_or_edit(chat_id, user_id, "Неизвестный тип.")
        return

    if callback_data.startswith("select_item|"):
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

                send_or_edit(chat_id, user_id, confirm_text)
                show_main_menu(chat_id, user_id)
            else:
                send_or_edit(chat_id, user_id, "❌ Ошибка при сохранении. Попробуйте позже.")
        else:
            send_or_edit(chat_id, user_id, "Неверный формат выбора.")
        return

    if callback_data.startswith("week|"):
        parts = callback_data.split("|")
        if len(parts) == 3:
            offset = int(parts[1])
            entity_id = int(parts[2])
            settings = user_service.get_user_settings(user_id)
            if not settings:
                send_or_edit(chat_id, user_id, "Сначала выберите расписание.")
                return
            search_type = settings.get('selected_type')
            show_schedule_for_week(chat_id, user_id, search_type, entity_id, week_offset=offset)
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

    send_or_edit(chat_id, user_id, f"Неизвестная команда.")

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
        keyboard = [
            [{"type": "callback", "text": "📅 Моё расписание", "intent": "default", "payload": "my_schedule"}],
            [{"type": "callback", "text": "🔄 Сменить расписание", "intent": "default", "payload": "change_schedule_type"}],
            [{"type": "callback", "text": "🚪 Выйти", "intent": "default", "payload": "logout"}]
        ]
    else:
        # Если расписание не выбрано, показываем меню выбора типа
        text = "Выберите, по какому критерию искать расписание:"
        keyboard = [
            [{"type": "callback", "text": "👥 По группе", "intent": "default", "payload": "select_type|group"}],
            [{"type": "callback", "text": "🏛 По аудитории", "intent": "default", "payload": "select_type|room"}],
            [{"type": "callback", "text": "👨‍🏫 По преподавателю", "intent": "default", "payload": "select_type|teacher"}],
            [{"type": "callback", "text": "🚪 Выйти", "intent": "default", "payload": "logout"}]
        ]
    return text, keyboard

def show_search_type_menu(chat_id: int, user_id: int):
    keyboard = [
        [{"type": "callback", "text": "👥 По группе", "intent": "default", "payload": "select_type|group"}],
        [{"type": "callback", "text": "🏛 По аудитории", "intent": "default", "payload": "select_type|room"}],
        [{"type": "callback", "text": "👨‍🏫 По преподавателю", "intent": "default", "payload": "select_type|teacher"}],
        [{"type": "callback", "text": "🚪 Выйти", "intent": "default", "payload": "logout"}]
    ]
    send_or_edit(chat_id, user_id, "Выберите, по какому критерию искать расписание:", keyboard=keyboard)
    user_service.set_dialog_state(user_id, STATE_AWAITING_SEARCH_TYPE)

def start_group_selection(chat_id: int, user_id: int):
    show_search_type_menu(chat_id, user_id)

def start_date_search(chat_id: int, user_id: int):
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
    user_service.logout_user(user_id)
    user_service.clear_dialog_state(user_id)
    cleanup.clear_last_message(user_id)
    handle_bot_started(chat_id, user_id)

def show_main_menu(chat_id: int, user_id: int):
    user = user_service.get_user_by_max_id(user_id)
    if not user or not user['is_authenticated']:
        handle_bot_started(chat_id, user_id)
        return

    settings = user_service.get_user_settings(user_id)
    text, keyboard = get_main_menu_content(user, settings)
    send_or_edit(chat_id, user_id, text, keyboard=keyboard, format="html")

def handle_my_schedule(chat_id: int, user_id: int):
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
    show_schedule_for_week(chat_id, user_id, search_type, entity_id, week_offset=0)

def show_schedule_for_week(chat_id: int, user_id: int, search_type: str, entity_id: int, week_offset: int = 0, target_monday: Optional[datetime.date] = None):
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