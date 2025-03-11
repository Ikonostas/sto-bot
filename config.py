import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройки бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
REGISTRATION_CODE = "admin"

# Настройки базы данных
DATABASE_URL = 'sqlite:///techservice.db'

# Настройки временных слотов
WORKING_HOURS_START = 9  # Начало рабочего дня
WORKING_HOURS_END = 18   # Конец рабочего дня
SLOT_DURATION = 30       # Длительность слота в минутах
DAYS_AHEAD = 7          # Количество дней для предварительной записи

# Состояния разговора
(CHOOSING, REGISTRATION_FULLNAME, REGISTRATION_COMPANY, REGISTRATION_CODE, 
 ENTER_CLIENT_NAME, ENTER_CAR_NUMBER, ENTER_PHONE, CHOOSE_STATION, 
 CHOOSE_DATE, CHOOSE_TIME) = range(10) 