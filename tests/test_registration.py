import pytest
from unittest.mock import AsyncMock, patch
from telegram import Update, Message, User as TelegramUser
from telegram.ext import ContextTypes, ConversationHandler
from handlers.registration import register, registration_fullname, registration_company, registration_code
from database.models import User
from config import (
    REGISTRATION_CODE, REGISTRATION_FULLNAME, REGISTRATION_COMPANY, 
    REGISTRATION_CODE_STATE, CHOOSING
)

@pytest.fixture
def mock_update():
    update = AsyncMock(spec=Update)
    update.effective_user = AsyncMock(spec=TelegramUser)
    update.effective_user.id = 123456
    update.effective_user.username = "test_user"
    update.message = AsyncMock(spec=Message)
    return update

@pytest.fixture
def mock_context():
    context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context

@pytest.mark.asyncio
async def test_register_new_user(mock_update, mock_context, mock_db):
    with patch('handlers.registration.SessionLocal', return_value=mock_db):
        result = await register(mock_update, mock_context)
        
        assert result == REGISTRATION_FULLNAME
        mock_update.message.reply_text.assert_called_once()
        assert len(mock_db.added_items) == 1
        assert mock_db.committed

@pytest.mark.asyncio
async def test_register_existing_user(mock_update, mock_context, mock_db):
    existing_user = User(telegram_id=123456, username="test_user", is_registered=True)
    mock_db.set_query_return(User, existing_user)
    
    with patch('handlers.registration.SessionLocal', return_value=mock_db):
        result = await register(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_registration_fullname_valid(mock_update, mock_context):
    mock_update.message.text = "Иван Иванов"
    result = await registration_fullname(mock_update, mock_context)
    
    assert result == REGISTRATION_COMPANY
    assert mock_context.user_data['full_name'] == "Иван Иванов"
    mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_registration_fullname_invalid(mock_update, mock_context):
    mock_update.message.text = "Ив"
    result = await registration_fullname(mock_update, mock_context)
    
    assert result == REGISTRATION_FULLNAME
    mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_registration_company_valid(mock_update, mock_context):
    mock_context.user_data['full_name'] = "Иван Иванов"
    mock_update.message.text = "ООО Тест"
    result = await registration_company(mock_update, mock_context)
    
    assert result == REGISTRATION_CODE_STATE
    assert mock_context.user_data['company_name'] == "ООО Тест"
    mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_registration_company_invalid(mock_update, mock_context):
    mock_context.user_data['full_name'] = "Иван Иванов"
    mock_update.message.text = "О"
    result = await registration_company(mock_update, mock_context)
    
    assert result == REGISTRATION_COMPANY
    mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_registration_code_valid(mock_update, mock_context, mock_db):
    mock_user = User(telegram_id=123456, username="test_user")
    mock_db.set_query_return(User, mock_user)
    
    with patch('handlers.registration.SessionLocal', return_value=mock_db):
        mock_context.user_data['full_name'] = "Иван Иванов"
        mock_context.user_data['company_name'] = "ООО Тест"
        mock_update.message.text = REGISTRATION_CODE
        
        result = await registration_code(mock_update, mock_context)
        
        assert result == ConversationHandler.END

@pytest.mark.asyncio
async def test_registration_code_invalid(mock_update, mock_context):
    mock_context.user_data['full_name'] = "Иван Иванов"
    mock_context.user_data['company_name'] = "ООО Тест"
    mock_update.message.text = "неверный_код"
    
    result = await registration_code(mock_update, mock_context)
    
    assert result == REGISTRATION_CODE_STATE
    mock_update.message.reply_text.assert_called_once() 