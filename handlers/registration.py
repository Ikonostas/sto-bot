from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from utils.logger import logger
from database.database import get_db
from handlers.user_handler import create_agent, get_agent_by_telegram_id

# Константы для состояний разговора
FULL_NAME, PHONE, COMPANY, CODE_WORD = range(4)

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса регистрации"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started registration process")
    
    # Проверяем, не зарегистрирован ли пользователь уже
    db = next(get_db())
    try:
        agent = get_agent_by_telegram_id(db, user_id)
        if agent:
            await update.message.reply_text(
                "Вы уже зарегистрированы. Используйте /start для доступа к главному меню."
            )
            return ConversationHandler.END
    finally:
        db.close()
    
    # Начинаем процесс регистрации
    await update.message.reply_text(
        "Добро пожаловать в процесс регистрации!\n\n"
        "Пожалуйста, введите ваше полное имя (ФИО):"
    )
    
    return FULL_NAME

async def full_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода ФИО"""
    full_name = update.message.text
    context.user_data["full_name"] = full_name
    logger.debug(f"User {update.effective_user.id} entered full name: {full_name}")
    
    # Запрашиваем номер телефона
    keyboard = [[KeyboardButton("Поделиться номером", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Спасибо! Теперь введите ваш номер телефона или нажмите кнопку 'Поделиться номером':",
        reply_markup=reply_markup
    )
    
    return PHONE

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода номера телефона"""
    user_id = update.effective_user.id
    
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
    
    context.user_data["phone"] = phone
    logger.debug(f"User {user_id} entered phone: {phone}")
    
    # Запрашиваем компанию
    await update.message.reply_text(
        "Отлично! В какой компании вы работаете?",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return COMPANY

async def company_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода названия компании"""
    company = update.message.text
    context.user_data["company"] = company
    logger.debug(f"User {update.effective_user.id} entered company: {company}")
    
    # Запрашиваем кодовое слово
    await update.message.reply_text(
        "Осталось немного! Пожалуйста, введите кодовое слово для завершения регистрации:"
    )
    
    return CODE_WORD

async def code_word_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода кодового слова и завершение регистрации"""
    user_id = update.effective_user.id
    code_word = update.message.text
    logger.debug(f"User {user_id} entered code word")
    
    # Создаем нового агента
    db = next(get_db())
    try:
        success, message = create_agent(
            db=db,
            telegram_id=user_id,
            full_name=context.user_data.get("full_name", ""),
            phone=context.user_data.get("phone", ""),
            company=context.user_data.get("company", ""),
            code_word=code_word
        )
        
        if success:
            await update.message.reply_text(
                f"{message}\n\nТеперь вы можете использовать /start для доступа к меню бота."
            )
            # Очищаем данные пользователя
            context.user_data.clear()
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                f"{message}\n\nПожалуйста, попробуйте еще раз ввести кодовое слово:"
            )
            return CODE_WORD
    finally:
        db.close()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена процесса регистрации"""
    logger.info(f"User {update.effective_user.id} cancelled registration")
    
    await update.message.reply_text(
        "Регистрация отменена. Вы можете начать снова с помощью команды /register."
    )
    
    # Очищаем данные пользователя
    context.user_data.clear()
    return ConversationHandler.END

def get_registration_handler():
    """Создание обработчика разговора для регистрации"""
    return ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_handler)],
            PHONE: [
                MessageHandler(filters.CONTACT, phone_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler)
            ],
            COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, company_handler)],
            CODE_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, code_word_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ) 