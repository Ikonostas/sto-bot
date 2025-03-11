from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import REGISTRATION_CODE
from database.db import SessionLocal
from database.models import User

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса регистрации"""
    user = update.effective_user
    db = SessionLocal()
    db_user = db.query(User).filter(User.telegram_id == user.id).first()
    
    if db_user and db_user.is_registered:
        await update.message.reply_text(
            f"Вы уже зарегистрированы как {db_user.full_name} из компании {db_user.company_name}."
        )
        db.close()
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Начинаем регистрацию.\n"
        "Пожалуйста, введите ваше ФИО:"
    )
    db.close()
    return REGISTRATION_FULLNAME

async def registration_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ФИО"""
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text("Введите название вашей компании:")
    return REGISTRATION_COMPANY

async def registration_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия компании"""
    context.user_data['company_name'] = update.message.text
    await update.message.reply_text(
        "Для завершения регистрации введите кодовое слово:"
    )
    return REGISTRATION_CODE

async def registration_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка кодового слова и завершение регистрации"""
    if update.message.text != REGISTRATION_CODE:
        await update.message.reply_text(
            "Неверное кодовое слово. Попробуйте еще раз:"
        )
        return REGISTRATION_CODE
    
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
    user.full_name = context.user_data['full_name']
    user.company_name = context.user_data['company_name']
    user.is_registered = True
    db.commit()
    
    await update.message.reply_text(
        f"Регистрация успешно завершена!\n"
        f"ФИО: {user.full_name}\n"
        f"Компания: {user.company_name}"
    )
    
    db.close()
    # Показываем главное меню
    from handlers.common import start
    return await start(update, context) 