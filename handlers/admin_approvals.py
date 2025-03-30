from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from utils.logger import logger
from utils.roles import admin_required
from database.database import get_db
from database.models import Agent, TOCard
from datetime import datetime

# Состояния для ConversationHandler
APPROVE_REJECT, REJECT_REASON = range(2)

@admin_required
async def show_pending_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показать список ожидающих согласования записей на ТО"""
    user_id = update.effective_user.id
    logger.info(f"Admin {user_id} requested pending approvals")
    
    # Определяем, вызвана функция из колбэка или напрямую
    query = update.callback_query
    if query:
        await query.answer()
    
    db = next(get_db())
    try:
        # Получаем все записи со статусом pending
        pending_cards = db.query(TOCard).filter(
            TOCard.status == "pending"
        ).order_by(TOCard.created_at).limit(5).offset(page * 5).all()
        
        # Получаем общее количество записей, ожидающих согласования
        total_pending = db.query(TOCard).filter(
            TOCard.status == "pending"
        ).count()
        
        # Формируем сообщение
        if not pending_cards:
            message_text = "Нет карточек ТО, ожидающих согласования."
        else:
            message_text = f"📋 Карточки ТО, ожидающие согласования ({page + 1}/{(total_pending - 1) // 5 + 1}):\n\n"
            
            for i, card in enumerate(pending_cards, 1):
                # Получаем информацию об агенте
                agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
                agent_name = agent.full_name if agent else "Неизвестный агент"
                
                # Форматируем дату и время
                created_at = card.created_at.strftime("%d.%m.%Y %H:%M")
                appointment_time = card.appointment_time.strftime("%d.%m.%Y %H:%M")
                
                message_text += (
                    f"{i}. Карточка ТО №{card.card_number}\n"
                    f"   📅 Создана: {created_at}\n"
                    f"   👤 Агент: {agent_name}\n"
                    f"   🚗 Категория: {card.category}\n"
                    f"   🏢 СТО: {card.sto_name}\n"
                    f"   ⏰ Время записи: {appointment_time}\n"
                    f"   👤 Клиент: {card.client_name}\n"
                    f"   🚘 Номер авто: {card.car_number}\n"
                    f"   📱 Телефон: {card.client_phone}\n"
                    f"   💰 Стоимость: {card.total_price} руб.\n"
                )
                
                if card.has_defects:
                    message_text += f"   🔧 Дефекты: {card.defect_type}\n"
                    message_text += f"   📝 Описание: {card.defect_description}\n"
                else:
                    message_text += "   ✅ Дефекты отсутствуют\n"
                
                # Добавляем кнопки для согласования или отклонения
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Согласовать", callback_data=f"approve_card_{card.id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_card_{card.id}")
                    ]
                ]
                
                # Добавляем разделитель между карточками
                message_text += "\n" + "-" * 30 + "\n\n"
        
        # Создаем клавиатуру для навигации и возврата в панель администратора
        keyboard = []
        
        # Кнопки пагинации
        pagination = []
        if page > 0:
            pagination.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"approvals_page_{page-1}"))
        
        if (page + 1) * 5 < total_pending:
            pagination.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"approvals_page_{page+1}"))
        
        if pagination:
            keyboard.append(pagination)
        
        keyboard.append([InlineKeyboardButton("Вернуться в админ-панель", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отвечаем в зависимости от способа вызова
        if query:
            await query.edit_message_text(message_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup)
            
    finally:
        db.close()

@admin_required
async def handle_approve_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка согласования карточки ТО"""
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
                    InlineKeyboardButton("Вернуться к согласованиям", callback_data="admin_approve")
                ]])
            )
            return
        
        # Обновляем статус карточки
        card.status = "approved"
        db.commit()
        
        logger.info(f"Admin {update.effective_user.id} approved TO card {card.card_number}")
        
        # Получаем информацию об агенте
        agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
        
        # Отправляем сообщение агенту (в реальном боте)
        # Здесь можно было бы добавить логику для отправки уведомления агенту
        
        await query.edit_message_text(
            f"✅ Карточка ТО №{card.card_number} успешно согласована!\n\n"
            f"Информация о карточке:\n"
            f"📅 Дата и время: {card.appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"👤 Агент: {agent.full_name if agent else 'Неизвестный агент'}\n"
            f"🚗 Категория: {card.category}\n"
            f"🏢 СТО: {card.sto_name}\n"
            f"💰 Стоимость: {card.total_price} руб.\n\n"
            f"Агент будет уведомлен о согласовании.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к согласованиям", callback_data="admin_approve")
            ]])
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error approving TO card: {e}")
        
        await query.edit_message_text(
            f"❌ Ошибка при согласовании карточки ТО: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к согласованиям", callback_data="admin_approve")
            ]])
        )
    
    finally:
        db.close()

@admin_required
async def start_reject_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса отклонения карточки ТО"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID карточки из данных callback
    card_id = int(query.data.split("_")[2])
    context.user_data["reject_card_id"] = card_id
    
    db = next(get_db())
    try:
        # Получаем карточку ТО
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        if not card:
            await query.edit_message_text(
                "Ошибка: карточка ТО не найдена.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к согласованиям", callback_data="admin_approve")
                ]])
            )
            return ConversationHandler.END
        
        await query.edit_message_text(
            f"Вы собираетесь отклонить карточку ТО №{card.card_number}.\n\n"
            "Пожалуйста, введите причину отклонения:"
        )
        
        return REJECT_REASON
    
    except Exception as e:
        logger.error(f"Error starting reject process: {e}")
        
        await query.edit_message_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к согласованиям", callback_data="admin_approve")
            ]])
        )
        
        return ConversationHandler.END
    
    finally:
        db.close()

@admin_required
async def process_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода причины отклонения и завершение процесса"""
    reject_reason = update.message.text
    card_id = context.user_data.get("reject_card_id")
    
    if not card_id:
        await update.message.reply_text(
            "Ошибка: не удалось найти ID карточки ТО. Пожалуйста, начните процесс заново."
        )
        return ConversationHandler.END
    
    db = next(get_db())
    try:
        # Получаем карточку ТО
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        if not card:
            await update.message.reply_text(
                "Ошибка: карточка ТО не найдена.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к согласованиям", callback_data="admin_approve")
                ]])
            )
            return ConversationHandler.END
        
        # Обновляем статус карточки и добавляем комментарий
        card.status = "rejected"
        card.admin_comment = reject_reason
        db.commit()
        
        logger.info(f"Admin {update.effective_user.id} rejected TO card {card.card_number}: {reject_reason}")
        
        # Получаем информацию об агенте
        agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
        
        # Отправляем сообщение агенту (в реальном боте)
        # Здесь можно было бы добавить логику для отправки уведомления агенту
        
        await update.message.reply_text(
            f"❌ Карточка ТО №{card.card_number} отклонена!\n\n"
            f"Информация о карточке:\n"
            f"📅 Дата и время: {card.appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"👤 Агент: {agent.full_name if agent else 'Неизвестный агент'}\n"
            f"🚗 Категория: {card.category}\n"
            f"🏢 СТО: {card.sto_name}\n"
            f"💰 Стоимость: {card.total_price} руб.\n\n"
            f"📝 Причина отклонения: {reject_reason}\n\n"
            f"Агент будет уведомлен об отклонении.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к согласованиям", callback_data="admin_approve")
            ]])
        )
        
        return ConversationHandler.END
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting TO card: {e}")
        
        await update.message.reply_text(
            f"❌ Ошибка при отклонении карточки ТО: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к согласованиям", callback_data="admin_approve")
            ]])
        )
        
        return ConversationHandler.END
    
    finally:
        db.close()

def get_approval_handler():
    """Создание обработчика разговора для согласования/отклонения карточек ТО"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_reject_card, pattern=r'^reject_card_\d+$')
        ],
        states={
            REJECT_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_reject_reason)
            ]
        },
        fallbacks=[],
        name="admin_approval_handler"
    ) 