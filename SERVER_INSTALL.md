# SERVER_INSTALL.md

## Требования к серверу для Telegram-бота с Whisper, ffmpeg, yt-dlp

### 1. Минимальные и рекомендуемые характеристики

#### CPU
- Для Whisper без GPU: минимум 8 ядер (лучше 16+)
- Для тестов: 4-8 ядер (медленно)

#### GPU (очень желательно)
- NVIDIA GPU с 8+ ГБ VRAM (лучше 16+ ГБ)
- Подойдут: RTX 3060/3070/3080/3090, A4000/A5000/A6000, V100, A100, H100 и др.
- Без GPU Whisper работает в 10-20 раз медленнее

#### RAM
- Минимум 16 ГБ, лучше 32-64 ГБ

#### Диск
- SSD (NVMe желательно), 50-100 ГБ

#### Сеть
- 100 Мбит/с и выше

---

### 2. Примеры конфигураций

#### Для тестов/1-2 пользователя
- CPU: 4-8 ядер
- RAM: 16-32 ГБ
- SSD: 50 ГБ
- GPU: RTX 3060/3070 (8-12 ГБ VRAM) или без GPU (медленно)

#### Для продакшена/нагрузки
- CPU: 8-16 ядер
- RAM: 32-64 ГБ
- SSD: 100+ ГБ
- GPU: RTX 3080/3090/4090, A5000/A6000 (16-24 ГБ VRAM)

---

### 3. Где арендовать сервер
- Hetzner, OVH, Yandex Cloud, Selectel, Gcore, AWS, Azure, Google Cloud — ищите тарифы с GPU
- Для тестов: Colab, Kaggle, Paperspace, RunPod, Vast.ai (почасовая аренда GPU)

---

### 4. Установка и настройка

#### 4.1. Установить зависимости
- Python 3.10+
- ffmpeg (`apt install ffmpeg`)
- yt-dlp (`pip install yt-dlp`)
- Whisper (`pip install openai-whisper` или `pip install git+https://github.com/openai/whisper.git`)
- Всё из requirements.txt (`pip install -r requirements.txt`)

#### 4.2. Установить драйверы и CUDA (если есть GPU)
- NVIDIA драйверы (под вашу карту)
- CUDA Toolkit (обычно 11.x или 12.x)
- cuDNN (если требуется)
- Проверить: `nvidia-smi` и `python -c "import torch; print(torch.cuda.is_available())"`

#### 4.3. Безопасность и сервисы
- Открыть только нужные порты (обычно 22 для SSH)
- Использовать systemd или supervisor для автозапуска бота
- Настроить swap (если мало RAM)
- Следить за логами (лог-файл не должен разрастаться бесконтрольно)

#### 4.4. Telegram Bot Token и конфиги
- Хранить токены и секреты в переменных окружения или .env файле
- Не выкладывать токены в публичный репозиторий

---

### 5. Пример команд для Ubuntu 22.04

```bash
sudo apt update
sudo apt install python3 python3-pip ffmpeg git -y
pip3 install -r requirements.txt
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118  # для CUDA 11.8
pip3 install openai-whisper yt-dlp aiogram aiosqlite
# Проверить GPU:
python3 -c "import torch; print(torch.cuda.is_available())"
```

---

### 6. Мониторинг
- Используйте htop, nvidia-smi, iotop для мониторинга ресурсов
- Следите за логами ошибок и работы бота

---

### 7. Рекомендации
- Планируете рост — берите сервер с запасом по GPU и RAM
- Для экономии — можно разделить обработку (бот на одном сервере, Whisper на другом с GPU)
- Для MVP/тестов — можно начать без GPU, но пользователи будут ждать дольше

---

**Если нужен подбор под ваш бюджет/нагрузку — укажите, сколько пользователей и сколько часов аудио/видео в месяц вы ожидаете!** 