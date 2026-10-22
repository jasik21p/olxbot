@echo off
chcp 65001 > nul
echo ========================================================
echo       Запуск Telegram-бота мониторинга авто OLX.uz
echo ========================================================
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ОШИБКА] Виртуальное окружение venv не найдено!
    echo Создаю виртуальное окружение...
    python -m venv venv
    venv\Scripts\pip.exe install -r requirements.txt
)

echo [ИНФО] Запуск бота...
venv\Scripts\python.exe bot.py
pause
