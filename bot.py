import os
import logging
from telegram import Update
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, 
                         MessageHandler, filters, ConversationHandler, ContextTypes)

# Импорт конфигурации
from config import BOT_TOKEN, CHOOSING, REGISTRATION_FULLNAME, REGISTRATION_COMPANY, REGISTRATION_CODE_STATE
from config import ENTER_CLIENT_NAME, ENTER_CAR_NUMBER, ENTER_PHONE, CHOOSE_STATION, CHOOSE_DATE, CHOOSE_TIME

# Импорт обработчиков
from handlers.common import start, back_to_menu
from handlers.registration import register, registration_fullname, registration_company, registration_code
from handlers.appointments import (new_appointment, enter_client_name, enter_car_number, enter_phone,
                                choose_station, choose_date, handle_unavailable_time, save_appointment,
                                my_appointments)
from handlers.manager import manage_appointments, cancel_appointment

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    """Основная функция запуска бота"""
    # Проверяем наличие токена
    if not BOT_TOKEN:
        logging.error("Не найден токен бота в переменных окружения")
        return

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Создаем отдельный обработчик для регистрации
    registration_handler = ConversationHandler(
        entry_points=[CommandHandler('register', register)],
        states={
            REGISTRATION_FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration_fullname)],
            REGISTRATION_COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration_company)],
            REGISTRATION_CODE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration_code)],
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )

    # Создаем основной обработчик для управления записями
    appointment_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(new_appointment, pattern='^new_appointment$'),
                CallbackQueryHandler(my_appointments, pattern='^my_appointments$'),
                CallbackQueryHandler(manage_appointments, pattern='^manage_appointments$'),
                CallbackQueryHandler(cancel_appointment, pattern='^cancel_\\d+$'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$')
            ],
            ENTER_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_client_name)],
            ENTER_CAR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_car_number)],
            ENTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)],
            CHOOSE_STATION: [CallbackQueryHandler(choose_station, pattern='^station_')],
            CHOOSE_DATE: [CallbackQueryHandler(choose_date, pattern='^date_')],
            CHOOSE_TIME: [
                CallbackQueryHandler(save_appointment, pattern='^time_'),
                CallbackQueryHandler(handle_unavailable_time, pattern='^unavailable$'),
                CallbackQueryHandler(choose_date, pattern='^back_to_date$'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$')
            ]
        },
        fallbacks=[
            CommandHandler('start', start),
            CommandHandler('register', register),
            MessageHandler(filters.COMMAND, start)
        ],
        allow_reentry=True
    )

    # Добавляем обработчики
    application.add_handler(registration_handler)
    application.add_handler(appointment_handler)

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 