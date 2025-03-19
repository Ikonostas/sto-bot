import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from telegram import Update, CallbackQuery, Message, User as TelegramUser
from telegram.ext import ContextTypes, ConversationHandler
from handlers.appointments import (
    new_appointment, enter_client_name, enter_car_number, enter_phone,
    choose_station, choose_date, save_appointment
)
from database.models import User, Station, Appointment
from config import (
    CHOOSING, ENTER_CLIENT_NAME, ENTER_CAR_NUMBER, ENTER_PHONE,
    CHOOSE_STATION, CHOOSE_DATE, CHOOSE_TIME
)

@pytest.fixture
def mock_update():
    update = AsyncMock(spec=Update)
    update.effective_user = AsyncMock(spec=TelegramUser)
    update.effective_user.id = 123456
    update.effective_user.username = "test_user"
    update.message = AsyncMock(spec=Message)
    update.callback_query = AsyncMock(spec=CallbackQuery)
    return update

@pytest.fixture
def mock_context():
    context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context

@pytest.mark.asyncio
async def test_new_appointment_registered_user(mock_update, mock_context, mock_db):
    mock_user = User(telegram_id=123456, username="test_user", is_registered=True)
    mock_db.set_query_return(User, mock_user)
    
    with patch('handlers.appointments.SessionLocal', return_value=mock_db):
        mock_update.callback_query.data = "new_appointment_B"
        result = await new_appointment(mock_update, mock_context)
        
        assert result == ENTER_CLIENT_NAME
        assert mock_context.user_data['vehicle_category'] == "B"
        mock_update.callback_query.edit_message_text.assert_called_once()

@pytest.mark.asyncio
async def test_new_appointment_unregistered_user(mock_update, mock_context, mock_db):
    mock_user = User(telegram_id=123456, username="test_user", is_registered=False)
    mock_db.set_query_return(User, mock_user)
    
    with patch('handlers.appointments.SessionLocal', return_value=mock_db):
        mock_update.callback_query.data = "new_appointment_B"
        result = await new_appointment(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_update.callback_query.edit_message_text.assert_called_once()

@pytest.mark.asyncio
async def test_enter_client_name(mock_update, mock_context):
    mock_context.user_data['vehicle_category'] = "B"
    mock_update.message.text = "Иван Иванов"
    
    result = await enter_client_name(mock_update, mock_context)
    
    assert result == ENTER_CAR_NUMBER
    assert mock_context.user_data['client_name'] == "Иван Иванов"
    mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_enter_car_number(mock_update, mock_context):
    mock_context.user_data['client_name'] = "Иван Иванов"
    mock_update.message.text = "А123БВ777"
    
    result = await enter_car_number(mock_update, mock_context)
    
    assert result == ENTER_PHONE
    assert mock_context.user_data['car_number'] == "А123БВ777"
    mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_enter_phone(mock_update, mock_context, mock_db):
    mock_station = Station(id=1, name="Тестовая станция", category="B")
    mock_db.set_query_return(Station, mock_station)
    
    with patch('handlers.appointments.SessionLocal', return_value=mock_db):
        mock_context.user_data['vehicle_category'] = "B"
        mock_context.user_data['client_name'] = "Иван Иванов"
        mock_context.user_data['car_number'] = "А123БВ777"
        mock_update.message.text = "+79001234567"
        
        result = await enter_phone(mock_update, mock_context)
        
        assert result == CHOOSE_STATION
        assert mock_context.user_data['phone'] == "+79001234567"
        mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_choose_station(mock_update, mock_context):
    mock_context.user_data['vehicle_category'] = "B"
    mock_update.callback_query.data = "station_1"
    
    result = await choose_station(mock_update, mock_context)
    
    assert result == CHOOSE_DATE
    assert mock_context.user_data['station_id'] == 1
    mock_update.callback_query.edit_message_text.assert_called_once()

@pytest.mark.asyncio
async def test_choose_date(mock_update, mock_context):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    mock_context.user_data['station_id'] = 1
    mock_update.callback_query.data = f"date_{tomorrow}"
    
    result = await choose_date(mock_update, mock_context)
    
    assert result == CHOOSE_TIME
    assert mock_context.user_data['date'] == tomorrow
    mock_update.callback_query.edit_message_text.assert_called_once()

@pytest.mark.asyncio
async def test_save_appointment(mock_update, mock_context, mock_db):
    mock_station = Station(id=1, name="Тестовая станция", category="B")
    mock_user = User(id=1, telegram_id=123456, username="test_user")
    mock_db.set_query_return(Station, mock_station)
    mock_db.set_query_return(User, mock_user)
    
    with patch('handlers.appointments.SessionLocal', return_value=mock_db):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        mock_context.user_data.update({
            'station_id': 1,
            'date': tomorrow,
            'client_name': "Иван Иванов",
            'car_number': "А123БВ777",
            'phone': "+79001234567"
        })
        mock_update.callback_query.data = "time_10:00"
        
        result = await save_appointment(mock_update, mock_context)
        
        assert result == CHOOSING
        assert len(mock_db.added_items) == 1
        assert mock_db.committed
        mock_update.callback_query.edit_message_text.assert_called_once() 