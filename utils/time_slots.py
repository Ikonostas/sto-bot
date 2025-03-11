from datetime import datetime, timedelta
from sqlalchemy import and_
from database.models import Appointment
from config import WORKING_HOURS_START, WORKING_HOURS_END, SLOT_DURATION, DAYS_AHEAD

def get_available_dates():
    """Получение списка доступных дат для записи"""
    return [(datetime.now() + timedelta(days=x)).date() for x in range(DAYS_AHEAD)]

def is_time_slot_available(db_session, station_id: int, appointment_time: datetime) -> bool:
    """Проверяет, доступно ли время для записи на станцию"""
    # Получаем количество слотов в час для станции
    station = db_session.query(Station).filter(Station.id == station_id).first()
    if not station:
        return False
    
    # Проверяем существующие записи на конкретное время
    existing_appointments = db_session.query(Appointment).filter(
        and_(
            Appointment.station_id == station_id,
            Appointment.appointment_time == appointment_time
        )
    ).count()
    
    # Если есть хотя бы одна запись на это время, слот занят
    if existing_appointments > 0:
        return False
    
    # Проверяем количество записей в текущий час
    start_time = appointment_time.replace(minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    hour_appointments = db_session.query(Appointment).filter(
        and_(
            Appointment.station_id == station_id,
            Appointment.appointment_time >= start_time,
            Appointment.appointment_time < end_time
        )
    ).count()
    
    return hour_appointments < station.slots_per_hour

def get_available_time_slots(db_session, station_id: int, selected_date: datetime.date):
    """Получение списка доступных временных слотов"""
    times = []
    current_time = datetime.now()
    
    for hour in range(WORKING_HOURS_START, WORKING_HOURS_END):
        for minute in range(0, 60, SLOT_DURATION):
            time_str = f"{hour:02d}:{minute:02d}"
            check_time = datetime.combine(selected_date, 
                                        datetime.strptime(time_str, "%H:%M").time())
            
            # Пропускаем прошедшее время
            if check_time < current_time:
                times.append((time_str, False))
                continue
            
            is_available = is_time_slot_available(db_session, station_id, check_time)
            times.append((time_str, is_available))
    
    return times 