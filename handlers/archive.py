from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.logger import logger
from utils.roles import registered_required
from database.database import get_db
from database.models import Agent, TOCard, Payment
from sqlalchemy import func, or_
from datetime import datetime

@registered_required
async def show_archive(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показать архив записей пользователя"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested archive (page {page})")
    
    # Определяем, вызвана функция из колбэка или напрямую
    query = update.callback_query
    if query:
        await query.answer()
    
    db = next(get_db())
    try:
        # Получаем информацию об агенте
        agent = db.query(Agent).filter(Agent.telegram_id == user_id).first()
        if not agent:
            message_text = "Ошибка: не удалось найти информацию о вашем профиле. Пожалуйста, перерегистрируйтесь."
            if query:
                await query.edit_message_text(message_text)
            else:
                await update.message.reply_text(message_text)
            return
        
        # Получаем завершенные записи агента (одобренные или отклоненные)
        archive_bookings = db.query(TOCard).filter(
            TOCard.agent_id == agent.id,
            or_(TOCard.status == "approved", TOCard.status == "rejected")
        ).order_by(TOCard.appointment_time.desc()).limit(5).offset(page * 5).all()
        
        # Получаем общее количество записей в архиве
        total_archive_bookings = db.query(func.count(TOCard.id)).filter(
            TOCard.agent_id == agent.id,
            or_(TOCard.status == "approved", TOCard.status == "rejected")
        ).scalar()
        
        # Получаем историю платежей
        payments = db.query(Payment).filter(
            Payment.agent_id == agent.id
        ).order_by(Payment.created_at.desc()).limit(5).offset(page * 5).all()
        
        # Формируем сообщение
        message_text = f"📂 Архив записей и платежей (страница {page + 1})\n\n"
        
        # Выводим карточки ТО
        if not archive_bookings:
            message_text += "У вас нет завершенных записей на ТО.\n\n"
        else:
            message_text += "📋 Завершенные записи на ТО:\n\n"
            
            for i, booking in enumerate(archive_bookings, 1):
                # Форматируем дату и время
                appointment_time = booking.appointment_time.strftime("%d.%m.%Y %H:%M")
                status = get_status_text(booking.status)
                
                message_text += (
                    f"{i}. Карточка ТО №{booking.card_number}\n"
                    f"   📅 Дата: {appointment_time}\n"
                    f"   🚗 Категория: {booking.category}\n"
                    f"   🏢 СТО: {booking.sto_name}\n"
                    f"   💰 Стоимость: {booking.total_price} руб.\n"
                    f"   🔄 Статус: {status}\n"
                )
                
                if booking.admin_comment:
                    message_text += f"   💬 Комментарий: {booking.admin_comment}\n"
                
                message_text += "\n"
        
        # Выводим платежи
        if payments:
            message_text += "💵 Карточки расчетов:\n\n"
            
            for i, payment in enumerate(payments, 1):
                # Форматируем дату
                payment_date = payment.created_at.strftime("%d.%m.%Y")
                amount = f"+{payment.amount}" if payment.amount > 0 else f"{payment.amount}"
                
                message_text += (
                    f"{i}. Платеж от {payment_date}\n"
                    f"   💰 Сумма: {amount} руб.\n"
                    f"   💬 Комментарий: {payment.comment}\n\n"
                )
        
        # Создаем клавиатуру для навигации и возврата в главное меню
        keyboard = []
        
        # Кнопки пагинации
        pagination = []
        if page > 0:
            pagination.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"archive_page_{page-1}"))
        
        if (page + 1) * 5 < total_archive_bookings:
            pagination.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"archive_page_{page+1}"))
        
        if pagination:
            keyboard.append(pagination)
        
        keyboard.append([InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отвечаем в зависимости от способа вызова
        if query:
            await query.edit_message_text(message_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup)
            
    finally:
        db.close()

def get_status_text(status):
    """Преобразование статуса в читаемый текст"""
    status_texts = {
        "pending": "🕒 Ожидает согласования",
        "approved": "✅ Согласовано",
        "rejected": "❌ Отклонено"
    }
    return status_texts.get(status, status) 