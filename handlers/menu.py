from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.logger import logger
from utils.roles import registered_required, admin_required, get_user_role
from database.models import UserRole
from database.database import get_db
from handlers.admin import admin_agents_list, agent_details, agent_info, agent_action, agent_archive
from handlers.my_bookings import show_my_bookings, view_card_details
from handlers.archive import show_archive
from handlers.admin_approvals import show_pending_approvals, handle_approve_card

@registered_required
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start для зарегистрированных пользователей"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} accessed main menu")
    
    # Определяем роль пользователя
    db = next(get_db())
    try:
        role = await get_user_role(user_id, db)
        
        if role == UserRole.ADMIN:
            await show_admin_menu(update, context)
        else:
            await show_agent_menu(update, context)
    finally:
        db.close()

async def show_agent_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню для агента"""
    keyboard = [
        [
            InlineKeyboardButton("Запись на ТО (категория B)", callback_data="to_category_B"),
            InlineKeyboardButton("Запись на ТО (категория C)", callback_data="to_category_C")
        ],
        [
            InlineKeyboardButton("Запись на ТО (категория E)", callback_data="to_category_E"),
            InlineKeyboardButton("Мои записи", callback_data="my_bookings")
        ],
        [
            InlineKeyboardButton("Архив", callback_data="archive")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Главное меню - выберите действие:",
        reply_markup=reply_markup
    )

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню для администратора"""
    keyboard = [
        [
            InlineKeyboardButton("Запись на ТО (категория B)", callback_data="to_category_B"),
            InlineKeyboardButton("Запись на ТО (категория C)", callback_data="to_category_C")
        ],
        [
            InlineKeyboardButton("Запись на ТО (категория E)", callback_data="to_category_E"),
            InlineKeyboardButton("Мои записи", callback_data="my_bookings")
        ],
        [
            InlineKeyboardButton("Архив", callback_data="archive"),
            InlineKeyboardButton("Админ панель", callback_data="admin_panel")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Главное меню (Администратор) - выберите действие:",
        reply_markup=reply_markup
    )

@admin_required
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать панель администратора"""
    keyboard = [
        [
            InlineKeyboardButton("Согласование", callback_data="admin_approve"),
            InlineKeyboardButton("Список агентов", callback_data="admin_agents_list")
        ],
        [
            InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отвечаем в зависимости от типа обновления
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Панель администратора - выберите действие:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Панель администратора - выберите действие:",
            reply_markup=reply_markup
        )

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки меню"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    callback_data = query.data
    logger.debug(f"User {user_id} clicked {callback_data}")
    
    # Обработка кнопок меню
    if callback_data == "admin_panel":
        await admin_panel(update, context)
    elif callback_data == "admin_approve":
        await show_pending_approvals(update, context)
    elif callback_data.startswith("approvals_page_"):
        page = int(callback_data.split("_")[2])
        await show_pending_approvals(update, context, page)
    elif callback_data.startswith("approve_card_"):
        await handle_approve_card(update, context)
    elif callback_data == "admin_agents_list":
        await admin_agents_list(update, context)
    elif callback_data.startswith("agents_page_"):
        page = int(callback_data.split("_")[2])
        await admin_agents_list(update, context, page)
    elif callback_data.startswith("agent_") and len(callback_data.split("_")) == 2:
        await agent_details(update, context)
    elif callback_data.startswith("agent_info_"):
        await agent_info(update, context)
    elif callback_data.startswith("agent_archive_"):
        # Проверяем, содержит ли callback данные о странице
        parts = callback_data.split("_")
        if len(parts) > 3 and parts[3] == "page":
            page = int(parts[4])
            await agent_archive(update, context, page)
        else:
            await agent_archive(update, context)
    elif callback_data.startswith("agent_action_"):
        await agent_action(update, context)
    elif callback_data == "my_bookings":
        await show_my_bookings(update, context)
    elif callback_data.startswith("view_card_"):
        await view_card_details(update, context)
    elif callback_data == "archive":
        await show_archive(update, context)
    elif callback_data.startswith("archive_page_"):
        page = int(callback_data.split("_")[2])
        await show_archive(update, context, page)
    elif callback_data == "back_to_main":
        # Определяем роль пользователя
        db = next(get_db())
        try:
            role = await get_user_role(user_id, db)
            
            if role == UserRole.ADMIN:
                keyboard = [
                    [
                        InlineKeyboardButton("Запись на ТО (категория B)", callback_data="to_category_B"),
                        InlineKeyboardButton("Запись на ТО (категория C)", callback_data="to_category_C")
                    ],
                    [
                        InlineKeyboardButton("Запись на ТО (категория E)", callback_data="to_category_E"),
                        InlineKeyboardButton("Мои записи", callback_data="my_bookings")
                    ],
                    [
                        InlineKeyboardButton("Архив", callback_data="archive"),
                        InlineKeyboardButton("Админ панель", callback_data="admin_panel")
                    ]
                ]
            else:
                keyboard = [
                    [
                        InlineKeyboardButton("Запись на ТО (категория B)", callback_data="to_category_B"),
                        InlineKeyboardButton("Запись на ТО (категория C)", callback_data="to_category_C")
                    ],
                    [
                        InlineKeyboardButton("Запись на ТО (категория E)", callback_data="to_category_E"),
                        InlineKeyboardButton("Мои записи", callback_data="my_bookings")
                    ],
                    [
                        InlineKeyboardButton("Архив", callback_data="archive")
                    ]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "Главное меню - выберите действие:",
                reply_markup=reply_markup
            )
        finally:
            db.close()
    # Остальные callback обрабатываются в соответствующих ConversationHandler 