#!/usr/bin/env python3
"""
Telegram бот с OpenRouter (только requests, без openai библиотеки)
"""

import os
import json
from flask import Flask, request, jsonify
import logging
import requests

app = Flask(__name__)

# === КОНФИГУРАЦИЯ ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = "google/gemini-3-pro-image-preview"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ask_openrouter(prompt):
    """Запрос к OpenRouter API через requests"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",  # Для OpenRouter
        "X-Title": "Telegram Bot"
    }
    
    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "system", 
                "content": "Ты полезный ассистент. Отвечай на русском языке. Будь кратким и информативным."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        logger.info(f"🔄 Отправляю запрос к OpenRouter: {prompt[:50]}...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        logger.info(f"📥 Ответ OpenRouter: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            logger.error(f"❌ Ошибка OpenRouter: {response.status_code}")
            logger.error(f"Ответ: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Исключение при запросе: {e}")
        return None

def send_message(chat_id, text):
    """Отправка сообщения в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Сообщение отправлено в {chat_id}")
            return True
        else:
            logger.error(f"❌ Ошибка Telegram: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

@app.route('/')
def home():
    return """
    <h1>🤖 Telegram Bot с OpenRouter</h1>
    <p>Использует DeepSeek R1 через OpenRouter</p>
    <p><a href="/test">Тест работы</a></p>
    <p>Чтобы активировать бота, напишите ему в Telegram</p>
    """

@app.route('/set_webhook')
def set_webhook():
    """Установка webhook"""
    try:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://deepseek-telegram-bot-c2rd.onrender.com")
        webhook_url = f"{render_url}/webhook"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        data = {"url": webhook_url}
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            return f"""
            <h1>✅ Webhook установлен!</h1>
            <p>URL: {webhook_url}</p>
            <p>Теперь напишите боту в Telegram</p>
            """
        else:
            return f"""
            <h1>❌ Ошибка {response.status_code}</h1>
            <p>Ответ: {response.text}</p>
            """
    except Exception as e:
        return f"<h1>❌ Ошибка: {e}</h1>"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик сообщений от Telegram"""
    data = request.json
    
    if not data:
        return jsonify({"error": "No data"}), 400
    
    logger.info(f"📩 Получен webhook запрос")
    
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        user_name = message['from'].get('first_name', 'Пользователь')
        
        logger.info(f"👤 {user_name} ({chat_id}): {text}")
        
        # Команда /start
        if text == '/start':
            send_message(chat_id, f"🤖 Привет, {user_name}!\nЯ бот с DeepSeek AI через OpenRouter.\nПросто напиши мне сообщение!")
        
        # Команда /help
        elif text == '/help':
            send_message(chat_id, "📚 Помощь:\nПросто напиши сообщение - я отвечу с помощью AI!")
        
        # Любое другое сообщение
        elif text.strip():
            # Отправляем статус "печатает"
            typing_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
            requests.post(typing_url, json={"chat_id": chat_id, "action": "typing"}, timeout=5)
            
            # Получаем ответ от AI
            answer = ask_openrouter(text)
            
            if answer:
                send_message(chat_id, answer)
                logger.info(f"✅ Ответ отправлен пользователю {user_name}")
            else:
                send_message(chat_id, "⚠️ Не удалось получить ответ. Попробуйте позже.")
                logger.error(f"❌ Не удалось получить ответ для: {text}")
    
    return jsonify({"status": "ok", "message": "processed"})

@app.route('/test')
def test():
    """Тестовая страница"""
    test_prompt = "Привет! Как дела?"
    answer = ask_openrouter(test_prompt)
    
    if answer:
        return jsonify({
            "status": "✅ OpenRouter работает!",
            "model": MODEL,
            "response": answer[:200],
            "length": len(answer)
        })
    else:
        return jsonify({
            "status": "❌ OpenRouter не отвечает",
            "model": MODEL,
            "error": "Проверьте API ключ и подключение"
        })

@app.route('/health')
def health():
    """Health check для Render"""
    return jsonify({
        "status": "healthy",
        "service": "telegram-openrouter-bot",
        "model": MODEL
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА С OPENROUTER")
    logger.info(f"🌐 URL: https://deepseek-telegram-bot-c2rd.onrender.com")
    logger.info(f"🧠 Модель: {MODEL}")
    logger.info(f"🔑 API ключ: {'установлен' if OPENROUTER_API_KEY else 'НЕ УСТАНОВЛЕН'}")
    logger.info("=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=False)
