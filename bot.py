import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from sqlalchemy import create_engine
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

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_date = query.data.split('_')[1]
    context.user_data['date'] = selected_date
    
    # Генерируем доступное время с 9:00 до 18:00
    times = []
    for hour in range(9, 18):
        times.append(f"{hour:02d}:00")
        times.append(f"{hour:02d}:30")
    
    keyboard = [[InlineKeyboardButton(time, callback_data=f'time_{time}')] 
                for time in times]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите время:", reply_markup=reply_markup)
    return CHOOSE_TIME

async def save_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_time = query.data.split('_')[1]
    date_str = context.user_data['date']
    time_obj = datetime.strptime(f"{date_str} {selected_time}", "%Y-%m-%d %H:%M")
    
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
    
    new_appointment = Appointment(
        station_id=context.user_data['station_id'],
        user_id=user.id,
        car_number=context.user_data['car_number'],
        client_name=context.user_data['client_name'],
        client_phone=context.user_data['phone'],
        appointment_time=time_obj
    )
    
    db.add(new_appointment)
    db.commit()
    
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
            CHOOSE_TIME: [CallbackQueryHandler(save_appointment, pattern='^time_')]
        },
        fallbacks=[]
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(my_appointments, pattern='^my_appointments$'))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 