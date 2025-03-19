from pydantic_settings import BaseSettings
from typing import List
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str
    
    # Database
    DATABASE_URL: str
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Application
    ADMIN_IDS: List[int]
    
    class Config:
        env_file = ".env"
        
    def validate(self):
        """Проверка конфигурации"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен")
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL не установлен")
        if not self.ADMIN_IDS:
            raise ValueError("ADMIN_IDS не установлен")

# Создаем экземпляр конфигурации
settings = Settings()
settings.validate()

# Настройки бота
BOT_TOKEN = settings.BOT_TOKEN
REGISTRATION_CODE = "admin"

# Настройки базы данных
DATABASE_URL = settings.DATABASE_URL

# Настройки временных слотов
WORKING_HOURS_START = 9  # Начало рабочего дня
WORKING_HOURS_END = 18   # Конец рабочего дня
SLOT_DURATION = 30       # Длительность слота в минутах
DAYS_AHEAD = 7          # Количество дней для предварительной записи

# Состояния разговора
(CHOOSING, REGISTRATION_FULLNAME, REGISTRATION_COMPANY, REGISTRATION_CODE_STATE, 
 ENTER_CLIENT_NAME, ENTER_CAR_NUMBER, ENTER_PHONE, CHOOSE_STATION, 
 CHOOSE_DATE, CHOOSE_TIME) = range(10)

# Константы для состояний
CHOOSING = "CHOOSING"
REGISTRATION_FULLNAME = "REGISTRATION_FULLNAME"
REGISTRATION_COMPANY = "REGISTRATION_COMPANY"
REGISTRATION_CODE = "REGISTRATION_CODE"
REGISTRATION_CODE_STATE = "REGISTRATION_CODE_STATE"

# Константы для сообщений
REGISTRATION_CODE = "Введите код подтверждения:"
REGISTRATION_COMPANY = "Введите название вашей компании:"
REGISTRATION_FULLNAME = "Введите ваше ФИО:" 