import pytest
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Добавляем корневую директорию проекта в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Настройка переменных окружения для тестов
os.environ['BOT_TOKEN'] = 'test_token'
os.environ['REGISTRATION_CODE'] = 'test_code'

class MockQuery:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.filter_return = self
        self.first_return = return_value
        self.all_return = [return_value] if return_value else []

    def filter(self, *args, **kwargs):
        return self.filter_return

    def first(self):
        return self.first_return

    def all(self):
        return self.all_return

class MockDB:
    def __init__(self):
        self.committed = False
        self.closed = False
        self.added_items = []
        self._query_returns = {}

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True

    def add(self, item):
        self.added_items.append(item)

    def query(self, model):
        return self._query_returns.get(model, MockQuery())

    def set_query_return(self, model, return_value):
        query = MockQuery(return_value)
        self._query_returns[model] = query
        return query

@pytest.fixture
def mock_db():
    return MockDB()

@pytest.fixture(autouse=True)
def mock_env():
    """Фикстура для мокирования переменных окружения"""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('BOT_TOKEN', 'test_token')
        mp.setenv('REGISTRATION_CODE', 'test_code')
        yield 