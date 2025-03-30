from sqlalchemy.orm import Session
from database.models import Agent, UserRole
from config import settings
from utils.logger import logger

def get_agent_by_telegram_id(db: Session, telegram_id: int):
    """Получение агента по его telegram_id"""
    return db.query(Agent).filter(Agent.telegram_id == telegram_id).first()

def create_agent(
    db: Session, 
    telegram_id: int, 
    full_name: str, 
    phone: str, 
    company: str, 
    code_word: str
):
    """Создание нового агента"""
    # Проверяем кодовое слово
    if code_word != settings.REGISTRATION_CODE:
        logger.warning(f"Registration failed: wrong code word for user {telegram_id}")
        return False, "Неверное кодовое слово"
    
    # Проверяем, зарегистрирован ли пользователь
    existing_agent = get_agent_by_telegram_id(db, telegram_id)
    if existing_agent:
        logger.warning(f"Registration failed: user {telegram_id} already registered")
        return False, "Вы уже зарегистрированы"
    
    # Определяем роль пользователя
    role = UserRole.AGENT
    if telegram_id in settings.ADMIN_IDS:
        role = UserRole.ADMIN
        logger.info(f"User {telegram_id} registered as admin")
    
    # Создаем нового агента
    agent = Agent(
        telegram_id=telegram_id,
        full_name=full_name,
        phone=phone,
        company=company,
        role=role,
        commission_rate=0.0
    )
    
    try:
        db.add(agent)
        db.commit()
        db.refresh(agent)
        logger.info(f"User {telegram_id} registered successfully")
        return True, "Регистрация успешно завершена"
    except Exception as e:
        db.rollback()
        logger.error(f"Error during registration: {e}")
        return False, "Ошибка при регистрации"

def get_all_agents(db: Session, limit: int = 30, skip: int = 0):
    """Получение списка всех агентов"""
    return db.query(Agent).offset(skip).limit(limit).all()

def update_agent_commission(db: Session, agent_id: int, new_commission_rate: float):
    """Обновление комиссии агента"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return False, "Агент не найден"
    
    try:
        agent.commission_rate = new_commission_rate
        db.commit()
        return True, f"Комиссия агента обновлена: {new_commission_rate}%"
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating agent commission: {e}")
        return False, "Ошибка при обновлении комиссии" 