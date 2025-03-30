# Руководство по разработке STO Bot

## Требования к окружению
- Python 3.8+
- PostgreSQL 12+


## Настройка окружения разработки

### 1. Установка зависимостей
```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows

# Установка зависимостей
pip install -r requirements-dev.txt
```

### 2. Настройка базы данных
```sql
CREATE DATABASE sto_bot_dev;
CREATE DATABASE sto_bot_test;
```

### 3. Настройка переменных окружения
Создайте файл `.env` в корне проекта:
```env
DEBUG=True

```

## Структура кода



## Стиль кода
- Следуйте PEP 8
- Используйте типизацию Python
- Документируйте все функции и классы
- Пишите тесты для новой функциональности

## Тестирование
```bash
# Запуск всех тестов
pytest

# Запуск конкретного теста
pytest tests/test_orders.py

# Запуск с покрытием
pytest --cov=sto_bot tests/
```

## Логирование
Используйте встроенный модуль logging:
```python
import logging

logger = logging.getLogger(__name__)
logger.info("Сообщение")
logger.error("Ошибка", exc_info=True)
```

## Git Flow
1. Создавайте ветки от `master`
2. Названия веток: `feature/`, `bugfix/`, `hotfix/`
3. Коммиты должны быть атомарными
4. Используйте conventional commits

## Деплой (пока не надо)
1. Создайте тег
2. Запустите CI/CD пайплайн
3. Проверьте логи после деплоя
4. Проведите smoke-тесты 