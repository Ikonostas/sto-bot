import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from models import Base, Station, User, Appointment

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния разговора
(CHOOSING, REGISTRATION_FULLNAME, REGISTRATION_COMPANY, REGISTRATION_CODE, 
 ENTER_CLIENT_NAME, ENTER_CAR_NUMBER, ENTER_PHONE, CHOOSE_STATION, 
 CHOOSE_DATE, CHOOSE_TIME) = range(10)

# Подключение к базе данных
engine = create_engine('sqlite:///techservice.db')
SessionLocal = sessionmaker(bind=engine)

# Кодовое слово для регистрации
REGISTRATION_CODE = "admin"

# Импорт конфигурации
from config import BOT_TOKEN

# Импорт обработчиков
from handlers.common import start, back_to_menu
from handlers.registration import register, registration_fullname, registration_company, registration_code
from handlers.appointments import (new_appointment, enter_client_name, enter_car_number, enter_phone,
                                choose_station, choose_date, handle_unavailable_time, save_appointment,
                                my_appointments)
from handlers.manager import manage_appointments, cancel_appointment

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало взаимодействия с ботом"""
    user = update.effective_user
    db = SessionLocal()
    
    # Проверяем, существует ли пользователь
    db_user = db.query(User).filter(User.telegram_id == user.id).first()
    if not db_user:
        db_user = User(telegram_id=user.id, username=user.username)
        db.add(db_user)
        db.commit()
    
    if not db_user.is_registered:
        await update.message.reply_text(
            "Добро пожаловать! Для использования бота необходимо зарегистрироваться.\n"
            "Используйте команду /register для начала регистрации."
        )
        return ConversationHandler.END
    
    # Очищаем данные предыдущего состояния
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("Записать на ТО", callback_data='new_appointment')],
        [InlineKeyboardButton("Мои записи", callback_data='my_appointments')]
    ]
    if db_user.is_manager:
        keyboard.append([InlineKeyboardButton("Управление записями", callback_data='manage_appointments')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            f"Здравствуйте, {db_user.full_name}! Выберите действие:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"Здравствуйте, {db_user.full_name}! Выберите действие:",
            reply_markup=reply_markup
        )
    
    db.close()
    return CHOOSING

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
    return await start(update, context)

async def new_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
    
    if not user.is_registered:
        await query.edit_message_text(
            "Для создания записи необходимо зарегистрироваться.\n"
            "Отправьте команду /start для начала регистрации."
        )
        return ConversationHandler.END
    
    await query.edit_message_text("Введите имя клиента:")
    return ENTER_CLIENT_NAME

async def enter_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['client_name'] = update.message.text
    await update.message.reply_text("Введите номер автомобиля:")
    return ENTER_CAR_NUMBER

async def enter_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['car_number'] = update.message.text
    await update.message.reply_text("Введите номер телефона клиента:")
    return ENTER_PHONE

async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    
    db = SessionLocal()
    stations = db.query(Station).all()
    keyboard = [[InlineKeyboardButton(station.name, callback_data=f'station_{station.id}')] 
                for station in stations]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите станцию ТО:", reply_markup=reply_markup)
    return CHOOSE_STATION

async def choose_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    station_id = int(query.data.split('_')[1])
    context.user_data['station_id'] = station_id
    
    # Генерируем даты на ближайшие 7 дней
    dates = [(datetime.now() + timedelta(days=x)).date() for x in range(7)]
    keyboard = [[InlineKeyboardButton(date.strftime("%d.%m.%Y"), 
                                    callback_data=f'date_{date.strftime("%Y-%m-%d")}')] 
                for date in dates]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите дату:", reply_markup=reply_markup)
    return CHOOSE_DATE

def is_time_slot_available(db_session, station_id: int, appointment_time: datetime) -> bool:
    """Проверяет, доступно ли время для записи на станцию"""
    # Получаем количество слотов в час для станции
    station = db_session.query(Station).filter(Station.id == station_id).first()
    if not station:
        return False
    
    # Проверяем существующие записи на конкретное время
    existing_appointments = db_session.query(Appointment).filter(
        and_(
            Appointment.station_id == station_id,
            Appointment.appointment_time == appointment_time
        )
    ).count()
    
    # Если есть хотя бы одна запись на это конкретное время, считаем слот занятым
    if existing_appointments > 0:
        return False
    
    # Проверяем количество записей в текущий час
    start_time = appointment_time.replace(minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    hour_appointments = db_session.query(Appointment).filter(
        and_(
            Appointment.station_id == station_id,
            Appointment.appointment_time >= start_time,
            Appointment.appointment_time < end_time
        )
    ).count()
    
    return hour_appointments < station.slots_per_hour

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_date = query.data.split('_')[1]
    context.user_data['date'] = selected_date
    
    db = SessionLocal()
    station_id = context.user_data.get('station_id')
    
    # Проверяем существование станции
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        await query.edit_message_text(
            "Ошибка: станция не найдена. Пожалуйста, начните запись заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu')
            ]])
        )
        db.close()
        return CHOOSING
    
    # Генерируем доступное время с 9:00 до 18:00
    times = []
    selected_date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
    current_time = datetime.now()
    
    for hour in range(9, 18):
        for minute in [0, 30]:
            time_str = f"{hour:02d}:{minute:02d}"
            check_time = selected_date_obj.replace(hour=hour, minute=minute)
            
            # Пропускаем прошедшее время
            if check_time < current_time:
                times.append((time_str, False))
                continue
            
            if is_time_slot_available(db, station_id, check_time):
                times.append((time_str, True))
            else:
                times.append((time_str, False))
    
    # Создаем клавиатуру с временными слотами
    keyboard = []
    for time_str, is_available in times:
        if is_available:
            keyboard.append([InlineKeyboardButton(time_str, callback_data=f'time_{time_str}')])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {time_str} (занято)", callback_data='unavailable')])
    
    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton("⬅️ Назад к выбору даты", callback_data='back_to_date')])
    keyboard.append([InlineKeyboardButton("В главное меню", callback_data='back_to_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Выберите время для записи на станцию {station.name}\n"
        f"Дата: {selected_date_obj.strftime('%d.%m.%Y')}\n"
        f"(недоступное время помечено ❌):", 
        reply_markup=reply_markup
    )
    return CHOOSE_TIME

async def handle_unavailable_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Это время уже занято. Пожалуйста, выберите другое время.", show_alert=True)
    return CHOOSE_TIME

async def save_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'unavailable':
        await query.answer("Это время уже занято. Пожалуйста, выберите другое время.", show_alert=True)
        return CHOOSE_TIME
    
    if query.data == 'back_to_date':
        station_id = context.user_data.get('station_id')
        dates = [(datetime.now() + timedelta(days=x)).date() for x in range(7)]
        keyboard = [[InlineKeyboardButton(date.strftime("%d.%m.%Y"), 
                                        callback_data=f'date_{date.strftime("%Y-%m-%d")}')] 
                    for date in dates]
        keyboard.append([InlineKeyboardButton("В главное меню", callback_data='back_to_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите дату:", reply_markup=reply_markup)
        return CHOOSE_DATE
    
    selected_time = query.data.split('_')[1]
    date_str = context.user_data.get('date')
    
    if not date_str:
        await query.edit_message_text(
            "Ошибка: дата не выбрана. Пожалуйста, начните запись заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        return CHOOSING
    
    time_obj = datetime.strptime(f"{date_str} {selected_time}", "%Y-%m-%d %H:%M")
    
    # Проверяем, не прошло ли выбранное время
    if time_obj < datetime.now():
        await query.edit_message_text(
            "Извините, но это время уже прошло. Пожалуйста, начните запись заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        return CHOOSING
    
    db = SessionLocal()
    station_id = context.user_data.get('station_id')
    
    # Проверяем существование станции
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        await query.edit_message_text(
            "Ошибка: станция не найдена. Пожалуйста, начните запись заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        db.close()
        return CHOOSING
    
    # Проверяем доступность времени еще раз перед сохранением
    if not is_time_slot_available(db, station_id, time_obj):
        await query.edit_message_text(
            "Извините, но это время уже занято. Пожалуйста, начните запись заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        db.close()
        return CHOOSING
    
    user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
    
    # Проверяем наличие всех необходимых данных
    required_data = ['car_number', 'client_name', 'phone']
    missing_data = [field for field in required_data if field not in context.user_data]
    
    if missing_data:
        await query.edit_message_text(
            "Ошибка: не хватает данных для записи. Пожалуйста, начните запись заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        db.close()
        return CHOOSING
    
    new_appointment = Appointment(
        station_id=station_id,
        user_id=user.id,
        car_number=context.user_data['car_number'],
        client_name=context.user_data['client_name'],
        client_phone=context.user_data['phone'],
        appointment_time=time_obj
    )
    
    try:
        db.add(new_appointment)
        db.commit()
        
        # Очищаем данные после успешной записи
        context.user_data.clear()
        
        await query.edit_message_text(
            f"✅ Запись успешно создана!\n\n"
            f"🏢 Станция: {station.name}\n"
            f"📅 Дата и время: {time_obj.strftime('%d.%m.%Y %H:%M')}\n"
            f"👤 Клиент: {new_appointment.client_name}\n"
            f"🚗 Номер авто: {new_appointment.car_number}\n"
            f"📞 Телефон: {new_appointment.client_phone}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка при сохранении записи: {e}")
        await query.edit_message_text(
            "Произошла ошибка при сохранении записи. Пожалуйста, попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
    finally:
        db.close()
    
    return CHOOSING

async def my_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
    appointments = db.query(Appointment).filter(
        and_(
            Appointment.user_id == user.id,
            Appointment.appointment_time >= datetime.now()
        )
    ).order_by(Appointment.appointment_time).all()
    
    keyboard = [[InlineKeyboardButton("Вернуться в меню", callback_data='back_to_menu')]]
    
    if not appointments:
        await query.edit_message_text(
            "У вас пока нет активных записей.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        db.close()
        return CHOOSING
    
    message = "Ваши активные записи:\n\n"
    for app in appointments:
        station = db.query(Station).filter(Station.id == app.station_id).first()
        message += f"📅 Дата и время: {app.appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
        message += f"🏢 Станция: {station.name}\n"
        message += f"👤 Клиент: {app.client_name}\n"
        message += f"🚗 Номер авто: {app.car_number}\n"
        message += f"📞 Телефон: {app.client_phone}\n"
        message += "-------------------\n"
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    db.close()
    return CHOOSING

async def manage_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление записями (для менеджеров)"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
    
    if not user.is_manager:
        await query.edit_message_text(
            "У вас нет прав для управления записями."
        )
        db.close()
        return ConversationHandler.END
    
    # Получаем все записи на сегодня и будущие даты
    current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    appointments = db.query(Appointment).filter(
        Appointment.appointment_time >= current_date
    ).order_by(Appointment.appointment_time).all()
    
    if not appointments:
        await query.edit_message_text(
            "Нет активных записей.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Назад", callback_data='back_to_menu')
            ]])
        )
        db.close()
        return CHOOSING
    
    # Формируем список записей
    message_text = "Активные записи:\n\n"
    keyboard = []
    
    for appointment in appointments:
        station = db.query(Station).filter(Station.id == appointment.station_id).first()
        message_text += (
            f"📅 {appointment.appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"🏢 Станция: {station.name}\n"
            f"👤 Клиент: {appointment.client_name}\n"
            f"🚗 Номер: {appointment.car_number}\n"
            f"📞 Телефон: {appointment.client_phone}\n\n"
        )
        keyboard.append([
            InlineKeyboardButton(
                f"Отменить запись {appointment.appointment_time.strftime('%d.%m.%Y %H:%M')}",
                callback_data=f'cancel_{appointment.id}'
            )
        ])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data='back_to_menu')])
    
    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    db.close()
    return CHOOSING

async def cancel_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена записи"""
    query = update.callback_query
    await query.answer()
    
    appointment_id = int(query.data.split('_')[1])
    
    db = SessionLocal()
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if appointment:
        db.delete(appointment)
        db.commit()
        await query.edit_message_text(
            "Запись успешно отменена.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Назад", callback_data='back_to_menu')
            ]])
        )
    else:
        await query.edit_message_text(
            "Запись не найдена.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Назад", callback_data='back_to_menu')
            ]])
        )
    
    db.close()
    return CHOOSING

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    return await start(update, context)

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
            REGISTRATION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration_code)],
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