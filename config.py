from pydantic_settings import BaseSettings
from typing import List, Dict
from pydantic import BaseModel
import json

class STOSettings(BaseModel):
    name: str
    address: str
    categories: List[str]
    prices: Dict[str, float]
    working_hours: Dict[str, str]
    time_slot: int  # в минутах
    defect_prices: Dict[str, float]

class Settings(BaseSettings):
    # Telegram settings
    BOT_TOKEN: str
    ADMIN_IDS: List[int]
    
    # Database settings
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    
    # Registration settings
    REGISTRATION_CODE: str
    
    # STO settings
    STO_STATIONS: Dict[str, STOSettings]
    
    # Logging settings
    LOG_LEVEL: str = "DEBUG"
    LOG_FILE: str = "logs/bot.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        json_loads = json.loads
        json_dumps = json.dumps

settings = Settings() 