from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from utils.logger import logger
from utils.roles import registered_required
from database.database import get_db
from database.models import TOCard, Agent
from config import settings
from datetime import datetime, timedelta
import json

# Состояния для ConversationHandler
(
    SELECT_STO, 
    CONFIRM_CATEGORY_PRICE, 
    CHECK_DEFECTS, 
    SPECIFY_DEFECTS, 
    SELECT_TIME, 
    CLIENT_NAME, 
    CAR_NUMBER, 
    VIN_NUMBER, 
    CLIENT_PHONE, 
    CONFIRM_BOOKING
) = range(10)

@registered_required
async def start_booking_category_b(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало бронирования для категории B"""
    return await start_booking(update, context, "B")

@registered_required
async def start_booking_category_c(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало бронирования для категории C"""
    return await start_booking(update, context, "C")

@registered_required
async def start_booking_category_e(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало бронирования для категории E"""
    return await start_booking(update, context, "E")

@registered_required
async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Начало процесса бронирования для указанной категории"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started booking for category {category}")
    
    # Сохраняем категорию в данных пользователя
    context.user_data["booking_category"] = category
    
    # Получаем список станций, которые работают с этой категорией
    sto_stations = settings.STO_STATIONS
    available_stations = []
    
    for station_id, station in sto_stations.items():
        if category in station.categories:
            available_stations.append({
                "id": station_id,
                "name": station.name,
                "address": station.address,
                "price": station.prices.get(category, 0)
            })
    
    if not available_stations:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"К сожалению, нет доступных станций для категории {category}."
            )
        else:
            await update.message.reply_text(
                f"К сожалению, нет доступных станций для категории {category}."
            )
        return ConversationHandler.END
    
    # Создаем клавиатуру с доступными станциями
    keyboard = []
    for station in available_stations:
        keyboard.append([
            InlineKeyboardButton(
                f"{station['name']} ({station['address']}) - {station['price']} руб.", 
                callback_data=f"sto_{station['id']}"
            )
        ])
    
    # Добавляем кнопку отмены
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel_booking")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отвечаем в зависимости от типа обновления
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"Выберите станцию СТО для категории {category}:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"Выберите станцию СТО для категории {category}:",
            reply_markup=reply_markup
        )
    
    return SELECT_STO

async def select_sto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора станции СТО"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_booking":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    # Получаем ID станции из данных callback
    station_id = query.data.split("_")[1]
    category = context.user_data["booking_category"]
    
    # Получаем информацию о станции
    station = settings.STO_STATIONS.get(station_id)
    if not station:
        await query.edit_message_text("Станция не найдена. Пожалуйста, начните бронирование заново.")
        return ConversationHandler.END
    
    # Сохраняем информацию о станции и цене
    context.user_data["station_id"] = station_id
    context.user_data["station_name"] = station.name
    context.user_data["station_address"] = station.address
    context.user_data["base_price"] = station.prices.get(category, 0)
    context.user_data["total_price"] = station.prices.get(category, 0)
    
    # Создаем клавиатуру для подтверждения категории и цены
    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm_price"),
            InlineKeyboardButton("Отмена", callback_data="cancel_booking")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Вы выбрали станцию {station.name} ({station.address})\n"
        f"Категория: {category}\n"
        f"Стоимость ТО: {station.prices.get(category, 0)} руб.\n\n"
        "Подтвердите выбор станции и категории:",
        reply_markup=reply_markup
    )
    
    return CONFIRM_CATEGORY_PRICE

async def confirm_category_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение категории и цены, переход к проверке дефектов"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_booking":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    # Создаем клавиатуру для указания дефектов
    keyboard = [
        [
            InlineKeyboardButton("Дефектов нет", callback_data="defects_none"),
            InlineKeyboardButton("Незначительные дефекты", callback_data="defects_minor")
        ],
        [
            InlineKeyboardButton("Значительные дефекты", callback_data="defects_major"),
            InlineKeyboardButton("Отмена", callback_data="cancel_booking")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Укажите наличие дефектов на автомобиле:",
        reply_markup=reply_markup
    )
    
    return CHECK_DEFECTS

async def check_defects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора наличия дефектов"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_booking":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    defect_type = query.data.split("_")[1]
    station_id = context.user_data["station_id"]
    station = settings.STO_STATIONS.get(station_id)
    base_price = context.user_data["base_price"]
    
    if defect_type == "none":
        # Нет дефектов, сохраняем и переходим к выбору времени
        context.user_data["has_defects"] = False
        context.user_data["defect_type"] = None
        context.user_data["defect_description"] = None
        context.user_data["total_price"] = base_price
        
        return await select_time_slot(update, context)
    
    elif defect_type in ["minor", "major"]:
        # Есть дефекты, запрашиваем описание и обновляем цену
        context.user_data["has_defects"] = True
        context.user_data["defect_type"] = defect_type
        
        # Обновляем цену в зависимости от типа дефекта
        additional_cost = station.defect_prices.get(defect_type, 0)
        context.user_data["total_price"] = base_price + additional_cost
        
        await query.edit_message_text(
            f"Опишите дефекты автомобиля ({defect_type}):\n\n"
            f"Дополнительная стоимость: +{additional_cost} руб.\n"
            f"Итоговая стоимость: {base_price + additional_cost} руб."
        )
        
        return SPECIFY_DEFECTS

async def specify_defects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода описания дефектов"""
    defect_description = update.message.text
    context.user_data["defect_description"] = defect_description
    
    logger.debug(f"User {update.effective_user.id} specified defects: {defect_description}")
    
    # Переходим к выбору времени
    return await select_time_slot(update, context)

async def select_time_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор времени для записи на ТО"""
    # Получаем информацию о станции
    station_id = context.user_data["station_id"]
    station = settings.STO_STATIONS.get(station_id)
    
    # Разбираем рабочие часы
    start_time = datetime.strptime(station.working_hours["start"], "%H:%M").time()
    end_time = datetime.strptime(station.working_hours["end"], "%H:%M").time()
    time_slot_minutes = station.time_slot
    
    # Создаем список доступных временных слотов на сегодня
    current_datetime = datetime.now()
    current_date = current_datetime.date()
    
    # Формируем список доступных дат (сегодня и следующие 7 дней)
    available_dates = [current_date + timedelta(days=i) for i in range(8)]
    
    # Создаем клавиатуру с датами
    keyboard = []
    for date in available_dates:
        formatted_date = date.strftime("%d.%m.%Y")
        keyboard.append([
            InlineKeyboardButton(formatted_date, callback_data=f"date_{formatted_date}")
        ])
    
    # Добавляем кнопку отмены
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel_booking")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отвечаем в зависимости от типа обновления
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Выберите дату для записи на ТО:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Выберите дату для записи на ТО:",
            reply_markup=reply_markup
        )
    
    return SELECT_TIME

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора даты"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_booking":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    # Получаем выбранную дату
    selected_date_str = query.data.split("_")[1]
    selected_date = datetime.strptime(selected_date_str, "%d.%m.%Y").date()
    
    # Сохраняем выбранную дату
    context.user_data["selected_date"] = selected_date_str
    
    # Получаем информацию о станции
    station_id = context.user_data["station_id"]
    station = settings.STO_STATIONS.get(station_id)
    
    # Разбираем рабочие часы
    start_time = datetime.strptime(station.working_hours["start"], "%H:%M").time()
    end_time = datetime.strptime(station.working_hours["end"], "%H:%M").time()
    time_slot_minutes = station.time_slot
    
    # Создаем список доступных временных слотов
    time_slots = []
    current_time = datetime.combine(selected_date, start_time)
    end_datetime = datetime.combine(selected_date, end_time)
    
    while current_time < end_datetime:
        time_slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=time_slot_minutes)
    
    # Получаем занятые слоты из базы данных
    db = next(get_db())
    try:
        # Находим занятые слоты на выбранную дату и станцию
        selected_date_start = datetime.combine(selected_date, datetime.min.time())
        selected_date_end = datetime.combine(selected_date, datetime.max.time())
        
        booked_slots = db.query(TOCard.appointment_time).filter(
            TOCard.sto_name == station.name,
            TOCard.appointment_time >= selected_date_start,
            TOCard.appointment_time <= selected_date_end
        ).all()
        
        # Преобразуем в список строк с временем
        booked_times = [slot[0].strftime("%H:%M") for slot in booked_slots]
        
        # Удаляем занятые слоты из списка доступных
        available_slots = [slot for slot in time_slots if slot not in booked_times]
        
        # Если текущий день, удаляем прошедшие слоты
        if selected_date == datetime.now().date():
            current_hour_minute = datetime.now().strftime("%H:%M")
            available_slots = [slot for slot in available_slots if slot > current_hour_minute]
        
        # Если нет доступных слотов
        if not available_slots:
            await query.edit_message_text(
                f"На выбранную дату ({selected_date_str}) нет доступных временных слотов. "
                "Пожалуйста, выберите другую дату."
            )
            return await select_time_slot(update, context)
        
        # Создаем клавиатуру с доступными временными слотами
        keyboard = []
        row = []
        for i, slot in enumerate(available_slots):
            row.append(InlineKeyboardButton(slot, callback_data=f"time_{slot}"))
            
            # По 3 кнопки в ряду
            if (i + 1) % 3 == 0 or i == len(available_slots) - 1:
                keyboard.append(row)
                row = []
        
        # Добавляем кнопки для навигации
        keyboard.append([InlineKeyboardButton("Назад к выбору даты", callback_data="back_to_date")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel_booking")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Выберите время для записи на ТО ({selected_date_str}):",
            reply_markup=reply_markup
        )
        
        return SELECT_TIME
    
    finally:
        db.close()

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора времени"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_booking":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    if query.data == "back_to_date":
        return await select_time_slot(update, context)
    
    # Получаем выбранное время
    selected_time = query.data.split("_")[1]
    selected_date = context.user_data["selected_date"]
    
    # Сохраняем дату и время
    appointment_datetime = datetime.strptime(f"{selected_date} {selected_time}", "%d.%m.%Y %H:%M")
    context.user_data["appointment_time"] = appointment_datetime
    
    await query.edit_message_text(
        f"Вы выбрали дату и время: {selected_date} {selected_time}\n\n"
        "Теперь введите имя клиента:"
    )
    
    return CLIENT_NAME

async def client_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода имени клиента"""
    client_name = update.message.text
    context.user_data["client_name"] = client_name
    
    logger.debug(f"User {update.effective_user.id} entered client name: {client_name}")
    
    await update.message.reply_text("Введите номер автомобиля:")
    
    return CAR_NUMBER

async def car_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода номера автомобиля"""
    car_number = update.message.text
    context.user_data["car_number"] = car_number
    
    logger.debug(f"User {update.effective_user.id} entered car number: {car_number}")
    
    await update.message.reply_text("Введите VIN номер автомобиля:")
    
    return VIN_NUMBER

async def vin_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода VIN номера"""
    vin_number = update.message.text
    context.user_data["vin_number"] = vin_number
    
    logger.debug(f"User {update.effective_user.id} entered VIN number: {vin_number}")
    
    await update.message.reply_text(
        "Введите номер телефона клиента (на этот номер будет отправлена диагностическая карта):"
    )
    
    return CLIENT_PHONE

async def client_phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода номера телефона клиента и формирование карточки ТО"""
    client_phone = update.message.text
    context.user_data["client_phone"] = client_phone
    
    logger.debug(f"User {update.effective_user.id} entered client phone: {client_phone}")
    
    # Формируем итоговую информацию о бронировании
    category = context.user_data["booking_category"]
    station_name = context.user_data["station_name"]
    station_address = context.user_data["station_address"]
    appointment_time = context.user_data["appointment_time"]
    total_price = context.user_data["total_price"]
    has_defects = context.user_data["has_defects"]
    defect_type = context.user_data["defect_type"]
    defect_description = context.user_data["defect_description"]
    
    # Формируем текст подтверждения
    confirmation_text = (
        "🔍 Информация о бронировании:\n\n"
        f"🚗 Категория ТС: {category}\n"
        f"🏢 СТО: {station_name} ({station_address})\n"
        f"📅 Дата и время: {appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"💰 Стоимость: {total_price} руб.\n\n"
        f"👤 Имя клиента: {context.user_data['client_name']}\n"
        f"🚘 Номер автомобиля: {context.user_data['car_number']}\n"
        f"🔢 VIN номер: {context.user_data['vin_number']}\n"
        f"📱 Телефон клиента: {client_phone}\n"
    )
    
    if has_defects:
        confirmation_text += f"\n🔧 Дефекты: {defect_type}\n"
        confirmation_text += f"📝 Описание: {defect_description}\n"
    else:
        confirmation_text += "\n✅ Дефекты отсутствуют\n"
    
    # Создаем клавиатуру для подтверждения бронирования
    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm_booking"),
            InlineKeyboardButton("Отмена", callback_data="cancel_booking")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        confirmation_text,
        reply_markup=reply_markup
    )
    
    return CONFIRM_BOOKING

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение бронирования и создание карточки ТО"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_booking":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    
    # Генерируем номер карточки ТО
    current_date = datetime.now().strftime("%d%m%Y")
    
    db = next(get_db())
    try:
        # Получаем агента
        agent = db.query(Agent).filter(Agent.telegram_id == user_id).first()
        if not agent:
            await query.edit_message_text("Ошибка: Агент не найден. Пожалуйста, пройдите регистрацию заново.")
            return ConversationHandler.END
        
        # Получаем количество записей этого агента за сегодня
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_bookings_count = db.query(TOCard).filter(
            TOCard.agent_id == agent.id,
            TOCard.created_at >= today_start
        ).count()
        
        # Формируем номер карточки ТО: дата + id агента*10 + порядковый номер записи
        booking_number = f"{current_date}{agent.id * 10}{today_bookings_count + 1}"
        
        # Создаем новую карточку ТО
        to_card = TOCard(
            card_number=booking_number,
            agent_id=agent.id,
            category=context.user_data["booking_category"],
            sto_name=context.user_data["station_name"],
            has_defects=context.user_data["has_defects"],
            defect_type=context.user_data["defect_type"],
            defect_description=context.user_data["defect_description"],
            appointment_time=context.user_data["appointment_time"],
            client_name=context.user_data["client_name"],
            car_number=context.user_data["car_number"],
            vin_number=context.user_data["vin_number"],
            client_phone=context.user_data["client_phone"],
            total_price=context.user_data["total_price"],
            status="pending"
        )
        
        db.add(to_card)
        db.commit()
        
        logger.info(f"User {user_id} created TO card: {booking_number}")
        
        await query.edit_message_text(
            f"✅ Бронирование успешно завершено!\n\n"
            f"📋 Номер карточки ТО: {booking_number}\n\n"
            f"Информация о бронировании добавлена в ваш список записей. "
            f"Статус записи будет обновлен после прохождения ТО."
        )
        
        # Очищаем данные бронирования
        for key in list(context.user_data.keys()):
            if key.startswith("booking_") or key in [
                "station_id", "station_name", "station_address", "base_price", 
                "total_price", "has_defects", "defect_type", "defect_description", 
                "appointment_time", "selected_date", "client_name", "car_number", 
                "vin_number", "client_phone"
            ]:
                del context.user_data[key]
        
        return ConversationHandler.END
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating TO card: {e}")
        
        await query.edit_message_text(
            f"❌ Ошибка при создании карточки ТО: {str(e)}\n"
            "Пожалуйста, попробуйте снова позже."
        )
        
        return ConversationHandler.END
    
    finally:
        db.close()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена бронирования"""
    if update.callback_query:
        await update.callback_query.edit_message_text("Бронирование отменено.")
    else:
        await update.message.reply_text("Бронирование отменено.")
    
    # Очищаем данные бронирования
    for key in list(context.user_data.keys()):
        if key.startswith("booking_") or key in [
            "station_id", "station_name", "station_address", "base_price", 
            "total_price", "has_defects", "defect_type", "defect_description", 
            "appointment_time", "selected_date", "client_name", "car_number", 
            "vin_number", "client_phone"
        ]:
            del context.user_data[key]
    
    return ConversationHandler.END

def get_booking_handler():
    """Создание обработчика разговора для бронирования"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_booking_category_b, pattern=r'^to_category_B$'),
            CallbackQueryHandler(start_booking_category_c, pattern=r'^to_category_C$'),
            CallbackQueryHandler(start_booking_category_e, pattern=r'^to_category_E$')
        ],
        states={
            SELECT_STO: [
                CallbackQueryHandler(select_sto, pattern=r'^sto_'),
                CallbackQueryHandler(cancel, pattern=r'^cancel_booking$')
            ],
            CONFIRM_CATEGORY_PRICE: [
                CallbackQueryHandler(confirm_category_price, pattern=r'^confirm_price$'),
                CallbackQueryHandler(cancel, pattern=r'^cancel_booking$')
            ],
            CHECK_DEFECTS: [
                CallbackQueryHandler(check_defects, pattern=r'^defects_'),
                CallbackQueryHandler(cancel, pattern=r'^cancel_booking$')
            ],
            SPECIFY_DEFECTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, specify_defects)
            ],
            SELECT_TIME: [
                CallbackQueryHandler(select_date, pattern=r'^date_'),
                CallbackQueryHandler(select_time, pattern=r'^time_'),
                CallbackQueryHandler(select_time_slot, pattern=r'^back_to_date$'),
                CallbackQueryHandler(cancel, pattern=r'^cancel_booking$')
            ],
            CLIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_name_handler)
            ],
            CAR_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, car_number_handler)
            ],
            VIN_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vin_number_handler)
            ],
            CLIENT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client_phone_handler)
            ],
            CONFIRM_BOOKING: [
                CallbackQueryHandler(confirm_booking, pattern=r'^confirm_booking$'),
                CallbackQueryHandler(cancel, pattern=r'^cancel_booking$')
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=r'^cancel_booking$')
        ],
        name="booking"
    ) 