@echo off
echo Starting GetGems WebApp...
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python не найден! Установите Python 3.8 или выше.
    pause
    exit /b 1
)

REM Проверка зависимостей
if not exist "requirements.txt" (
    echo Файл requirements.txt не найден!
    pause
    exit /b 1
)

REM Проверка .env файла
if not exist ".env" (
    echo Файл .env не найден! Создайте его по образцу из README.md
    pause
    exit /b 1
)

echo Запуск GetGems WebApp...
python main.py

pause