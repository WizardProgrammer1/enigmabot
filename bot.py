# Entry point for the OOP-based Telegram transcription bot

import asyncio
import sys
import traceback
from src.telegram_bot import TelegramBot
from src.config import Config

def main():
    try:
        # Проверяем конфигурацию перед запуском
        Config.validate_config()
        print("✅ Конфигурация проверена успешно")
        # Создаем и запускаем бота
        print("🔧 Создание экземпляра TelegramBot...")
        bot = TelegramBot()
        print("🚀 Запуск бота...")
        bot.run()
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\n📋 Убедитесь, что создан файл .env со следующими переменными:")
        print("TELEGRAM_API_TOKEN=ваш_токен_бота")
        print("TELEGRAM_PAYMENT_TOKEN=ваш_платежный_токен")
        print("YOOKASSA_SHOP_ID=ваш_shop_id")
        print("YOOKASSA_SECRET_KEY=ваш_секретный_ключ")
        print("GOOGLE_CLIENT_ID=ваш_google_client_id")
        print("GOOGLE_CLIENT_SECRET=ваш_google_client_secret")
        print("\n📄 См. файл env_example.txt для примера")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        print("=== ДЕТАЛЬНАЯ ОШИБКА ===")
        print(f"Тип ошибки: {type(e).__name__}")
        print("Полный стек вызовов:")
        traceback.print_exc()
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main() 