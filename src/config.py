import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

print("[CONFIG] Загрузка конфигурации...")

class Config:
    # Telegram Configuration
    API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
    PAYMENT_TOKEN = os.getenv('TELEGRAM_PAYMENT_TOKEN')
    CRYPTOBOT_API_KEY = os.environ.get("CRYPTOBOT_API_KEY")
    LEMONSQUEEZY_API_KEY = os.environ.get("LEMONSQUEEZY_API_KEY")
    
    print(f"[CONFIG] TELEGRAM_API_TOKEN: {'Установлен' if API_TOKEN else 'НЕ УСТАНОВЛЕН'}")
    print(f"[CONFIG] CRYPTOBOT_API_KEY: {'Установлен' if CRYPTOBOT_API_KEY else 'НЕ УСТАНОВЛЕН'}")
    print(f"[CONFIG] LEMONSQUEEZY_API_KEY: {'Установлен' if LEMONSQUEEZY_API_KEY else 'НЕ УСТАНОВЛЕН'}")
    
    if LEMONSQUEEZY_API_KEY:
        print(f"[CONFIG] LEMONSQUEEZY_API_KEY (первые 10 символов): {LEMONSQUEEZY_API_KEY[:10]}...")
    
    # YooKassa Configuration
    YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
    YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
    
    # Google Drive Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    
    # Database Configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'users.db')
    
    # Admin Configuration
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '486355497'))
    
    # File Configuration
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '50'))
    SUPPORTED_AUDIO = ['mp3', 'wav', 'ogg', 'm4a']
    SUPPORTED_VIDEO = ['mp4', 'mov', 'avi']
    
    # Whisper Configuration - обновлено для максимального качества
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'large-v3')  # large-v3 для максимального качества
    WHISPER_OPTIONS = {
        'fp16': False,  # Отключаем для лучшей точности
        'temperature': 0.0,  # Нулевая температура для детерминированных результатов
        'compression_ratio_threshold': 2.4,
        'logprob_threshold': -1.0,
        'no_speech_threshold': 0.6,
        'condition_on_previous_text': True,
        'initial_prompt': None
    }
    
    # Whisper Configuration для тайм-кодов
    WHISPER_TIMESTAMPS_OPTIONS = {
        'fp16': False,
        'temperature': 0.0,
        'compression_ratio_threshold': 2.4,
        'logprob_threshold': -1.0,
        'no_speech_threshold': 0.6,
        'condition_on_previous_text': True,
        'initial_prompt': None,
        'word_timestamps': True  # Включаем тайм-коды для слов
    }
    
    # API Configuration для платных сервисов
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_CLOUD_CREDENTIALS = os.getenv('GOOGLE_CLOUD_CREDENTIALS')
    AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
    AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION')
    ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
    
    # Выбор провайдера транскрипции
    TRANSCRIPTION_PROVIDER = os.getenv('TRANSCRIPTION_PROVIDER', 'whisper_local')  # whisper_local, openai, google, azure, assemblyai
    
    # Поддерживаемые платформы для транскрипции
    SUPPORTED_PLATFORMS = [
        "YouTube",
        "Rutube", 
        "VK",
        "Instagram",
        "TikTok",
        "Twitter/X",
        "Facebook",
        "LinkedIn",
        "Tumblr",
        "Reddit",
        "Twitch",
        "Vimeo",
        "Dailymotion",
        "Bilibili",
        "Odysee",
        "PeerTube",
        "и другие платформы"
    ]
    
    # Тарифы и скидки теперь хранятся в базе данных
    
    FREE_FILE_LIMIT_MB = 150
    
    CHUNK_LENGTH = 300  # длина чанка в секундах для обработки (5 минут)
    
    @classmethod
    def validate_config(cls):
        """Проверяет, что все необходимые переменные окружения установлены"""
        required_vars = [
            'TELEGRAM_API_TOKEN',
            'TELEGRAM_PAYMENT_TOKEN',
            'YOOKASSA_SHOP_ID',
            'YOOKASSA_SECRET_KEY',
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        
        return True

print("[CONFIG] Конфигурация загружена") 