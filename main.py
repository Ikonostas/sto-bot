import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler
from config import settings
from utils.logger import logger
from database.database import engine
from database.models import Base
from handlers.registration import get_registration_handler
from handlers.booking import get_booking_handler
from handlers.menu import start_command, handle_menu_callback
from handlers.admin import (
    process_payment_amount, process_payment_comment, process_change_commission,
    start_add_payment, start_change_commission,
    PAYMENT_AMOUNT, PAYMENT_COMMENT, CHANGE_COMMISSION, AGENT_ACTION
)
from handlers.admin_approvals import get_approval_handler
from handlers.my_bookings import get_booking_cancel_handler
from utils.roles import get_user_role
from database.database import get_db

async def start(update, context):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")
    
    # Проверяем, зарегистрирован ли пользователь
    db = next(get_db())
    try:
        role = await get_user_role(user_id, db)
        
        if role:
            # Пользователь зарегистрирован, показываем главное меню
            await start_command(update, context)
        else:
            # Пользователь не зарегистрирован, предлагаем регистрацию
            await update.message.reply_text(
                "Добро пожаловать в бот для записи на СТО!\n\n"
                "Вы еще не зарегистрированы. Используйте команду /register для регистрации."
            )
    finally:
        db.close()

async def handle_message(update, context):
    """Обработчик неизвестных сообщений"""
    logger.warning(f"Unknown message from user {update.effective_user.id}")
    await update.message.reply_text(
        "Извините, я не понимаю эту команду. Используйте /start для начала работы."
    )

def main():
    """Основная функция запуска бота"""
    # Создаем таблицы в базе данных
    Base.metadata.create_all(bind=engine)
    
    # Инициализируем бота
    application = Application.builder().token(settings.BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    
    # Добавляем обработчик регистрации
    application.add_handler(get_registration_handler())
    
    # Добавляем обработчик для бронирования
    application.add_handler(get_booking_handler())
    
    # Создаем ConversationHandler для админ-функций
    admin_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_payment, pattern=r'^add_payment_\d+$'),
            CallbackQueryHandler(start_change_commission, pattern=r'^change_commission_\d+$')
        ],
        states={
            PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_payment_amount)],
            PAYMENT_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_payment_comment)],
            CHANGE_COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_change_commission)],
            AGENT_ACTION: [CallbackQueryHandler(handle_menu_callback)]
        },
        fallbacks=[],
        map_to_parent={
            # Если диалог завершится, возвращаемся к обработчику меню
            ConversationHandler.END: CallbackQueryHandler(handle_menu_callback)
        },
        name="admin_functions"
    )
    
    # Добавляем обработчик для админ-функций
    application.add_handler(admin_handler)
    
    # Добавляем обработчик для согласований
    application.add_handler(get_approval_handler())
    
    # Добавляем обработчик для отмены карточек ТО
    application.add_handler(get_booking_cancel_handler())
    
    # Добавляем обработчик для кнопок меню
    application.add_handler(CallbackQueryHandler(handle_menu_callback))
    
    # Добавляем обработчик для неизвестных сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    main() 