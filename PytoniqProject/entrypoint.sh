#!/bin/sh

# Запуск Celery в фоновом режиме
celery -A worker.celery_app worker --loglevel=info &

# Запуск Flower в фоновом режиме
celery -A worker.celery_app flower &

# Дождаться, пока Celery и Flower запустятся, можно использовать sleep или проверку состояния.
# Запуск основной программы
python __main__.py

# Удержание контейнера активным
exec sleep infinity
