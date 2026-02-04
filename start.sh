#!/bin/bash

echo "Starting GetGems WebApp..."
echo

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "Python3 не найден! Установите Python 3.8 или выше."
    exit 1
fi

# Проверка зависимостей
if [ ! -f "requirements.txt" ]; then
    echo "Файл requirements.txt не найден!"
    exit 1
fi

# Проверка .env файла
if [ ! -f ".env" ]; then
    echo "Файл .env не найден! Создайте его по образцу из README.md"
    exit 1
fi

# Проверка виртуального окружения (опционально)
if [ -d "venv" ]; then
    echo "Активация виртуального окружения..."
    source venv/bin/activate
fi

echo "Запуск GetGems WebApp..."
python3 main.py