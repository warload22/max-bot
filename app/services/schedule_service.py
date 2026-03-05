"""
Модуль для получения данных из базы расписания (MS SQL).
Предоставляет функции для получения списков групп, аудиторий, преподавателей
и расписания для них с фильтром по датам.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from app.core.database import get_schedule_connection

logger = logging.getLogger(__name__)

# ---------- Вспомогательные функции ----------
def get_current_academic_year() -> str:
    """
    Определяет текущий учебный год в зависимости от даты.
    Учебный год начинается 1 сентября.
    Например: если сейчас 25.02.2026, то год = "2025-2026".
    """
    today = datetime.now()
    year = today.year
    month = today.month
    if month >= 9:
        start_year = year
        end_year = year + 1
    else:
        start_year = year - 1
        end_year = year
    return f"{start_year}-{end_year}"

def clean_topic(topic_raw: Optional[str]) -> str:
    """
    Очищает строку темы: заменяет запятые на точки, удаляет всё, кроме цифр и точки.
    Возвращает очищенный номер темы или пустую строку, если после очистки ничего не осталось.
    """
    if not topic_raw:
        return ""
    cleaned = topic_raw.replace(',', '.')
    cleaned = re.sub(r'[^\d\.]', '', cleaned)
    return cleaned

def get_current_week_dates() -> Tuple[datetime, datetime]:
    """
    Возвращает даты понедельника и воскресенья текущей недели.
    """
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    start = datetime.combine(monday, datetime.min.time())
    end = datetime.combine(sunday, datetime.max.time())
    return start, end

# ---------- Списки сущностей ----------
def get_groups(academic_year: Optional[str] = None) -> List[Dict[str, any]]:
    """
    Возвращает список всех активных групп из таблицы Все_Группы за указанный учебный год.
    Если academic_year не передан, используется текущий учебный год.
    Каждая группа содержит поля: id (Код), name (Название), course (Курс).
    """
    if academic_year is None:
        academic_year = get_current_academic_year()
    
    conn = None
    try:
        conn = get_schedule_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    Код as id, 
                    Название as name, 
                    Курс as course
                FROM Все_Группы 
                WHERE (Удалена = 0 OR Удалена IS NULL)
                  AND УчебныйГод = %s
                ORDER BY Название
            """, (academic_year,))
            rows = cursor.fetchall()
            groups = [dict(row) for row in rows]
            logger.info(f"Получено групп за {academic_year}: {len(groups)}")
            return groups
    except Exception as e:
        logger.error(f"Ошибка при получении списка групп: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_rooms() -> List[Dict[str, any]]:
    """
    Возвращает список всех аудиторий из таблицы Аудитории.
    """
    conn = None
    try:
        conn = get_schedule_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    Код as id, 
                    Аудитория as name
                FROM Аудитории 
                ORDER BY name
            """)
            rows = cursor.fetchall()
            rooms = [dict(row) for row in rows]
            logger.info(f"Получено аудиторий: {len(rooms)}")
            return rooms
    except Exception as e:
        logger.error(f"Ошибка при получении списка аудиторий: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_teachers() -> List[Dict[str, any]]:
    """
    Возвращает список преподавателей из таблицы Преподаватели.
    Используем поля Код и ФИО.
    """
    conn = None
    try:
        conn = get_schedule_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    Код as id, 
                    ФИО as name
                FROM Преподаватели 
                WHERE isDelete IS NULL OR isDelete = 0
                ORDER BY ФИО
            """)
            rows = cursor.fetchall()
            teachers = [dict(row) for row in rows]
            logger.info(f"Получено преподавателей: {len(teachers)}")
            return teachers
    except Exception as e:
        logger.error(f"Ошибка при получении списка преподавателей: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ---------- Получение расписания ----------
def get_schedule_for_group(group_id: int, start_date: datetime, end_date: datetime) -> List[Dict[str, any]]:
    """
    Возвращает расписание для указанной группы за период [start_date, end_date].
    """
    conn = None
    try:
        conn = get_schedule_connection()
        with conn.cursor() as cursor:
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT 
                    r.Дата as date,
                    r.ВремяС as time_start,
                    r.ВремяПо as time_end,
                    r.Дисциплина as discipline,
                    r.Преподаватель as teacher,
                    r.Аудитория as room,
                    r.ВидЗанятия as lesson_type,
                    r.НомерЗанятия as lesson_number,
                    r.НомерПодгруппы as subgroup,
                    r.Тема as topic,
                    r.ДеньНедели as day_of_week,
                    g.Название as group_name
                FROM Расписание r
                LEFT JOIN Все_Группы g ON r.Код_Группы = g.Код
                WHERE r.Код_Группы = %s 
                    AND r.Дата >= %s 
                    AND r.Дата <= %s
                ORDER BY r.Дата, r.НомерЗанятия
            """, (group_id, start_str, end_str))
            rows = cursor.fetchall()
            schedule = [dict(row) for row in rows]
            logger.info(f"Для группы {group_id} получено записей: {len(schedule)}")
            return schedule
    except Exception as e:
        logger.error(f"Ошибка при получении расписания для группы {group_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_schedule_for_room(room_id: int, start_date: datetime, end_date: datetime) -> List[Dict[str, any]]:
    """
    Возвращает расписание для указанной аудитории за период [start_date, end_date].
    """
    conn = None
    try:
        conn = get_schedule_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT Аудитория FROM Аудитории WHERE Код = %s", (room_id,))
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Аудитория с ID {room_id} не найдена")
                return []
            room_name = row['Аудитория']

            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT 
                    r.Дата as date,
                    r.ВремяС as time_start,
                    r.ВремяПо as time_end,
                    r.Дисциплина as discipline,
                    r.Преподаватель as teacher,
                    r.Аудитория as room,
                    r.ВидЗанятия as lesson_type,
                    r.НомерЗанятия as lesson_number,
                    r.НомерПодгруппы as subgroup,
                    r.Тема as topic,
                    r.ДеньНедели as day_of_week,
                    g.Название as group_name
                FROM Расписание r
                LEFT JOIN Все_Группы g ON r.Код_Группы = g.Код
                WHERE r.Аудитория = %s 
                    AND r.Дата >= %s 
                    AND r.Дата <= %s
                ORDER BY r.Дата, r.НомерЗанятия
            """, (room_name, start_str, end_str))
            rows = cursor.fetchall()
            schedule = [dict(row) for row in rows]
            logger.info(f"Для аудитории {room_name} получено записей: {len(schedule)}")
            return schedule
    except Exception as e:
        logger.error(f"Ошибка при получении расписания для аудитории {room_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_schedule_for_teacher(teacher_id: int, start_date: datetime, end_date: datetime) -> List[Dict[str, any]]:
    """
    Возвращает расписание для указанного преподавателя за период [start_date, end_date].
    """
    conn = None
    try:
        conn = get_schedule_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT ФИО FROM Преподаватели WHERE Код = %s", (teacher_id,))
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Преподаватель с ID {teacher_id} не найден")
                return []
            teacher_name = row['ФИО']

            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT 
                    r.Дата as date,
                    r.ВремяС as time_start,
                    r.ВремяПо as time_end,
                    r.Дисциплина as discipline,
                    r.Преподаватель as teacher,
                    r.Аудитория as room,
                    r.ВидЗанятия as lesson_type,
                    r.НомерЗанятия as lesson_number,
                    r.НомерПодгруппы as subgroup,
                    r.Тема as topic,
                    r.ДеньНедели as day_of_week,
                    g.Название as group_name
                FROM Расписание r
                LEFT JOIN Все_Группы g ON r.Код_Группы = g.Код
                WHERE r.Преподаватель LIKE %s 
                    AND r.Дата >= %s 
                    AND r.Дата <= %s
                ORDER BY r.Дата, r.НомерЗанятия
            """, (f'%{teacher_name}%', start_str, end_str))
            rows = cursor.fetchall()
            schedule = [dict(row) for row in rows]
            logger.info(f"Для преподавателя {teacher_name} получено записей: {len(schedule)}")
            return schedule
    except Exception as e:
        logger.error(f"Ошибка при получении расписания для преподавателя {teacher_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ---------- Форматирование ----------
def format_schedule(schedule: List[Dict[str, any]], view_type: str) -> str:
    """
    Форматирует список занятий с эмодзи и многострочным выводом.
    Формат:
      {номер_пары} ⏰ {время}
      📚 {дисциплина}
      {эмодзи_типа} {тип_занятия} {тема}
      👤 {персона}
      🏫 {место}
    где персона и место зависят от view_type.
    """
    if not schedule:
        return "На текущую неделю расписания нет."

    type_emoji = {
        'лек': '📖', 'л': '📖',
        'пр': '📝', 'пз': '📝', 'сем': '📝', 'с': '📝',
        'лр': '🧪', 'лаб': '🧪',
        'экз': '✅', 'эк': '✅', 'зач': '✅', 'з': '✅',
        'конс': '💬',
        'кп': '🛠️',
        'кр': '✍️',
        'реф': '📄',
        'курс': '📋',
        'др': '📌'
    }

    days_map = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

    by_date = {}
    for item in schedule:
        date_obj = item['date']
        by_date.setdefault(date_obj, []).append(item)

    lines = ["📅 <b>Расписание на неделю:</b>"]
    
    for date_obj in sorted(by_date):
        day = days_map[date_obj.weekday()]
        date_str = date_obj.strftime('%d.%m')
        lines.append(f"\n<b>{day} {date_str}</b>")
        
        sorted_items = sorted(by_date[date_obj], key=lambda x: (x.get('time_start') or ''))
        for idx, item in enumerate(sorted_items, 1):
            lesson_type = (item.get('lesson_type') or '').strip()
            discipline_raw = (item.get('discipline') or '—').strip()
            
            if lesson_type and discipline_raw.startswith(lesson_type):
                discipline = discipline_raw[len(lesson_type):].lstrip()
                if discipline.startswith(lesson_type):
                    discipline = discipline[len(lesson_type):].lstrip()
            else:
                discipline = discipline_raw
            if not discipline:
                discipline = '—'

            teacher = item.get('teacher') or '—'
            room = item.get('room') or '—'
            group_name = item.get('group_name') or '—'
            time = f"{item.get('time_start')}-{item.get('time_end')}" if item.get('time_start') else 'время ?'
            topic_raw = item.get('topic')
            topic = clean_topic(topic_raw)

            emoji = type_emoji.get(lesson_type.lower(), '📌')

            lines.append(f"{idx} ⏰ {time}")
            lines.append(f"📚 {discipline}")
            if topic:
                lines.append(f"{emoji} {lesson_type} {topic}")
            else:
                lines.append(f"{emoji} {lesson_type}")

            # Две отдельные строки для персоны и места
            if view_type == 'group':
                lines.append(f"👤 {teacher}")
                lines.append(f"🏫 {room}")
            elif view_type == 'room':
                lines.append(f"👤 {group_name}")
                lines.append(f"🏫 {teacher}")
            elif view_type == 'teacher':
                lines.append(f"👤 {group_name}")
                lines.append(f"🏫 {room}")
            else:
                lines.append(f"👤 {teacher}")
                lines.append(f"🏫 {room}")
    
    return "\n".join(lines)