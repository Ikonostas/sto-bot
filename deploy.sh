#!/bin/bash

# Остановка и удаление существующих контейнеров
docker-compose down

# Сборка и запуск контейнеров
docker-compose up -d --build

# Применение миграций базы данных
docker-compose exec app python -m database.migrations

# Проверка статуса контейнеров
docker-compose ps 