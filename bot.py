#!/usr/bin/env python3
"""
Telegram бот с поддержкой фото через OpenRouter и памятью диалога
"""

import os
import json
import base64
from flask import Flask, request, jsonify
import logging
import requests
from collections import defaultdict

app = Flask(__name__)

# === КОНФИГУРАЦИЯ ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = "openai/gpt-5.1-codex-mini"  # Модель которая понимает картинки

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === ПАМЯТЬ ДИАЛОГА ===
conversation_history = defaultdict(list)
MAX_HISTORY = 10  # Сохранять последние 10 сообщений (5 пар вопрос-ответ)

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

def ask_openrouter_with_history(messages):
    """Запрос к OpenRouter с историей диалога"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
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

def ask_openrouter_with_image(prompt, image_bytes=None, image_url=None, history=None):
    """Запрос к OpenRouter с изображением и историей"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Формируем сообщения с историей
    messages = [
        {
            "role": "system", 
            "content": "Ты полезный ассистент. Отвечай на русском языке. Помни историю диалога."
        }
    ]
    
    # Добавляем историю диалога если есть
    if history:
        for msg in history:
            messages.append(msg)
    
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
    <h1>🤖 Бот с поддержкой фото и памятью диалога</h1>
    <p>Можно отправлять фото и текст!</p>
    <p>Бот запоминает историю разговора (последние 5 пар вопрос-ответ)</p>
    <p>Модель: openai/gpt-4o-mini</p>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик сообщений с фото и памятью диалога"""
    data = request.json
    
    if not data:
        return jsonify({"error": "No data"}), 400
    
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        user_id = message['from']['id']  # Получаем ID пользователя для памяти
        text = message.get('text', '')
        
        # Команда /start
        if text == '/start':
            conversation_history[user_id] = []  # Очищаем историю
            name = message['from'].get('first_name', 'друг')
            send_message(chat_id, 
                f"🤖 Привет, {name}!\n"
                f"Я бот с AI который понимает фото и запоминает разговор!\n\n"
                f"📸 **Что умею:**\n"
                f"• Отвечать на текстовые сообщения\n"
                f"• Анализировать фотографии\n"
                f"• Помнить историю нашего диалога\n\n"
                f"🔄 **Команды:**\n"
                f"/clear - очистить историю разговора\n"
                f"/help - справка\n\n"
                f"Память: сохраняю последние {MAX_HISTORY//2} пар вопрос-ответ.")
        
        # Команда /clear
        elif text == '/clear':
            conversation_history[user_id] = []
            send_message(chat_id, "🗑️ История диалога очищена! Начинаем новый разговор.")
        
        # Команда /help
        elif text == '/help':
            send_message(chat_id,
                "📸 **Что умеет бот:**\n"
                "1. Отправь фото - опишу что на нём\n"
                "2. Отправь фото с текстом - отвечу по контексту\n"
                "3. Просто текст - обычный ответ с учётом истории\n\n"
                "🔄 **Команды:**\n"
                "/start - начать заново\n"
                "/clear - очистить историю\n"
                "/help - эта справка\n\n"
                "💾 **Память:** бот помнит последние " + str(MAX_HISTORY//2) + " пар вопрос-ответ\n\n"
                "📋 **Примеры:**\n"
                "• Фото еды → 'Это пицца с грибами'\n"
                "• Фото + 'Что это?' → описание\n"
                "• 'Привет' → 'Привет!' с памятью диалога")
        
        # Если есть фото
        elif 'photo' in message:
            send_chat_action(chat_id, "typing")
            
            # Берем историю диалога (без учета system сообщения)
            history = conversation_history[user_id][-MAX_HISTORY:] if user_id in conversation_history else []
            
            # Берем самое большое фото
            photos = message['photo']
            largest_photo = photos[-1]  # Последнее - самое большое
            file_id = largest_photo['file_id']
            
            caption = message.get('caption', '')
            user_message = caption if caption else "Что на этом изображении?"
            
            # Скачиваем фото
            image_data = get_file_from_telegram(file_id)
            
            if image_data:
                send_message(chat_id, "🤔 Анализирую изображение...")
                
                # Запрос к AI с фото и историей
                answer = ask_openrouter_with_image(
                    prompt=user_message, 
                    image_bytes=image_data,
                    history=history
                )
                
                if answer:
                    # Сохраняем в историю
                    conversation_history[user_id].append({
                        "role": "user", 
                        "content": user_message + " [ФОТО]"
                    })
                    conversation_history[user_id].append({
                        "role": "assistant", 
                        "content": answer
                    })
                    
                    # Ограничиваем размер истории
                    if len(conversation_history[user_id]) > MAX_HISTORY * 2:
                        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY*2:]
                    
                    send_message(chat_id, answer)
                else:
                    send_message(chat_id, "⚠️ Не удалось проанализировать фото.")
            else:
                send_message(chat_id, "❌ Не удалось загрузить фото.")
        
        # Только текст (не команда)
        elif text.strip() and not text.startswith('/'):
            send_chat_action(chat_id, "typing")
            
            # Получаем историю диалога
            history = conversation_history[user_id][-MAX_HISTORY:] if user_id in conversation_history else []
            
            # Формируем сообщения для AI
            messages = [
                {
                    "role": "system", 
                    "content": "Ты полезный ассистент. Отвечай на русском языке. Помни историю диалога."
                }
            ]
            
            # Добавляем историю
            for msg in history:
                messages.append(msg)
            
            # Добавляем текущее сообщение
            messages.append({"role": "user", "content": text})
            
            # Запрос к AI с историей
            answer = ask_openrouter_with_history(messages)
            
            if answer:
                # Сохраняем в историю
                conversation_history[user_id].append({"role": "user", "content": text})
                conversation_history[user_id].append({"role": "assistant", "content": answer})
                
                # Ограничиваем размер истории
                if len(conversation_history[user_id]) > MAX_HISTORY * 2:
                    conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY*2:]
                
                send_message(chat_id, answer)
            else:
                send_message(chat_id, "⚠️ Ошибка. Попробуйте позже.")
    
    return jsonify({"status": "ok"})

@app.route('/test')
def test():
    """Тест работы"""
    answer = ask_openrouter_with_history([
        {"role": "system", "content": "Ты полезный ассистент."},
        {"role": "user", "content": "Привет! Работает?"}
    ])
    
    if answer:
        return jsonify({
            "status": "✅ Работает",
            "model": MODEL,
            "capabilities": "text + images + memory",
            "memory_type": "in-memory (max " + str(MAX_HISTORY//2) + " QA pairs)"
        })
    else:
        return jsonify({
            "status": "❌ Ошибка",
            "model": MODEL
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Запуск бота с поддержкой фото и памятью диалога")
    logger.info(f"🧠 Модель: {MODEL}")
    logger.info(f"💾 Память: сохраняет последние {MAX_HISTORY//2} пар вопрос-ответ")
    app.run(host='0.0.0.0', port=port, debug=False)
