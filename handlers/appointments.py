from datetime import datetime
import logging
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
    try:
        user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
        if not user:
            await query.edit_message_text(
                "Ошибка: пользователь не найден. Пожалуйста, начните с команды /start"
            )
            return ConversationHandler.END
        
        if not user.is_registered:
            await query.edit_message_text(
                "Для создания записи необходимо зарегистрироваться.\n"
                "Отправьте команду /start для начала регистрации."
            )
            return ConversationHandler.END
        
        await query.edit_message_text("Введите имя клиента:")
        return ENTER_CLIENT_NAME
    except Exception as e:
        logging.error(f"Ошибка в new_appointment: {e}")
        await query.edit_message_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
        return ConversationHandler.END
    finally:
        db.close()

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
    try:
        stations = db.query(Station).all()
        if not stations:
            await update.message.reply_text(
                "В системе нет доступных станций. Пожалуйста, обратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
                ]])
            )
            return CHOOSING
        
        keyboard = [[InlineKeyboardButton(station.name, callback_data=f'station_{station.id}')] 
                    for station in stations]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите станцию ТО:", reply_markup=reply_markup)
        return CHOOSE_STATION
    except Exception as e:
        logging.error(f"Ошибка в enter_phone: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже или обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        return CHOOSING
    finally:
        db.close()

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
    try:
        station_id = context.user_data.get('station_id')
        if not station_id:
            await query.edit_message_text(
                "Ошибка: станция не выбрана. Пожалуйста, начните запись заново.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
                ]])
            )
            return CHOOSING
        
        # Проверяем существование станции
        station = db.query(Station).filter(Station.id == station_id).first()
        if not station:
            await query.edit_message_text(
                "Ошибка: станция не найдена. Пожалуйста, начните запись заново.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
                ]])
            )
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
        return CHOOSE_TIME
    except Exception as e:
        logging.error(f"Ошибка в choose_date: {e}")
        await query.edit_message_text(
            "Произошла ошибка при загрузке доступного времени. Пожалуйста, попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        return CHOOSING
    finally:
        db.close()

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
        dates = get_available_dates()
        keyboard = [[InlineKeyboardButton(date.strftime("%d.%m.%Y"), 
                                        callback_data=f'date_{date.strftime("%Y-%m-%d")}')] 
                    for date in dates]
        keyboard.append([InlineKeyboardButton("В главное меню", callback_data='back_to_menu')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите дату:", reply_markup=reply_markup)
        return CHOOSE_DATE
    
    try:
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
            if not user:
                raise ValueError("Пользователь не найден")
            
            # Проверяем наличие всех необходимых данных
            required_data = ['car_number', 'client_name', 'phone']
            missing_data = [field for field in required_data if field not in context.user_data]
            if missing_data:
                raise ValueError(f"Отсутствуют данные: {', '.join(missing_data)}")
            
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
            return CHOOSING
            
        except ValueError as e:
            db.rollback()
            await query.edit_message_text(
                f"Ошибка: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
                ]])
            )
            return CHOOSING
        except Exception as e:
            db.rollback()
            logging.error(f"Ошибка при сохранении записи: {e}")
            await query.edit_message_text(
                "Произошла ошибка при сохранении записи. Пожалуйста, попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
                ]])
            )
            return CHOOSING
        finally:
            db.close()
            
    except Exception as e:
        logging.error(f"Ошибка в save_appointment: {e}")
        await query.edit_message_text(
            "Произошла неизвестная ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        return CHOOSING

async def my_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
        if not user:
            await query.edit_message_text(
                "Ошибка: пользователь не найден. Пожалуйста, начните с команды /start",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
                ]])
            )
            return CHOOSING
        
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
            return CHOOSING
        
        message = "Ваши активные записи:\n\n"
        for app in appointments:
            station = db.query(Station).filter(Station.id == app.station_id).first()
            if station:
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
        return CHOOSING
    except Exception as e:
        logging.error(f"Ошибка в my_appointments: {e}")
        await query.edit_message_text(
            "Произошла ошибка при получении списка записей. Пожалуйста, попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data='back_to_menu')
            ]])
        )
        return CHOOSING
    finally:
        db.close() 