from database.db import SessionLocal, engine
from database.models import Base, Station

def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Проверяем, есть ли уже станции в базе
    if db.query(Station).count() == 0:
        # Добавляем станции для разных категорий
        stations = [
            # Станции для категории B
            Station(name="СТО №1 (кат. B)", address="ул. Первая, 1", slots_per_hour=2, category='B'),
            Station(name="СТО №2 (кат. B)", address="ул. Вторая, 2", slots_per_hour=3, category='B'),
            Station(name="СТО №3 (кат. B)", address="ул. Третья, 3", slots_per_hour=2, category='B'),
            
            # Станции для категории C
            Station(name="СТО №4 (кат. C)", address="ул. Грузовая, 1", slots_per_hour=2, category='C'),
            Station(name="СТО №5 (кат. C)", address="ул. Грузовая, 2", slots_per_hour=2, category='C'),
            
            # Станции для категории D
            Station(name="СТО №6 (кат. D)", address="ул. Автобусная, 1", slots_per_hour=1, category='D'),
            Station(name="СТО №7 (кат. D)", address="ул. Автобусная, 2", slots_per_hour=1, category='D')
        ]
        
        db.add_all(stations)
        db.commit()
        print("Станции для всех категорий успешно добавлены")
    else:
        print("Станции уже существуют в базе данных")
    
    db.close()

if __name__ == "__main__":
    init_db() 