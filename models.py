from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Station(Base):
    __tablename__ = 'stations'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String)
    slots_per_hour = Column(Integer, default=2)
    appointments = relationship("Appointment", back_populates="station")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    full_name = Column(String)
    company_name = Column(String)
    is_registered = Column(Boolean, default=False)
    is_manager = Column(Boolean, default=False)
    appointments = relationship("Appointment", back_populates="user")

class Appointment(Base):
    __tablename__ = 'appointments'
    
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey('stations.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    car_number = Column(String, nullable=False)
    client_name = Column(String, nullable=False)
    client_phone = Column(String)
    appointment_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    station = relationship("Station", back_populates="appointments")
    user = relationship("User", back_populates="appointments")

# Создание базы данных
engine = create_engine('sqlite:///techservice.db')
Base.metadata.create_all(engine) 