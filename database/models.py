from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    AGENT = "agent"
    ADMIN = "admin"

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    full_name = Column(String)
    phone = Column(String)
    company = Column(String)
    role = Column(Enum(UserRole), default=UserRole.AGENT)
    commission_rate = Column(Float, default=0.0)
    messenger_link = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    to_cards = relationship("TOCard", back_populates="agent")
    payments = relationship("Payment", back_populates="agent")
    calculations = relationship("Calculation", back_populates="agent")

class TOCard(Base):
    __tablename__ = "to_cards"
    
    id = Column(Integer, primary_key=True)
    card_number = Column(String, unique=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    category = Column(String)  # B, C, E
    sto_name = Column(String)
    has_defects = Column(Boolean, default=False)
    defect_type = Column(String, nullable=True)  # minor, major
    defect_description = Column(Text, nullable=True)
    appointment_time = Column(DateTime)
    client_name = Column(String)
    car_number = Column(String)
    vin_number = Column(String)
    client_phone = Column(String)
    total_price = Column(Float)
    status = Column(String, default="pending")  # pending, approved, rejected, cancelled
    admin_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    agent = relationship("Agent", back_populates="to_cards")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    amount = Column(Float)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    agent = relationship("Agent", back_populates="payments")

class Calculation(Base):
    __tablename__ = "calculations"
    
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    amount = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    agent = relationship("Agent", back_populates="calculations") 