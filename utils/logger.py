import logging
import sys
from pathlib import Path
from config import settings

# Создаем директорию для логов если её нет
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Настраиваем логгер
logger = logging.getLogger("sto_bot")
logger.setLevel(settings.LOG_LEVEL)

# Форматтер для логов
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Хендлер для файла
file_handler = logging.FileHandler(
    log_dir / "bot.log",
    encoding='utf-8'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Хендлер для консоли
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def get_logger():
    """Получить настроенный логгер"""
    return logger 