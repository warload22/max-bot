"""
Модуль для сбора административной статистики: статистика пользователей,
логи сервера, статус сервера, информация о бекапах.
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Tuple, List
import psutil
from app.core.database import get_local_connection

logger = logging.getLogger(__name__)

# Пути
PROJECT_DIR = "/opt/max_bot"
LOG_FILE = os.path.join(PROJECT_DIR, "logs", "app.log")
BACKUP_DIR_BOT = os.path.join(PROJECT_DIR, "backups")

# Список возможных папок с бекапами Moodle
MOODLE_BACKUP_DIRS = [
    "/mnt/moodledata/backups/db/daily",
    "/mnt/moodledata/backups/db/weekly",
    "/mnt/moodledata/backups/db/monthly",
    "/mnt/moodledata/backups/code"
]

def get_stats(period: str = 'day') -> str:
    now = datetime.now()
    if period == 'day':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_name = "сегодня"
    elif period == 'week':
        start = now - timedelta(days=7)
        period_name = "за 7 дней"
    elif period == 'month':
        start = now - timedelta(days=30)
        period_name = "за 30 дней"
    else:
        return "❌ Неизвестный период"

    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            # Уникальные MAX (все)
            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_actions WHERE created_at >= %s", (start,))
            unique_max = cursor.fetchone()[0] or 0

            # Уникальные MAX авторизованные (те, у которых есть moodle_user_id)
            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_actions WHERE created_at >= %s AND moodle_user_id IS NOT NULL", (start,))
            unique_auth_max = cursor.fetchone()[0] or 0

            # Уникальные Moodle (учётные записи)
            cursor.execute("SELECT COUNT(DISTINCT moodle_user_id) FROM user_actions WHERE created_at >= %s AND moodle_user_id IS NOT NULL", (start,))
            unique_moodle = cursor.fetchone()[0] or 0

            # Запросы расписания
            cursor.execute("SELECT COUNT(*) FROM user_actions WHERE action_type = 'view_schedule' AND created_at >= %s", (start,))
            schedule_requests = cursor.fetchone()[0] or 0

            # Всего действий
            cursor.execute("SELECT COUNT(*) FROM user_actions WHERE created_at >= %s", (start,))
            total_actions = cursor.fetchone()[0] or 0

        conn.close()
        return (
            f"📊 <b>Статистика {period_name}:</b>\n\n"
            f"👥 MAX (все пользователи): {unique_max}\n"
            f"🔐 MAX авторизованные: {unique_auth_max}\n"
            f"🎓 Moodle (учётные записи): {unique_moodle}\n"
            f"📅 Запросов расписания: {schedule_requests}\n"
            f"🔄 Всего действий: {total_actions}"
        )
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        return "❌ Не удалось получить статистику."

def get_logs(lines: int = 50) -> str:
    """Последние N строк лога (читает файл напрямую, не требует tail)."""
    if not os.path.exists(LOG_FILE):
        return f"❌ Файл лога не найден: {LOG_FILE}"
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:]
            output = ''.join(last_lines).strip()
        if not output:
            return "📋 Лог пуст."
        if len(output) > 3500:
            output = output[:3500] + "\n... (обрезано)"
        return f"📋 <b>Последние {lines} строк лога:</b>\n<pre>{output}</pre>"
    except Exception as e:
        logger.error(f"Ошибка лога: {e}")
        return f"❌ Ошибка при чтении лога: {e}"

def get_folder_size(path: str) -> str:
    """Размер папки в человекочитаемом виде."""
    try:
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if total < 1024.0:
                return f"{total:.1f} {unit}"
            total /= 1024.0
        return f"{total:.1f} TB"
    except Exception:
        return "N/A"

def get_backup_info(dirs: List[str], days: int = 7) -> Tuple[int, str, int]:
    """
    Анализ директорий бекапов: (количество, размер, успешные).
    Сканирует все переданные папки, суммирует файлы с датой модификации не старше days дней.
    """
    total_count = 0
    total_size = 0
    cutoff = datetime.now() - timedelta(days=days)

    for directory in dirs:
        if not os.path.isdir(directory):
            continue
        try:
            for name in os.listdir(directory):
                path = os.path.join(directory, name)
                if os.path.isfile(path):
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    if mtime >= cutoff:
                        total_count += 1
                        total_size += os.path.getsize(path)
        except Exception as e:
            logger.warning(f"Ошибка чтения {directory}: {e}")

    # форматирование размера
    for unit in ['B', 'KB', 'MB', 'GB']:
        if total_size < 1024.0:
            size_str = f"{total_size:.1f} {unit}"
            break
        total_size /= 1024.0
    else:
        size_str = f"{total_size:.1f} TB"

    return total_count, size_str, total_count  # все файлы считаем успешными

def get_restarts_today() -> int:
    """Количество рестартов бота за сегодня."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM bot_restarts WHERE restart_time >= %s", (today_start,))
            count = cursor.fetchone()[0] or 0
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Ошибка при подсчёте рестартов: {e}")
        return 0

def log_restart() -> None:
    """Логирует перезапуск бота в таблицу bot_restarts."""
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO bot_restarts (restart_time) VALUES (DEFAULT)")
        conn.commit()
        conn.close()
        logger.info("Рестарт бота залогирован")
    except Exception as e:
        logger.error(f"Ошибка при логировании рестарта: {e}")

def get_server_status() -> str:
    """Полная информация о состоянии сервера."""
    try:
        load = psutil.getloadavg()
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        ram_used_gb = mem.used / (1024**3)
        ram_total_gb = mem.total / (1024**3)
        project_size = get_folder_size(PROJECT_DIR)
        restarts_today = get_restarts_today()

        # Информация о дисках
        disk_root = shutil.disk_usage('/')
        root_used_gb = disk_root.used / (1024**3)
        root_total_gb = disk_root.total / (1024**3)

        mnt_path = '/mnt'
        mnt_info = ""
        if os.path.exists(mnt_path):
            try:
                disk_mnt = shutil.disk_usage(mnt_path)
                mnt_used_gb = disk_mnt.used / (1024**3)
                mnt_total_gb = disk_mnt.total / (1024**3)
                mnt_info = f"/mnt: {mnt_used_gb:.1f} ГБ / {mnt_total_gb:.1f} ГБ ({disk_mnt.used/disk_mnt.total*100:.1f}%)"
            except:
                mnt_info = "/mnt: недоступно"

        # Бекапы бота
        bot_cnt, bot_size, bot_ok = get_backup_info([BACKUP_DIR_BOT])

        # Бекапы Moodle (по списку папок)
        mdl_cnt, mdl_size, mdl_ok = get_backup_info(MOODLE_BACKUP_DIRS)

        return f"""🖥 <b>Статус сервера</b>

<b>CPU:</b>
  Load average: {load[0]:.2f} (1мин), {load[1]:.2f} (5мин), {load[2]:.2f} (15мин)
  Использование: {cpu_percent}%

<b>RAM:</b>
  Использовано: {ram_used_gb:.1f} ГБ / {ram_total_gb:.1f} ГБ ({mem.percent:.1f}%)

<b>Диски:</b>
  Корень /: {root_used_gb:.1f} ГБ / {root_total_gb:.1f} ГБ ({disk_root.used/disk_root.total*100:.1f}%)
  {mnt_info}

<b>Рестарты за сегодня:</b> {restarts_today}

<b>Размер проекта {PROJECT_DIR}:</b> {project_size}

<b>Бекапы бота (7 дней):</b>
  Файлов: {bot_cnt}, размер: {bot_size}, успешных: {bot_ok}

<b>Бекапы Moodle (7 дней):</b>
  Файлов: {mdl_cnt}, размер: {mdl_size}, успешных: {mdl_ok}"""
    except Exception as e:
        logger.error(f"Ошибка статуса сервера: {e}")
        return "❌ Не удалось получить статус сервера."
