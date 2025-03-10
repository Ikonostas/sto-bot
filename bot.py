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
CHOOSE_ACTION = 0
ENTER_CLIENT_NAME = 1
ENTER_CAR_NUMBER = 2
ENTER_PHONE = 3
CHOOSE_STATION = 4
CHOOSE_DATE = 5
CHOOSE_TIME = 6

# Подключение к базе данных
engine = create_engine('sqlite:///techservice.db')
SessionLocal = sessionmaker(bind=engine)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    
    # Проверяем, существует ли пользователь
    db_user = db.query(User).filter(User.telegram_id == user.id).first()
    if not db_user:
        db_user = User(telegram_id=user.id, username=user.username)
        db.add(db_user)
        db.commit()
    
    keyboard = [
        [InlineKeyboardButton("Записать на ТО", callback_data='new_appointment')],
        [InlineKeyboardButton("Мои записи", callback_data='my_appointments')]
    ]
    if db_user.is_manager:
        keyboard.append([InlineKeyboardButton("Управление записями", callback_data='manage_appointments')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Здравствуйте, {user.first_name}! Выберите действие:",
        reply_markup=reply_markup
    )
    return CHOOSE_ACTION

async def new_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
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
    station_id = context.user_data['station_id']
    
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
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите время (недоступное время помечено ❌):", reply_markup=reply_markup)
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
        return await choose_station(update, context)
    
    selected_time = query.data.split('_')[1]
    date_str = context.user_data['date']
    time_obj = datetime.strptime(f"{date_str} {selected_time}", "%Y-%m-%d %H:%M")
    
    # Проверяем, не прошло ли выбранное время
    if time_obj < datetime.now():
        await query.edit_message_text(
            "Извините, но это время уже прошло. Пожалуйста, начните запись заново и выберите другое время.",
        )
        return ConversationHandler.END
    
    db = SessionLocal()
    
    # Проверяем доступность времени еще раз перед сохранением
    if not is_time_slot_available(db, context.user_data['station_id'], time_obj):
        await query.edit_message_text(
            "Извините, но это время уже занято. Пожалуйста, начните запись заново и выберите другое время.",
        )
        return ConversationHandler.END
    
    user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
    
    new_appointment = Appointment(
        station_id=context.user_data['station_id'],
        user_id=user.id,
        car_number=context.user_data['car_number'],
        client_name=context.user_data['client_name'],
        client_phone=context.user_data['phone'],
        appointment_time=time_obj
    )
    
    try:
        db.add(new_appointment)
        db.commit()
    except Exception as e:
        db.rollback()
        await query.edit_message_text(
            "Произошла ошибка при сохранении записи. Пожалуйста, попробуйте еще раз.",
        )
        return ConversationHandler.END
    
    station = db.query(Station).filter(Station.id == context.user_data['station_id']).first()
    
    await query.edit_message_text(
        f"Запись создана!\n\n"
        f"Станция: {station.name}\n"
        f"Дата и время: {time_obj.strftime('%d.%m.%Y %H:%M')}\n"
        f"Клиент: {context.user_data['client_name']}\n"
        f"Номер авто: {context.user_data['car_number']}\n"
        f"Телефон: {context.user_data['phone']}"
    )
    return ConversationHandler.END

async def my_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
    appointments = db.query(Appointment).filter(Appointment.user_id == user.id).all()
    
    if not appointments:
        await query.edit_message_text("У вас пока нет записей.")
        return
    
    message = "Ваши записи:\n\n"
    for app in appointments:
        message += f"Станция: {app.station.name}\n"
        message += f"Дата и время: {app.appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
        message += f"Клиент: {app.client_name}\n"
        message += f"Номер авто: {app.car_number}\n"
        message += f"Телефон: {app.client_phone}\n"
        message += "-------------------\n"
    
    await query.edit_message_text(message)

def main():
    application = Application.builder().token(os.getenv('BOT_TOKEN')).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(new_appointment, pattern='^new_appointment$')
        ],
        states={
            ENTER_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_client_name)],
            ENTER_CAR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_car_number)],
            ENTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)],
            CHOOSE_STATION: [CallbackQueryHandler(choose_station, pattern='^station_')],
            CHOOSE_DATE: [CallbackQueryHandler(choose_date, pattern='^date_')],
            CHOOSE_TIME: [
                CallbackQueryHandler(save_appointment, pattern='^time_'),
                CallbackQueryHandler(handle_unavailable_time, pattern='^unavailable$')
            ]
        },
        fallbacks=[]
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(my_appointments, pattern='^my_appointments$'))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 