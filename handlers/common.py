import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import SessionLocal
from database.models import User
from config import CHOOSING

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало взаимодействия с ботом"""
    db = SessionLocal()
    try:
        user = update.effective_user
        logging.info(f"Запуск функции start для пользователя {user.id}")
        
        # Проверяем, существует ли пользователь
        db_user = db.query(User).filter(User.telegram_id == user.id).first()
        logging.info(f"Найден пользователь в БД: {db_user is not None}")
        
        if not db_user:
            logging.info("Создаем нового пользователя")
            db_user = User(telegram_id=user.id, username=user.username)
            db.add(db_user)
            db.commit()
        
        logging.info(f"Статус регистрации пользователя: {db_user.is_registered}")
        if not db_user.is_registered:
            message = ("Добро пожаловать! Для использования бота необходимо зарегистрироваться.\n"
                      "Используйте команду /register для начала регистрации.")
            logging.info("Отправляем сообщение о необходимости регистрации")
            if update.callback_query:
                await update.callback_query.message.edit_text(message)
            else:
                await update.message.reply_text(message)
            return ConversationHandler.END
        
        # Очищаем данные предыдущего состояния
        context.user_data.clear()
        
        keyboard = [
            [InlineKeyboardButton("🚗 Записать на ТО (кат. B)", callback_data='new_appointment_B')],
            [InlineKeyboardButton("🚛 Записать на ТО (кат. C)", callback_data='new_appointment_C')],
            [InlineKeyboardButton("🚌 Записать на ТО (кат. D)", callback_data='new_appointment_D')],
            [InlineKeyboardButton("📋 Мои записи", callback_data='my_appointments')]
        ]
        if db_user.is_manager:
            keyboard.append([InlineKeyboardButton("⚙️ Управление записями", callback_data='manage_appointments')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = f"Здравствуйте, {db_user.full_name}! Выберите действие:"
        
        logging.info("Отправляем главное меню")
        if update.callback_query:
            await update.callback_query.message.edit_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, reply_markup=reply_markup)
        
        return CHOOSING
        
    except Exception as e:
        logging.error(f"Ошибка в start: {e}")
        message = "Произошла ошибка. Пожалуйста, попробуйте позже или обратитесь к администратору."
        if update.callback_query:
            await update.callback_query.message.edit_text(message)
        else:
            await update.message.reply_text(message)
        return ConversationHandler.END
    finally:
        db.close()

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    try:
        query = update.callback_query
        await query.answer()
        return await start(update, context)
    except Exception as e:
        logging.error(f"Ошибка в back_to_menu: {e}")
        if update.callback_query:
            await update.callback_query.message.edit_text(
                "Произошла ошибка при возврате в меню. Пожалуйста, используйте команду /start"
            )
        return ConversationHandler.END 