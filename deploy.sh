#!/bin/bash
# Скрипт быстрой настройки на Linux сервере
cd "$(dirname "$0")"

echo "=== Настройка бота на сервере ==="
if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения Python..."
    python3 -m venv venv || apt update && apt install -y python3-venv python3-pip && python3 -m venv venv
fi

echo "Установка зависимостей..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "=== Готово! ==="
echo "Для ручного запуска: ./venv/bin/python bot.py"
