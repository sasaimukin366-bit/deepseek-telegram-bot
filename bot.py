#!/usr/bin/env python3
"""
Telegram бот с DeepSeek AI для Render.com
openai==0.28.1
"""

import os
import openai  # ← Старая версия
from flask import Flask, request, jsonify
import logging
import requests

app = Flask(__name__)

# === КОНФИГУРАЦИЯ ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    raise ValueError("❌ Установи TELEGRAM_TOKEN и DEEPSEEK_API_KEY")

# Настройка DeepSeek (СТАРЫЙ API)
openai.api_key = DEEPSEEK_API_KEY
openai.api_base = "https://api.deepseek.com/v1"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

@app.route('/')
def home():
    return """
    <h1>🤖 DeepSeek Telegram Bot</h1>
    <p>Бот работает на Render.com!</p>
    <p>После деплоя открой: /set_webhook</p>
    """

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
        webhook_url = f"{render_url}/webhook"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        data = {"url": webhook_url}
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            return f"""
            <h1>✅ Webhook установлен!</h1>
            <p>URL: {webhook_url}</p>
            <p>Теперь открой Telegram и напиши боту /start</p>
            """
        else:
            return f"""
            <h1>❌ Ошибка {response.status_code}</h1>
            <p>{response.text}</p>
            """
    except Exception as e:
        return f"<h1>❌ Ошибка: {e}</h1>"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    if not data:
        return jsonify({"error": "No data"}), 400
    
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        if text == '/start':
            name = message['from'].get('first_name', 'друг')
            send_message(chat_id, f"🤖 Привет, {name}!\nЯ бот с DeepSeek AI.")
        
        elif text.strip():
            try:
                # СТАРЫЙ API ДЛЯ openai==0.28.1
                response = openai.ChatCompletion.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "Ты полезный ассистент. Отвечай на русском."},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=1000
                )
                
                answer = response.choices[0].message.content
                send_message(chat_id, answer)
                
            except Exception as e:
                logger.error(f"Ошибка: {e}")
                send_message(chat_id, "⚠️ Ошибка")
    
    return jsonify({"status": "ok"})

@app.route('/test')
def test():
    try:
        response = openai.ChatCompletion.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Привет"}],
            max_tokens=10
        )
        answer = response.choices[0].message.content
        
        return jsonify({
            "status": "✅ Работает",
            "response": answer,
            "openai_version": "0.28.1"
        })
    except Exception as e:
        return jsonify({
            "status": "❌ Ошибка",
            "error": str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Запуск бота")
    app.run(host='0.0.0.0', port=port, debug=False)
