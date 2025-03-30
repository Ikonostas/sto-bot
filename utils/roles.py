from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from database.models import UserRole
from sqlalchemy.orm import Session
from database.database import get_db
from utils.logger import logger

async def get_user_role(telegram_id: int, db: Session = None):
    """Получение роли пользователя по telegram_id"""
    from handlers.user_handler import get_agent_by_telegram_id
    
    close_db = False
    if db is None:
        db = next(get_db())
        close_db = True
    
    try:
        agent = get_agent_by_telegram_id(db, telegram_id)
        if agent:
            return agent.role
        return None
    finally:
        if close_db:
            db.close()

def admin_required(func):
    """Декоратор для проверки прав администратора"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        db = next(get_db())
        
        try:
            role = await get_user_role(user_id, db)
            
            if role == UserRole.ADMIN:
                return await func(update, context, *args, **kwargs)
            else:
                logger.warning(f"Access denied: user {user_id} tried to access admin function")
                await update.message.reply_text("У вас нет доступа к этой функции.")
                return None
        finally:
            db.close()
    
    return wrapper

def registered_required(func):
    """Декоратор для проверки регистрации пользователя"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        db = next(get_db())
        
        try:
            role = await get_user_role(user_id, db)
            
            if role:
                return await func(update, context, *args, **kwargs)
            else:
                logger.warning(f"Access denied: user {user_id} is not registered")
                await update.message.reply_text(
                    "Вы не зарегистрированы. Используйте команду /register для регистрации."
                )
                return None
        finally:
            db.close()
    
    return wrapper 