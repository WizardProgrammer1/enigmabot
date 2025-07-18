# 🚀 Быстрая установка Telegram бота на сервер

## 📋 Что нужно сделать

### 1. Подготовка сервера
```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем нужные пакеты
sudo apt install -y python3 python3-pip python3-venv git ffmpeg
```

### 2. Скачиваем код
```bash
# Клонируем репозиторий
git clone https://github.com/your-username/your-bot-repo.git
cd your-bot-repo

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 3. Настраиваем конфигурацию
```bash
# Копируем пример конфигурации
cp env_example.txt .env

# Редактируем файл
nano .env
```

**Заполните в .env файле:**
```env
TELEGRAM_API_TOKEN=ваш_токен_бота
TELEGRAM_PAYMENT_TOKEN=ваш_токен_платежей
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_секретный_ключ
GOOGLE_CLIENT_ID=ваш_google_client_id
GOOGLE_CLIENT_SECRET=ваш_google_client_secret
ADMIN_USER_ID=ваш_id_в_telegram
```

### 4. Настраиваем Google Cloud (если используете Google Speech API)

#### Создаем проект в Google Cloud Console:
1. Идите на https://console.cloud.google.com/
2. Создайте новый проект
3. Включите API: Speech-to-Text, Cloud Storage, Drive API

#### Создаем сервисный аккаунт:
```bash
# Устанавливаем Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Создаем сервисный аккаунт
gcloud iam service-accounts create bot-account --display-name="Bot Account"

# Получаем email
SA_EMAIL=$(gcloud iam service-accounts list --filter="displayName:Bot Account" --format="value(email)")

# Даем права
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:$SA_EMAIL" --role="roles/speech.admin"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:$SA_EMAIL" --role="roles/storage.admin"

# Создаем ключ
gcloud iam service-accounts keys create google-credentials.json --iam-account=$SA_EMAIL

# Создаем bucket
gsutil mb gs://your-bucket-name
```

#### Добавляем в .env:
```env
GOOGLE_CLOUD_CREDENTIALS=/path/to/your/bot/google-credentials.json
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name
TRANSCRIPTION_PROVIDER=google
```

### 5. Инициализируем базу данных
```bash
# Активируем окружение
source venv/bin/activate

# Создаем базу
python init_db_only.py
```

### 6. Тестируем запуск
```bash
# Запускаем бота
python bot.py
```

**Проверьте:**
- Отправьте боту сообщение в Telegram
- Посмотрите логи на ошибки
- Убедитесь что бот отвечает

### 7. Настраиваем автозапуск

#### Создаем systemd сервис:
```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

**Вставляем:**
```ini
[Unit]
Description=Telegram Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/your/bot
Environment=PATH=/path/to/your/bot/venv/bin
ExecStart=/path/to/your/bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Запускаем сервис:
```bash
# Перезагружаем systemd
sudo systemctl daemon-reload

# Включаем автозапуск
sudo systemctl enable telegram-bot

# Запускаем
sudo systemctl start telegram-bot

# Проверяем статус
sudo systemctl status telegram-bot
```

## 🔧 Управление ботом

### Основные команды:
```bash
# Остановить бота
sudo systemctl stop telegram-bot

# Запустить бота
sudo systemctl start telegram-bot

# Перезапустить бота
sudo systemctl restart telegram-bot

# Посмотреть логи
sudo journalctl -u telegram-bot -f

# Посмотреть статус
sudo systemctl status telegram-bot
```

### Обновление бота:
```bash
cd /path/to/your/bot
sudo systemctl stop telegram-bot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start telegram-bot
```

## 🛠️ Если что-то не работает

### Проверяем логи:
```bash
# Логи systemd
sudo journalctl -u telegram-bot -f

# Логи приложения
tail -f /path/to/your/bot/bot.log
```

### Частые проблемы:

**Бот не запускается:**
```bash
# Проверяем токен
source venv/bin/activate
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Token:', os.getenv('TELEGRAM_API_TOKEN')[:10] + '...')"
```

**Ошибки Google API:**
```bash
# Проверяем credentials
ls -la google-credentials.json
python -c "from google.cloud import speech; print('Google API OK')"
```

**Недостаточно памяти:**
```bash
# Создаем swap файл
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## ✅ Чек-лист

- [ ] Сервер обновлен
- [ ] Python и зависимости установлены
- [ ] Код скачан
- [ ] .env файл настроен
- [ ] Google Cloud настроен (если нужно)
- [ ] База данных создана
- [ ] Бот запускается вручную
- [ ] Systemd сервис создан
- [ ] Бот работает в фоне

**🎉 Готово! Бот работает на сервере!** 