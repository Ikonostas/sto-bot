from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from utils.logger import logger
from utils.roles import admin_required
from database.database import get_db
from database.models import Agent, TOCard, Payment, Calculation
from handlers.user_handler import get_all_agents, update_agent_commission
from sqlalchemy import func
from datetime import datetime
from sqlalchemy.orm import Session

# Состояния для ConversationHandler
(
    ADMIN_ACTION, 
    SELECT_AGENT, 
    AGENT_INFO, 
    AGENT_ARCHIVE, 
    AGENT_ACTION,
    PAYMENT_AMOUNT, 
    PAYMENT_COMMENT,
    EDIT_CARD, 
    EDIT_CARD_SELECT_FIELD,
    CHANGE_COMMISSION,
    WAITING_CALCULATION_AMOUNT
) = range(11)

@admin_required
async def admin_agents_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показать список агентов"""
    query = update.callback_query
    if query:
        await query.answer()
    
    db = next(get_db())
    try:
        # Получаем список агентов с пагинацией
        agents = get_all_agents(db, limit=30, skip=page * 30)
        total_agents = db.query(func.count(Agent.id)).scalar()
        
        keyboard = []
        for agent in agents:
            keyboard.append([
                InlineKeyboardButton(
                    f"{agent.full_name} ({agent.company})",
                    callback_data=f"agent_{agent.id}"
                )
            ])
        
        # Добавляем кнопки пагинации если нужно
        navigation = []
        if page > 0:
            navigation.append(
                InlineKeyboardButton("⬅️ Назад", callback_data=f"agents_page_{page-1}")
            )
        
        if (page + 1) * 30 < total_agents:
            navigation.append(
                InlineKeyboardButton("Вперед ➡️", callback_data=f"agents_page_{page+1}")
            )
        
        if navigation:
            keyboard.append(navigation)
        
        # Кнопка возврата в админ-панель
        keyboard.append([
            InlineKeyboardButton("Вернуться в админ-панель", callback_data="admin_panel")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отвечаем в зависимости от типа обновления
        if query:
            await query.edit_message_text(
                "Список агентов:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "Список агентов:",
                reply_markup=reply_markup
            )
        
        return SELECT_AGENT
    finally:
        db.close()

@admin_required
async def agent_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню действий с агентом"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID агента из данных callback
    agent_id = int(query.data.split("_")[1])
    context.user_data["selected_agent_id"] = agent_id
    
    db = next(get_db())
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            await query.edit_message_text(
                "Агент не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
                ]])
            )
            return SELECT_AGENT
        
        # Создаем клавиатуру с действиями
        keyboard = [
            [
                InlineKeyboardButton("Info", callback_data=f"agent_info_{agent_id}"),
                InlineKeyboardButton("Archive", callback_data=f"agent_archive_{agent_id}"),
                InlineKeyboardButton("Action", callback_data=f"agent_action_{agent_id}")
            ],
            [
                InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Выберите действие для агента {agent.full_name}:",
            reply_markup=reply_markup
        )
        
        return ADMIN_ACTION
    finally:
        db.close()

@admin_required
async def agent_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию об агенте"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID агента из данных callback
    agent_id = int(query.data.split("_")[2])
    
    db = next(get_db())
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            await query.edit_message_text(
                "Агент не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
                ]])
            )
            return SELECT_AGENT
        
        # Получаем статистику по ТО
        approved_to = db.query(func.count(TOCard.id)).filter(
            TOCard.agent_id == agent_id,
            TOCard.status == "approved"
        ).scalar()
        
        rejected_to = db.query(func.count(TOCard.id)).filter(
            TOCard.agent_id == agent_id,
            TOCard.status == "rejected"
        ).scalar()
        
        # Получаем сумму всех одобренных ТО
        approved_sum = db.query(func.sum(TOCard.total_price)).filter(
            TOCard.agent_id == agent_id,
            TOCard.status == "approved"
        ).scalar() or 0
        
        # Рассчитываем комиссионные
        commission = approved_sum * (agent.commission_rate / 100)
        
        # Получаем сумму всех платежей
        payments_sum = db.query(func.sum(Payment.amount)).filter(
            Payment.agent_id == agent_id
        ).scalar() or 0
        
        # Формируем текст с информацией
        info_text = (
            f"📋 Информация о агенте\n\n"
            f"👤 ФИО: {agent.full_name}\n"
            f"🏢 Компания: {agent.company}\n"
            f"📱 Телефон: {agent.phone}\n"
            f"🔗 Мессенджер: {agent.messenger_link or 'Не указан'}\n\n"
            f"📊 Статистика ТО:\n"
            f"✅ Согласованных: {approved_to}\n"
            f"❌ Отклоненных: {rejected_to}\n\n"
            f"💰 Финансы:\n"
            f"💲 Баланс: {approved_sum - commission - payments_sum:.2f} руб.\n"
            f"🧮 Комиссия: {agent.commission_rate}%\n"
            f"💵 Сумма комиссии: {commission:.2f} руб.\n"
            f"💸 Сумма выплат: {payments_sum:.2f} руб.\n"
        )
        
        keyboard = [[
            InlineKeyboardButton("Назад", callback_data=f"agent_{agent_id}")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            info_text,
            reply_markup=reply_markup
        )
        
        return AGENT_INFO
    finally:
        db.close()

@admin_required
async def agent_archive(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показать архив агента - все карточки ТО и карточки расчетов"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID агента из данных callback
    parts = query.data.split("_")
    agent_id = int(parts[2])
    
    # Проверяем, содержит ли callback данные о странице
    if len(parts) > 3 and parts[3] == "page":
        page = int(parts[4])
    
    db = next(get_db())
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            await query.edit_message_text(
                "Агент не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
                ]])
            )
            return SELECT_AGENT
        
        # Получаем все карточки ТО для этого агента с пагинацией
        to_cards = db.query(TOCard).filter(
            TOCard.agent_id == agent_id
        ).order_by(TOCard.created_at.desc()).limit(5).offset(page * 5).all()
        
        # Получаем общее количество карточек ТО
        total_cards = db.query(func.count(TOCard.id)).filter(
            TOCard.agent_id == agent_id
        ).scalar()
        
        # Получаем платежи для этого агента
        payments = db.query(Payment).filter(
            Payment.agent_id == agent_id
        ).order_by(Payment.created_at.desc()).all()
        
        # Формируем сообщение с информацией о карточках ТО
        message_text = f"📋 Архив агента: {agent.full_name}\n\n"
        
        if to_cards:
            message_text += f"🚗 Карточки ТО (страница {page + 1}/{(total_cards - 1) // 5 + 1}):\n\n"
            
            for card in to_cards:
                appointment_time = card.appointment_time.strftime("%d.%m.%Y %H:%M")
                created_at = card.created_at.strftime("%d.%m.%Y %H:%M")
                
                status_text = {
                    "pending": "🕒 Ожидает согласования",
                    "approved": "✅ Согласовано",
                    "rejected": "❌ Отклонено",
                    "cancelled": "🚫 Отменено"
                }.get(card.status, card.status)
                
                message_text += (
                    f"Карточка ТО №{card.card_number}\n"
                    f"Создана: {created_at}\n"
                    f"Категория: {card.category}\n"
                    f"СТО: {card.sto_name}\n"
                    f"Запись на: {appointment_time}\n"
                    f"Клиент: {card.client_name}\n"
                    f"Номер авто: {card.car_number}\n"
                    f"Стоимость: {card.total_price:.2f} руб.\n"
                    f"Статус: {status_text}\n"
                )
                
                if card.status == "rejected" and card.admin_comment:
                    message_text += f"Причина отклонения: {card.admin_comment}\n"
                
                message_text += "\n---\n\n"
        else:
            message_text += "У агента нет карточек ТО.\n\n"
        
        # Добавляем информацию о платежах
        if payments:
            message_text += "💰 Карточки расчета:\n\n"
            
            for payment in payments:
                created_at = payment.created_at.strftime("%d.%m.%Y %H:%M")
                sign = "+" if payment.amount >= 0 else ""
                
                message_text += (
                    f"Дата: {created_at}\n"
                    f"Сумма: {sign}{payment.amount:.2f} руб.\n"
                    f"Комментарий: {payment.comment}\n\n"
                )
        else:
            message_text += "У агента нет карточек расчета.\n"
        
        # Создаем клавиатуру для навигации
        keyboard = []
        
        # Кнопки пагинации для карточек ТО
        if total_cards > 5:
            pagination = []
            if page > 0:
                pagination.append(
                    InlineKeyboardButton("⬅️ Назад", callback_data=f"agent_archive_{agent_id}_page_{page-1}")
                )
            
            if (page + 1) * 5 < total_cards:
                pagination.append(
                    InlineKeyboardButton("Вперед ➡️", callback_data=f"agent_archive_{agent_id}_page_{page+1}")
                )
            
            if pagination:
                keyboard.append(pagination)
        
        # Кнопка возврата
        keyboard.append([
            InlineKeyboardButton("Назад", callback_data=f"agent_{agent_id}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup
        )
        
        return AGENT_ARCHIVE
    finally:
        db.close()

@admin_required
async def agent_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню действий для агента"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID агента из данных callback
    agent_id = int(query.data.split("_")[2])
    context.user_data["selected_agent_id"] = agent_id
    
    db = next(get_db())
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            await query.edit_message_text(
                "Агент не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
                ]])
            )
            return SELECT_AGENT
        
        # Создаем клавиатуру с действиями
        keyboard = [
            [
                InlineKeyboardButton("Добавить карточку расчета", callback_data=f"add_payment_{agent_id}")
            ],
            [
                InlineKeyboardButton("Изменить карточку ТО", callback_data=f"edit_to_card_{agent_id}")
            ],
            [
                InlineKeyboardButton("Изменить комиссию", callback_data=f"change_commission_{agent_id}")
            ],
            [
                InlineKeyboardButton("Назад", callback_data=f"agent_{agent_id}")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Выберите действие для агента {agent.full_name}:",
            reply_markup=reply_markup
        )
        
        return AGENT_ACTION
    finally:
        db.close()

@admin_required
async def start_add_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления карточки расчета"""
    query = update.callback_query
    await query.answer()
    
    agent_id = int(query.data.split("_")[2])
    context.user_data["payment_agent_id"] = agent_id
    
    await query.edit_message_text(
        "Введите сумму платежа. Используйте '-' для вычитания средств и запятую для разделения рублей и копеек.\n"
        "Примеры: 1000, -500, 1500,50, -750,25"
    )
    
    return PAYMENT_AMOUNT

@admin_required
async def process_payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода суммы платежа"""
    try:
        # Получаем текст сообщения и заменяем запятые на точки для корректного преобразования
        amount_text = update.message.text.replace(',', '.')
        amount = float(amount_text)
        
        # Сохраняем сумму платежа в данных пользователя
        context.user_data["payment_amount"] = amount
        
        await update.message.reply_text(
            f"Введите комментарий к платежу на сумму {amount:.2f} руб.:"
        )
        
        return PAYMENT_COMMENT
    
    except ValueError:
        await update.message.reply_text(
            "Ошибка! Пожалуйста, введите корректное число с использованием запятой в качестве разделителя.\n"
            "Примеры: 1000, -500, 1500,50, -750,25"
        )
        
        return PAYMENT_AMOUNT

@admin_required
async def process_payment_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода комментария и завершение добавления платежа"""
    comment = update.message.text
    agent_id = context.user_data.get("payment_agent_id")
    amount = context.user_data.get("payment_amount")
    
    if not agent_id or amount is None:
        await update.message.reply_text(
            "Ошибка: не удалось найти ID агента или сумму платежа. Пожалуйста, начните процесс заново."
        )
        return ConversationHandler.END
    
    db = next(get_db())
    try:
        # Получаем агента
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            await update.message.reply_text(
                "Ошибка: агент не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
                ]])
            )
            return ConversationHandler.END
        
        # Создаем новый платеж
        payment = Payment(
            agent_id=agent_id,
            amount=amount,
            comment=comment
        )
        
        db.add(payment)
        db.commit()
        
        logger.info(f"Admin {update.effective_user.id} added payment of {amount} to agent {agent_id} with comment: {comment}")
        
        # Получаем актуальную информацию о балансе
        approved_sum = db.query(func.sum(TOCard.total_price)).filter(
            TOCard.agent_id == agent_id,
            TOCard.status == "approved"
        ).scalar() or 0
        
        commission = approved_sum * (agent.commission_rate / 100)
        
        payments_sum = db.query(func.sum(Payment.amount)).filter(
            Payment.agent_id == agent_id
        ).scalar() or 0
        
        balance = approved_sum - commission - payments_sum
        
        # Формируем сообщение об успешном добавлении платежа
        sign = "+" if amount >= 0 else ""
        keyboard = [[
            InlineKeyboardButton("Назад к действиям с агентом", callback_data=f"agent_action_{agent_id}")
        ]]
        
        await update.message.reply_text(
            f"✅ Карточка расчета успешно добавлена!\n\n"
            f"Агент: {agent.full_name}\n"
            f"Сумма: {sign}{amount:.2f} руб.\n"
            f"Комментарий: {comment}\n\n"
            f"Текущий баланс агента: {balance:.2f} руб.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return AGENT_ACTION
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding payment: {e}")
        
        await update.message.reply_text(
            f"❌ Ошибка при добавлении платежа: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться к действиям с агентом", callback_data=f"agent_action_{agent_id}")
            ]])
        )
        
        return AGENT_ACTION
    
    finally:
        db.close()

@admin_required
async def start_change_commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса изменения комиссии агента"""
    query = update.callback_query
    await query.answer()
    
    agent_id = int(query.data.split("_")[2])
    context.user_data["commission_agent_id"] = agent_id
    
    db = next(get_db())
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            await query.edit_message_text(
                "Ошибка: агент не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
                ]])
            )
            return ConversationHandler.END
        
        await query.edit_message_text(
            f"Текущая ставка комиссии для агента {agent.full_name}: {agent.commission_rate}%\n\n"
            "Введите новое значение комиссии в процентах (используйте запятую в качестве разделителя для дробных значений).\n"
            "Примеры: 10, 15,5, 20"
        )
        
        return CHANGE_COMMISSION
    finally:
        db.close()

@admin_required
async def process_change_commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода новой комиссии и её применение"""
    try:
        # Получаем текст сообщения и заменяем запятые на точки для корректного преобразования
        commission_text = update.message.text.replace(',', '.')
        new_commission = float(commission_text)
        
        if new_commission < 0:
            await update.message.reply_text(
                "Ошибка! Комиссия не может быть отрицательной. Пожалуйста, введите положительное число."
            )
            return CHANGE_COMMISSION
        
        agent_id = context.user_data.get("commission_agent_id")
        
        if not agent_id:
            await update.message.reply_text(
                "Ошибка: не удалось найти ID агента. Пожалуйста, начните процесс заново."
            )
            return ConversationHandler.END
        
        db = next(get_db())
        try:
            # Получаем агента
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                await update.message.reply_text(
                    "Ошибка: агент не найден.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
                    ]])
                )
                return ConversationHandler.END
            
            # Сохраняем старую комиссию для логирования
            old_commission = agent.commission_rate
            
            # Обновляем комиссию
            update_agent_commission(db, agent_id, new_commission)
            
            logger.info(f"Admin {update.effective_user.id} changed commission for agent {agent_id} from {old_commission}% to {new_commission}%")
            
            # Получаем актуальную информацию о балансе
            approved_sum = db.query(func.sum(TOCard.total_price)).filter(
                TOCard.agent_id == agent_id,
                TOCard.status == "approved"
            ).scalar() or 0
            
            commission = approved_sum * (new_commission / 100)
            
            payments_sum = db.query(func.sum(Payment.amount)).filter(
                Payment.agent_id == agent_id
            ).scalar() or 0
            
            balance = approved_sum - commission - payments_sum
            
            # Формируем сообщение об успешном изменении комиссии
            keyboard = [[
                InlineKeyboardButton("Назад к действиям с агентом", callback_data=f"agent_action_{agent_id}")
            ]]
            
            await update.message.reply_text(
                f"✅ Комиссия успешно изменена!\n\n"
                f"Агент: {agent.full_name}\n"
                f"Старая комиссия: {old_commission}%\n"
                f"Новая комиссия: {new_commission}%\n\n"
                f"Новый баланс агента: {balance:.2f} руб.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return AGENT_ACTION
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error changing commission: {e}")
            
            await update.message.reply_text(
                f"❌ Ошибка при изменении комиссии: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к действиям с агентом", callback_data=f"agent_action_{agent_id}")
                ]])
            )
            
            return AGENT_ACTION
        
        finally:
            db.close()
    
    except ValueError:
        await update.message.reply_text(
            "Ошибка! Пожалуйста, введите корректное число с использованием запятой в качестве разделителя.\n"
            "Примеры: 10, 15,5, 20"
        )
        
        return CHANGE_COMMISSION

@admin_required
async def start_edit_to_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса редактирования карточки ТО"""
    query = update.callback_query
    await query.answer()
    
    agent_id = int(query.data.split("_")[3])
    context.user_data["edit_agent_id"] = agent_id
    
    db = next(get_db())
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            await query.edit_message_text(
                "Ошибка: агент не найден.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться к списку", callback_data="admin_agents_list")
                ]])
            )
            return ConversationHandler.END
        
        # Получаем все карточки ТО для этого агента
        to_cards = db.query(TOCard).filter(
            TOCard.agent_id == agent_id
        ).order_by(TOCard.created_at.desc()).all()
        
        if not to_cards:
            await query.edit_message_text(
                f"У агента {agent.full_name} нет карточек ТО.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Назад", callback_data=f"agent_action_{agent_id}")
                ]])
            )
            return ConversationHandler.END
        
        # Создаем клавиатуру с карточками ТО
        keyboard = []
        for card in to_cards:
            appointment_time = card.appointment_time.strftime("%d.%m.%Y %H:%M")
            status_text = {
                "pending": "🕒", "approved": "✅", "rejected": "❌", "cancelled": "🚫"
            }.get(card.status, "")
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{status_text} Карточка №{card.card_number} ({appointment_time})", 
                    callback_data=f"edit_card_{card.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("Отмена", callback_data=f"agent_action_{agent_id}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Выберите карточку ТО для изменения (агент: {agent.full_name}):",
            reply_markup=reply_markup
        )
        
        return EDIT_CARD
    finally:
        db.close()

@admin_required
async def select_to_card_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор карточки ТО для редактирования"""
    query = update.callback_query
    await query.answer()
    
    card_id = int(query.data.split("_")[2])
    context.user_data["edit_card_id"] = card_id
    
    db = next(get_db())
    try:
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        if not card:
            await query.edit_message_text(
                "Ошибка: карточка ТО не найдена.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Назад", callback_data=f"agent_action_{context.user_data.get('edit_agent_id')}")
                ]])
            )
            return ConversationHandler.END
        
        agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
        agent_name = agent.full_name if agent else "Неизвестный агент"
        
        # Форматируем дату и время
        appointment_time = card.appointment_time.strftime("%d.%m.%Y %H:%M")
        
        # Формируем сообщение с информацией о карточке
        message_text = (
            f"📋 Карточка ТО №{card.card_number}\n\n"
            f"👤 Агент: {agent_name}\n"
            f"📅 Дата и время: {appointment_time}\n"
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
            message_text += f"📝 Описание: {card.defect_description}\n\n"
        else:
            message_text += "✅ Дефекты отсутствуют\n\n"
        
        message_text += f"🔄 Статус: {get_status_text(card.status)}\n"
        
        if card.admin_comment:
            message_text += f"💬 Комментарий администратора: {card.admin_comment}\n"
        
        # Создаем клавиатуру с полями для редактирования
        keyboard = [
            [InlineKeyboardButton("📅 Изменить дату и время", callback_data="edit_field_appointment_time")],
            [InlineKeyboardButton("🚗 Изменить категорию", callback_data="edit_field_category")],
            [InlineKeyboardButton("🏢 Изменить СТО", callback_data="edit_field_sto_name")],
            [InlineKeyboardButton("💰 Изменить стоимость", callback_data="edit_field_total_price")],
            [InlineKeyboardButton("👤 Изменить клиента", callback_data="edit_field_client_name")],
            [InlineKeyboardButton("🚘 Изменить номер авто", callback_data="edit_field_car_number")],
            [InlineKeyboardButton("🔢 Изменить VIN", callback_data="edit_field_vin_number")],
            [InlineKeyboardButton("📱 Изменить телефон", callback_data="edit_field_client_phone")]
        ]
        
        # Добавляем возможность изменить статус, если карточка не отменена
        if card.status != "cancelled":
            keyboard.append([InlineKeyboardButton("🔄 Изменить статус", callback_data="edit_field_status")])
        
        # Добавляем возможность изменить информацию о дефектах
        if card.has_defects:
            keyboard.append([InlineKeyboardButton("🔧 Изменить информацию о дефектах", callback_data="edit_field_defects")])
        else:
            keyboard.append([InlineKeyboardButton("🔧 Добавить дефекты", callback_data="edit_field_add_defects")])
        
        # Добавляем кнопку для изменения комментария администратора
        keyboard.append([InlineKeyboardButton("💬 Изменить комментарий", callback_data="edit_field_admin_comment")])
        
        # Добавляем кнопку для отмены
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data=f"agent_action_{card.agent_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text + "\nВыберите поле для редактирования:",
            reply_markup=reply_markup
        )
        
        return EDIT_CARD_SELECT_FIELD
    finally:
        db.close()

@admin_required
async def add_calculation_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление карточки расчёта для агента"""
    query = update.callback_query
    await query.answer()
    
    agent_id = context.user_data.get('selected_agent_id')
    if not agent_id:
        await query.edit_message_text(
            "❌ Агент не выбран",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin_menu")]])
        )
        return
    
    await query.edit_message_text(
        "💰 Введите сумму для карточки расчёта (только число, например: 1000):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Отмена", callback_data="admin_agent_actions")]])
    )
    return WAITING_CALCULATION_AMOUNT

@admin_required
async def process_calculation_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенной суммы для карточки расчёта"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите корректную сумму (положительное число)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Отмена", callback_data="admin_agent_actions")]])
        )
        return WAITING_CALCULATION_AMOUNT
    
    agent_id = context.user_data.get('selected_agent_id')
    with Session() as db:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            await update.message.reply_text("❌ Агент не найден")
            return ConversationHandler.END
        
        # Создаем новую карточку расчёта
        calculation = Calculation(
            agent_id=agent_id,
            amount=amount,
            created_at=datetime.now()
        )
        
        # Обновляем баланс агента (может быть отрицательным)
        agent.balance = (agent.balance or 0) - amount
        
        try:
            db.add(calculation)
            db.commit()
            
            # Уведомляем агента
            try:
                await context.bot.send_message(
                    chat_id=agent.telegram_id,
                    text=f"💰 Администратор добавил карточку расчёта на сумму {amount:.2f} руб.\n"
                         f"Ваш новый баланс: {agent.balance:.2f} руб."
                )
            except Exception as e:
                logger.error(f"Failed to notify agent {agent.telegram_id}: {e}")
            
            await update.message.reply_text(
                f"✅ Карточка расчёта на сумму {amount:.2f} руб. добавлена для агента {agent.full_name}\n"
                f"Новый баланс агента: {agent.balance:.2f} руб.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« К действиям", callback_data="admin_agent_actions")]])
            )
            return ConversationHandler.END
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding calculation card: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при добавлении карточки расчёта",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« К действиям", callback_data="admin_agent_actions")]])
            )
            return ConversationHandler.END

def get_status_text(status):
    """Преобразование статуса в читаемый текст"""
    status_texts = {
        "pending": "🕒 Ожидает согласования",
        "approved": "✅ Согласовано",
        "rejected": "❌ Отклонено",
        "cancelled": "🚫 Отменено"
    }
    return status_texts.get(status, status)

async def edit_to_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список карточек ТО для редактирования"""
    query = update.callback_query
    await query.answer()
    
    agent_id = context.user_data.get('selected_agent_id')
    if not agent_id:
        await query.edit_message_text(
            "❌ Агент не выбран",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin_menu")]])
        )
        return
    
    page = context.user_data.get('to_cards_page', 1)
    per_page = 5
    
    with Session() as db:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        cards = db.query(TOCard).filter(TOCard.agent_id == agent_id).order_by(TOCard.created_at.desc()).all()
        
        if not cards:
            await query.edit_message_text(
                "📭 У агента нет карточек ТО",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin_agent_actions")]])
            )
            return
        
        total_pages = (len(cards) + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        current_cards = cards[start_idx:end_idx]
        
        keyboard = []
        for card in current_cards:
            status_text = get_status_text(card.status)
            card_text = f"ТО №{card.card_number} | {status_text}"
            keyboard.append([InlineKeyboardButton(card_text, callback_data=f"edit_card_{card.id}")])
        
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("« Пред.", callback_data=f"to_cards_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("След. »", callback_data=f"to_cards_page_{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)
            
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin_agent_actions")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"📋 Карточки ТО агента {agent.full_name} (стр. {page}/{total_pages}):"
        await query.edit_message_text(text=message, reply_markup=reply_markup)

async def show_card_edit_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает опции редактирования карточки ТО"""
    query = update.callback_query
    await query.answer()
    
    card_id = int(query.data.split('_')[-1])
    context.user_data['edit_card_id'] = card_id
    
    with Session() as db:
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        if not card:
            await query.edit_message_text(
                "❌ Карточка не найдена",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin_agent_actions")]])
            )
            return
        
        message = (
            f"📄 Карточка ТО №{card.card_number}\n\n"
            f"🏢 СТО: {card.sto_name}\n"
            f"🚗 Категория: {card.category}\n"
            f"📅 Время: {card.appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"💰 Стоимость: {card.total_price} руб.\n"
            f"📝 Комментарий: {card.comment or 'нет'}\n\n"
            "Выберите поле для редактирования:"
        )
        
        keyboard = [
            [InlineKeyboardButton("🏢 СТО", callback_data="edit_field_sto")],
            [InlineKeyboardButton("🚗 Категория", callback_data="edit_field_category")],
            [InlineKeyboardButton("📅 Время", callback_data="edit_field_time")],
            [InlineKeyboardButton("💰 Стоимость", callback_data="edit_field_price")],
            [InlineKeyboardButton("📝 Комментарий", callback_data="edit_field_comment")],
            [InlineKeyboardButton("« Назад", callback_data="edit_to_card")]
        ]
        
        await query.edit_message_text(text=message, reply_markup=InlineKeyboardMarkup(keyboard))
        return EDIT_CARD_SELECT_FIELD

async def process_card_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка редактирования поля карточки ТО"""
    field = update.callback_query.data.split('_')[-1]
    card_id = context.user_data.get('edit_card_id')
    
    with Session() as db:
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        if not card:
            await update.callback_query.edit_message_text(
                "❌ Карточка не найдена",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin_agent_actions")]])
            )
            return ConversationHandler.END
        
        field_prompts = {
            'sto': "🏢 Введите название СТО:",
            'category': "🚗 Введите категорию ТС (B, C или E):",
            'time': "📅 Введите дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ:",
            'price': "💰 Введите новую стоимость (только число):",
            'comment': "📝 Введите новый комментарий:"
        }
        
        await update.callback_query.edit_message_text(
            field_prompts[field],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Отмена", callback_data="edit_to_card")]])
        )
        context.user_data['edit_field'] = field
        return EDIT_CARD

async def save_card_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение изменений в карточке ТО"""
    field = context.user_data.get('edit_field')
    card_id = context.user_data.get('edit_card_id')
    new_value = update.message.text
    
    with Session() as db:
        card = db.query(TOCard).filter(TOCard.id == card_id).first()
        agent = db.query(Agent).filter(Agent.id == card.agent_id).first()
        
        if not card:
            await update.message.reply_text("❌ Карточка не найдена")
            return ConversationHandler.END
        
        try:
            if field == 'sto':
                card.sto_name = new_value
            elif field == 'category':
                if new_value not in ['B', 'C', 'E']:
                    raise ValueError("Неверная категория")
                card.category = new_value
            elif field == 'time':
                try:
                    new_time = datetime.strptime(new_value, '%d.%m.%Y %H:%M')
                    card.appointment_time = new_time
                except ValueError:
                    raise ValueError("Неверный формат даты и времени")
            elif field == 'price':
                try:
                    new_price = float(new_value)
                    if new_price <= 0:
                        raise ValueError()
                    card.total_price = new_price
                except ValueError:
                    raise ValueError("Неверная сумма")
            elif field == 'comment':
                card.comment = new_value
            
            db.commit()
            
            # Уведомляем агента
            try:
                await context.bot.send_message(
                    chat_id=agent.telegram_id,
                    text=f"✏️ Администратор изменил вашу карточку ТО №{card.card_number}"
                )
            except Exception as e:
                logger.error(f"Failed to notify agent {agent.telegram_id}: {e}")
            
            await update.message.reply_text(
                f"✅ Карточка ТО №{card.card_number} успешно изменена",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« К списку карточек", callback_data="edit_to_card")]])
            )
            return ConversationHandler.END
            
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« К списку карточек", callback_data="edit_to_card")]])
            )
            return EDIT_CARD
        except Exception as e:
            db.rollback()
            logger.error(f"Error editing TO card: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при изменении карточки",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« К списку карточек", callback_data="edit_to_card")]])
            )
            return ConversationHandler.END

def get_admin_handlers():
    """Возвращает обработчики для админ-панели"""
    return [
        CallbackQueryHandler(show_admin_menu, pattern="^admin_menu$"),
        CallbackQueryHandler(show_agent_list, pattern="^admin_agents$"),
        CallbackQueryHandler(show_agent_list, pattern="^agent_page_"),
        CallbackQueryHandler(show_agent_details, pattern="^agent_details_"),
        CallbackQueryHandler(show_agent_actions, pattern="^agent_actions$"),
        CallbackQueryHandler(add_calculation_card, pattern="^add_calculation$"),
        CallbackQueryHandler(edit_to_card, pattern="^edit_to_card$"),
        CallbackQueryHandler(edit_to_card, pattern="^to_cards_page_"),
        CallbackQueryHandler(show_card_edit_options, pattern="^edit_card_"),
        CallbackQueryHandler(process_card_edit, pattern="^edit_field_"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, process_calculation_amount, WAITING_CALCULATION_AMOUNT),
        MessageHandler(filters.TEXT & ~filters.COMMAND, save_card_edit, EDIT_CARD)
    ] 