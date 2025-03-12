from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    full_name = Column(String)
    company_name = Column(String)
    is_registered = Column(Boolean, default=False)
    is_manager = Column(Boolean, default=False)
    
    appointments = relationship("Appointment", back_populates="user")

class Station(Base):
    __tablename__ = 'stations'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String)
    slots_per_hour = Column(Integer, default=2)
    category = Column(String, nullable=False, default='B')  # Категория станции (B, C, D)
    
    appointments = relationship("Appointment", back_populates="station")

class Appointment(Base):
    __tablename__ = 'appointments'
    
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey('stations.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    client_name = Column(String, nullable=False)
    car_number = Column(String, nullable=False)
    client_phone = Column(String, nullable=False)
    appointment_time = Column(DateTime, nullable=False)
    
    station = relationship("Station", back_populates="appointments")
    user = relationship("User", back_populates="appointments") 