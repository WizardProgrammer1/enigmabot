# 🚀 Инструкция по установке и запуску Telegram бота на сервере

## 📋 Содержание
- [Требования к серверу](#требования-к-серверу)
- [Подготовка сервера](#подготовка-сервера)
- [Установка зависимостей](#установка-зависимостей)
- [Настройка конфигурации](#настройка-конфигурации)
- [Настройка Google Cloud](#настройка-google-cloud)
- [Настройка базы данных](#настройка-базы-данных)
- [Запуск бота](#запуск-бот)
- [Настройка автозапуска](#настройка-автозапуска)
- [Мониторинг и логи](#мониторинг-и-логи)
- [Обновление бота](#обновление-бота)
- [Устранение неполадок](#устранение-неполадок)

## 🖥️ Требования к серверу

### Минимальные требования:
- **ОС**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **RAM**: 4 GB
- **CPU**: 2 ядра
- **Диск**: 20 GB свободного места
- **Сеть**: Стабильное интернет-соединение

### Рекомендуемые требования:
- **ОС**: Ubuntu 22.04 LTS
- **RAM**: 8 GB
- **CPU**: 4 ядра
- **Диск**: 50 GB SSD
- **Сеть**: Высокоскоростное соединение

## 🔧 Подготовка сервера

### 1. Обновление системы
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Установка необходимых пакетов
```bash
sudo apt install -y python3 python3-pip python3-venv git curl wget ffmpeg
```

### 3. Установка Python 3.11 (если нужно)
```bash
# Для Ubuntu/Debian
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Для CentOS/RHEL
sudo yum install python3.11 python3.11-pip
```

## 📦 Установка зависимостей

### 1. Клонирование репозитория
```bash
git clone https://github.com/your-username/your-bot-repo.git
cd your-bot-repo
```

### 2. Создание виртуального окружения
```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Установка Python зависимостей
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Установка системных зависимостей для Whisper
```bash
# Для CUDA (если есть GPU)
sudo apt install nvidia-cuda-toolkit

# Для CPU
sudo apt install build-essential
```

## ⚙️ Настройка конфигурации

### 1. Создание .env файла
```bash
cp env_example.txt .env
nano .env
```

### 2. Заполнение переменных окружения
```env
# Telegram Bot Configuration
TELEGRAM_API_TOKEN=your_telegram_bot_token_here
TELEGRAM_PAYMENT_TOKEN=your_telegram_payment_token_here

# YooKassa Configuration (для РФ)
YOOKASSA_SHOP_ID=your_yookassa_shop_id_here
YOOKASSA_SECRET_KEY=your_yookassa_secret_key_here

# Google Drive API Configuration
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# Google Cloud Configuration
GOOGLE_CLOUD_CREDENTIALS=/path/to/your/google-credentials.json
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name

# Database Configuration
DATABASE_PATH=users.db

# Admin Configuration
ADMIN_USER_ID=your_admin_user_id_here

# Security Configuration
MAX_FILE_SIZE_MB=50

# Transcription Provider
TRANSCRIPTION_PROVIDER=google
```

## 🔐 Настройка Google Cloud

### 1. Создание проекта в Google Cloud Console
1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Запишите ID проекта

### 2. Включение API
```bash
# Установка Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Включение необходимых API
gcloud services enable speech.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable drive.googleapis.com
```

### 3. Создание сервисного аккаунта
```bash
# Создание сервисного аккаунта
gcloud iam service-accounts create bot-service-account \
    --display-name="Bot Service Account"

# Получение email сервисного аккаунта
SA_EMAIL=$(gcloud iam service-accounts list --filter="displayName:Bot Service Account" --format="value(email)")

# Привязка ролей
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/speech.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/drive.admin"
```

### 4. Создание ключа сервисного аккаунта
```bash
# Создание JSON ключа
gcloud iam service-accounts keys create google-credentials.json \
    --iam-account=$SA_EMAIL

# Перемещение ключа в проект
mv google-credentials.json /path/to/your/bot/
chmod 600 /path/to/your/bot/google-credentials.json
```

### 5. Создание Cloud Storage bucket
```bash
# Создание bucket для временных файлов
gsutil mb gs://your-bucket-name
gsutil iam ch serviceAccount:$SA_EMAIL:objectAdmin gs://your-bucket-name
```

## 🗄️ Настройка базы данных

### 1. Инициализация базы данных
```bash
# Активация виртуального окружения
source venv/bin/activate

# Инициализация базы данных
python init_db_only.py
```

### 2. Проверка базы данных
```bash
# Проверка структуры базы
sqlite3 users.db ".schema"
```

## 🚀 Запуск бота

### 1. Тестовый запуск
```bash
# Активация виртуального окружения
source venv/bin/activate

# Запуск бота
python bot.py
```

### 2. Проверка работы
- Отправьте сообщение боту в Telegram
- Проверьте логи на наличие ошибок
- Убедитесь, что бот отвечает

## 🔄 Настройка автозапуска

### 1. Создание systemd сервиса
```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

### 2. Содержимое файла сервиса
```ini
[Unit]
Description=Telegram Bot Service
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

### 3. Активация сервиса
```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable telegram-bot

# Запуск сервиса
sudo systemctl start telegram-bot

# Проверка статуса
sudo systemctl status telegram-bot
```

### 4. Управление сервисом
```bash
# Остановка
sudo systemctl stop telegram-bot

# Перезапуск
sudo systemctl restart telegram-bot

# Просмотр логов
sudo journalctl -u telegram-bot -f
```

## 📊 Мониторинг и логи

### 1. Настройка ротации логов
```bash
sudo nano /etc/logrotate.d/telegram-bot
```

```conf
/path/to/your/bot/bot.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 your-username your-username
    postrotate
        systemctl reload telegram-bot
    endscript
}
```

### 2. Мониторинг ресурсов
```bash
# Установка htop для мониторинга
sudo apt install htop

# Мониторинг в реальном времени
htop
```

### 3. Настройка алертов
```bash
# Создание скрипта для проверки состояния
nano /path/to/your/bot/health_check.sh
```

```bash
#!/bin/bash
if ! systemctl is-active --quiet telegram-bot; then
    echo "Bot is down! Restarting..."
    systemctl restart telegram-bot
    # Здесь можно добавить уведомление в Telegram
fi
```

```bash
chmod +x /path/to/your/bot/health_check.sh

# Добавление в crontab
crontab -e
# Добавить строку:
# */5 * * * * /path/to/your/bot/health_check.sh
```

## 🔄 Обновление бота

### 1. Создание скрипта обновления
```bash
nano /path/to/your/bot/update.sh
```

```bash
#!/bin/bash
cd /path/to/your/bot

# Остановка бота
sudo systemctl stop telegram-bot

# Обновление кода
git pull origin main

# Обновление зависимостей
source venv/bin/activate
pip install -r requirements.txt

# Запуск бота
sudo systemctl start telegram-bot

echo "Bot updated successfully!"
```

```bash
chmod +x /path/to/your/bot/update.sh
```

### 2. Автоматическое обновление
```bash
# Добавление в crontab для ежедневного обновления
crontab -e
# Добавить строку:
# 0 3 * * * /path/to/your/bot/update.sh
```

## 🛠️ Устранение неполадок

### 1. Проверка логов
```bash
# Логи systemd
sudo journalctl -u telegram-bot -f

# Логи приложения
tail -f /path/to/your/bot/bot.log
```

### 2. Частые проблемы

#### Проблема: Бот не запускается
```bash
# Проверка зависимостей
source venv/bin/activate
python -c "import aiogram; print('aiogram OK')"

# Проверка токена
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Token:', os.getenv('TELEGRAM_API_TOKEN')[:10] + '...')"
```

#### Проблема: Ошибки Google API
```bash
# Проверка Google credentials
python -c "from google.cloud import speech; print('Google API OK')"

# Проверка bucket
gsutil ls gs://your-bucket-name
```

#### Проблема: Недостаточно памяти
```bash
# Увеличение swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3. Восстановление из резервной копии
```bash
# Создание резервной копии
cp users.db users.db.backup

# Восстановление
cp users.db.backup users.db
```

## 📞 Поддержка

### Полезные команды для диагностики:
```bash
# Статус сервиса
sudo systemctl status telegram-bot

# Использование ресурсов
top -p $(pgrep -f bot.py)

# Свободное место на диске
df -h

# Использование памяти
free -h

# Сетевые соединения
netstat -tulpn | grep python
```

### Контакты для поддержки:
- **Telegram**: @your_support_username
- **Email**: support@your-domain.com
- **Документация**: https://your-docs-url.com

---

## ✅ Чек-лист установки

- [ ] Сервер подготовлен и обновлен
- [ ] Python 3.11 установлен
- [ ] Зависимости установлены
- [ ] .env файл настроен
- [ ] Google Cloud настроен
- [ ] База данных инициализирована
- [ ] Бот запускается вручную
- [ ] Systemd сервис создан и запущен
- [ ] Автозапуск настроен
- [ ] Логи настроены
- [ ] Мониторинг настроен
- [ ] Резервное копирование настроено

**🎉 Поздравляем! Ваш Telegram бот успешно установлен и настроен на сервере!** 