from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Station

# Создаем подключение к базе данных
engine = create_engine('sqlite:///techservice.db')
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Список станций ТО
stations = [
    {"name": "СТО №1", "address": "ул. Первая, 1", "slots_per_hour": 2},
    {"name": "СТО №2", "address": "ул. Вторая, 2", "slots_per_hour": 2},
    {"name": "СТО №3", "address": "ул. Третья, 3", "slots_per_hour": 2},
    {"name": "СТО №4", "address": "ул. Четвертая, 4", "slots_per_hour": 2},
    {"name": "СТО №5", "address": "ул. Пятая, 5", "slots_per_hour": 2},
    {"name": "СТО №6", "address": "ул. Шестая, 6", "slots_per_hour": 2},
    {"name": "СТО №7", "address": "ул. Седьмая, 7", "slots_per_hour": 2},
    {"name": "СТО №8", "address": "ул. Восьмая, 8", "slots_per_hour": 2},
    {"name": "СТО №9", "address": "ул. Девятая, 9", "slots_per_hour": 2},
    {"name": "СТО №10", "address": "ул. Десятая, 10", "slots_per_hour": 2},
]

# Добавляем станции в базу данных
for station_data in stations:
    station = Station(**station_data)
    db.add(station)

db.commit()
print("Станции ТО успешно добавлены в базу данных!") 