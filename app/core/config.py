import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env файла (находится в корне проекта)
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

class Config:
    """Конфигурация приложения. Все секреты берутся из переменных окружения."""

    # ------------------ База Moodle (MariaDB) - только чтение ------------------
    MOODLE_DB_HOST = os.getenv('MOODLE_DB_HOST', 'localhost')
    MOODLE_DB_PORT = int(os.getenv('MOODLE_DB_PORT', '3306'))
    MOODLE_DB_NAME = os.getenv('MOODLE_DB_NAME', 'moodle')
    MOODLE_DB_USER = os.getenv('MOODLE_DB_USER', 'moodle_user')
    MOODLE_DB_PASSWORD = os.getenv('MOODLE_DB_PASSWORD')  # обязательная, без дефолта

    # ------------------ База расписания (MS SQL) - только чтение ------------------
    SCHEDULE_DB_SERVER = os.getenv('SCHEDULE_DB_SERVER')  # обязательная, без дефолта (IP или домен)
    SCHEDULE_DB_PORT = int(os.getenv('SCHEDULE_DB_PORT', '1433'))
    SCHEDULE_DB_NAME = os.getenv('SCHEDULE_DB_NAME', 'DeKanat')  # или другое имя
    SCHEDULE_DB_USER = os.getenv('SCHEDULE_DB_USER', 'schedule_user')
    SCHEDULE_DB_PASSWORD = os.getenv('SCHEDULE_DB_PASSWORD')  # обязательная

    # ------------------ Локальная база бота (PostgreSQL) ------------------
    LOCAL_DB_HOST = os.getenv('LOCAL_DB_HOST', 'localhost')
    LOCAL_DB_PORT = int(os.getenv('LOCAL_DB_PORT', '5432'))
    LOCAL_DB_NAME = os.getenv('LOCAL_DB_NAME', 'max_bot_db')
    LOCAL_DB_USER = os.getenv('LOCAL_DB_USER', 'max_bot_user')
    LOCAL_DB_PASSWORD = os.getenv('LOCAL_DB_PASSWORD')  # обязательная

    # ------------------ Мессенджер MAX ------------------
    MAX_BOT_TOKEN = os.getenv('MAX_BOT_TOKEN')  # обязательная

    # ------------------ Настройки приложения ------------------
    APP_SECRET = os.getenv('APP_SECRET', 'dev-secret-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    # ------------------ Пути (можно вынести, но пока оставим) ------------------
    PROJECT_DIR = os.getenv('PROJECT_DIR', '/opt/max_bot')
    LOG_FILE = os.getenv('LOG_FILE', '/opt/max_bot/logs/app.log')
    BACKUP_DIR_BOT = os.getenv('BACKUP_DIR_BOT', '/opt/max_bot/backups')

    # ------------------ Проверка конфигурации ------------------
    @classmethod
    def validate(cls):
        """Проверяет, что все обязательные переменные заданы."""
        required_vars = [
            'MOODLE_DB_PASSWORD',
            'SCHEDULE_DB_SERVER',
            'SCHEDULE_DB_PASSWORD',
            'LOCAL_DB_PASSWORD',
            'MAX_BOT_TOKEN'
        ]
        missing = [var for var in required_vars if getattr(cls, var) is None]
        if missing:
            raise ValueError(f"❌ Отсутствуют обязательные переменные в .env: {', '.join(missing)}")
        print("✅ Конфигурация загружена и проверена")
        return True

# Создаём экземпляр конфигурации
config = Config()

# При импорте сразу проверяем (опционально, можно раскомментировать)
# config.validate()