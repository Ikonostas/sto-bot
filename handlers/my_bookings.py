from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, 
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from utils.logger import logger
from utils.roles import registered_required
from database.database import get_db
from database.models import Agent, TOCard, Payment
from sqlalchemy import func
from datetime import datetime

# Состояния для ConversationHandler
CANCEL_CONFIRM = range(1)

@registered_required
async def show_my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные записи пользователя"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested active bookings")
    
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
        
        # Получаем активные записи агента (со статусом pending)
        active_bookings = db.query(TOCard).filter(
            TOCard.agent_id == agent.id,
            TOCard.status == "pending"
        ).order_by(TOCard.appointment_time).all()
        
        # Получаем сумму всех активных записей
        active_sum = db.query(func.sum(TOCard.total_price)).filter(
            TOCard.agent_id == agent.id,
            TOCard.status == "pending"
        ).scalar() or 0
        
        # Рассчитываем баланс согласно требованиям ТЗ:
        # (сумма всех карточек ТО, которые имеют согласование об успешности прохождения от администратора 
        # минус комиссия агента и минус сумма выплат)
        
        # Сумма всех одобренных ТО
        approved_sum = db.query(func.sum(TOCard.total_price)).filter(
            TOCard.agent_id == agent.id,
            TOCard.status == "approved"
        ).scalar() or 0
        
        # Рассчитываем комиссионные
        commission = approved_sum * (agent.commission_rate / 100)
        
        # Получаем сумму всех платежей
        payments_sum = db.query(func.sum(Payment.amount)).filter(
            Payment.agent_id == agent.id
        ).scalar() or 0
        
        # Рассчитываем баланс
        balance = approved_sum - commission - payments_sum
        
        # Формируем сообщение - самой первой строкой отображаем баланс агента
        message_text = f"💰 Баланс: {balance:.2f} руб.\n"
        message_text += f"(Одобренные карточки: {approved_sum:.2f} руб., комиссия: {commission:.2f} руб., выплаты: {payments_sum:.2f} руб.)\n\n"
        
        if not active_bookings:
            message_text += "У вас нет активных записей на ТО."
            
            # Создаем клавиатуру для возврата в главное меню
            keyboard = [[InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            message_text += f"📋 Ваши активные записи ({len(active_bookings)}):\n"
            message_text += f"💸 Общая сумма активных записей: {active_sum:.2f} руб.\n\n"
            
            # Создаем клавиатуру с кнопками для просмотра карточек и возврата в меню
            keyboard = []
            
            for i, booking in enumerate(active_bookings, 1):
                # Форматируем дату и время
                appointment_time = booking.appointment_time.strftime("%d.%m.%Y %H:%M")
                
                message_text += (
                    f"{i}. Карточка ТО №{booking.card_number}\n"
                    f"   📅 Дата и время: {appointment_time}\n"
                    f"   🚗 Категория: {booking.category}\n"
                    f"   🏢 СТО: {booking.sto_name}\n"
                    f"   💰 Стоимость: {booking.total_price:.2f} руб.\n"
                )
                
                # Добавляем кнопку для просмотра подробной информации о карточке
                keyboard.append([
                    InlineKeyboardButton(f"Подробнее о карточке №{booking.card_number}", callback_data=f"view_card_{booking.id}")
                ])
            
            keyboard.append([InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")])
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отвечаем в зависимости от способа вызова
        if query:
            await query.edit_message_text(message_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup)
            
    finally:
        db.close()

@registered_required
async def view_card_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение подробной информации о карточке ТО"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID карточки из данных callback
    card_id = int(query.data.split("_")[2])
    
    db = next(get_db())
    try:
        # Получаем карточку ТО
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        if not card:
            await query.edit_message_text(
                "Ошибка: карточка ТО не найдена.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к моим записям", callback_data="my_bookings")
                ]])
            )
            return
        
        # Форматируем дату и время
        appointment_time = card.appointment_time.strftime("%d.%m.%Y %H:%M")
        created_at = card.created_at.strftime("%d.%m.%Y %H:%M")
        
        # Формируем подробную информацию о карточке
        message_text = (
            f"📋 Карточка ТО №{card.card_number}\n\n"
            f"📅 Дата и время записи: {appointment_time}\n"
            f"📆 Создана: {created_at}\n"
            f"🚗 Категория: {card.category}\n"
            f"🏢 СТО: {card.sto_name}\n"
            f"💰 Стоимость: {card.total_price:.2f} руб.\n\n"
            f"👤 Клиент: {card.client_name}\n"
            f"🚘 Номер авто: {card.car_number}\n"
            f"🔢 VIN: {card.vin_number}\n"
            f"📱 Телефон: {card.client_phone}\n\n"
        )
        
        if card.has_defects:
            message_text += f"🔧 Дефекты: {card.defect_type}\n"
            if card.defect_description:
                message_text += f"📝 Описание дефектов: {card.defect_description}\n\n"
        else:
            message_text += "✅ Дефекты отсутствуют\n\n"
        
        message_text += f"🔄 Статус: {get_status_text(card.status)}\n"
        
        if card.status == "rejected" and card.admin_comment:
            message_text += f"💬 Комментарий администратора: {card.admin_comment}\n"
        
        # Создаем клавиатуру с кнопками для возврата и, если карточка в статусе pending, для отмены
        keyboard = []
        
        if card.status == "pending":
            keyboard.append([
                InlineKeyboardButton("❌ Отменить запись", callback_data=f"cancel_card_{card.id}")
            ])
        
        keyboard.append([InlineKeyboardButton("Назад к моим записям", callback_data="my_bookings")])
        keyboard.append([InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup
        )
        
    finally:
        db.close()

@registered_required
async def start_cancel_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса отмены карточки ТО"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID карточки из данных callback
    card_id = int(query.data.split("_")[2])
    context.user_data["cancel_card_id"] = card_id
    
    db = next(get_db())
    try:
        # Получаем карточку ТО
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        if not card:
            await query.edit_message_text(
                "Ошибка: карточка ТО не найдена.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к моим записям", callback_data="my_bookings")
                ]])
            )
            return ConversationHandler.END
        
        # Проверяем статус карточки
        if card.status != "pending":
            await query.edit_message_text(
                "Ошибка: отменить можно только карточки в статусе 'Ожидает согласования'.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к моим записям", callback_data="my_bookings")
                ]])
            )
            return ConversationHandler.END
        
        # Создаем клавиатуру для подтверждения отмены
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить отмену", callback_data="confirm_cancel"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"view_card_{card_id}")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"❗ Вы действительно хотите отменить запись на ТО №{card.card_number}?\n\n"
            f"📅 Дата и время: {card.appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"🚗 Категория: {card.category}\n"
            f"🏢 СТО: {card.sto_name}\n\n"
            "Это действие нельзя будет отменить.",
            reply_markup=reply_markup
        )
        
        return CANCEL_CONFIRM
    
    except Exception as e:
        logger.error(f"Error starting cancel process: {e}")
        
        await query.edit_message_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к моим записям", callback_data="my_bookings")
            ]])
        )
        
        return ConversationHandler.END
    
    finally:
        db.close()

@registered_required
async def confirm_cancel_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение отмены карточки ТО"""
    query = update.callback_query
    await query.answer()
    
    if query.data != "confirm_cancel":
        # Возвращаемся к просмотру карточки
        card_id = context.user_data.get("cancel_card_id")
        if card_id:
            await view_card_details(update, context)
        else:
            await show_my_bookings(update, context)
        return ConversationHandler.END
    
    card_id = context.user_data.get("cancel_card_id")
    if not card_id:
        await query.edit_message_text(
            "Ошибка: не удалось найти ID карточки ТО. Пожалуйста, начните процесс заново.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к моим записям", callback_data="my_bookings")
            ]])
        )
        return ConversationHandler.END
    
    db = next(get_db())
    try:
        # Получаем карточку ТО
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        if not card:
            await query.edit_message_text(
                "Ошибка: карточка ТО не найдена.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к моим записям", callback_data="my_bookings")
                ]])
            )
            return ConversationHandler.END
        
        # Обновляем статус карточки на "отменено"
        card.status = "cancelled"
        card.admin_comment = "Отменено агентом"
        db.commit()
        
        logger.info(f"User {update.effective_user.id} cancelled TO card {card.card_number}")
        
        await query.edit_message_text(
            f"✅ Карточка ТО №{card.card_number} успешно отменена.\n\n"
            "Вы можете создать новую запись через главное меню.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Вернуться к моим записям", callback_data="my_bookings")],
                [InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")]
            ])
        )
        
        return ConversationHandler.END
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling TO card: {e}")
        
        await query.edit_message_text(
            f"❌ Ошибка при отмене карточки ТО: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к моим записям", callback_data="my_bookings")
            ]])
        )
        
        return ConversationHandler.END
    
    finally:
        db.close()

def get_status_text(status):
    """Преобразование статуса в читаемый текст"""
    status_texts = {
        "pending": "🕒 Ожидает согласования",
        "approved": "✅ Согласовано",
        "rejected": "❌ Отклонено",
        "cancelled": "🚫 Отменено"
    }
    return status_texts.get(status, status)

def get_booking_cancel_handler():
    """Создание обработчика разговора для отмены карточек ТО"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_cancel_card, pattern=r'^cancel_card_\d+$')
        ],
        states={
            CANCEL_CONFIRM: [
                CallbackQueryHandler(confirm_cancel_card, pattern=r'^confirm_cancel$|^view_card_\d+$')
            ]
        },
        fallbacks=[],
        name="booking_cancel_handler"
    ) 