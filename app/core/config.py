import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env файла
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

class Config:
    """Конфигурация приложения. Все секреты берутся из переменных окружения."""
    
    # 1. БАЗА MOODLE (MariaDB) - ТОЛЬКО ДЛЯ ЧТЕНИЯ
    MOODLE_DB_HOST = os.getenv('MOODLE_DB_HOST', '')
    MOODLE_DB_PORT = int(os.getenv('MOODLE_DB_PORT', '3306'))
    MOODLE_DB_NAME = os.getenv('MOODLE_DB_NAME', '')
    MOODLE_DB_USER = os.getenv('MOODLE_DB_USER', '')
    MOODLE_DB_PASSWORD = os.getenv('MOODLE_DB_PASSWORD')  # БЕЗ ДЕФОЛТНОГО ЗНАЧЕНИЯ!
    
    # 2. БАЗА РАСПИСАНИЯ (MS SQL) - ТОЛЬКО ДЛЯ ЧТЕНИЯ
    SCHEDULE_DB_SERVER = os.getenv('SCHEDULE_DB_SERVER', '')
    SCHEDULE_DB_PORT = int(os.getenv('SCHEDULE_DB_PORT', '1433'))
    SCHEDULE_DB_NAME = os.getenv('SCHEDULE_DB_NAME', '')
    SCHEDULE_DB_USER = os.getenv('SCHEDULE_DB_USER', '')
    SCHEDULE_DB_PASSWORD = os.getenv('SCHEDULE_DB_PASSWORD')  # БЕЗ ДЕФОЛТНОГО ЗНАЧЕНИЯ!
    
    # 3. ЛОКАЛЬНАЯ БАЗА БОТА (PostgreSQL)
    LOCAL_DB_HOST = os.getenv('LOCAL_DB_HOST', '')
    LOCAL_DB_PORT = int(os.getenv('LOCAL_DB_PORT', '5432'))
    LOCAL_DB_NAME = os.getenv('LOCAL_DB_NAME', '')
    LOCAL_DB_USER = os.getenv('LOCAL_DB_USER', '')
    LOCAL_DB_PASSWORD = os.getenv('LOCAL_DB_PASSWORD')  # БЕЗ ДЕФОЛТНОГО ЗНАЧЕНИЯ!
    
    # 4. МЕССЕНДЖЕР MAX
    MAX_BOT_TOKEN = os.getenv('MAX_BOT_TOKEN')  # БЕЗ ДЕФОЛТНОГО ЗНАЧЕНИЯ!
    MAX_API_URL = os.getenv('MAX_API_URL', 'https://api.max.messenger')
    
    # 5. НАСТРОЙКИ ПРИЛОЖЕНИЯ
    APP_SECRET = os.getenv('APP_SECRET', 'dev-secret-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # 6. ПРОВЕРКА КОНФИГУРАЦИИ
    @classmethod
    def validate(cls):
        """Проверяет, что все обязательные переменные заданы."""
        required_vars = [
            'MOODLE_DB_PASSWORD',
            'SCHEDULE_DB_PASSWORD', 
            'LOCAL_DB_PASSWORD',
            'MAX_BOT_TOKEN'
        ]
        
        missing = []
        for var in required_vars:
            if getattr(cls, var) is None:
                missing.append(var)
        
        if missing:
            raise ValueError(f"Отсутствуют обязательные переменные в .env: {', '.join(missing)}")
        
        print("✅ Конфигурация загружена и проверена")
        return True

# Создаем экземпляр конфигурации
config = Config()
