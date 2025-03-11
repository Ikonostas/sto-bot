from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import and_
from database.db import SessionLocal
from database.models import User, Station, Appointment
from utils.time_slots import get_available_dates, get_available_time_slots
from config import (CHOOSING, ENTER_CLIENT_NAME, ENTER_CAR_NUMBER, 
                   ENTER_PHONE, CHOOSE_STATION, CHOOSE_DATE, CHOOSE_TIME)

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
    db.close()
    return CHOOSE_STATION

async def choose_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    station_id = int(query.data.split('_')[1])
    context.user_data['station_id'] = station_id
    
    dates = get_available_dates()
    keyboard = [[InlineKeyboardButton(date.strftime("%d.%m.%Y"), 
                                    callback_data=f'date_{date.strftime("%Y-%m-%d")}')] 
                for date in dates]
    keyboard.append([InlineKeyboardButton("В главное меню", callback_data='back_to_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите дату:", reply_markup=reply_markup)
    return CHOOSE_DATE

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
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        db.close()
        return CHOOSING
    
    selected_date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
    time_slots = get_available_time_slots(db, station_id, selected_date_obj)
    
    # Создаем клавиатуру с временными слотами
    keyboard = []
    for time_str, is_available in time_slots:
        if is_available:
            keyboard.append([InlineKeyboardButton(time_str, callback_data=f'time_{time_str}')])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {time_str} (занято)", callback_data='unavailable')])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад к выбору даты", callback_data='back_to_date')])
    keyboard.append([InlineKeyboardButton("В главное меню", callback_data='back_to_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Выберите время для записи на станцию {station.name}\n"
        f"Дата: {selected_date_obj.strftime('%d.%m.%Y')}\n"
        f"(недоступное время помечено ❌):", 
        reply_markup=reply_markup
    )
    db.close()
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
    
    db = SessionLocal()
    try:
        # Проверяем существование станции
        station_id = context.user_data.get('station_id')
        station = db.query(Station).filter(Station.id == station_id).first()
        if not station:
            raise ValueError("Станция не найдена")
        
        # Проверяем, не прошло ли выбранное время
        if time_obj < datetime.now():
            raise ValueError("Выбранное время уже прошло")
        
        user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
        
        new_appointment = Appointment(
            station_id=station_id,
            user_id=user.id,
            car_number=context.user_data['car_number'],
            client_name=context.user_data['client_name'],
            client_phone=context.user_data['phone'],
            appointment_time=time_obj
        )
        
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
            f"Произошла ошибка при сохранении записи: {str(e)}",
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