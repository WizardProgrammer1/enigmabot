#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы Lemon Squeezy API
"""

import asyncio
import os
from dotenv import load_dotenv
from src.telegram_bot import LemonSqueezyClient

# Загружаем переменные окружения
load_dotenv()

async def test_lemonsqueezy():
    """Тестирует подключение к Lemon Squeezy API"""
    
    print("🧪 ТЕСТ LEMON SQUEEZY API")
    print("=" * 50)
    
    # Проверяем переменные окружения
    api_key = os.getenv('LEMONSQUEEZY_API_KEY')
    
    print(f"API Key: {'Установлен' if api_key else 'НЕ УСТАНОВЛЕН'}")
    if api_key:
        print(f"API Key (первые 10 символов): {api_key[:10]}...")
    print()
    
    if not api_key:
        print("❌ ОШИБКА: API ключ Lemon Squeezy не установлен!")
        print("Добавьте LEMONSQUEEZY_API_KEY в файл .env")
        return
    
    try:
        # Создаем клиент
        print("🔌 Создание клиента Lemon Squeezy...")
        async with LemonSqueezyClient(api_key) as client:
            print("✅ Клиент создан успешно")
            
            # Получаем список stores
            print("\n🏪 Получение списка stores...")
            stores = await client.get_stores()
            print(f"✅ Найдено stores: {len(stores)}")
            
            store_id = None
            if stores:
                store_id = stores[0]['id']
                print(f"📋 Используем Store ID: {store_id}")
                print(f"   Название: {stores[0]['attributes'].get('name', 'N/A')}")
            else:
                print("❌ ОШИБКА: Не найдено ни одного store!")
                return
            
            # Получаем список variants
            print("\n📦 Получение списка variants...")
            variants = await client.get_variants()
            print(f"✅ Найдено variants: {len(variants)}")
            
            variant_id = "570700"
            if variants:
                # Ищем variant с динамической ценой или используем первый
                for variant in variants:
                    if variant['attributes'].get('has_licenses', False) or variant['attributes'].get('price', 0) == 0:
                        variant_id = variant['id']
                        print(f"📋 Используем Variant ID: {variant_id}")
                        print(f"   Название: {variant['attributes'].get('name', 'N/A')}")
                        print(f"   Цена: {variant['attributes'].get('price', 'Dynamic')}")
                        break
                
                if not variant_id:
                    variant_id = variants[0]['id']
                    print(f"📋 Используем первый Variant ID: {variant_id}")
                    print(f"   Название: {variants[0]['attributes'].get('name', 'N/A')}")
            else:
                print("❌ ОШИБКА: Не найдено ни одного variant!")
                return
            
            # Тестируем создание checkout с правильными ID
            print(f"\n🛒 Тестирование создания checkout...")
            print(f"Store ID: {store_id}")
            print(f"Variant ID: {variant_id}")
            print("Тестовая сумма: $10.00 (1000 центов)")
            
            checkout = await client.create_checkout(
                product_id=variant_id,
                user_id=123456789,
                tariff_id=1,
                amount_usd=10.00,  # $10.00
                description="Тестовый платеж"
            )
            
            print("✅ Checkout создан успешно!")
            print(f"Checkout ID: {checkout['id']}")
            print(f"URL: {checkout['attributes']['url']}")
            
            # Сохраняем правильные ID для использования в боте
            print(f"\n💾 Правильные ID для настройки бота:")
            print(f"Store ID: {store_id}")
            print(f"Variant ID: {variant_id}")
            
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_lemonsqueezy()) 