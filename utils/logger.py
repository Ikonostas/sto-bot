import sys
from loguru import logger
from pathlib import Path
from config import settings

# Создаем директорию для логов если её нет
log_path = Path(settings.LOG_FILE)
log_path.parent.mkdir(parents=True, exist_ok=True)

# Настраиваем логирование
logger.remove()  # Удаляем стандартный обработчик

# Добавляем обработчик для консоли
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL
)

# Добавляем обработчик для файла
logger.add(
    settings.LOG_FILE,
    rotation="300 MB",
    retention="10 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO"
) 