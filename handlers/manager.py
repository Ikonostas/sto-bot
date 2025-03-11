from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import SessionLocal
from database.models import User, Station, Appointment
from config import CHOOSING

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