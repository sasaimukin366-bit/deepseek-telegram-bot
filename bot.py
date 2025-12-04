#!/usr/bin/env python3
"""
Telegram бот с поддержкой фото через OpenRouter и памятью диалога
Может как получать, так и отправлять фото
"""

import os
import json
import base64
from flask import Flask, request, jsonify
import logging
import requests
from collections import defaultdict
from io import BytesIO
import mimetypes

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

def download_image_from_url(url):
    """Скачать изображение по URL"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
    return None

def send_photo(chat_id, photo_data, caption=""):
    """Отправить фото в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    # Определяем MIME тип
    mime_type = mimetypes.guess_type("photo.jpg")[0] or "image/jpeg"
    
    files = {'photo': ('photo.jpg', BytesIO(photo_data), mime_type)}
    data = {'chat_id': chat_id}
    
    if caption:
        data['caption'] = caption[:1024]  # Ограничение Telegram
    
    try:
        response = requests.post(url, files=files, data=data, timeout=30)
        if response.status_code == 200:
            logger.info(f"Photo sent successfully to {chat_id}")
            return True
        else:
            logger.error(f"Error sending photo: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        return False

def send_document(chat_id, document_data, filename="image.png", caption=""):
    """Отправить документ (изображение как файл)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    
    files = {'document': (filename, BytesIO(document_data))}
    data = {'chat_id': chat_id}
    
    if caption:
        data['caption'] = caption[:1024]
    
    try:
        response = requests.post(url, files=files, data=data, timeout=30)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending document: {e}")
        return False

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
        "max_tokens": 1500  # Увеличили для ответов с URL изображений
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
            "content": """Ты полезный ассистент. Отвечай на русском языке. Помни историю диалога.

Если пользователь просит картинку, изображение, фото, рисунок или что-то визуальное:
1. Ты МОЖЕШЬ генерировать/создавать изображения
2. Для этого используй специальный формат:
   [IMAGE:URL_ЗДЕСЬ]
   Например: [IMAGE:https://example.com/image.jpg]
3. Можешь добавить описание после URL, разделяя вертикальной чертой: [IMAGE:https://example.com/image.jpg|Описание изображения]
4. Если не можешь или не нужно генерировать изображение - просто ответь текстом."""
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
        "max_tokens": 1500
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

def send_message(chat_id, text, parse_mode="Markdown"):
    """Отправка сообщения"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id, 
        "text": text,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Send error: {e}")
        return False

def send_chat_action(chat_id, action="typing"):
    """Отправка действия (typing, upload_photo, upload_document)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
    data = {"chat_id": chat_id, "action": action}
    
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

def extract_image_urls_from_response(text):
    """Извлечь URL изображений из ответа AI"""
    import re
    # Паттерн для поиска [IMAGE:URL|описание] или [IMAGE:URL]
    pattern = r'\[IMAGE:(https?://[^\s\|\[\]]+)(?:\|([^\]]+))?\]'
    matches = re.findall(pattern, text)
    
    image_data = []
    for url, description in matches:
        image_data.append({
            'url': url,
            'description': description or 'Изображение'
        })
    
    # Убираем теги из текста
    clean_text = re.sub(pattern, '', text).strip()
    
    return clean_text, image_data

@app.route('/')
def home():
    return """
    <h1>🤖 Бот с поддержкой фото и памятью диалога</h1>
    <p>Можно отправлять фото и текст! Бот тоже может отправлять фото.</p>
    <p>Бот запоминает историю разговора (последние 5 пар вопрос-ответ)</p>
    <p>Модель: openai/gpt-5.1-codex-mini</p>
    <p>🎨 Бот может отправлять изображения по запросу!</p>
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
                f"• Отправлять изображения по запросу\n"
                f"• Помнить историю нашего диалога\n\n"
                f"🎨 **Как получить изображение:**\n"
                f"Просто попроси меня нарисовать что-то! Например:\n"
                f"• \"Нарисуй кота\"\n"
                f"• \"Покажи фото заката\"\n"
                f"• \"Сгенерируй изображение города будущего\"\n\n"
                f"🔄 **Команды:**\n"
                f"/clear - очистить историю разговора\n"
                f"/help - справка\n"
                f"/image - примеры запросов для изображений\n\n"
                f"💾 Память: сохраняю последние {MAX_HISTORY//2} пар вопрос-ответ.")
        
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
                "3. Просто текст - обычный ответ с учётом истории\n"
                "4. Попроси изображение - постараюсь отправить картинку\n\n"
                "🔄 **Команды:**\n"
                "/start - начать заново\n"
                "/clear - очистить историю\n"
                "/help - эта справка\n"
                "/image - примеры запросов для изображений\n\n"
                "💾 **Память:** бот помнит последние " + str(MAX_HISTORY//2) + " пар вопрос-ответ\n\n"
                "📋 **Примеры:**\n"
                "• Фото еды → 'Это пицца с грибами'\n"
                "• 'Нарисуй кота' → картинка кота\n"
                "• 'Привет' → 'Привет!' с памятью диалога")
        
        # Команда /image
        elif text == '/image':
            send_message(chat_id,
                "🎨 **Примеры запросов для изображений:**\n\n"
                "🖼️ **Животные:**\n"
                "• Нарисуй милого кота\n"
                "• Покажи фото собаки породы хаски\n"
                "• Сгенерируй изображение панды\n\n"
                "🌄 **Природа:**\n"
                "• Покажи красивый закат\n"
                "• Нарисуй горный пейзаж\n"
                "• Фото тропического пляжа\n\n"
                "🏙️ **Города:**\n"
                "• Изображение Нью-Йорка\n"
                "• Нарисуй старый европейский город\n"
                "• Город будущего\n\n"
                "🎨 **Искусство:**\n"
                "• Картина в стиле Ван Гога\n"
                "• Абстрактное искусство\n"
                "• Мандала для медитации\n\n"
                "📝 **Просто попроси, и я постараюсь!**")
        
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
                    # Проверяем, содержит ли ответ URL изображения
                    clean_text, image_urls = extract_image_urls_from_response(answer)
                    
                    # Сохраняем в историю (без тегов изображений)
                    conversation_history[user_id].append({
                        "role": "user", 
                        "content": user_message + " [ФОТО]"
                    })
                    
                    # Отправляем изображения если есть
                    if image_urls:
                        send_chat_action(chat_id, "upload_photo")
                        for img in image_urls[:3]:  # Максимум 3 изображения за раз
                            img_data = download_image_from_url(img['url'])
                            if img_data:
                                send_photo(chat_id, img_data, img['description'])
                            else:
                                send_message(chat_id, f"⚠️ Не удалось загрузить изображение: {img['description']}")
                    
                    # Отправляем текстовую часть если есть
                    if clean_text:
                        send_message(chat_id, clean_text)
                    
                    # Сохраняем ответ в историю (без тегов)
                    conversation_history[user_id].append({
                        "role": "assistant", 
                        "content": clean_text or f"Отправил {len(image_urls)} изображение(й)"
                    })
                    
                    # Ограничиваем размер истории
                    if len(conversation_history[user_id]) > MAX_HISTORY * 2:
                        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY*2:]
                    
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
                    "content": """Ты полезный ассистент. Отвечай на русском языке. Помни историю диалога.

Если пользователь просит картинку, изображение, фото, рисунок или что-то визуальное:
1. Ты МОЖЕШЬ генерировать/создавать изображения
2. Для этого используй специальный формат:
   [IMAGE:URL_ЗДЕСЬ]
   Например: [IMAGE:https://example.com/image.jpg]
3. Можешь добавить описание после URL, разделяя вертикальной чертой: [IMAGE:https://example.com/image.jpg|Описание изображения]
4. Если не можешь или не нужно генерировать изображение - просто ответь текстом."""
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
                # Проверяем, содержит ли ответ URL изображения
                clean_text, image_urls = extract_image_urls_from_response(answer)
                
                # Отправляем изображения если есть
                if image_urls:
                    send_chat_action(chat_id, "upload_photo")
                    for img in image_urls[:3]:  # Максимум 3 изображения за раз
                        img_data = download_image_from_url(img['url'])
                        if img_data:
                            success = send_photo(chat_id, img_data, img['description'])
                            if not success:
                                # Пробуем отправить как документ
                                send_document(chat_id, img_data, "image.jpg", img['description'])
                        else:
                            send_message(chat_id, f"⚠️ Не удалось загрузить изображение: {img['description']}")
                
                # Отправляем текстовую часть если есть
                if clean_text:
                    send_message(chat_id, clean_text)
                elif not image_urls:
                    # Если нет ни текста, ни изображений, отправляем оригинальный ответ
                    send_message(chat_id, answer)
                
                # Сохраняем в историю
                conversation_history[user_id].append({"role": "user", "content": text})
                conversation_history[user_id].append({
                    "role": "assistant", 
                    "content": clean_text or f"Отправил {len(image_urls)} изображение(й)" if image_urls else answer
                })
                
                # Ограничиваем размер истории
                if len(conversation_history[user_id]) > MAX_HISTORY * 2:
                    conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY*2:]
                
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
            "capabilities": "text + images + memory + send images",
            "memory_type": "in-memory (max " + str(MAX_HISTORY//2) + " QA pairs)",
            "image_support": "Can receive and send images"
        })
    else:
        return jsonify({
            "status": "❌ Ошибка",
            "model": MODEL
        })

@app.route('/send_test_photo')
def send_test_photo():
    """Тест отправки фото (для проверки)"""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return "Need chat_id parameter", 400
    
    # Создаем простое тестовое изображение
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (400, 300), color='lightblue')
    d = ImageDraw.Draw(img)
    d.text((100, 150), "Тест от бота!", fill='black')
    
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    success = send_photo(chat_id, img_byte_arr, "Тестовое изображение от бота!")
    
    return jsonify({"success": success})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Запуск бота с поддержкой фото и памятью диалога")
    logger.info(f"🧠 Модель: {MODEL}")
    logger.info(f"💾 Память: сохраняет последние {MAX_HISTORY//2} пар вопрос-ответ")
    logger.info(f"🎨 Возможности: получение и отправка изображений")
    app.run(host='0.0.0.0', port=port, debug=False)
