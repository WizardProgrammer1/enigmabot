# Настройка Lemon Squeezy для оплаты зарубежными картами

## Что уже настроено

✅ **Код интеграции готов** - добавлен класс `LemonSqueezyClient` и обработчики  
✅ **Product ID**: `570647` - используется для создания динамических checkout  
✅ **API ключ**: Уже добавлен в конфигурацию  

## Что нужно сделать

### 1. Добавить переменную окружения

Добавьте в файл `.env`:

```env
LEMONSQUEEZY_API_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiI5NGQ1OWNlZi1kYmI4LTRlYTUtYjE3OC1kMjU0MGZjZDY5MTkiLCJqdGkiOiIyYmE0MWVkMTQzOTgxNGI5ODM1YTNkN2I3YjVlZTRhYjk3OWM4YWZhYzFjZWM1YTA2NjBmNTQ1ZDQzNjNiZjQxMGVhYThkZTAwMDg3MDY1YSIsImlhdCI6MTc1MTgyOTU2OS45NDY1MywibmJmIjoxNzUxODI5NTY5Ljk0NjUzMywiZXhwIjoyMDY3MzYyMzY5Ljg5NTc5OCwic3ViIjoiNTE2NTk3NCIsInNjb3BlcyI6W119.WG_9A38OZpiQC-4Hj648VYJIHvRLHQ9CcfYqR2Jd7ApOY5beY6RY8s0bqbN4tu_1YDFy5t8FYHGW7Cs9GKJGQ0njwFkSh2vlq7TEM-We_mDrvtL23gmOLhU8Gz4We2V-ECSxjOneaE3WX-JERJMRGhDu2MtmpyuV2w0VKZPGAMuCBXSPKX07J7k4tPdL0uITCSfSHM2GiUv5fS2YKCsV3SheL2yP0sKgcih117CDd9-5TfVLLEfdIiP2UQWPBRN-M0Te3OvXLc3IaG9PvxKR_v_tw_P7kkp0Tn_i97CqpBNNpHeL8nosD9NaciP_7VnmuRrOvNK95mwd8LHVcnF7ohNWMQ0xfrCXN6FVv3NL-ISNckfDQ0y6CW34qZgACK67aUoVPbL4sO3SfbOkkdJYgpDbthDiua2iYKjBV588UhNfnDA7mjNIh93ytwfqNXIUFqXhCtJZHk328L8ktos2wifxGJN6dffO1JJ_0tbAwhZPCyWpnaZ8hloy1nI-ARsj
```

### 2. Настроить Product в Lemon Squeezy

1. Зайдите в [Lemon Squeezy Dashboard](https://app.lemonsqueezy.com/)
2. Перейдите в раздел "Products"
3. Найдите продукт с ID `570647`
4. Убедитесь, что продукт активен и настроен для приема платежей

### 3. Настроить Webhook (опционально, но рекомендуется)

Для автоматического подтверждения оплаты:

1. В Lemon Squeezy Dashboard перейдите в "Settings" → "Webhooks"
2. Добавьте новый webhook:
   - **URL**: `https://yourdomain.com/lemonsqueezy-webhook`
   - **Events**: `order_created`, `order_refunded`
   - **Secret**: Создайте секретный ключ

3. Добавьте обработчик webhook в код (будет создан позже)

## Как это работает

### Процесс оплаты:

1. **Пользователь выбирает тариф** → нажимает "🌐💳 Зарубежная карта"
2. **Бот рассчитывает цену**:
   - Берет цену из базы данных (в рублях)
   - Применяет скидку (если есть)
   - Конвертирует RUB → USD через CryptoBot API
   - Если курс недоступен, использует фиксированный курс (1 RUB = 0.011 USD)
3. **Создается checkout** через Lemon Squeezy API с динамической ценой
4. **Пользователь получает ссылку** для оплаты картой
5. **После оплаты** пользователь нажимает "✅ Проверить оплату"

### Поддерживаемые карты:
- ✅ Visa
- ✅ MasterCard  
- ✅ American Express
- ✅ Discover
- ✅ И другие международные карты

## Тестирование

### 1. Тестовые карты Lemon Squeezy:
- **Visa**: `4242424242424242`
- **MasterCard**: `5555555555554444`
- **American Express**: `378282246310005`
- **CVV**: Любые 3 цифры
- **Дата**: Любая будущая дата

### 2. Проверка интеграции:
1. Запустите бота
2. Выберите любой тариф
3. Нажмите "🌐💳 Зарубежная карта"
4. Убедитесь, что создается checkout с правильной ценой
5. Протестируйте оплату тестовой картой

## Возможные проблемы

### 1. "API ключ не настроен"
- Проверьте, что `LEMONSQUEEZY_API_KEY` добавлен в `.env`
- Убедитесь, что ключ действителен

### 2. "Ошибка создания checkout"
- Проверьте Product ID в коде (`570647`)
- Убедитесь, что продукт активен в Lemon Squeezy
- Проверьте права API ключа

### 3. "Некорректная сумма"
- Проверьте курс валют через CryptoBot API
- Убедитесь, что цены в базе данных корректны

## Дополнительные настройки

### Для продакшена рекомендуется:

1. **Настроить webhook** для автоматического подтверждения
2. **Добавить логирование** платежей
3. **Настроить уведомления** администратору о платежах
4. **Добавить обработку ошибок** и повторные попытки

### Безопасность:
- API ключ хранится в переменных окружения
- Все платежи логируются в базу данных
- Проверка прав доступа перед созданием платежа 