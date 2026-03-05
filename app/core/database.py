"""
Модуль для работы с подключениями к базам данных.
Содержит функции для получения соединений с тремя БД:
- Moodle (MariaDB, только чтение)
- Расписание (MS SQL, только чтение)
- Локальная (PostgreSQL, чтение/запись)
А также инициализацию локальной БД (создание таблиц).
"""

import logging
import pymysql
import pymssql
import psycopg2
import psycopg2.extras
from app.core.config import config

# Настройка логирования (пока простой вывод в консоль)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_moodle_connection():
    """
    Возвращает соединение с базой данных Moodle (MariaDB).
    Использует параметры из config.MOODLE_*.
    Только для чтения (можно установить READ ONLY сессию, если поддерживается).
    """
    try:
        conn = pymysql.connect(
            host=config.MOODLE_DB_HOST,
            port=config.MOODLE_DB_PORT,
            user=config.MOODLE_DB_USER,
            password=config.MOODLE_DB_PASSWORD,
            database=config.MOODLE_DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        # Устанавливаем режим только для чтения (для MariaDB/MySQL)
        with conn.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY;")
        logger.info("Подключение к Moodle (MariaDB) установлено")
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к Moodle: {e}")
        raise

def get_schedule_connection():
    """
    Возвращает соединение с базой данных расписания (MS SQL).
    Использует pymssql (FreeTDS). Параметры из config.SCHEDULE_*.
    Только для чтения.
    """
    try:
        # Формируем строку сервера: хост:порт
        server = f"{config.SCHEDULE_DB_SERVER}:{config.SCHEDULE_DB_PORT}"
        conn = pymssql.connect(
            server=server,
            user=config.SCHEDULE_DB_USER,
            password=config.SCHEDULE_DB_PASSWORD,
            database=config.SCHEDULE_DB_NAME,
            as_dict=True
        )
        # Устанавливаем режим только для чтения (для MS SQL)
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
        logger.info("Подключение к MS SQL (расписание) установлено")
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к MS SQL: {e}")
        raise

def get_local_connection():
    """
    Возвращает соединение с локальной базой данных PostgreSQL.
    Параметры из config.LOCAL_*.
    """
    try:
        conn = psycopg2.connect(
            host=config.LOCAL_DB_HOST,
            port=config.LOCAL_DB_PORT,
            dbname=config.LOCAL_DB_NAME,
            user=config.LOCAL_DB_USER,
            password=config.LOCAL_DB_PASSWORD
        )
        # Включаем возможность работы с DictCursor (по желанию)
        conn.cursor_factory = psycopg2.extras.DictCursor
        logger.info("Подключение к локальной PostgreSQL установлено")
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к локальной PostgreSQL: {e}")
        raise

def init_local_db():
    """
    Создаёт необходимые таблицы в локальной PostgreSQL, если они ещё не существуют.
    Таблицы:
    - users: связь max_user_id с moodle_username, статус аутентификации
    - dialog_states: состояние диалога для каждого пользователя
    - user_settings: выбранные пользователем группа/преподаватель/аудитория
    """
    create_tables_sql = """
    -- Таблица пользователей
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        max_user_id VARCHAR(255) UNIQUE NOT NULL,
        moodle_username VARCHAR(255),
        is_authenticated BOOLEAN DEFAULT FALSE,
        authenticated_at TIMESTAMP,
        last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Таблица состояний диалога (конечный автомат)
    CREATE TABLE IF NOT EXISTS dialog_states (
        id SERIAL PRIMARY KEY,
        max_user_id VARCHAR(255) UNIQUE NOT NULL,
        state VARCHAR(50) NOT NULL,
        data JSONB,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Таблица настроек пользователя (выбранные группа/преподаватель/аудитория)
    CREATE TABLE IF NOT EXISTS user_settings (
        id SERIAL PRIMARY KEY,
        max_user_id VARCHAR(255) UNIQUE NOT NULL,
        selected_type VARCHAR(20) CHECK (selected_type IN ('group', 'teacher', 'room')),
        selected_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    conn = None
    try:
        conn = get_local_connection()
        with conn.cursor() as cursor:
            cursor.execute(create_tables_sql)
        conn.commit()
        logger.info("Локальные таблицы успешно созданы или уже существуют")
    except Exception as e:
        logger.error(f"Ошибка при инициализации локальной БД: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
