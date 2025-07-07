#!/usr/bin/env python3
"""
Быстрый тест создания checkout с правильными ID
"""

import asyncio
import os
from dotenv import load_dotenv
from src.telegram_bot import LemonSqueezyClient

# Загружаем переменные окружения
load_dotenv()

async def quick_test():
    """Быстрый тест создания checkout"""
    
    print("⚡ БЫСТРЫЙ ТЕСТ LEMON SQUEEZY")
    print("=" * 40)
    
    api_key = os.getenv('LEMONSQUEEZY_API_KEY')
    
    if not api_key:
        print("❌ API ключ не найден!")
        return
    
    try:
        print("🔌 Создание клиента...")
        async with LemonSqueezyClient(api_key) as client:
            print("✅ Клиент создан")
            
            # Используем правильные ID из предыдущего теста
            store_id = "198522"
            variant_id = "570700"
            
            print(f"🏪 Store ID: {store_id}")
            print(f"📦 Variant ID: {variant_id}")
            print("🛒 Создание checkout...")
            
            checkout = await client.create_checkout(
                product_id=variant_id,
                user_id=123456789,
                tariff_id=1,
                amount_usd=10.00,
                description="Быстрый тест"
            )
            
            print("✅ УСПЕХ! Checkout создан!")
            print(f"ID: {checkout['id']}")
            print(f"URL: {checkout['attributes']['url']}")
            
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")

if __name__ == "__main__":
    asyncio.run(quick_test()) 