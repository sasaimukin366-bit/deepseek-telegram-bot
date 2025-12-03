#!/usr/bin/env python3
"""
Telegram бот с поддержкой фото через OpenRouter
"""

import os
import json
import base64
from flask import Flask, request, jsonify
import logging
import requests

app = Flask(__name__)

# === КОНФИГУРАЦИЯ ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = "openai/gpt-5.1-codex-mini"  # Модель которая понимает картинки

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_file_from_telegram(file_id):
    """Получить файл от Telegram"""
    # 1. Получаем информацию о файле
    file_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile"
    file_info = requests.post(file_url, json={"file_id": file_id}).json()
    
    if not file_info.get('ok'):
        return None
    
    file_path = file_info['result']['file_path']
    
    # 2. Скачиваем файл
    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    response = requests.get(download_url)
    
    if response.status_code == 200:
        return response.content
    return None

def ask_openrouter_with_image(prompt, image_bytes=None, image_url=None):
    """Запрос к OpenRouter с изображением"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Формируем сообщения
    messages = [
        {
            "role": "system", 
            "content": "Ты полезный ассистент. Отвечай на русском языке."
        }
    ]
    
    # Если есть изображение
    if image_bytes:
        # Конвертируем в base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt if prompt else "Что на этом изображении?"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        })
    elif image_url:
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": prompt if prompt else "Что на этом изображении?"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            ]
        })
    else:
        # Только текст
        messages.append({
            "role": "user",
            "content": prompt
        })
    
    data = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            logger.error(f"OpenRouter error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Request error: {e}")
        return None

def send_message(chat_id, text):
    """Отправка сообщения"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Send error: {e}")
        return False

def send_chat_action(chat_id, action="typing"):
    """Отправка действия (typing, upload_photo)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
    data = {"chat_id": chat_id, "action": action}
    
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

@app.route('/')
def home():
    return """
    <h1>🤖 Бот с поддержкой фото</h1>
    <p>Можно отправлять фото и текст!</p>
    <p>Модель: openai/gpt-4o-mini</p>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик сообщений с фото"""
    data = request.json
    
    if not data:
        return jsonify({"error": "No data"}), 400
    
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        # Команда /start
        if text == '/start':
            name = message['from'].get('first_name', 'друг')
            send_message(chat_id, 
                f"🤖 Привет, {name}!\n"
                f"Я бот с AI который понимает фото!\n"
                f"Отправь мне фото с подписью или без.")
        
        # Команда /help
        elif text == '/help':
            send_message(chat_id,
                "📸 **Что умеет бот:**\n"
                "1. Отправь фото - опишу что на нём\n"
                "2. Отправь фото с текстом - отвечу по контексту\n"
                "3. Просто текст - обычный ответ\n\n"
                "Примеры:\n"
                "• Фото еды → 'Это пицца с грибами'\n"
                "• Фото + 'Что это?' → описание\n"
                "• 'Привет' → 'Привет!'")
        
        # Если есть фото
        elif 'photo' in message:
            send_chat_action(chat_id, "typing")
            
            # Берем самое большое фото
            photos = message['photo']
            largest_photo = photos[-1]  # Последнее - самое большое
            file_id = largest_photo['file_id']
            
            caption = message.get('caption', '')
            
            # Скачиваем фото
            send_message(chat_id, "🖼️ Получаю фото...")
            image_data = get_file_from_telegram(file_id)
            
            if image_data:
                send_message(chat_id, "🤔 Анализирую изображение...")
                
                # Запрос к AI с фото
                prompt = caption if caption else "Что на этом изображении? Опиши подробно."
                answer = ask_openrouter_with_image(prompt, image_bytes=image_data)
                
                if answer:
                    send_message(chat_id, answer)
                else:
                    send_message(chat_id, "⚠️ Не удалось проанализировать фото.")
            else:
                send_message(chat_id, "❌ Не удалось загрузить фото.")
        
        # Только текст
        elif text.strip():
            send_chat_action(chat_id, "typing")
            
            answer = ask_openrouter_with_image(text)
            if answer:
                send_message(chat_id, answer)
            else:
                send_message(chat_id, "⚠️ Ошибка. Попробуйте позже.")
    
    return jsonify({"status": "ok"})

@app.route('/test')
def test():
    """Тест работы"""
    answer = ask_openrouter_with_image("Привет! Работает?")
    if answer:
        return jsonify({
            "status": "✅ Работает",
            "model": MODEL,
            "capabilities": "text + images"
        })
    else:
        return jsonify({
            "status": "❌ Ошибка",
            "model": MODEL
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Запуск бота с поддержкой фото")
    logger.info(f"🧠 Модель: {MODEL}")
    app.run(host='0.0.0.0', port=port, debug=False)
