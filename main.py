#!/usr/bin/env python3
"""
Единый файл запуска для GetGems WebApp
Локальный запуск без multiprocessing
"""

import asyncio
import logging
import sys
import threading
import time
from flask import Flask

from config import Config
from app import app
from telegram_bot import main as bot_main


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('main.log', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)


def run_flask():
    """Запуск Flask в отдельном потоке"""
    logger = logging.getLogger('flask_server')
    try:
        logger.info("Запуск Flask сервера...")
        app.run(
            debug=Config.FLASK_DEBUG,
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Ошибка при запуске Flask сервера: {e}")


async def run_telegram():
    """Запуск Telegram бота"""
    logger = logging.getLogger('telegram_bot')
    try:
        logger.info("Запуск Telegram бота...")
        await bot_main()
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram бота: {e}")


def main():
    """Главная функция"""
    # Проверка Python версии
    if sys.version_info < (3, 8):
        print("Требуется Python 3.8 или выше!")
        sys.exit(1)
        
    logger = setup_logging()
    
    try:
        logger.info("Запуск GetGems WebApp...")
        logger.info(f"Flask сервер: {Config.FLASK_HOST}:{Config.FLASK_PORT}")
        logger.info(f"Webhook URL: {Config.WEBAPP_URL}/webhook")
        
        # Проверка конфигурации
        if not Config.validate():
            logger.error("Валидация конфигурации не пройдена")
            return
        
        # Запуск Flask в отдельном потоке
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Небольшая задержка для запуска Flask
        time.sleep(2)
        
        # Запуск Telegram бота
        asyncio.run(run_telegram())
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    main()