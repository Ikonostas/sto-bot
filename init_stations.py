from database.db import SessionLocal, engine
from database.models import Base, Station

def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Проверяем, есть ли уже станции в базе
    if db.query(Station).count() == 0:
        # Добавляем тестовые станции
        stations = [
            Station(name="СТО №1", address="ул. Первая, 1", slots_per_hour=2),
            Station(name="СТО №2", address="ул. Вторая, 2", slots_per_hour=3),
            Station(name="СТО №3", address="ул. Третья, 3", slots_per_hour=2)
        ]
        
        db.add_all(stations)
        db.commit()
        print("Тестовые станции успешно добавлены")
    else:
        print("Станции уже существуют в базе данных")
    
    db.close()

if __name__ == "__main__":
    init_db() 