import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import REGISTRATION_CODE, REGISTRATION_FULLNAME, REGISTRATION_COMPANY, REGISTRATION_CODE_STATE
from database.db import SessionLocal
from database.models import User

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса регистрации"""
    db = SessionLocal()
    try:
        user = update.effective_user
        db_user = db.query(User).filter(User.telegram_id == user.id).first()
        
        # Если пользователя нет, создаем его
        if not db_user:
            db_user = User(telegram_id=user.id, username=user.username)
            db.add(db_user)
            db.commit()
        elif db_user.is_registered:
            await update.message.reply_text(
                f"Вы уже зарегистрированы как {db_user.full_name} из компании {db_user.company_name}."
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            "Начинаем регистрацию.\n"
            "Пожалуйста, введите ваше ФИО:"
        )
        return REGISTRATION_FULLNAME
    except Exception as e:
        logging.error(f"Ошибка в register: {e}")
        await update.message.reply_text(
            "Произошла ошибка при начале регистрации. Пожалуйста, попробуйте позже."
        )
        return ConversationHandler.END
    finally:
        db.close()

async def registration_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ФИО"""
    try:
        if not update.message.text or len(update.message.text.strip()) < 3:
            await update.message.reply_text(
                "ФИО должно содержать не менее 3 символов. Пожалуйста, введите корректное ФИО:"
            )
            return REGISTRATION_FULLNAME
            
        context.user_data['full_name'] = update.message.text.strip()
        await update.message.reply_text("Введите название вашей компании:")
        return REGISTRATION_COMPANY
    except Exception as e:
        logging.error(f"Ошибка в registration_fullname: {e}")
        await update.message.reply_text(
            "Произошла ошибка при сохранении ФИО. Пожалуйста, попробуйте позже или используйте /start"
        )
        return ConversationHandler.END

async def registration_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия компании"""
    try:
        if not update.message.text or len(update.message.text.strip()) < 2:
            await update.message.reply_text(
                "Название компании должно содержать не менее 2 символов. Пожалуйста, введите корректное название:"
            )
            return REGISTRATION_COMPANY
            
        context.user_data['company_name'] = update.message.text.strip()
        await update.message.reply_text(
            "Для завершения регистрации введите кодовое слово.\n"
            "Важно: введите слово в точности как указано, с учетом регистра букв."
        )
        return REGISTRATION_CODE_STATE
    except Exception as e:
        logging.error(f"Ошибка в registration_company: {e}")
        await update.message.reply_text(
            "Произошла ошибка при сохранении названия компании. Пожалуйста, попробуйте позже или используйте /start"
        )
        return ConversationHandler.END

async def registration_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка кодового слова и завершение регистрации"""
    db = SessionLocal()
    try:
        # Убираем пробелы, но сохраняем регистр
        entered_code = update.message.text.strip()
        logging.info(f"Проверка кодового слова. Введено: '{entered_code}', Ожидается: '{REGISTRATION_CODE}'")
        
        if entered_code != REGISTRATION_CODE:
            logging.warning(f"Неверное кодовое слово от пользователя {update.effective_user.id}. Введено: '{entered_code}'")
            await update.message.reply_text(
                "Неверное кодовое слово. Убедитесь, что вы вводите слово точно как указано, с учетом регистра. Попробуйте еще раз:"
            )
            return REGISTRATION_CODE_STATE
        
        if 'full_name' not in context.user_data or 'company_name' not in context.user_data:
            raise ValueError("Отсутствуют необходимые данные для регистрации")
        
        user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
        if not user:
            raise ValueError("Пользователь не найден")
            
        user.full_name = context.user_data['full_name']
        user.company_name = context.user_data['company_name']
        user.is_registered = True
        db.commit()
        
        await update.message.reply_text(
            f"Регистрация успешно завершена!\n"
            f"ФИО: {user.full_name}\n"
            f"Компания: {user.company_name}"
        )
        
        # Показываем главное меню
        from handlers.common import start
        return await start(update, context)
        
    except ValueError as e:
        logging.error(f"Ошибка валидации в registration_code: {e}")
        await update.message.reply_text(
            f"Ошибка при регистрации: {str(e)}. Пожалуйста, начните регистрацию заново с помощью /register"
        )
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Ошибка в registration_code: {e}")
        await update.message.reply_text(
            "Произошла ошибка при завершении регистрации. Пожалуйста, попробуйте позже или используйте /start"
        )
        return ConversationHandler.END
    finally:
        db.close() 