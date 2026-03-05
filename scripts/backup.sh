#!/bin/bash
set -e

PROJECT_DIR="/opt/max_bot"
BACKUP_DIR="$PROJECT_DIR/backups"
DB_NAME="max_bot_db"
DB_USER="max_bot_user"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/max_bot_backup_${TIMESTAMP}.tar.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Извлекаем пароль из .env
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "$(date): Файл .env не найден!" >> "$LOG_FILE"
    exit 1
fi

# Читаем LOCAL_DB_PASSWORD из .env
DB_PASS=$(grep -E '^LOCAL_DB_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\n' | tr -d '\r')
if [ -z "$DB_PASS" ]; then
    echo "$(date): Не удалось найти LOCAL_DB_PASSWORD в .env" >> "$LOG_FILE"
    exit 1
fi

export PGPASSWORD="$DB_PASS"

mkdir -p "$BACKUP_DIR"

echo "$(date): Начало бекапа" >> "$LOG_FILE"

# Дамп базы данных
echo "$(date): Дамп базы..." >> "$LOG_FILE"
pg_dump -U "$DB_USER" -h localhost "$DB_NAME" > "/tmp/max_bot_db_${TIMESTAMP}.sql" 2>> "$LOG_FILE"
if [ $? -ne 0 ]; then
    echo "$(date): ОШИБКА при дампе базы" >> "$LOG_FILE"
    exit 1
fi

# Копируем .env
cp "$ENV_FILE" "/tmp/.env_${TIMESTAMP}" 2>> "$LOG_FILE"

# Создаём архив
cd /tmp
tar -czf "$BACKUP_FILE" "max_bot_db_${TIMESTAMP}.sql" ".env_${TIMESTAMP}" 2>> "$LOG_FILE"
if [ $? -ne 0 ]; then
    echo "$(date): ОШИБКА при создании архива" >> "$LOG_FILE"
    exit 1
fi

# Удаляем временные файлы
rm -f "/tmp/max_bot_db_${TIMESTAMP}.sql" "/tmp/.env_${TIMESTAMP}"

# Удаляем старые бекапы (старше 7 дней)
find "$BACKUP_DIR" -name "max_bot_backup_*.tar.gz" -type f -mtime +7 -delete >> "$LOG_FILE" 2>&1

echo "$(date): Бекап успешно завершён: $BACKUP_FILE" >> "$LOG_FILE"
