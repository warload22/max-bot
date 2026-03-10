"""
Модуль для взаимодействия с API MAX.
Содержит класс MaxAPI для отправки сообщений, клавиатур и ответов на callback.
"""

import requests
import logging
from typing import Optional, Dict, List
from app.core.config import config

logger = logging.getLogger(__name__)

class MaxAPI:
    """
    Клиент для API MAX.
    Использует токен бота из конфигурации.
    """
    BASE_URL = "https://platform-api.max.ru"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }

    def _request(self, method: str, url: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Базовый метод для выполнения HTTP-запросов к API MAX.
        """
        try:
            response = requests.request(method, url, headers=self.headers, json=data, timeout=10)
            logger.info(f"Ответ от {url}: статус {response.status_code}, тело: {response.text}")
            response.raise_for_status()
            # Возвращаем JSON, если есть контент, иначе None (для 204 No Content)
            return response.json() if response.content else {"success": True}
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к MAX API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Ответ сервера: {e.response.text}")
            return None

    def send_message(
        self,
        chat_id: int,
        text: str,
        keyboard: Optional[List[List[Dict]]] = None,
        format: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Отправляет текстовое сообщение в чат.
        """
        url = f"{self.BASE_URL}/messages?chat_id={chat_id}"
        payload = {"text": text}
        if format:
            payload["format"] = format
        if keyboard:
            payload["attachments"] = [
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": keyboard}
                }
            ]
        logger.info(f"📤 Отправка сообщения в чат {chat_id}: {text[:50]}...")
        logger.debug(f"📦 Полный payload: {payload}")
        return self._request("POST", url, payload)

    def send_message_to_user(self, user_id: int, text: str, keyboard: Optional[List[List[Dict]]] = None, format: Optional[str] = None) -> Optional[Dict]:
        """
        Отправляет личное сообщение пользователю (использует user_id в URL).
        """
        url = f"{self.BASE_URL}/messages?user_id={user_id}"
        payload = {"text": text}
        if format:
            payload["format"] = format
        if keyboard:
            payload["attachments"] = [
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": keyboard}
                }
            ]
        logger.info(f"📤 Отправка личного сообщения пользователю {user_id}: {text[:50]}...")
        return self._request("POST", url, payload)

    def answer_callback(self, callback_query_id: str, text: Optional[str] = None) -> Optional[Dict]:
        """
        Отвечает на callback-запрос (убирает "часики" на кнопке).
        """
        url = f"{self.BASE_URL}/answer_callback"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return self._request("POST", url, payload)

    def edit_message(
        self,
        message_id: str,
        text: Optional[str] = None,
        keyboard: Optional[List[List[Dict]]] = None,
        format: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Редактирует существующее сообщение по его message_id.
        В соответствии с документацией MAX: PUT /messages?message_id={message_id}
        """
        url = f"{self.BASE_URL}/messages?message_id={message_id}"
        payload = {}
        if text:
            payload["text"] = text
        if format:
            payload["format"] = format
        if keyboard:
            payload["attachments"] = [
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": keyboard}
                }
            ]
        logger.info(f"📝 Редактирование сообщения {message_id} с текстом: {text[:50] if text else 'без текста'}")
        return self._request("PUT", url, payload)

    def delete_message(self, message_id: str) -> Optional[Dict]:
        """
        Удаляет сообщение по его message_id.
        В соответствии с документацией MAX: DELETE /messages?message_id={message_id}
        """
        url = f"{self.BASE_URL}/messages?message_id={message_id}"
        logger.info(f"🗑️ Удаление сообщения {message_id}")
        result = self._request("DELETE", url)
        if result is not None:
            logger.info(f"✅ Сообщение {message_id} успешно удалено")
        else:
            logger.error(f"❌ Не удалось удалить сообщение {message_id}")
        return result

    def delete_message_with_retry(self, message_id: str, retries: int = 3, delay: float = 0.5) -> Optional[Dict]:
        """
        Удаляет сообщение с повторными попытками в случае неудачи.
        """
        import time
        for attempt in range(retries):
            result = self.delete_message(message_id)
            if result is not None:
                return result
            logger.warning(f"Попытка {attempt+1} удаления сообщения {message_id} не удалась, повтор через {delay} сек")
            time.sleep(delay)
        logger.error(f"Не удалось удалить сообщение {message_id} после {retries} попыток")
        return None

# Создаём глобальный экземпляр для использования во всём приложении
max_api = MaxAPI(config.MAX_BOT_TOKEN)