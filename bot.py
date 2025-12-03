#!/usr/bin/env python3
"""
Telegram бот с DeepSeek через OpenRouter (бесплатно!)
"""

import os
from openai import OpenAI
from flask import Flask, request, jsonify
import logging
import requests

app = Flask(__name__)

# === КОНФИГУРАЦИЯ OPENROUTER ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Настройка OpenRouter клиента
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# Модель (бесплатная)
MODEL = "deepseek/deepseek-r1:free"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_message(chat_id, text):
    """Отправка сообщения в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        return False

@app.route('/')
def home():
    return """
    <h1>🤖 Бот с DeepSeek R1 (OpenRouter)</h1>
    <p>Бесплатный доступ через OpenRouter!</p>
    <p><a href="/test">Тест работы</a></p>
    """

@app.route('/set_webhook')
def set_webhook():
    """Установка webhook"""
    try:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
        webhook_url = f"{render_url}/webhook"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        data = {"url": webhook_url}
        
        response = requests.post(url, json=data, timeout=10)
        
        return f"""
        <h1>Webhook установлен</h1>
        <p>Статус: {response.status_code}</p>
        <p>Ответ: {response.text}</p>
        """
    except Exception as e:
        return f"<h1>Ошибка: {e}</h1>"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик сообщений"""
    data = request.json
    
    if not data:
        return jsonify({"error": "No data"}), 400
    
    logger.info(f"📩 Получен запрос")
    
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        user_name = message['from'].get('first_name', 'друг')
        
        logger.info(f"👤 {user_name}: {text}")
        
        # Команда /start
        if text == '/start':
            send_message(chat_id, f"🤖 Привет, {user_name}!\nЯ бот с DeepSeek R1 (бесплатно через OpenRouter).\nНапиши мне что-нибудь!")
        
        # Любое сообщение
        elif text.strip():
            try:
                # Запрос через OpenRouter
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {
                            "role": "system", 
                            "content": "Ты полезный ассистент. Отвечай на русском языке. Будь дружелюбным."
                        },
                        {
                            "role": "user",
                            "content": text
                        }
                    ],
                    max_tokens=500,
                    temperature=0.7
                )
                
                answer = response.choices[0].message.content
                send_message(chat_id, answer)
                logger.info(f"✅ Ответ отправлен")
                
            except Exception as e:
                logger.error(f"❌ Ошибка OpenRouter: {e}")
                send_message(chat_id, "⚠️ Ошибка обработки. Попробуйте позже.")
    
    return jsonify({"status": "ok"})

@app.route('/test')
def test():
    """Тест работы OpenRouter"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": "Привет! Ответь коротко."}
            ],
            max_tokens=50
        )
        answer = response.choices[0].message.content
        
        return jsonify({
            "status": "✅ OpenRouter работает!",
            "model": MODEL,
            "response": answer,
            "provider": "OpenRouter (free)"
        })
    except Exception as e:
        return jsonify({
            "status": "❌ Ошибка OpenRouter",
            "error": str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Запуск бота с OpenRouter")
    logger.info(f"🧠 Модель: {MODEL}")
    app.run(host='0.0.0.0', port=port, debug=False)
