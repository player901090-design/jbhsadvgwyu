#!/usr/bin/env python3
"""
Единый файл запуска для GetGems WebApp
Запускает Flask сервер и Telegram бота одновременно

Заказать бота/проект - @flickTXF
"""

import asyncio
import logging
import multiprocessing
import signal
import sys
import time
from threading import Thread

from config import Config
from app import app
from telegram_bot import main as bot_main


def setup_logging():
    """Настройка логирования для главного процесса
    
    Заказать бота/проект - @flickTXF
    """
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('main.log', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)


def run_flask_server():
    """Запуск Flask сервера
    
    Заказать бота/проект - @flickTXF
    """
    logger = logging.getLogger('flask_server')
    try:
        logger.info("Запуск Flask сервера...")
        app.run(
            debug=Config.FLASK_DEBUG,
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            use_reloader=False  # Отключаем reloader для избежания конфликтов
        )
    except Exception as e:
        logger.error(f"Ошибка при запуске Flask сервера: {e}")
        raise


def run_telegram_bot():
    """Запуск Telegram бота
    
    Заказать бота/проект - @flickTXF
    """
    logger = logging.getLogger('telegram_bot')
    try:
        logger.info("Запуск Telegram бота...")
        asyncio.run(bot_main())
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram бота: {e}")
        raise


class MainApplication:
    """Главный класс приложения для управления процессами"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.flask_process = None
        self.bot_process = None
        self.running = False
        
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        self.logger.info(f"Получен сигнал {signum}, завершение работы...")
        self.stop()
        
    def start(self):
        """Запуск всех компонентов приложения"""
        try:
            # Проверка конфигурации
            self.logger.info("Проверка конфигурации...")
            Config.validate_bot_token()
            Config.ensure_directories()
            Config.print_config_info()
            
            self.logger.info("Запуск GetGems WebApp...")
            self.running = True
            
            # Настройка обработчиков сигналов
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            # Запуск Flask сервера в отдельном процессе
            self.logger.info("Создание процесса Flask сервера...")
            self.flask_process = multiprocessing.Process(
                target=run_flask_server,
                name="FlaskServer"
            )
            self.flask_process.start()
            
            # Небольшая задержка для запуска Flask
            time.sleep(2)
            
            # Запуск Telegram бота в отдельном процессе
            self.logger.info("Создание процесса Telegram бота...")
            self.bot_process = multiprocessing.Process(
                target=run_telegram_bot,
                name="TelegramBot"
            )
            self.bot_process.start()
            
            self.logger.info("Все компоненты запущены успешно!")
            self.logger.info(f"Flask сервер доступен по адресу: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
            self.logger.info(f"Telegram бот: @{Config.BOT_USERNAME}")
            
            # Мониторинг процессов
            self.monitor_processes()
            
        except Exception as e:
            self.logger.error(f"Ошибка при запуске приложения: {e}")
            self.stop()
            sys.exit(1)
            
    def monitor_processes(self):
        """Мониторинг состояния процессов"""
        while self.running:
            try:
                # Проверка Flask процесса
                if self.flask_process and not self.flask_process.is_alive():
                    self.logger.error("Flask сервер завершился неожиданно!")
                    self.stop()
                    break
                    
                # Проверка бот процесса
                if self.bot_process and not self.bot_process.is_alive():
                    self.logger.error("Telegram бот завершился неожиданно!")
                    self.stop()
                    break
                    
                time.sleep(5)  # Проверка каждые 5 секунд
                
            except KeyboardInterrupt:
                self.logger.info("Получен сигнал прерывания...")
                self.stop()
                break
            except Exception as e:
                self.logger.error(f"Ошибка в мониторинге процессов: {e}")
                
    def stop(self):
        """Остановка всех компонентов"""
        if not self.running:
            return
            
        self.logger.info("Остановка приложения...")
        self.running = False
        
        # Остановка Flask процесса
        if self.flask_process and self.flask_process.is_alive():
            self.logger.info("Остановка Flask сервера...")
            self.flask_process.terminate()
            self.flask_process.join(timeout=10)
            if self.flask_process.is_alive():
                self.logger.warning("Принудительное завершение Flask сервера...")
                self.flask_process.kill()
                
        # Остановка бот процесса
        if self.bot_process and self.bot_process.is_alive():
            self.logger.info("Остановка Telegram бота...")
            self.bot_process.terminate()
            self.bot_process.join(timeout=10)
            if self.bot_process.is_alive():
                self.logger.warning("Принудительное завершение Telegram бота...")
                self.bot_process.kill()
                
        self.logger.info("Приложение остановлено")


def main():
    """Главная функция"""
    # Проверка Python версии
    if sys.version_info < (3, 8):
        print("Требуется Python 3.8 или выше!")
        sys.exit(1)
        
    # Поддержка multiprocessing на Windows
    if sys.platform.startswith('win'):
        multiprocessing.set_start_method('spawn', force=True)
        
    # Создание и запуск приложения
    app_instance = MainApplication()
    
    try:
        app_instance.start()
    except KeyboardInterrupt:
        print("\nПолучен сигнал прерывания...")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        app_instance.stop()


if __name__ == "__main__":
    main()