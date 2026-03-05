#!/usr/bin/env python3
"""
Основной файл Flask-приложения для MAX-бота.
Содержит:
- Настройку логирования с ротацией
- Эндпоинт /health для проверки работоспособности
- Подключение blueprint'а для /webhook
- Глобальный обработчик исключений
"""

import logging
import logging.handlers
from pathlib import Path
from flask import Flask, jsonify

# Создаём директорию для логов, если её нет
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

# Настройка логирования с ротацией
log_file = log_dir / 'app.log'
handler = logging.handlers.RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10 МБ
    backupCount=5,
    encoding='utf-8'
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# Настройка корневого логгера
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        handler,
        logging.StreamHandler()  # вывод в консоль тоже оставим
    ]
)

logger = logging.getLogger(__name__)

# Создаём Flask-приложение
app = Flask(__name__)

# Глобальный обработчик исключений для Flask
@app.errorhandler(Exception)
def handle_exception(e):
    """Логирует все необработанные исключения и возвращает 500."""
    logger.exception("Необработанное исключение: %s", e)
    return jsonify({"error": "Internal server error"}), 500

# Импортируем и регистрируем blueprint для API
try:
    from app.api.routes import api_bp
    app.register_blueprint(api_bp)
    logger.info("Blueprint API зарегистрирован")
except ImportError as e:
    logger.error(f"Не удалось зарегистрировать blueprint: {e}")

@app.route('/health', methods=['GET'])
def health():
    """Эндпоинт для проверки работоспособности"""
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # Загружаем конфигурацию
    try:
        from app.core.config import config
        debug = config.DEBUG
    except ImportError:
        debug = True
        logger.warning("Не удалось загрузить config, используется DEBUG=True")

    logger.info("Запуск Flask-приложения")
    app.run(host='0.0.0.0', port=5000, debug=debug)