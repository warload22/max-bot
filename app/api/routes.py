"""
Модуль маршрутов API.
Содержит эндпоинт для приёма вебхуков от MAX.
"""

import logging
from flask import Blueprint, request, jsonify
from app.handlers.message_handler import handle_update

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

def extract_update_data(json_data):
    """
    Извлекает стандартные поля из входящего вебхука MAX.
    Возвращает словарь с update_type, chat_id, user_id, text и другими полями.
    """
    update = {
        'update_type': json_data.get('update_type'),
        'timestamp': json_data.get('timestamp'),
        'user_locale': json_data.get('user_locale'),
        'raw': json_data
    }

    # Для bot_started и подобных (без message)
    if update['update_type'] == 'bot_started':
        update['chat_id'] = json_data.get('chat_id')
        user = json_data.get('user')
        if user:
            update['user_id'] = user.get('user_id')
        update['payload'] = json_data.get('payload')
        return update

    # Для message_created и других с message
    message = json_data.get('message')
    if message and isinstance(message, dict):
        recipient = message.get('recipient')
        if recipient and isinstance(recipient, dict):
            update['chat_id'] = recipient.get('chat_id')
            update['recipient_user_id'] = recipient.get('user_id')
            update['chat_type'] = recipient.get('chat_type')

        sender = message.get('sender')
        if sender and isinstance(sender, dict):
            update['sender_user_id'] = sender.get('user_id')
            # Для обычных сообщений user_id берём из sender
            if update['update_type'] != 'message_callback':
                update['user_id'] = sender.get('user_id')
            update['sender_name'] = sender.get('name')
            update['sender_first_name'] = sender.get('first_name')
            update['sender_last_name'] = sender.get('last_name')

        body = message.get('body')
        if body and isinstance(body, dict):
            update['text'] = body.get('text')
            update['message_id'] = body.get('mid')
            update['seq'] = body.get('seq')

    # Для событий типа bot_started (уже обработали выше, но на случай, если не попали)
    if not update.get('chat_id') and json_data.get('chat_id'):
        update['chat_id'] = json_data.get('chat_id')
        if json_data.get('user') and isinstance(json_data['user'], dict):
            update['user_id'] = json_data['user'].get('user_id')
        update['payload'] = json_data.get('payload')

    # Для callback-кнопок
    if update['update_type'] == 'message_callback':
        callback_obj = json_data.get('callback')
        if callback_obj and isinstance(callback_obj, dict):
            update['callback_data'] = callback_obj.get('payload')
            update['callback_id'] = callback_obj.get('callback_id')
            user = callback_obj.get('user')
            if user and isinstance(user, dict):
                update['user_id'] = user.get('user_id')

    return update

@api_bp.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data:
        logger.warning("Получен пустой запрос")
        return jsonify({"error": "empty request"}), 400

    logger.info(f"Получен вебхук: {data}")

    update = extract_update_data(data)
    logger.info(f"Извлечённые данные: {update}")

    try:
        handle_update(update)
    except Exception as e:
        logger.exception(f"Ошибка при обработке обновления: {e}")

    return jsonify({"result": "ok"})