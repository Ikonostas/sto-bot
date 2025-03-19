#!/usr/bin/env python3
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from utils.logger import logger_setup
from config import settings

def main():
    """Очистка старых логов"""
    try:
        logger_setup.cleanup_old_logs(days=settings.LOG_RETENTION_DAYS)
        print(f"Логи старше {settings.LOG_RETENTION_DAYS} дней успешно удалены")
    except Exception as e:
        print(f"Ошибка при очистке логов: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 