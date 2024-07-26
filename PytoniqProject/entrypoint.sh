#!/bin/sh

# Запуск основной программы
celery -A worker.celery_app worker --loglevel=info
celery -A worker.celery_app flower
python __main__.py

# Удержание контейнера активным
exec sleep infinity

