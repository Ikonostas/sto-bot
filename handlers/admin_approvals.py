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
from sqlalchemy.orm import Session

# Состояния для ConversationHandler
APPROVE_REJECT, REJECT_REASON = range(2)
WAITING_DECLINE_REASON = 3

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

async def show_approval_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список карточек ТО для согласования"""
    query = update.callback_query
    if query:
        await query.answer()
    
    page = context.user_data.get('approval_page', 1)
    per_page = 5
    
    with Session() as db:
        cards = db.query(TOCard).filter(TOCard.status == 'pending').order_by(TOCard.created_at.desc()).all()
        
        if not cards:
            message = "📭 Нет карточек ТО для согласования"
            keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if query:
                await query.edit_message_text(text=message, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text=message, reply_markup=reply_markup)
            return
        
        total_pages = (len(cards) + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        current_cards = cards[start_idx:end_idx]
        
        keyboard = []
        for card in current_cards:
            agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
            card_text = f"ТО №{card.card_number} | {agent.full_name}"
            keyboard.append([InlineKeyboardButton(card_text, callback_data=f"approve_card_{card.id}")])
        
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("« Пред.", callback_data=f"approval_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("След. »", callback_data=f"approval_page_{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)
            
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"📋 Карточки ТО для согласования (стр. {page}/{total_pages}):"
        
        if query:
            await query.edit_message_text(text=message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text=message, reply_markup=reply_markup)

async def show_card_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали карточки ТО и кнопки для согласования/отклонения"""
    query = update.callback_query
    await query.answer()
    
    card_id = int(query.data.split('_')[-1])
    
    with Session() as db:
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
        
        if not card:
            await query.edit_message_text(
                "❌ Карточка не найдена",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin_approve")]])
            )
            return
        
        message = (
            f"📄 Карточка ТО №{card.card_number}\n\n"
            f"👤 Агент: {agent.full_name}\n"
            f"📱 Телефон агента: {agent.phone}\n"
            f"🏢 СТО: {card.sto_name}\n"
            f"🚗 Категория ТС: {card.category}\n"
            f"📅 Дата и время: {card.appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"💰 Стоимость: {card.total_price} руб.\n"
            f"📝 Комментарий: {card.comment or 'нет'}\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Согласовать", callback_data=f"confirm_card_{card_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_card_{card_id}")
            ],
            [InlineKeyboardButton("« Назад", callback_data="admin_approve")]
        ]
        
        await query.edit_message_text(text=message, reply_markup=InlineKeyboardMarkup(keyboard))

async def confirm_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Согласование карточки ТО"""
    query = update.callback_query
    await query.answer()
    
    card_id = int(query.data.split('_')[-1])
    
    with Session() as db:
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
        
        if not card:
            await query.edit_message_text("❌ Карточка не найдена")
            return
        
        card.status = 'approved'
        card.approved_at = datetime.now()
        db.commit()
        
        # Уведомляем агента
        try:
            await context.bot.send_message(
                chat_id=agent.telegram_id,
                text=f"✅ Ваша карточка ТО №{card.card_number} была согласована администратором!"
            )
        except Exception as e:
            logger.error(f"Failed to notify agent {agent.telegram_id}: {e}")
        
        await query.edit_message_text(
            f"✅ Карточка ТО №{card.card_number} согласована",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« К списку", callback_data="admin_approve")]])
        )

async def decline_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклонение карточки ТО"""
    query = update.callback_query
    await query.answer()
    
    card_id = int(query.data.split('_')[-1])
    context.user_data['decline_card_id'] = card_id
    
    await query.edit_message_text(
        "📝 Пожалуйста, укажите причину отклонения:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Отмена", callback_data="admin_approve")]])
    )
    return WAITING_DECLINE_REASON

async def process_decline_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка причины отклонения карточки ТО"""
    reason = update.message.text
    card_id = context.user_data.get('decline_card_id')
    
    with Session() as db:
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
        
        if not card:
            await update.message.reply_text("❌ Карточка не найдена")
            return ConversationHandler.END
        
        card.status = 'declined'
        card.decline_reason = reason
        db.commit()
        
        # Уведомляем агента
        try:
            await context.bot.send_message(
                chat_id=agent.telegram_id,
                text=f"❌ Ваша карточка ТО №{card.card_number} была отклонена.\n\nПричина: {reason}"
            )
        except Exception as e:
            logger.error(f"Failed to notify agent {agent.telegram_id}: {e}")
        
        await update.message.reply_text(
            f"❌ Карточка ТО №{card.card_number} отклонена",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« К списку", callback_data="admin_approve")]])
        )
        return ConversationHandler.END

def get_approval_handlers():
    """Возвращает обработчики для раздела согласования"""
    return [
        CallbackQueryHandler(show_approval_list, pattern="^admin_approve$"),
        CallbackQueryHandler(show_approval_list, pattern="^approval_page_"),
        CallbackQueryHandler(show_card_details, pattern="^approve_card_"),
        CallbackQueryHandler(confirm_card, pattern="^confirm_card_"),
        CallbackQueryHandler(decline_card, pattern="^decline_card_"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, process_decline_reason, WAITING_DECLINE_REASON)
    ] 