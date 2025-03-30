# API Документация STO Bot

## Общая информация
API STO Bot предоставляет RESTful интерфейс для взаимодействия с системой записи на СТО.

## Базовый URL
```
https://api.sto-bot.com/v1
```

## Аутентификация
Все запросы должны содержать токен в заголовке:
```
Authorization: Bearer YOUR_API_TOKEN
```

## Endpoints

### Заказы

#### Создание заказа
```http
POST /orders
Content-Type: application/json

{
    "client_name": "Иван Иванов",
    "phone": "+79001234567",
    "service_type": "oil",
    "date": "2024-03-30",
    "time": "14:00",
    "notes": "Замена масла и фильтра"
}
```

#### Получение списка заказов
```http
GET /orders
Query Parameters:
- status: фильтр по статусу
- date: фильтр по дате
- page: номер страницы
- limit: количество записей на странице
```

#### Получение информации о заказе
```http
GET /orders/{order_id}
```

#### Обновление статуса заказа
```http
PATCH /orders/{order_id}
Content-Type: application/json

{
    "status": "completed"
}
```

### Услуги

#### Получение списка доступных услуг
```http
GET /services
```

#### Получение информации об услуге
```http
GET /services/{service_id}
```

## Коды ответов
- 200: Успешный запрос
- 201: Успешно создан
- 400: Ошибка в запросе
- 401: Не авторизован
- 403: Доступ запрещен
- 404: Не найдено
- 500: Внутренняя ошибка сервера

## Обработка ошибок
В случае ошибки API возвращает JSON с описанием:
```json
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Описание ошибки"
    }
}
``` 