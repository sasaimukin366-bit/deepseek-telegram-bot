#!/usr/bin/env python3
"""
Telegram бот с DeepSeek AI для Render.com
"""

import os
from openai import OpenAI
from flask import Flask, request, jsonify
import logging
import requests

app = Flask(__name__)

# === КОНФИГУРАЦИЯ ===
# Получаем из переменных окружения Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# Проверка
if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    raise ValueError("❌ Установи TELEGRAM_TOKEN и DEEPSEEK_API_KEY в настройках Render")

# Инициализация DeepSeek
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Логирование
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
    <h1>🤖 DeepSeek Telegram Bot</h1>
    <p>Бот работает на Render.com!</p>
    <p>После деплоя открой: /set_webhook</p>
    <p>Затем напиши боту /start в Telegram</p>
    """

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка webhook через браузер"""
    try:
        # Получаем URL Render автоматически
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-bot.onrender.com")
        webhook_url = f"{render_url}/webhook"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        data = {"url": webhook_url}
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            return f"""
            <h1>✅ Webhook установлен!</h1>
            <p>URL: {webhook_url}</p>
            <p>Теперь открой Telegram и напиши боту /start</p>
            <p><a href="/">На главную</a></p>
            """
        else:
            return f"""
            <h1>❌ Ошибка {response.status_code}</h1>
            <p>{response.text}</p>
            <p><a href="/">На главную</a></p>
            """
    except Exception as e:
        return f"<h1>❌ Ошибка: {e}</h1>"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик сообщений от Telegram"""
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
            send_message(chat_id, f"🤖 Привет, {user_name}!\nЯ бот с DeepSeek AI.\nПросто напиши мне сообщение!")
        
        # Любое другое сообщение
        elif text.strip():
            try:
                # Запрос к DeepSeek
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "Ты полезный ассистент. Отвечай на русском языке."},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                
                answer = response.choices[0].message.content
                send_message(chat_id, answer)
                
                logger.info(f"✅ Ответ отправлен {user_name}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка DeepSeek: {e}")
                send_message(chat_id, "⚠️ Произошла ошибка. Попробуйте позже.")
    
    return jsonify({"status": "ok"})

@app.route('/health')
def health():
    """Health check для Render"""
    return jsonify({"status": "healthy", "service": "telegram-bot"})

@app.route('/test')
def test():
    """Тестовая страница"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Привет! Ответь коротко."}],
            max_tokens=10
        )
        answer = response.choices[0].message.content
        
        return jsonify({
            "status": "✅ Всё работает",
            "deepseek": answer,
            "telegram_token_set": bool(TELEGRAM_TOKEN)
        })
    except Exception as e:
        return jsonify({
            "status": "❌ Ошибка",
            "error": str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Запуск бота на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
