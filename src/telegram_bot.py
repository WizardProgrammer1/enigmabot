import asyncio
import datetime
import os
import re
import sys
import uuid
import aiohttp
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from src.config import Config
from src.user_repository import UserRepository
from src.transcriber import Transcriber
from src.logger import Logger
from src.file_handler import FileHandler

# Добавляем логирование для отслеживания ошибки
import traceback

def log_error_with_traceback(error, context=""):
    """Логирует ошибку с полным стеком вызовов"""
    print(f"=== ОШИБКА {context} ===")
    print(f"Тип ошибки: {type(error).__name__}")
    print(f"Сообщение: {error}")
    print("Полный стек вызовов:")
    traceback.print_exc()
    print("=" * 50)

LANGUAGES = [
    ("Русский 🇷🇺", "ru"),
    ("Английский 🇺🇸", "en"),
    ("Украинский 🇺🇦", "uk"),
    ("Казахский 🇰🇿", "kk"),
    ("Французский 🇫🇷", "fr"),
    ("Немецкий 🇩🇪", "de"),
    ("Португальский 🇧🇷", "pt"),
    ("Испанский 🇪🇸", "es"),
    ("Другие языки 🌍", "other"),
]

class TelegramBot:
    def __init__(self):
        print("[INIT] Инициализация TelegramBot...")
        
        if not Config.API_TOKEN:
            raise ValueError("TELEGRAM_API_TOKEN не установлен в переменных окружения")
        
        self.bot = Bot(token=Config.API_TOKEN)
        self.dp = Dispatcher(self.bot)
        self.transcriber = Transcriber()
        self.user_repo = UserRepository()
        self.support_waiting = set()  # Для поддержки
        self.support_topics = {}  # Для тем обращений в поддержке
        self.appeal_waiting = set()  # Для апелляций
        self._register_handlers()
        self.logger = Logger.setup()
        self.file_handler = FileHandler(self.bot)
        self.user_tariff = {}  # user_id -> {'tariff_id': ..., 'payment_id': ...}
        
        # Тестовый режим
        self.test_mode = False
        self.test_logs = []
        self.test_log_file = f"test_logs_{datetime.datetime.now().strftime('%Y-%m-%d')}.txt"
        
        # Загружаем существующие логи из файла
        self._load_test_logs_from_file()
        
        # CryptoBot API ключ
        self.cryptobot_api_key = Config.CRYPTOBOT_API_KEY
        
        # Lemon Squeezy API ключ и Product ID
        self.lemonsqueezy_api_key = Config.LEMONSQUEEZY_API_KEY
        self.lemonsqueezy_product_id = 570700  # Variant ID для динамических цен
        
        print("[INIT] Инициализация завершена")

    def get_main_keyboard(self):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎁 Бонусная генерация")],
                [KeyboardButton(text="👥 Реферальная программа"), KeyboardButton(text="💳 Тарифы")],
                [KeyboardButton(text="🤖 Про сервис"), KeyboardButton(text="🛟 Служба поддержки")],
                [KeyboardButton(text="🌍 Выбрать язык"), KeyboardButton(text="📊 Мои лимиты")],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder='',
            selective=False,
            is_persistent=False
        )

    def get_language_keyboard(self):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=LANGUAGES[0][0]), KeyboardButton(text=LANGUAGES[1][0]), KeyboardButton(text=LANGUAGES[2][0])],
                [KeyboardButton(text=LANGUAGES[3][0]), KeyboardButton(text=LANGUAGES[4][0]), KeyboardButton(text=LANGUAGES[5][0])],
                [KeyboardButton(text=LANGUAGES[6][0]), KeyboardButton(text=LANGUAGES[7][0]), KeyboardButton(text=LANGUAGES[8][0])],
                [KeyboardButton(text="🔙 Назад в меню")],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder='',
            selective=False,
            is_persistent=False
        )

    def get_about_inline(self):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Наш сайт", url="https://ai-level.pro")],
            ]
        )

    def get_tariff_keyboard(self):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🟢 Базовый (1 месяц)"), KeyboardButton(text="🔵 Про (1 месяц)")],
                [KeyboardButton(text="🟢 Базовый (3 месяца)"), KeyboardButton(text="🔵 Про (3 месяца)")],
                [KeyboardButton(text="🟢 Базовый (6 месяцев)"), KeyboardButton(text="🔵 Про (6 месяцев)")],
                [KeyboardButton(text="🟢 Базовый (12 месяцев)"), KeyboardButton(text="🔵 Про (12 месяцев)")],
                [KeyboardButton(text="🎁 Бонусная генерация"), KeyboardButton(text="🔙 Назад в меню")],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder='',
            selective=False,
            is_persistent=False
        )

    def get_payment_keyboard(self):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🇷🇺💳 Карта РФ"), KeyboardButton(text="🌐💳 Зарубежная карта")],
                [KeyboardButton(text="₿ Оплатить через CryptoBot")],
                [KeyboardButton(text="📋 К выбору тарифа"), KeyboardButton(text="🔙 Назад в меню")],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder='',
            selective=False,
            is_persistent=False
        )

    def get_support_keyboard(self):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="❌ Не проходит оплата")],
                [KeyboardButton(text="💡 Идеи по улучшению работы"), KeyboardButton(text="🤝 Предложение по сотрудничеству")],
                [KeyboardButton(text="📝 Другое"), KeyboardButton(text="🔙 Назад в меню")],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder='',
            selective=False,
            is_persistent=False
        )

    def log_test_event(self, event_type, user_id, **kwargs):
        """Логирует событие в тестовом режиме"""
        if not self.test_mode:
            return
            
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'event_type': event_type,
            'user_id': user_id,
            **kwargs
        }
        self.test_logs.append(log_entry)
        
        # Записываем в файл
        try:
            with open(self.test_log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {event_type} | User: {user_id}")
                for key, value in kwargs.items():
                    f.write(f" | {key}: {value}")
                f.write('\n')
        except Exception as e:
            print(f"Ошибка записи в тестовый лог: {e}")

    def _load_test_logs_from_file(self):
        """Загружает логи из файла при инициализации"""
        try:
            if os.path.exists(self.test_log_file):
                with open(self.test_log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Парсим строку лога: [timestamp] event_type | User: user_id | key: value
                    try:
                        # Извлекаем timestamp
                        timestamp_start = line.find('[') + 1
                        timestamp_end = line.find(']')
                        if timestamp_start > 0 and timestamp_end > timestamp_start:
                            timestamp = line[timestamp_start:timestamp_end]
                            
                            # Извлекаем event_type
                            remaining = line[timestamp_end + 1:].strip()
                            parts = remaining.split(' | ')
                            if len(parts) >= 2:
                                event_type = parts[0].strip()
                                user_part = parts[1]
                                
                                # Извлекаем user_id
                                user_id_start = user_part.find('User: ') + 6
                                user_id = user_part[user_id_start:].strip()
                                
                                # Создаем запись лога
                                log_entry = {
                                    'timestamp': timestamp,
                                    'event_type': event_type,
                                    'user_id': user_id
                                }
                                
                                # Добавляем дополнительные параметры
                                for part in parts[2:]:
                                    if ': ' in part:
                                        key, value = part.split(': ', 1)
                                        log_entry[key.strip()] = value.strip()
                                
                                self.test_logs.append(log_entry)
                    except Exception as e:
                        print(f"Ошибка парсинга строки лога: {line}, ошибка: {e}")
                        continue
                        
        except Exception as e:
            print(f"Ошибка загрузки логов из файла: {e}")

    def get_test_logs_summary(self):
        """Формирует красивый отчет тестовых логов"""
        if not self.test_logs:
            return "Тестовые логи пусты"
            
        summary = f"📊 ОТЧЕТ ТЕСТОВЫХ ЛОГОВ\n"
        summary += f"📅 Дата: {datetime.datetime.now().strftime('%Y-%m-%d')}\n"
        summary += f"📝 Всего записей: {len(self.test_logs)}\n\n"
        
        # Группируем по типам событий
        event_counts = {}
        for log in self.test_logs:
            event_type = log['event_type']
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        summary += "📈 СТАТИСТИКА ПО СОБЫТИЯМ:\n"
        for event_type, count in event_counts.items():
            summary += f"  • {event_type}: {count}\n"
        
        summary += "\n🔍 ДЕТАЛЬНЫЕ ЛОГИ:\n"
        summary += "=" * 80 + "\n"
        
        for log in self.test_logs:
            summary += f"[{log['timestamp']}] {log['event_type']} | User: {log['user_id']}"
            for key, value in log.items():
                if key not in ['timestamp', 'event_type', 'user_id']:
                    summary += f" | {key}: {value}"
            summary += "\n"
        
        return summary

    async def init(self):
        try:
            print("INIT STARTED")
            await self.user_repo.init_db()
            print("INIT COMPLETED SUCCESSFULLY")
        except Exception as e:
            log_error_with_traceback(e, "в методе init")
            print(f"Exception in init: {e}")
            raise

    def _register_handlers(self):
        @self.dp.message_handler(commands=["start", "help"])
        async def send_welcome(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            username = getattr(message.from_user, 'username', None)
            if user_id is not None:
                await self.user_repo.upsert_user(user_id, username or "-")
            user = await self.user_repo.get_user(user_id)
            a_rank = user[2] if user and len(user) > 2 else 0
            await message.reply(
                'Выберите язык файла 🌍\n\n(нажмите на кнопку с нужным языком, не пишите текстом!)',
                reply_markup=self.get_language_keyboard()
            )

        @self.dp.message_handler(lambda m: m.text == "🌍 Выбрать язык")
        async def choose_language(message: types.Message):
            if await self.check_ban(message): return
            await message.reply(
                'Выберите язык файла 🌍\n\n(нажмите на кнопку с нужным языком, не пишите текстом!)',
                reply_markup=self.get_language_keyboard()
            )

        @self.dp.message_handler(lambda m: m.text == "🔙 Назад в меню")
        async def back_to_menu(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            a_rank = user[2] if user and len(user) > 2 else 0
            await message.reply('Главное меню', reply_markup=self.get_main_keyboard())

        for lang_name, lang_code in LANGUAGES:
            @self.dp.message_handler(lambda m, ln=lang_name: m.text == ln)
            async def set_language(message: types.Message, lang_code=lang_code, lang_name=lang_name):
                if await self.check_ban(message): return
                user_id = getattr(message.from_user, 'id', None)
                if user_id is not None:
                    await self.user_repo.update_language(user_id, lang_code)
                user = await self.user_repo.get_user(user_id)
                a_rank = user[2] if user and len(user) > 2 else 0
                await message.reply(f'Язык для распознавания установлен: {lang_name}', reply_markup=self.get_main_keyboard())

        @self.dp.message_handler(lambda m: m.text == "💳 Тарифы")
        async def tariffs(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            if not user:
                await message.reply('Пожалуйста, нажмите СТАРТ для начала работы.')
                return
            sub = user[3]
            sub_rank = user[4]
            sub_time = user[5]
            if sub == 0:
                status = 'Ваша подписка: Бесплатная'
            elif sub_rank == 1:
                status = f'Ваша подписка: Базовый до {sub_time}'
            elif sub_rank == 2:
                status = f'Ваша подписка: Про до {sub_time}'
            else:
                status = 'Ваша подписка: Неизвестно'
            # --- Динамический вывод тарифов ---
            tariffs = await self.user_repo.get_all_tariffs()
            import datetime
            import aiosqlite
            now = datetime.datetime.now().isoformat()
            def format_price(old, new, percent, end_time):
                if percent > 0:
                    end_str = datetime.datetime.fromisoformat(end_time).strftime('%d.%m.%Y %H:%M')
                    return f"<s>{old}₽</s> {new}₽ (-{percent}% до {end_str})"
                else:
                    return f"{old}₽"
            # Группируем тарифы по sub_rank
            basic = []
            pro = []
            for t in tariffs:
                plan_id, title, desc, amount, currency, sub_rank, months, *_ = t
                price = int(amount / 100)
                # Получаем скидку
                discount_percent = await self.user_repo.get_active_discount(plan_id)
                price_with_discount = price
                discount_str = ""
                if discount_percent > 0:
                    # Получаем дату окончания скидки
                    async with aiosqlite.connect(self.user_repo.db_path) as db:
                        async with db.execute('SELECT end_time FROM discounts WHERE plan_id=? AND start_time<=? AND end_time>=? ORDER BY end_time DESC LIMIT 1', (plan_id, now, now)) as cursor:
                            row = await cursor.fetchone()
                            if row:
                                end_time = row[0]
                                price_with_discount = int(round(price * (1 - discount_percent / 100)))
                                discount_str = f"<s>{price}₽</s> {price_with_discount}₽ (-{discount_percent}% до {datetime.datetime.fromisoformat(end_time).strftime('%d.%m.%Y %H:%M')})"
                if discount_str:
                    price_line = f"  {months} месяц{'а' if months in (3,6) else 'ев'} – {discount_str}"
                else:
                    price_line = f"  {months} месяц{'а' if months in (3,6) else 'ев'} – {price}₽"
                if sub_rank == 1:
                    basic.append(price_line)
                elif sub_rank == 2:
                    pro.append(price_line)
            text = f'{status}\n\nТарифы:\nБазовый:\n' + '\n'.join(basic) + '\n  30 часов в месяц\n\nПро:\n' + '\n'.join(pro) + '\n  Безлимитная генерация\n\nНа платных тарифах вы сможете обрабатывать видео/аудио до 4-х часов, а так же отправлять 10 ссылок одним сообщением.'
            await message.reply(text, parse_mode="HTML", reply_markup=self.get_tariff_keyboard())

        @self.dp.message_handler(lambda m: m.text == "🎁 Бонусная генерация")
        async def bonus_gen(message: types.Message):
            if await self.check_ban(message): return
            await message.reply(
                'Бонусная генерация: вы можете получить бесплатные минуты за активность или участие в акциях! Подробности скоро появятся.',
                reply_markup=self.get_tariff_keyboard()
            )

        @self.dp.message_handler(lambda m: m.text == "🔙 Назад в меню")
        async def back_to_menu_tariff(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            a_rank = user[2] if user and len(user) > 2 else 0
            await message.reply('Главное меню', reply_markup=self.get_main_keyboard())

        @self.dp.message_handler(lambda m: m.text == "👥 Реферальная программа")
        async def referral_program(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            a_rank = user[2] if user and len(user) > 2 else 0
            await message.reply(
                'Реферальная программа: приглашайте друзей и получайте бонусы! Ваша реферальная ссылка: https://ai-level.pro/ref/ваш_id',
                reply_markup=self.get_main_keyboard()
            )

        @self.dp.message_handler(lambda m: m.text == "🤖 Про сервис")
        async def about_service(message: types.Message):
            if await self.check_ban(message): return
            platforms_text = ", ".join(Config.SUPPORTED_PLATFORMS[:8]) + " и другие"
            await message.reply(
                f'AI Level Pro — сервис для быстрой транскрибации аудио и видео в текст.\n\n'
                f'📹 Поддерживаемые платформы: {platforms_text}\n'
                f'🎯 Высокая точность распознавания\n'
                f'⚡ Быстрая обработка\n\n'
                'Сайт: https://ai-level.pro',
                reply_markup=self.get_about_inline()
            )

        @self.dp.message_handler(lambda m: m.text == "🛟 Служба поддержки")
        async def support_start(message: types.Message):
            if await self.check_ban(message): return
            await message.reply(
                'Выберите категорию вашего вопроса:',
                reply_markup=self.get_support_keyboard()
            )

        @self.dp.message_handler(lambda m: m.text == "📊 Мои лимиты")
        async def my_limits(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            if not user:
                await message.reply('Пожалуйста, нажмите СТАРТ для начала работы.')
                return
            sub = user[3] or 0
            sub_rank = user[4] or 0
            sub_time = user[5] or '-'
            limit_month = user[7] if user[7] is not None else (5 if sub == 0 else (30 if sub_rank == 1 else 9999))
            limit_links = user[8] if user[8] is not None else (5 if sub == 0 else (10 if sub_rank in (1,2) else 5))
            # Лимиты по размеру файлов
            if sub == 0:
                file_limit = f'{Config.FREE_FILE_LIMIT_MB} МБ'
            else:
                # Определяем тариф пользователя
                tariff_id = user[10] if len(user) > 10 and user[10] else None
                tariff = await self.user_repo.get_tariff(tariff_id) if tariff_id else None
                if tariff and len(tariff) > 10 and tariff[10] is not None:
                    file_limit_mb = tariff[10]
                else:
                    if sub_rank == 1:
                        file_limit_mb = 350
                    elif sub_rank == 2:
                        file_limit_mb = 2048
                    else:
                        file_limit_mb = Config.FREE_FILE_LIMIT_MB
                file_limit = f'{file_limit_mb} МБ'
            text = (
                f'Ваша подписка: {"Бесплатная" if sub == 0 else ("Базовый" if sub_rank == 1 else "Про")}\n'
                f'До: {sub_time}\n'
                f'Лимит часов в месяц: {limit_month}\n'
                f'Лимит ссылок за раз: {limit_links}\n'
                f'Максимальный размер файла: {file_limit}'
            )
            a_rank = user[2] if user and len(user) > 2 else 0
            await message.reply(text, reply_markup=self.get_main_keyboard())

        TARIFF_BUTTONS = [
            "🟢 Базовый (1 месяц)", "🟢 Базовый (3 месяца)", "🟢 Базовый (6 месяцев)", "🟢 Базовый (12 месяцев)",
            "🔵 Про (1 месяц)", "🔵 Про (3 месяца)", "🔵 Про (6 месяцев)", "🔵 Про (12 месяцев)",
            "🎁 Бонусная генерация", "🔙 Назад в меню", "🇷🇺💳 Карта РФ", "🌐💳 Зарубежная карта", "📋 К выбору тарифа"
        ]

        @self.dp.message_handler(lambda m: m.content_type == "document")
        async def handle_document(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            # Логируем получение документа
            self.log_test_event("DOCUMENT_RECEIVED", user_id,
                               file_name=getattr(message.document, 'file_name', 'unknown'),
                               file_size=getattr(message.document, 'file_size', 0),
                               mime_type=getattr(message.document, 'mime_type', 'unknown'))
            # Проверяем лимит размера файла
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            sub = user[3] or 0
            sub_rank = user[4] or 0
            tariff_id = user[10] if len(user) > 10 and user[10] else None
            if sub == 0:
                file_limit_mb = Config.FREE_FILE_LIMIT_MB
            else:
                tariff = await self.user_repo.get_tariff(tariff_id) if tariff_id else None
                if tariff and len(tariff) > 10 and tariff[10] is not None:
                    file_limit_mb = tariff[10]
                else:
                    if sub_rank == 1:
                        file_limit_mb = 350
                    elif sub_rank == 2:
                        file_limit_mb = 2048
                    else:
                        file_limit_mb = Config.FREE_FILE_LIMIT_MB
            file_obj = message.document
            file_size_mb = file_obj.file_size / (1024 * 1024)
            if file_size_mb > file_limit_mb:
                await message.reply(f'Файл слишком большой! Максимальный размер — {file_limit_mb} МБ.', reply_markup=self.get_main_keyboard())
                return
            await self.handle_file(message, message.document)

        @self.dp.message_handler(lambda m: m.content_type == "audio")
        async def handle_audio(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            self.log_test_event("AUDIO_RECEIVED", user_id,
                               file_name=getattr(message.audio, 'file_name', 'unknown'),
                               file_size=getattr(message.audio, 'file_size', 0),
                               duration=getattr(message.audio, 'duration', 0),
                               mime_type=getattr(message.audio, 'mime_type', 'unknown'))
            # Проверяем лимит размера файла
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            sub = user[3] or 0
            sub_rank = user[4] or 0
            tariff_id = user[10] if len(user) > 10 and user[10] else None
            if sub == 0:
                file_limit_mb = Config.FREE_FILE_LIMIT_MB
            else:
                tariff = await self.user_repo.get_tariff(tariff_id) if tariff_id else None
                if tariff and len(tariff) > 10 and tariff[10] is not None:
                    file_limit_mb = tariff[10]
                else:
                    if sub_rank == 1:
                        file_limit_mb = 350
                    elif sub_rank == 2:
                        file_limit_mb = 2048
                    else:
                        file_limit_mb = Config.FREE_FILE_LIMIT_MB
            file_obj = message.audio
            file_size_mb = file_obj.file_size / (1024 * 1024)
            if file_size_mb > file_limit_mb:
                await message.reply(f'Файл слишком большой! Максимальный размер — {file_limit_mb} МБ.', reply_markup=self.get_main_keyboard())
                return
            await self.handle_file(message, message.audio)

        @self.dp.message_handler(lambda m: m.content_type == "video")
        async def handle_video(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            self.log_test_event("VIDEO_RECEIVED", user_id,
                               file_name=getattr(message.video, 'file_name', 'unknown'),
                               file_size=getattr(message.video, 'file_size', 0),
                               duration=getattr(message.video, 'duration', 0),
                               width=getattr(message.video, 'width', 0),
                               height=getattr(message.video, 'height', 0),
                               mime_type=getattr(message.video, 'mime_type', 'unknown'))
            # Проверяем лимит размера файла
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            sub = user[3] or 0
            sub_rank = user[4] or 0
            tariff_id = user[10] if len(user) > 10 and user[10] else None
            if sub == 0:
                file_limit_mb = Config.FREE_FILE_LIMIT_MB
            else:
                tariff = await self.user_repo.get_tariff(tariff_id) if tariff_id else None
                if tariff and len(tariff) > 10 and tariff[10] is not None:
                    file_limit_mb = tariff[10]
                else:
                    if sub_rank == 1:
                        file_limit_mb = 350
                    elif sub_rank == 2:
                        file_limit_mb = 2048
                    else:
                        file_limit_mb = Config.FREE_FILE_LIMIT_MB
            file_obj = message.video
            file_size_mb = file_obj.file_size / (1024 * 1024)
            if file_size_mb > file_limit_mb:
                await message.reply(f'Файл слишком большой! Максимальный размер — {file_limit_mb} МБ.', reply_markup=self.get_main_keyboard())
                return
            await self.handle_file(message, message.video)

        @self.dp.message_handler(lambda m: m.content_type == "photo")
        async def handle_support_photo(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            if not user:
                await message.reply('Пожалуйста, нажмите СТАРТ для начала работы.')
                return
            sub = user[3] or 0
            sub_rank = user[4] or 0
            tariff_id = user[10] if len(user) > 10 and user[10] else None
            if sub == 0:
                file_limit_mb = Config.FREE_FILE_LIMIT_MB
            else:
                tariff = await self.user_repo.get_tariff(tariff_id) if tariff_id else None
                if tariff and len(tariff) > 10 and tariff[10] is not None:
                    file_limit_mb = tariff[10]
                else:
                    if sub_rank == 1:
                        file_limit_mb = 350
                    elif sub_rank == 2:
                        file_limit_mb = 2048
                    else:
                        file_limit_mb = Config.FREE_FILE_LIMIT_MB
            file_obj = message.photo[-1]
            file_size_mb = file_obj.file_size / (1024 * 1024)
            print(f"[DEBUG] user_id={user_id}, тариф={sub_rank}, file_size={getattr(file_obj, 'file_size', None)}, file_size_mb={file_size_mb}, file_limit_mb={file_limit_mb}, file_name={getattr(file_obj, 'file_name', None)}, mime_type={getattr(file_obj, 'mime_type', None)}")
            if file_size_mb > file_limit_mb:
                print(f"[DEBUG] ЛИМИТ ПРЕВЫШЕН: file_size_mb={file_size_mb}, file_limit_mb={file_limit_mb}")
                await message.reply(f'Файл слишком большой! Максимальный размер — {file_limit_mb} МБ.', reply_markup=self.get_main_keyboard())
                return
            await self.handle_file(message, file_obj)

        @self.dp.message_handler(lambda m: re.search(r'https?://', m.text or ""))
        async def handle_links(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            if not user:
                await message.reply('Пожалуйста, нажмите СТАРТ для начала работы.')
                return
            sub = user[3] or 0
            sub_rank = user[4] or 0
            limit_month = user[7] if user[7] is not None else (5 if sub == 0 else (30 if sub_rank == 1 else 9999))
            user_lang = user[9] if user and len(user) > 9 and user[9] else 'ru'
            lang_code = None if user_lang == 'other' else user_lang
            if sub == 0:
                max_links = 5
            elif sub_rank == 1:
                max_links = 10
            elif sub_rank == 2:
                max_links = 10
            else:
                max_links = 5
            links = re.findall(r'https?://[^\s]+', message.text or "")
            # Логируем факт получения ссылки
            self.log_test_event("LINKS_RECEIVED", user_id, links=links, count=len(links), text=message.text)
            if len(links) > max_links:
                await message.reply(f'Слишком много ссылок! Максимум {max_links} ссылок за раз.', reply_markup=self.get_main_keyboard())
                return
            progress_msg = await message.reply('Обрабатываю ссылки, это может занять несколько минут...')
            total_duration = 0
            all_texts = []
            for i, link in enumerate(links):
                link_start = datetime.datetime.now()
                self.log_test_event("LINK_PROCESSING_START", user_id, link=link, index=i+1)
                try:
                    await progress_msg.edit_text(f'Обрабатываю ссылку {i+1}/{len(links)}...')
                    file_path, _ = self.file_handler.download_from_url(link)
                    if not file_path:
                        await progress_msg.edit_text(f'Не удалось обработать ссылку {i+1}: видео не может быть скачано или обработано (3 попытки исчерпаны).')
                        self.log_test_event("LINK_PROCESSING_ERROR", user_id, link=link, index=i+1, error="file not downloaded after 3 attempts", processing_time=(datetime.datetime.now()-link_start).total_seconds(), success=False)
                        all_texts.append(f'[Ссылка {i+1}] Не удалось обработать: видео не может быть скачано или обработано (3 попытки исчерпаны).\n')
                        continue
                    if file_path:
                        duration = self.transcriber.get_duration(file_path)
                        total_duration += duration
                        if sub == 0 and total_duration > 7200:  # 2 часа
                            await progress_msg.edit_text('Превышен лимит времени для бесплатного тарифа!')
                            self.log_test_event("LINK_LIMIT_EXCEEDED", user_id, link=link, index=i+1, total_duration=total_duration)
                            return
                        elif sub_rank == 1 and total_duration > 14400:  # 4 часа
                            await progress_msg.edit_text('Превышен лимит времени для базового тарифа!')
                            self.log_test_event("LINK_LIMIT_EXCEEDED", user_id, link=link, index=i+1, total_duration=total_duration)
                            return
                        async def progress_callback(percent):
                            try:
                                await progress_msg.edit_text(f'Обрабатываю ссылку {i+1}/{len(links)}... {percent}%')
                            except Exception:
                                pass
                        options = Config.WHISPER_OPTIONS.copy()
                        if lang_code:
                            options['language'] = lang_code
                        text = await self.transcriber.transcribe_long_file_with_progress(file_path, options, progress_callback)
                        all_texts.append(f'[Ссылка {i+1}]\n{text}\n')
                        os.remove(file_path)
                        link_end = datetime.datetime.now()
                        self.log_test_event("LINK_PROCESSED", user_id, link=link, index=i+1, duration=duration, processing_time=(link_end-link_start).total_seconds(), success=True)
                except Exception as e:
                    all_texts.append(f'[Ссылка {i+1}] Ошибка обработки: {str(e)}\n')
                    link_end = datetime.datetime.now()
                    self.log_test_event("LINK_PROCESSING_ERROR", user_id, link=link, index=i+1, error=str(e), processing_time=(link_end-link_start).total_seconds(), success=False)
            # Логируем итоговую статистику по всем ссылкам
            self.log_test_event("LINKS_PROCESSING_SUMMARY", user_id, count=len(links), total_duration=total_duration, all_success=all(t['event_type']=="LINK_PROCESSED" for t in self.test_logs if t.get('user_id')==user_id and t.get('event_type') in ["LINK_PROCESSED","LINK_PROCESSING_ERROR"]))
            if all_texts:
                combined_text = '\n'.join(all_texts)
                info_text = ""
                if sub == 0:
                    info_text = f"У вас осталось бесплатных транскрибаций: {limit_month}\nРекомендуем приобрести подписку!\n"
                elif sub_rank == 1:
                    try:
                        sub_time = user[5] if user and user[5] else None
                        if sub_time:
                            days_left = (datetime.datetime.fromisoformat(sub_time) - datetime.datetime.now()).days
                        else:
                            days_left = '-'
                    except Exception:
                        days_left = '-'
                    info_text = f"У вас осталось часов: {limit_month}\nДо конца подписки: {days_left} дней\n\n"
                elif sub_rank == 2:
                    try:
                        sub_time = user[5] if user and user[5] else None
                        if sub_time:
                            days_left = (datetime.datetime.fromisoformat(sub_time) - datetime.datetime.now()).days
                        else:
                            days_left = '-'
                    except Exception:
                        days_left = '-'
                    info_text = f"У вас осталось часов: Безлимит\nДо конца подписки: {days_left} дней\n\n"
                combined_text = info_text + combined_text
                combined_text += "\n\nСоздано нами "
                import uuid
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
                file_id = str(uuid.uuid4())
                lang_code = user[9] if user and len(user) > 9 and user[9] else 'ru'
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Добавить таймкоды", callback_data=f"add_timestamps:{file_id}:{lang_code}")]
                    ]
                )
                if not hasattr(self, 'user_files'):
                    self.user_files = {}
                last_file_path = None
                last_orig_name = None
                for i, link in enumerate(links[::-1]):
                    try:
                        file_path, orig_name = self.file_handler.download_from_url(link)
                        last_file_path = file_path
                        last_orig_name = orig_name
                        break
                    except Exception:
                        continue
                if last_file_path:
                    self.user_files[(user_id, file_id)] = (last_file_path, last_orig_name)
                await progress_msg.edit_text('Обработка завершена!')
                # --- ВОССТАНОВЛЕНИЕ: если длительность больше 2 минут, отправлять как txt файл ---
                if total_duration > 120:  # 2 минуты
                    txt_path = f"/tmp/transcript_{file_id}.txt"
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(combined_text)
                    await self.bot.send_document(message.chat.id, InputFile(txt_path), caption="Результат транскрибации длинного видео", reply_markup=markup)
                    os.remove(txt_path)
                else:
                    await safe_send_message(self.bot, message.chat.id, combined_text, reply_markup=markup)
            else:
                await progress_msg.edit_text('Не удалось обработать ссылки.', reply_markup=self.get_main_keyboard())

        @self.dp.message_handler(commands=["subs"])
        async def cmd_subs(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            count = await self.user_repo.count_subs()
            await message.reply(f'Активных подписок: {count}')

        @self.dp.message_handler(commands=["users"])
        async def cmd_users(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            count = await self.user_repo.count_users()
            await message.reply(f'Всего пользователей: {count}')

        @self.dp.message_handler(commands=["ban"])
        async def cmd_ban(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            if not user or user[2] < 1:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            import re
            args = message.text.split() if message.text else []
            if len(args) < 4:
                await message.reply('Использование: /ban <id|username> <срок: 1h-30d> <причина>')
                return
            target, period, reason = args[1], args[2], args[3]
            # Поиск пользователя
            target_user = None
            if target.isdigit():
                target_user = await self.user_repo.get_user(int(target))
            if not target_user:
                target_user = await self.user_repo.get_user_by_username(target)
            if not target_user:
                await message.reply('Пользователь не найден.')
                return
            # Проверка уровня
            if target_user[2] >= 3:
                await message.reply('Нельзя забанить супер-админа.')
                return
            # Парсим срок
            m = re.match(r'^(\d+)([hd])$', period)
            if not m:
                await message.reply('Срок должен быть в формате 1h-30d (h — часы, d — дни)')
                return
            value, typ = int(m.group(1)), m.group(2)
            if typ == 'h':
                if not (1 <= value <= 720):
                    await message.reply('Срок должен быть от 1 до 720 часов.')
                    return
                until = datetime.datetime.now() + datetime.timedelta(hours=value)
            else:
                if not (1 <= value <= 30):
                    await message.reply('Срок должен быть от 1 до 30 дней.')
                    return
                until = datetime.datetime.now() + datetime.timedelta(days=value)
            await self.user_repo.ban_user(target_user[0], until.isoformat(), reason)
            await self.user_repo.log_admin_action(user_id, user[1], f'ban {target_user[0]} {target_user[1]} на {period} причина: {reason}')
            try:
                await self.bot.send_message(target_user[0], f'Вы были заблокированы на {period} по причине: {reason}')
            except Exception:
                pass
            # уведомление спец-админу:
            admins = await self.user_repo.get_admins()
            for a in admins:
                if a[2] == 3 and a[0] != user_id:
                    try:
                        await self.bot.send_message(a[0], f'Админ {user[1]} заблокировал @{target_user[1]} | {target_user[0]} по причине {reason} на срок {period}')
                    except Exception:
                        pass
            await message.reply(f'Пользователь {target_user[1]} заблокирован до {until.strftime("%Y-%m-%d %H:%M")}')

        @self.dp.message_handler(commands=["admins"])
        async def cmd_admins(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            admins = await self.user_repo.get_admins()
            lines = []
            for a in admins:
                # a: (id, user_name, a_rank)
                # Получаем username из Telegram API, если возможно
                try:
                    chat = await self.bot.get_chat(a[0])
                    username = f'@{chat.username}' if getattr(chat, 'username', None) else a[1]
                except Exception:
                    username = a[1]
                lines.append(f'{a[0]} | {username} | {a[2]}')
            text = '\n'.join(lines)
            await message.reply(text)

        @self.dp.message_handler(commands=["unban"])
        async def cmd_unban(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            args = message.text.split() if message.text else []
            if len(args) < 2:
                await message.reply('Использование: /unban <id|username>')
                return
            target = args[1]
            target_user = None
            if target.isdigit():
                target_user = await self.user_repo.get_user(int(target))
            if not target_user:
                target_user = await self.user_repo.get_user_by_username(target)
            if not target_user:
                await message.reply('Пользователь не найден.')
                return
            await self.user_repo.unban_user(target_user[0])
            await self.user_repo.log_admin_action(user_id, getattr(message.from_user, 'username', None), f'unban {target_user[0]}')
            await message.reply(f'Пользователь {target_user[1]} разблокирован.')

        @self.dp.message_handler(commands=["arang"])
        async def cmd_arang(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            args = message.text.split() if message.text else []
            if len(args) < 3:
                await message.reply('Использование: /arang <id|username> <0-3>')
                return
            target = args[1]
            try:
                new_rank = int(args[2])
                if new_rank < 0 or new_rank > 3:
                    await message.reply('Ранг должен быть от 0 до 3.')
                    return
            except ValueError:
                await message.reply('Ранг должен быть числом.')
                return
            target_user = None
            if target.isdigit():
                target_user = await self.user_repo.get_user(int(target))
            if not target_user:
                target_user = await self.user_repo.get_user_by_username(target)
            if not target_user:
                await message.reply('Пользователь не найден.')
                return
            await self.user_repo.update_admin(target_user[0], new_rank)
            await self.user_repo.log_admin_action(user_id, getattr(message.from_user, 'username', None), f'arang {target_user[0]} {new_rank}')
            rank_names = {0: 'обычный пользователь', 1: 'модератор', 2: 'админ', 3: 'супер админ'}
            await message.reply(f'Пользователь {target_user[1]} теперь {rank_names[new_rank]}.')

        @self.dp.message_handler(commands=["ahelp"])
        async def cmd_ahelp(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 1:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            help_text = (
                "/ban <id|username> <срок: 1h-30d> <причина> — заблокировать пользователя\n"
                "/admins — список админов (ID | Ник | Лвл админки)\n"
                "/reply <id> <ответ> — ответить на вопрос поддержки\n"
                "/support_info <id> — посмотреть вопрос и ответ\n"
                "/get_id <username> — получить ID пользователя по нику\n"
                "/ahelp — список админских команд\n"
            )
            if user[2] >= 2:
                help_text += (
                    "\n/subs — количество активных подписок\n"
                    "/users — количество всех пользователей\n"
                    "/unban <id|username> — разбанить пользователя\n"
                    "/support_off — отключить уведомления поддержки\n"
                    "/support_on — включить уведомления поддержки\n"
                    "/all_answer — все вопросы и ответы поддержки (постранично)\n"
                    "/banned — список забаненных пользователей (id | username | дата блокировки | срок блокировки | причина | кто заблокировал)\n"
                    "/give_users [page] — список всех пользователей (по 10 на страницу)\n"
                    "/get_appeal — список всех апелляций и их статус\n"
                    "/appeal <id> <ответ> — ответить на апелляцию\n"
                )
            if user[2] == 3:
                help_text += (
                    "\n/arang <id|username> <0-3> — назначить/снять админа (0 — снять, 1 — модератор, 2 — админ, 3 — супер админ)\n"
                    "/orders <all|pending|paid> [limit] — просмотр заказов\n"
                    "/give_subs — список всех активных подписок (id | @username | уровень | срок)\n"
                    "/d_sub <id|username> — аннулировать подписку по id или username\n"
                    "/g_sub <id|username> <1|2> <срок: YYYY-MM-DD> — выдать подписку (1 — Базовый, 2 — Про) на срок\n"
                    "/logs [page] — логи действий админов (по 10 на страницу)\n"
                    "/testmode — включить/выключить тестовый режим с логированием\n"
                    "/get_testlogs — получить отчет тестовых логов за день\n"
                    "/amount <plan_id> <percent> <срок: 1d-30d> — скидка на тариф (только для супер-админа)\n"
                    "/s_tariff <id> <цена> — изменить цену тарифа по id и уведомить всех пользователей\n"
                    "/get_tariff — вывести список тарифов с ценами и скидками\n"
                    "/get_amount — вывести текущие скидки (id | tariff_id | срок)\n"
                    "/d_amount <id> — удалить скидку по её id\n"
                )
            await message.reply(help_text)

        # --- Универсальная функция для отправки длинных сообщений ---
        async def safe_send_message(bot, chat_id, text, **kwargs):
            max_len = 4096
            for i in range(0, len(text), max_len):
                await bot.send_message(chat_id, text[i:i+max_len], **kwargs)

        @self.dp.message_handler(commands=["s_tariff"])
        async def cmd_s_tariff(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав. Требуется уровень 3 админа.')
                return
            if await self.check_ban(message): return
            args = message.text.split()
            if len(args) != 3:
                await message.reply('Использование: /s_tariff <id> <цена>')
                return
            plan_id, price_str = args[1], args[2]
            try:
                price = int(float(price_str))
            except Exception:
                await message.reply('Цена должна быть числом.')
                return
            tariff = await self.user_repo.get_tariff(plan_id)
            if not tariff:
                await message.reply('Тариф с таким id не найден.')
                return
            # Обновляем цену
            new_tariff = list(tariff)
            new_tariff[3] = price * 100  # amount в копейках
            await self.user_repo.upsert_tariff(tuple(new_tariff))
            # Постраничная рассылка всем пользователям
            from aiogram.utils.exceptions import BotBlocked
            page = 1
            page_size = 1000
            while True:
                users = await self.user_repo.get_users_page(page=page, page_size=page_size)
                if not users:
                    break
                for u in users:
                    try:
                        await safe_send_message(self.bot, u[0], f'ℹ️ Цена тарифа "{tariff[1]}" изменилась и теперь составляет {price}₽.')
                    except BotBlocked:
                        pass
                    except Exception:
                        pass
                page += 1
            await message.reply(f'Цена тарифа "{tariff[1]}" успешно изменена на {price}₽ и отправлена рассылка.')

        @self.dp.message_handler(commands=["get_tariff"])
        async def cmd_get_tariff(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав. Требуется уровень 3 админа.')
                return
            if await self.check_ban(message): return
            tariffs = await self.user_repo.get_all_tariffs()
            import datetime
            import aiosqlite
            now = datetime.datetime.now().isoformat()
            lines = ["id | название | цена | скидка | срок скидки"]
            for t in tariffs:
                plan_id, title, desc, amount, currency, sub_rank, months, *_ = t
                price = int(amount / 100)
                discount_percent = await self.user_repo.get_active_discount(plan_id)
                discount_str = "-"
                end_str = "-"
                if discount_percent > 0:
                    async with aiosqlite.connect(self.user_repo.db_path) as db:
                        async with db.execute('SELECT end_time FROM discounts WHERE plan_id=? AND start_time<=? AND end_time>=? ORDER BY end_time DESC LIMIT 1', (plan_id, now, now)) as cursor:
                            row = await cursor.fetchone()
                            if row:
                                end_time = row[0]
                                end_str = datetime.datetime.fromisoformat(end_time).strftime('%d.%m.%Y %H:%M')
                                discount_str = f"{discount_percent}%"
                lines.append(f"{plan_id} | {title} | {price}₽ | {discount_str} | {end_str}")
            await message.reply('\n'.join(lines))

        @self.dp.message_handler(commands=["get_amount"])
        async def cmd_get_amount(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав. Требуется уровень 3 админа.')
                return
            if await self.check_ban(message): return
            
            discounts = await self.user_repo.get_all_discounts()
            if not discounts:
                await message.reply('📝 Скидки не найдены.')
                return
            
            import datetime
            lines = ["id | tariff_id | процент | начало | конец"]
            for discount in discounts:
                discount_id, plan_id, percent, start_time, end_time = discount
                start_str = datetime.datetime.fromisoformat(start_time).strftime('%d.%m.%Y %H:%M')
                end_str = datetime.datetime.fromisoformat(end_time).strftime('%d.%m.%Y %H:%M')
                lines.append(f"{discount_id} | {plan_id} | {percent}% | {start_str} | {end_str}")
            
            await message.reply('\n'.join(lines))

        @self.dp.message_handler(commands=["d_amount"])
        async def cmd_d_amount(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав. Требуется уровень 3 админа.')
                return
            if await self.check_ban(message): return
            
            args = message.text.split()
            if len(args) != 2:
                await message.reply('Использование: /d_amount <id>')
                return
            
            try:
                discount_id = int(args[1])
            except ValueError:
                await message.reply('ID скидки должен быть числом.')
                return
            
            # Проверяем, существует ли скидка
            discounts = await self.user_repo.get_all_discounts()
            discount_exists = any(d[0] == discount_id for d in discounts)
            
            if not discount_exists:
                await message.reply(f'❌ Скидка с ID {discount_id} не найдена.')
                return
            
            # Удаляем скидку
            await self.user_repo.delete_discount(discount_id)
            
            # Логируем действие
            await self.user_repo.log_admin_action(user_id, user[1] if user else "unknown", f"удалил скидку {discount_id}")
            
            await message.reply(f'✅ Скидка с ID {discount_id} успешно удалена.')

        @self.dp.message_handler(commands=["testmode"])
        async def cmd_testmode(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user:
                await message.reply('Пожалуйста, нажмите СТАРТ для начала работы.')
                return
            if await self.check_ban(message): return
            
            # Переключаем режим
            self.test_mode = not self.test_mode
            status = "ВКЛЮЧЕН" if self.test_mode else "ВЫКЛЮЧЕН"
            await message.reply(f'🔬 Тестовый режим {status}')
            
            # Логируем включение/выключение тестового режима
            self.log_test_event("TEST_MODE_TOGGLE", user_id, status=status, admin=user[1] if user else "unknown")

        @self.dp.message_handler(commands=["get_testlogs"])
        async def cmd_get_testlogs(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав. Требуется уровень 3+ админа.')
                return
            if await self.check_ban(message): return
            
            # Проверяем состояние тестового режима
            mode_status = "ВКЛЮЧЕН" if self.test_mode else "ВЫКЛЮЧЕН"
            
            if not self.test_logs:
                await message.reply(f'📝 Тестовые логи пусты.\n🔬 Тестовый режим: {mode_status}\n\nВключите тестовый режим командой /testmode для начала логирования.')
                return
            
            # Создаем файл с отчетами
            report_filename = f"test_report_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
            try:
                with open(report_filename, 'w', encoding='utf-8') as f:
                    f.write(self.get_test_logs_summary())
                
                # Отправляем файл
                await message.reply_document(
                    InputFile(report_filename),
                    caption=f'📊 Отчет тестовых логов\n📅 Дата: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n📝 Записей: {len(self.test_logs)}\n🔬 Тестовый режим: {mode_status}'
                )
                
                # Удаляем временный файл
                os.remove(report_filename)
                
            except Exception as e:
                await message.reply(f'❌ Ошибка при создании отчета: {e}')



        @self.dp.message_handler(commands=["get_id"])
        async def cmd_get_id(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 1:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            
            args = message.text.split() if message.text else []
            if len(args) < 2:
                await message.reply('Использование: /get_id <username>')
                return
            
            username = args[1].lstrip('@')  # Убираем @ если есть
            target_user = await self.user_repo.get_user_by_username(username)
            
            if target_user:
                await message.reply(f'Пользователь @{username} имеет ID: {target_user[0]}')
            else:
                await message.reply(f'Пользователь @{username} не найден в базе данных.')

        @self.dp.message_handler(lambda m: m.text in ["❌ Не проходит оплата", "💡 Идеи по улучшению работы", "🤝 Предложение по сотрудничеству", "📝 Другое"])
        async def support_category(message: types.Message):
            if await self.check_ban(message): return
            await message.reply("✅ Принято!", reply=False)
            await support_instruction(message)
            user_id = getattr(message.from_user, 'id', None)
            if user_id is not None:
                self.support_waiting.add(user_id)
                # Сохраняем тему обращения
                if not hasattr(self, 'support_topics'):
                    self.support_topics = {}
            self.support_topics[user_id] = message.text

        @self.dp.message_handler(lambda m: m.text in [
            "🟢 Базовый (1 месяц)", "🟢 Базовый (3 месяца)", "🟢 Базовый (6 месяцев)", "🟢 Базовый (12 месяцев)",
            "🔵 Про (1 месяц)", "🔵 Про (3 месяца)", "🔵 Про (6 месяцев)", "🔵 Про (12 месяцев)"
        ])
        async def tariff_selected(message: types.Message):
            if await self.check_ban(message): return
            tariffs_map = {
                "🟢 Базовый (1 месяц)": "basic_1",
                "🟢 Базовый (3 месяца)": "basic_3",
                "🟢 Базовый (6 месяцев)": "basic_6",
                "🟢 Базовый (12 месяцев)": "basic_12",
                "🔵 Про (1 месяц)": "pro_1",
                "🔵 Про (3 месяца)": "pro_3",
                "🔵 Про (6 месяцев)": "pro_6",
                "🔵 Про (12 месяцев)": "pro_12"
            }
            tariff_id = tariffs_map.get(message.text)
            if not tariff_id:
                await message.reply("Ошибка: тариф не найден.")
                return
            user_id = getattr(message.from_user, 'id', None)
            if not hasattr(self, 'selected_tariffs'):
                self.selected_tariffs = {}
            self.selected_tariffs[user_id] = tariff_id
            self.user_tariff[user_id] = {'tariff_id': tariff_id}
            tariff = await self.user_repo.get_tariff(tariff_id)
            title = tariff[1] if tariff else 'Неизвестный тариф'
            description = tariff[2] if tariff else ''
            amount = (tariff[3] if tariff else 0) / 100
            currency = tariff[4] if tariff else 'RUB'
            # --- Добавляем инфо о скидке ---
            discount_percent = await self.user_repo.get_active_discount(tariff_id)
            discount_text = ""
            amount_with_discount = amount
            if discount_percent > 0:
                # Получаем дату окончания скидки
                import datetime
                import aiosqlite
                async with aiosqlite.connect(self.user_repo.db_path) as db:
                    async with db.execute('SELECT end_time FROM discounts WHERE plan_id=? AND start_time<=? AND end_time>=? ORDER BY end_time DESC LIMIT 1', (tariff_id, datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat())) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            end_time = row[0]
                            discount_text = f'🔥 <b>На этот тариф действует скидка {discount_percent}% до {end_time[:16].replace("T", " ")}</b>\n\n'
                amount_with_discount = round(amount * (1 - discount_percent / 100), 2)
            if discount_percent > 0:
                price_text = f"<s>{amount} {currency}</s> → <b>{amount_with_discount} {currency}</b>"
            else:
                price_text = f"<b>{amount} {currency}</b>"
            text = f"{discount_text}<b>{title}</b>\n\n{description}\n\n💳 Стоимость: {price_text}\n\nДля оплаты выберите карту ниже."
            await message.reply(text, parse_mode="HTML", reply_markup=self.get_payment_keyboard())

        @self.dp.message_handler(lambda m: m.text == "🇷🇺💳 Карта РФ")
        async def pay_russia(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            selected_tariff = getattr(self, 'selected_tariffs', {}).get(user_id)
            if not selected_tariff:
                await message.reply("Сначала выберите тариф для оплаты.")
                return
            tariff = await self.user_repo.get_tariff(selected_tariff)
            if not tariff:
                await message.reply("Ошибка: тариф не найден.")
                return
            from yookassa import Payment, Configuration
            import uuid
            if not Config.YOOKASSA_SHOP_ID or not Config.YOOKASSA_SECRET_KEY:
                await message.reply("Ошибка: не заданы ключи YOOKASSA_SHOP_ID или YOOKASSA_SECRET_KEY в .env")
                return
            Configuration.account_id = Config.YOOKASSA_SHOP_ID
            Configuration.secret_key = Config.YOOKASSA_SECRET_KEY
            amount = tariff[3] if tariff else 0
            # --- Скидка ---
            discount_percent = await self.user_repo.get_active_discount(selected_tariff)
            amount_with_discount = amount
            discount_info = ""
            if discount_percent > 0:
                amount_with_discount = int(round(amount * (1 - discount_percent / 100)))
                discount_info = f" (скидка {discount_percent}%)"
            description = f"Оплата тарифа: {tariff[1] if tariff else 'Неизвестный тариф'} (тестовый платеж)"
            payment_id = str(uuid.uuid4())
            payment = Payment.create({
                "amount": {
                    "value": str(amount_with_discount / 100),
                    "asset": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/"
                },
                "capture": True,
                "description": description
            }, payment_id)
            if not hasattr(self, 'user_tariff'):
                self.user_tariff = {}
            self.user_tariff[user_id] = {'tariff_id': selected_tariff, 'payment_id': payment.id}
            url = getattr(getattr(payment, 'confirmation', None), 'confirmation_url', None)
            if not url:
                await message.reply("Ошибка: не удалось получить ссылку на оплату от ЮKassa. Попробуйте позже или обратитесь в поддержку.")
                return
            check_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Проверить оплату")],
                    [KeyboardButton(text="🔙 Назад в меню")]
                ],
                resize_keyboard=True
            )
            if discount_percent > 0:
                price_text = f"<s>{amount / 100} RUB</s> → <b>{amount_with_discount / 100} RUB</b>"
            else:
                price_text = f"<b>{amount / 100} RUB</b>"
            await message.reply(
                f"Для оплаты тарифа '{tariff[1] if tariff else selected_tariff}' перейдите по ссылке (тестовый платеж):\n{url}\n\nСумма: {price_text}{discount_info}\n\nПосле оплаты вернитесь в бот и нажмите 'Проверить оплату'.",
                parse_mode="HTML",
                reply_markup=check_keyboard
            )

        @self.dp.message_handler(lambda m: m.text == "✅ Проверить оплату")
        async def check_payment(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user_data = getattr(self, 'user_tariff', {}).get(user_id)
            if not user_data or 'payment_id' not in user_data or 'tariff_id' not in user_data:
                await message.reply('Нет активного платежа для проверки. Сначала выберите тариф и создайте платёж.', reply_markup=self.get_tariff_keyboard())
                return
            
            payment_id = user_data['payment_id']
            tariff_id = user_data['tariff_id']
            invoice_id = user_data.get('invoice_id')  # Для CryptoBot
            
            # Получаем информацию о платеже из базы данных
            payment_info = await self.user_repo.get_payment(payment_id)
            if not payment_info:
                await message.reply('Платеж не найден в базе данных.', reply_markup=self.get_main_keyboard())
                del self.user_tariff[user_id]
                return
            
            payment_method = payment_info[5]  # payment_method
            tariff = await self.user_repo.get_tariff(tariff_id)
            
            # Проверяем статус платежа в зависимости от метода оплаты
            if payment_method == "cryptobot":
                # Проверяем CryptoBot платеж
                if not self.cryptobot_api_key:
                    await message.reply('API ключ CryptoBot не настроен. Обратитесь к администратору.', reply_markup=self.get_main_keyboard())
                    return
                
                try:
                    async with CryptoBotClient(self.cryptobot_api_key) as cryptobot:
                        invoice = await cryptobot.get_invoice(invoice_id)
                        
                        if invoice["status"] == "paid":
                            # Платеж оплачен
                            end_date = datetime.datetime.now() + datetime.timedelta(days=30 * (tariff[6] if tariff else 1))
                            end_date_str = end_date.strftime("%Y-%m-%d")
                            
                            # Обновляем статус платежа в базе
                            await self.user_repo.update_payment_status(payment_id, "paid")
                            
                            # Активируем подписку
                            await self.user_repo.set_subscription(user_id, tariff[5] if tariff else 1, end_date_str, tariff_id)
                            
                            await message.reply(
                                f'✅ Оплата через CryptoBot прошла успешно!\n\n'
                                f'Тариф: {tariff[1] if tariff else tariff_id}\n'
                                f'Подписка активна до: {end_date_str}\n\n'
                                f'Теперь вы можете использовать все возможности сервиса!',
                                reply_markup=self.get_main_keyboard()
                            )
                            del self.user_tariff[user_id]
                            
                        elif invoice["status"] == "pending":
                            await message.reply(
                                'Платёж ещё не завершён. Пожалуйста, оплатите по ссылке и попробуйте снова.',
                                reply_markup=self.get_main_keyboard()
                            )
                        else:
                            await message.reply(
                                f'Платёж не прошёл или отменён. Статус: {invoice["status"]}',
                                reply_markup=self.get_main_keyboard()
                            )
                            del self.user_tariff[user_id]
                            
                except Exception as e:
                    await message.reply(
                        f'Ошибка при проверке платежа: {str(e)}\n\nПопробуйте позже или обратитесь в поддержку.',
                        reply_markup=self.get_main_keyboard()
                    )
                    
            elif payment_method == "lemonsqueezy":
                # Проверяем Lemon Squeezy платеж
                if not self.lemonsqueezy_api_key:
                    await message.reply('API ключ Lemon Squeezy не настроен. Обратитесь к администратору.', reply_markup=self.get_main_keyboard())
                    return
                
                try:
                    checkout_id = user_data.get('checkout_id')
                    if not checkout_id:
                        await message.reply('Ошибка: не найден ID checkout. Попробуйте создать платеж заново.', reply_markup=self.get_tariff_keyboard())
                        return
                    
                    # Получаем информацию о заказе через checkout_id
                    # Примечание: Lemon Squeezy не предоставляет прямой API для получения заказа по checkout_id
                    # Поэтому мы будем проверять статус через webhook или по времени создания
                    
                    # Для простоты пока что считаем, что если прошло больше 5 минут с создания платежа,
                    # то нужно проверить вручную или через webhook
                    payment_created = payment_info[4]  # created_at
                    if payment_created:
                        from datetime import datetime
                        created_time = datetime.fromisoformat(payment_created.replace('Z', '+00:00'))
                        time_diff = datetime.now(created_time.tzinfo) - created_time
                        
                        if time_diff.total_seconds() < 300:  # 5 минут
                            await message.reply(
                                '💳 Платеж обрабатывается...\n\n'
                                'Пожалуйста, подождите несколько минут и попробуйте снова.\n'
                                'Если вы уже оплатили, но статус не обновился, обратитесь в поддержку.',
                                reply_markup=self.get_main_keyboard()
                            )
                            return
                    
                    # Если прошло больше 5 минут, предлагаем проверить вручную
                    await message.reply(
                        '⏰ Платеж создан более 5 минут назад.\n\n'
                        'Для проверки статуса оплаты:\n'
                        '1. Убедитесь, что вы завершили оплату на странице Lemon Squeezy\n'
                        '2. Если оплата прошла, но статус не обновился, обратитесь в поддержку\n'
                        '3. Укажите ваш ID: ' + str(user_id),
                        reply_markup=self.get_main_keyboard()
                    )
                    
                except Exception as e:
                    await message.reply(
                        f'Ошибка при проверке платежа: {str(e)}\n\nПопробуйте позже или обратитесь в поддержку.',
                        reply_markup=self.get_main_keyboard()
                    )
                    
            else:
                # Проверяем YooKassa платеж (старая логика)
                from yookassa import Payment
                import datetime
                payment = Payment.find_one(payment_id)
                
                if payment.status == 'succeeded':
                    end_date = datetime.datetime.now() + datetime.timedelta(days=30 * (tariff[6] if tariff else 1))
                    end_date_str = end_date.strftime("%Y-%m-%d")
                    await self.user_repo.set_subscription(user_id, tariff[5] if tariff else 1, end_date_str, tariff_id)
                    await message.reply(
                        f'✅ Оплата прошла успешно!\n\nТариф: {tariff[1] if tariff else tariff_id}\nПодписка активна до: {end_date_str}\n\nТеперь вы можете использовать все возможности сервиса!',
                        reply_markup=self.get_main_keyboard()
                    )
                    del self.user_tariff[user_id]
                elif payment.status == 'pending':
                    await message.reply('Платёж ещё не завершён. Пожалуйста, оплатите по ссылке и попробуйте снова.', reply_markup=self.get_main_keyboard())
                else:
                    await message.reply(f'Платёж не прошёл или отменён. Статус: {payment.status}', reply_markup=self.get_main_keyboard())
                    del self.user_tariff[user_id]

        @self.dp.message_handler(lambda m: m.text == "🌐💳 Зарубежная карта")
        async def pay_foreign(message: types.Message):
            try:
                print(f"[PAY_FOREIGN] Начало обработки для пользователя {message.from_user.id}")
                
                if await self.check_ban(message): return
                user_id = getattr(message.from_user, 'id', None)
                
                if user_id not in self.user_tariff:
                    await message.reply("Сначала выберите тариф!", reply_markup=self.get_tariff_keyboard())
                    return
                
                tariff_data = self.user_tariff[user_id]
                tariff_id = tariff_data.get('tariff_id')
                
                print(f"[PAY_FOREIGN] Данные тарифа: {tariff_data}")
                
                if not tariff_id:
                    await message.reply("Ошибка: тариф не найден. Выберите тариф заново.", reply_markup=self.get_tariff_keyboard())
                    return
                
                # Получаем информацию о тарифе
                tariff = await self.user_repo.get_tariff(tariff_id)
                if not tariff:
                    await message.reply("Ошибка: тариф не найден в базе данных.", reply_markup=self.get_tariff_keyboard())
                    return
                
                print(f"[PAY_FOREIGN] Тариф из БД: {tariff}")
                
                tariff_name = tariff[1]
                base_price = tariff[3]  # Цена в копейках
                price_rub = int(base_price) / 100
                
                print(f"[PAY_FOREIGN] Базовая цена: {price_rub}₽")
                
                # Применяем скидку, если есть
                discount = await self.user_repo.get_active_discount(tariff_id)
                final_price_rub = price_rub
                discount_text = ""
                
                if discount:
                    discount_percent = discount
                    final_price_rub = price_rub * (1 - discount_percent / 100)
                    discount_text = f"\n🎉 <b>СКИДКА {discount_percent}%!</b>\n"
                    discount_text += f"~~{price_rub:.0f}₽~~ → <b>{final_price_rub:.0f}₽</b>\n"
                    print(f"[PAY_FOREIGN] Применена скидка {discount_percent}%, итоговая цена: {final_price_rub}₽")
                
                # Проверяем API ключ Lemon Squeezy
                print(f"[PAY_FOREIGN] Lemon Squeezy API key: {'Установлен' if self.lemonsqueezy_api_key else 'НЕ УСТАНОВЛЕН'}")
                print(f"[PAY_FOREIGN] Lemon Squeezy Product ID: {self.lemonsqueezy_product_id}")
                
                if not self.lemonsqueezy_api_key:
                    payment_text = f"💳 <b>Оплата зарубежной картой</b>\n\n"
                    payment_text += f"📦 Тариф: <b>{tariff_name}</b>\n"
                    payment_text += f"💰 Сумма: <b>{final_price_rub:.0f}₽</b>\n"
                    payment_text += f"💳 Способ: <b>Lemon Squeezy</b>\n\n"
                    
                    if discount_text:
                        payment_text += discount_text
                    
                    payment_text += "⚠️ <b>ВНИМАНИЕ:</b> API ключ Lemon Squeezy не настроен.\n"
                    payment_text += "Обратитесь к администратору для настройки."
                    
                    await message.reply(payment_text, parse_mode="HTML", reply_markup=self.get_payment_keyboard())
                    return
                
                # Получаем курс RUB→USD через CryptoBot API
                rub_to_usd = None
                if self.cryptobot_api_key:
                    try:
                        print(f"[PAY_FOREIGN] Получение курса валют через CryptoBot...")
                        async with CryptoBotClient(self.cryptobot_api_key) as cryptobot:
                            exchange_rates = await cryptobot.get_exchange_rates()
                            
                            # Ищем курс RUB→USD
                            for rate in exchange_rates:
                                if rate.get('source') == 'RUB' and rate.get('target') == 'USD':
                                    rub_to_usd = float(rate['rate'])
                                    print(f"[PAY_FOREIGN] Найден прямой курс RUB→USD: {rub_to_usd}")
                                    break
                            
                            # Если не найден прямой курс, ищем обратный
                            if not rub_to_usd:
                                for rate in exchange_rates:
                                    if rate.get('source') == 'USD' and rate.get('target') == 'RUB':
                                        rub_to_usd = 1 / float(rate['rate'])
                                        print(f"[PAY_FOREIGN] Найден обратный курс USD→RUB, вычислен RUB→USD: {rub_to_usd}")
                                        break
                    except Exception as e:
                        print(f"[PAY_FOREIGN] Ошибка получения курса валют: {e}")
                
                # Если не удалось получить курс, используем фиксированный
                if not rub_to_usd or rub_to_usd <= 0:
                    rub_to_usd = 0.011  # Примерный курс 1 RUB = 0.011 USD (90 RUB за 1 USD)
                    print(f"[PAY_FOREIGN] Используется фиксированный курс: {rub_to_usd}")
                
                # Проверяем разумность курса
                if rub_to_usd > 1:
                    print(f"[PAY_FOREIGN] ВНИМАНИЕ: Курс слишком высокий ({rub_to_usd}), используем фиксированный")
                    rub_to_usd = 0.011
                
                # Конвертируем цену в USD
                final_price_usd = round(final_price_rub * rub_to_usd, 2)
                print(f"[PAY_FOREIGN] Конвертированная цена в USD: ${final_price_usd}")
                print(f"[PAY_FOREIGN] Расчет: {final_price_rub}₽ × {rub_to_usd} = ${final_price_usd}")
                
                # Проверяем разумность суммы
                if final_price_usd <= 0 or final_price_usd > 10000:
                    print(f"[PAY_FOREIGN] ОШИБКА: Некорректная сумма ${final_price_usd}")
                    await message.reply('Ошибка: рассчитанная сумма для оплаты некорректна. Обратитесь к администратору.', reply_markup=self.get_payment_keyboard())
                    return
                
                # Создаем checkout через Lemon Squeezy
                print(f"[PAY_FOREIGN] Создание checkout через Lemon Squeezy...")
                async with LemonSqueezyClient(self.lemonsqueezy_api_key) as lemonsqueezy:
                    checkout = await lemonsqueezy.create_checkout(
                        product_id=self.lemonsqueezy_product_id,
                        user_id=user_id,
                        tariff_id=tariff_id,
                        amount_usd=final_price_usd,
                        description=f"Подписка {tariff_name}"
                    )
                    
                    print(f"[PAY_FOREIGN] Checkout создан: {checkout}")
                    
                    # Сохраняем информацию о платеже
                    payment_id = await self.user_repo.create_payment(
                        user_id=user_id,
                        tariff_id=tariff_id,
                        amount=int(final_price_rub * 100),  # В копейках
                        currency="RUB",
                        payment_method="lemonsqueezy",
                        external_id=checkout['id']
                    )
                    
                    print(f"[PAY_FOREIGN] Платеж сохранен в БД с ID: {payment_id}")
                    
                    # Обновляем user_tariff
                    self.user_tariff[user_id] = {
                        'tariff_id': tariff_id,
                        'payment_id': payment_id,
                        'checkout_id': checkout['id']
                    }
                    
                    # Формируем сообщение с ссылкой на оплату
                    payment_text = f"💳 <b>Оплата зарубежной картой</b>\n\n"
                    payment_text += f"📦 Тариф: <b>{tariff_name}</b>\n"
                    payment_text += f"💰 Сумма: <b>{final_price_rub:.0f}₽</b> (${final_price_usd})\n"
                    payment_text += f"💳 Способ: <b>Lemon Squeezy</b>\n\n"
                    
                    if discount_text:
                        payment_text += discount_text
                    
                    payment_text += f"🔗 <a href='{checkout['attributes']['url']}'>Оплатить картой</a>\n\n"
                    payment_text += "⚠️ <b>ВАЖНО:</b>\n"
                    payment_text += "• Принимаются карты Visa, MasterCard, American Express\n"
                    payment_text += "• Оплата обрабатывается автоматически\n"
                    payment_text += "• После оплаты подписка активируется\n"
                    payment_text += "• Если оплата не прошла, попробуйте еще раз"
                    
                    # Создаем клавиатуру с кнопкой проверки оплаты
                    check_keyboard = ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text="✅ Проверить оплату")],
                            [KeyboardButton(text="📋 К выбору тарифа"), KeyboardButton(text="🔙 Назад в меню")],
                        ],
                        resize_keyboard=True,
                        one_time_keyboard=False,
                        input_field_placeholder='',
                        selective=False,
                        is_persistent=False
                    )
                    
                    await message.reply(payment_text, parse_mode="HTML", reply_markup=check_keyboard)
                    print(f"[PAY_FOREIGN] Сообщение об оплате отправлено пользователю")
                    
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"[PAY_FOREIGN] Ошибка: {e}")
                print(f"[PAY_FOREIGN] Traceback: {tb}")
                await message.reply(f"❌ Внутренняя ошибка:\n<code>{e}</code>", parse_mode="HTML")

        @self.dp.message_handler(lambda m: m.text == "₿ Оплатить через CryptoBot")
        async def pay_cryptobot(message: types.Message):
            try:
                if await self.check_ban(message): return
                user_id = getattr(message.from_user, 'id', None)
                if user_id not in self.user_tariff:
                    await message.reply("Сначала выберите тариф!", reply_markup=self.get_tariff_keyboard())
                    return
                tariff_data = self.user_tariff[user_id]
                tariff_id = tariff_data.get('tariff_id')
                if not tariff_id:
                    await message.reply("Ошибка: тариф не найден. Выберите тариф заново.", reply_markup=self.get_tariff_keyboard())
                    return
                # Получаем информацию о тарифе
                tariff = await self.user_repo.get_tariff(tariff_id)
                if not tariff:
                    await message.reply("Ошибка: тариф не найден в базе данных.", reply_markup=self.get_tariff_keyboard())
                    return
                tariff_name = tariff[1]
                base_price = tariff[3]  # Цена в копейках
                price_rub = int(base_price) / 100
                # Применяем скидку, если есть
                discount = await self.user_repo.get_active_discount(tariff_id)
                final_price = price_rub
                discount_text = ""
                if discount:
                    discount_percent = discount
                    final_price = price_rub * (1 - discount_percent / 100)
                    discount_text = f"\n🎉 <b>СКИДКА {discount_percent}%!</b>\n"
                    discount_text += f"~~{price_rub:.0f}₽~~ → <b>{final_price:.0f}₽</b>\n"
                if not self.cryptobot_api_key:
                    payment_text = f"💳 <b>Оплата через CryptoBot</b>\n\n"
                    payment_text += f"📦 Тариф: <b>{tariff_name}</b>\n"
                    payment_text += f"💰 Сумма: <b>{final_price:.0f}₽</b>\n"
                    payment_text += f"💎 Криптовалюта: <b>USDT</b>\n\n"
                    if discount_text:
                        payment_text += discount_text
                    payment_text += "⚠️ <b>ВНИМАНИЕ:</b> Для оплаты через CryptoBot нужен API ключ.\n"
                    payment_text += "Получите его в @CryptoBot: /start → Crypto Pay → Create App\n\n"
                    payment_text += "🔗 После получения API ключа, отправьте его администратору для настройки."
                    await message.reply(payment_text, parse_mode="HTML", reply_markup=self.get_payment_keyboard())
                    return
                # Получаем курс RUB→USDT через CryptoBot API
                async with CryptoBotClient(self.cryptobot_api_key) as cryptobot:
                    exchange_rates = await cryptobot.get_exchange_rates()
                    rub_to_usdt = None
                    usdt_to_rub = None
                    for rate in exchange_rates:
                        if rate.get('source') == 'RUB' and rate.get('target') == 'USDT':
                            rub_to_usdt = float(rate['rate'])
                        if rate.get('source') == 'USDT' and rate.get('target') == 'RUB':
                            usdt_to_rub = float(rate['rate'])
                    # Корректно определяем курс
                    if rub_to_usdt and rub_to_usdt > 0:
                        amount_usdt = round(final_price / rub_to_usdt, 2)
                        used_rate = rub_to_usdt
                        rate_type = 'RUB→USDT'
                    elif usdt_to_rub and usdt_to_rub > 0:
                        amount_usdt = round(final_price / usdt_to_rub, 2)
                        used_rate = usdt_to_rub
                        rate_type = 'USDT→RUB (инверсия)'
                    else:
                        await message.reply('Не удалось получить курс RUB↔USDT для оплаты через CryptoBot. Попробуйте позже.', reply_markup=self.get_payment_keyboard())
                        return
                    if amount_usdt <= 0:
                        await message.reply('Ошибка: рассчитанная сумма для оплаты в USDT некорректна. Обратитесь к администратору.', reply_markup=self.get_payment_keyboard())
                        return
                    # Для отладки (можно раскомментировать):
                    # await message.reply(f"DEBUG: RUB={final_price}, rate={used_rate} ({rate_type}), USDT={amount_usdt}")
                    payload = f"user_{user_id}_tariff_{tariff_id}"
                    invoice = await cryptobot.create_invoice(
                        amount=amount_usdt,
                        currency="USDT",
                        description=f"Оплата тарифа {tariff_name}",
                        paid_btn_name="viewItem",
                        paid_btn_url="https://t.me/your_bot_username",
                        payload=payload
                    )
                    payment_id = await self.user_repo.create_payment(
                        user_id=user_id,
                        tariff_id=tariff_id,
                        amount=int(final_price * 100),
                        currency="RUB",
                        payment_method="cryptobot",
                        external_id=invoice["invoice_id"]
                    )
                    self.user_tariff[user_id] = {
                        'tariff_id': tariff_id,
                        'payment_id': payment_id,
                        'invoice_id': invoice["invoice_id"]
                    }
                    payment_text = f"💳 <b>Оплата через CryptoBot</b>\n\n"
                    payment_text += f"📦 Тариф: <b>{tariff_name}</b>\n"
                    payment_text += f"💰 Сумма: <b>{final_price:.0f}₽</b>\n"
                    payment_text += f"💎 Криптовалюта: <b>USDT</b>\n\n"
                    if discount_text:
                        payment_text += discount_text
                    payment_text += f"🔗 <a href='{invoice['pay_url']}'>Оплатить через CryptoBot</a>\n\n"
                    payment_text += "⚠️ <b>ВАЖНО:</b>\n"
                    payment_text += "• Оплата обрабатывается автоматически\n"
                    payment_text += "• После оплаты подписка активируется\n"
                    payment_text += "• Если оплата не прошла, попробуйте еще раз"
                    check_keyboard = ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text="✅ Проверить оплату")],
                            [KeyboardButton(text="📋 К выбору тарифа"), KeyboardButton(text="🔙 Назад в меню")],
                        ],
                        resize_keyboard=True,
                        one_time_keyboard=False,
                        input_field_placeholder='',
                        selective=False,
                        is_persistent=False
                    )
                    await message.reply(payment_text, parse_mode="HTML", reply_markup=check_keyboard)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                await message.reply(f"❌ Внутренняя ошибка:\n<code>{e}</code>\n<code>{tb}</code>", parse_mode="HTML")
                print(f"Ошибка в pay_cryptobot: {e}\n{tb}")

        @self.dp.message_handler(lambda m: m.text == "📋 К выбору тарифа")
        async def back_to_tariffs(message: types.Message):
            if await self.check_ban(message): return
            await message.reply('Выберите тариф:', reply_markup=self.get_tariff_keyboard())

        @self.dp.message_handler(commands=["support_on"])
        async def cmd_support_on(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            # Убираем проверку бана для админских команд
            await self.user_repo.set_support_notify(user_id, off=False)
            await message.reply('Уведомления поддержки включены.')

        @self.dp.message_handler(commands=["support_off"])
        async def cmd_support_off(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            # Убираем проверку бана для админских команд
            await self.user_repo.set_support_notify(user_id, off=True)
            await message.reply('Уведомления поддержки отключены.')

        @self.dp.message_handler(commands=["reply"])
        async def cmd_reply(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 1:
                await message.reply('Недостаточно прав.')
                return
            # Убираем проверку бана для админских команд
            args = message.text.split(maxsplit=2) if message.text else []
            if len(args) < 3:
                await message.reply('Использование: /reply <id> <ответ>')
                return
            qid, answer = args[1], args[2]
            question = await self.user_repo.get_support_question(qid)
            if not question:
                await message.reply('Вопрос не найден.')
                return
            # Отправляем ответ пользователю
            try:
                await self.bot.send_message(question[1], f'Ответ поддержки: {answer}')
            except Exception:
                pass
            await self.user_repo.answer_support_question(qid, answer, user_id)
            await message.reply('Ответ отправлен.')

        # Исправление: если пользователь в режиме подачи апелляции, не делать проверку бана в support_collect
        @self.dp.message_handler(lambda m: not m.text or not m.text.startswith('/') and (not hasattr(self, 'appeal_waiting') or getattr(m.from_user, 'id', None) not in getattr(self, 'appeal_waiting', set())))
        async def support_collect(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            if user_id in self.support_waiting:
                # Получаем тему обращения
                topic = getattr(self, 'support_topics', {}).get(user_id, None)
                qid = await self.user_repo.add_support_question(user_id, getattr(message.from_user, 'username', None), message.text, topic)
                self.support_waiting.remove(user_id)
                if hasattr(self, 'support_topics') and user_id in self.support_topics:
                    del self.support_topics[user_id]
                admin_ids = await self.user_repo.get_admins_with_notify()
                for aid in admin_ids:
                    try:
                        topic_text = f"\nТема: {topic}" if topic else ""
                        await self.bot.send_message(aid, f'Новый вопрос поддержки #{qid} от @{getattr(message.from_user, "username", user_id)}:{topic_text}\n{message.text}\n\nДля ответа: /reply {qid} <ответ>')
                    except Exception:
                        pass
                await message.reply('Ваше сообщение передано в службу поддержки. Ожидайте ответа.', reply_markup=self.get_main_keyboard())
            else:
                pass  # Не отвечаем, если пользователь не в режиме поддержки

        @self.dp.callback_query_handler(lambda c: re.match(r'^all_answer:(\\d+)$', c.data))
        async def cb_all_answer(callback: types.CallbackQuery):
            user_id = getattr(callback.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 1:
                await callback.answer('Недостаточно прав.', show_alert=True)
                return
            import re
            m = re.match(r'all_answer:(\\d+)', callback.data or '')
            page = int(m.group(1)) if m else 1
            PAGE_SIZE = 10
            offset = (page - 1) * PAGE_SIZE
            questions = await self.user_repo.get_support_questions(offset, PAGE_SIZE)
            total = await self.user_repo.count_support_questions()
            if not questions:
                await callback.answer('Нет вопросов поддержки.', show_alert=True)
                return
            lines = []
            for q in questions:
                # Обрабатываем разные структуры данных (с topic и без)
                if len(q) >= 8:  # Новая структура с topic
                    qid, uid, uname, text, topic, created, status, answer, answered_by = q[:9]
                    topic_str = f"\nТема: {topic}" if topic else ""
                else:  # Старая структура без topic
                    qid, uid, uname, text, created, status, answer, answered_by = q[:8]
                    topic_str = ""
                
                status_str = 'ожидает ответа' if not answer else 'отвечено'
                answer_str = answer if answer else '—'
                lines.append(f'#{qid} от @{uname} ({created[:16]}){topic_str}\nВопрос: {text}\nОтвет: {answer_str}\nСтатус: {status_str}\n')
            text_out = '\n'.join(lines)
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            buttons = []
            if page > 1:
                buttons.append(InlineKeyboardButton(text=f'⬅️ Стр. {page-1}', callback_data=f'all_answer:{page-1}'))
            if offset + PAGE_SIZE < total:
                buttons.append(InlineKeyboardButton(text=f'Стр. {page+1} ➡️', callback_data=f'all_answer:{page+1}'))
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
            try:
                await callback.message.edit_text(text_out, reply_markup=markup)
            except Exception:
                await callback.answer(text_out, show_alert=True)
            await callback.answer()

        async def support_instruction(message: types.Message):
            await message.reply(
                "<b>Служба заботы уже мчится со всех ног!</b> 🏃‍♂️💨\n\n"
                "Пока оператор подключается – опиши свою проблему максимально подробно. Если требуется – приложи скриншоты.\n\n"
                "Мы работаем с 10:00 до 22:00 по Мск",
                parse_mode="HTML"
            )

        @self.dp.message_handler(lambda m: m.text == "🔙 Назад в меню")
        async def back_to_menu_from_support(message: types.Message):
            if await self.check_ban(message): return
            await message.reply('Главное меню', reply_markup=self.get_main_keyboard())

        @self.dp.message_handler(commands=["orders"])
        async def cmd_orders(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав.')
                return
            
            args = message.text.split() if message.text else []
            if len(args) < 2:
                await message.reply('Использование: /orders <all|pending|paid> [limit]')
                return
            
            status_filter = args[1]
            limit = int(args[2]) if len(args) > 2 else 10
            
            if status_filter not in ['all', 'pending', 'paid']:
                await message.reply('Статус должен быть: all, pending или paid')
                return
            
            try:
                if status_filter == 'all':
                    orders = await self.user_repo.get_all_orders(limit)
                elif status_filter == 'pending':
                    orders = await self.user_repo.get_pending_orders()
                else:  # paid
                    orders = await self.user_repo.get_paid_orders(limit)
                
                if not orders:
                    await message.reply(f'Заказы со статусом "{status_filter}" не найдены.')
                    return
                
                lines = [f'Заказы ({status_filter}):']
                orders_list = list(orders)[:limit]
                for order in orders_list:
                    order_id, user_id, tariff_id, amount, currency, status, created_at, paid_at = order[:8]
                    tariff = await self.user_repo.get_tariff(tariff_id)
                    tariff_title = tariff[1] if tariff and len(tariff) > 1 else tariff_id
                    amount_rub = amount / 100 if amount else 0
                    created_date = created_at[:10] if created_at else "N/A"
                    lines.append(f'{order_id} | {user_id} | {tariff_title} | {amount_rub} {currency} | {status} | {created_date}')
                
                await message.reply('\n'.join(lines))
                
            except Exception as e:
                await message.reply(f'Ошибка: {e}')

        @self.dp.message_handler(commands=["give_users"])
        async def cmd_give_users(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            page = 1
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit():
                page = int(args[1])
            page_size = 10
            users = await self.user_repo.get_users_page(page, page_size)
            total = await self.user_repo.count_users()
            if not users:
                await message.reply('Нет пользователей.')
                return
            lines = []
            for u in users:
                uid, uname, sub, sub_rank = u
                sub_str = 'Нет' if not sub else ('Базовый' if sub_rank == 1 else ('Про' if sub_rank == 2 else 'Неизвестно'))
                lines.append(f'{uid} | {uname} | {sub_str} | {sub_rank}')
            text = '\n'.join(lines)
            buttons = []
            if page > 1:
                buttons.append(InlineKeyboardButton(text=f'⬅️ {page-1}', callback_data=f'give_users:{page-1}'))
            if page * page_size < total:
                buttons.append(InlineKeyboardButton(text=f'{page+1} ➡️', callback_data=f'give_users:{page+1}'))
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
            await message.reply(text, reply_markup=markup)

        @self.dp.callback_query_handler(lambda c: re.match(r'^give_users:(\d+)$', c.data))
        async def cb_give_users(callback: types.CallbackQuery):
            user_id = getattr(callback.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await callback.answer('Недостаточно прав.', show_alert=True)
                return
            import re
            m = re.match(r'give_users:(\d+)', callback.data or '')
            page = int(m.group(1)) if m else 1
            page_size = 10
            users = await self.user_repo.get_users_page(page, page_size)
            total = await self.user_repo.count_users()
            if not users:
                await callback.answer('Нет пользователей.', show_alert=True)
                return
            lines = []
            for u in users:
                uid, uname, sub, sub_rank = u
                sub_str = 'Нет' if not sub else ('Базовый' if sub_rank == 1 else ('Про' if sub_rank == 2 else 'Неизвестно'))
                lines.append(f'{uid} | {uname} | {sub_str} | {sub_rank}')
            text = '\n'.join(lines)
            buttons = []
            if page > 1:
                buttons.append(InlineKeyboardButton(text=f'⬅️ {page-1}', callback_data=f'give_users:{page-1}'))
            if page * page_size < total:
                buttons.append(InlineKeyboardButton(text=f'{page+1} ➡️', callback_data=f'give_users:{page+1}'))
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
            try:
                await callback.message.edit_text(text, reply_markup=markup)
            except Exception:
                await callback.answer(text, show_alert=True)
            await callback.answer()

        @self.dp.message_handler(commands=["logs"])
        async def cmd_logs(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав.')
                return
            page = 1
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit():
                page = int(args[1])
            page_size = 10
            logs = await self.user_repo.get_admin_logs(offset=(page-1)*page_size, limit=page_size)
            if not logs:
                await message.reply('Нет логов.')
                return
            lines = []
            for log in logs:
                aid, aname, action, atime = log
                lines.append(f'{aid} | {aname} | {action} | {atime[:16]}')
            text = '\n'.join(lines)
            await message.reply(text)

        @self.dp.message_handler(commands=["banned"])
        async def cmd_banned(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            banned_users = await self.user_repo.get_banned_users()
            if not banned_users:
                await message.reply('Нет заблокированных пользователей.')
                return
            lines = []
            for u in banned_users:
                uid, uname, banned_until, reason, admin_id, admin_username, action_time = u
                admin_str = f'@{admin_username}' if admin_username else f'{admin_id}' if admin_id else 'неизвестно'
                lines.append(f'{uid} | {uname} | {banned_until} | {reason} | {admin_str}')
            await message.reply('\n'.join(lines))

        @self.dp.callback_query_handler(lambda c: re.match(r'^add_timestamps:(.+?):(.+)$', c.data))
        async def add_timestamps_callback(callback: types.CallbackQuery):
            user_id = getattr(callback.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            if not user:
                await callback.answer('Ошибка пользователя. Попробуйте позже.', show_alert=True)
                return
            import re
            m = re.match(r'add_timestamps:(.+?):(.+)', callback.data or '')
            if not m:
                await callback.answer('Ошибка данных.', show_alert=True)
                return
            file_id, lang_code = m.group(1), m.group(2)
            file_path, orig_name = self.user_files.get((user_id, file_id), (None, None))
            if not file_path:
                await callback.answer('Файл не найден. Попробуйте заново.', show_alert=True)
                return
            # Определяем имя файла для Google Docs
            if not orig_name:
                if hasattr(file_path, 'file_name'):
                    orig_name = file_path.file_name.rsplit('.', 1)[0]
                else:
                    try:
                        orig_name = os.path.splitext(os.path.basename(file_path))[0]
                    except Exception:
                        orig_name = 'transcription'
            duration = self.transcriber.get_duration(file_path)
            if duration <= 300:
                text_with_ts = self.transcriber.get_text_with_timestamps(file_path, lang_code)
                MAX_TG_TEXT_LEN = 4096
                if len(text_with_ts) > MAX_TG_TEXT_LEN:
                    docx_path = self.transcriber.get_docx_with_timestamps(file_path, lang_code)
                    link = self.transcriber.upload_docx_to_gdrive(docx_path, filename=f"{orig_name}_transcript.docx")
                    markup = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="Транскрипция с таймкодом", url=link)]
                        ]
                    )
                    await callback.message.edit_text(
                        f'Текст с таймкодами слишком длинный для чата. Вот ссылка на Google Docs:',
                        reply_markup=markup
                    )
                    os.remove(docx_path)
                    # Удаляем временный файл после использования
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                    # Удаляем из user_files
                    if (user_id, file_id) in self.user_files:
                        del self.user_files[(user_id, file_id)]
                else:
                    try:
                        await callback.message.edit_text(text_with_ts, reply_markup=None)
                        # Удаляем временный файл после использования
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                        # Удаляем из user_files
                        if (user_id, file_id) in self.user_files:
                            del self.user_files[(user_id, file_id)]
                    except Exception:
                        await callback.answer('Не удалось обновить сообщение.', show_alert=True)
            else:
                docx_path = self.transcriber.get_docx_with_timestamps(file_path, lang_code)
                link = self.transcriber.upload_docx_to_gdrive(docx_path, filename=f"{orig_name}_transcript.docx")
                # Вместо edit_text отправляем новое сообщение, чтобы не было ошибки Telegram
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Транскрипция с таймкодом", url=link)]
                    ]
                )
                await callback.message.answer(
                    f'Текст с таймкодами слишком длинный для чата. Вот ссылка на Google Docs:',
                    reply_markup=markup
                )
                os.remove(docx_path)
                # Удаляем временный файл после использования
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                # Удаляем из user_files
                if (user_id, file_id) in self.user_files:
                    del self.user_files[(user_id, file_id)]

        # Обработчики для апелляций
        @self.dp.callback_query_handler(lambda c: c.data == "submit_appeal")
        async def submit_appeal_callback(callback: types.CallbackQuery):
            user_id = getattr(callback.from_user, 'id', None)
            if not user_id:
                await callback.answer('Ошибка пользователя.', show_alert=True)
                return
            
            # Добавляем пользователя в режим подачи апелляции
            if not hasattr(self, 'appeal_waiting'):
                self.appeal_waiting = set()
            self.appeal_waiting.add(user_id)
            
            await callback.message.edit_text(
                '📝 Подача апелляции\n\n'
                'Опишите подробно, почему вы считаете, что блокировка была применена по ошибке. '
                'Будьте вежливы и конструктивны.\n\n'
                'Отправьте ваше обращение одним сообщением:'
            )
            await callback.answer()

        @self.dp.callback_query_handler(lambda c: c.data == "appeal_already_submitted")
        async def appeal_already_submitted_callback(callback: types.CallbackQuery):
            await callback.answer('Ваша апелляция уже на рассмотрении. Это может занимать до 48 часов.', show_alert=True)

        # Обработчик для текста апелляции
        @self.dp.message_handler(lambda m: m.text and not m.text.startswith('/') and hasattr(self, 'appeal_waiting') and getattr(m.from_user, 'id', None) in getattr(self, 'appeal_waiting', set()))
        async def handle_appeal_text(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            if user_id not in self.appeal_waiting:
                return
            
            self.appeal_waiting.remove(user_id)
            
            # Получаем информацию о бане
            user = await self.user_repo.get_user(user_id)
            ban_reason = user[10] if user and user[10] else "Не указана"
            
            # Создаем апелляцию
            appeal_id = await self.user_repo.create_appeal(
                user_id, 
                getattr(message.from_user, 'username', None), 
                ban_reason, 
                message.text
            )
            
            # Отправляем уведомление админам уровня 2+
            admin_ids = await self.user_repo.get_admins_with_notify()
            for aid in admin_ids:
                admin_user = await self.user_repo.get_user(aid)
                if admin_user and admin_user[2] >= 2:  # Только админы 2+ уровня
                    try:
                        await self.bot.send_message(
                            aid, 
                            f'📝 Новая апелляция #{appeal_id} от @{getattr(message.from_user, "username", user_id)}\n\n'
                            f'Причина бана: {ban_reason}\n'
                            f'Текст апелляции: {message.text}\n\n'
                            f'Для ответа: /appeal {appeal_id} <ответ>'
                        )
                    except Exception:
                        pass
            
            await message.reply(
                '✅ Ваша апелляция подана и передана на рассмотрение администрации.\n\n'
                'Ожидайте ответа. Это может занимать до 48 часов.',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="appeal_submitted")]
                ])
            )

        # Команды для работы с апелляциями
        @self.dp.message_handler(commands=["get_appeal"])
        async def cmd_get_appeal(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            
            appeals = await self.user_repo.get_all_appeals()
            if not appeals:
                await message.reply('Нет апелляций.')
                return
            
            lines = []
            for appeal in appeals:
                aid, uid, uname, ban_reason, appeal_text, created, status, admin_response, reviewed_by, reviewed_at = appeal
                status_str = '⏳ На рассмотрении' if status == 'pending' else '✅ Рассмотрена'
                lines.append(f'#{aid} от @{uname} ({created[:16]})\nСтатус: {status_str}\nПричина бана: {ban_reason[:50]}...')
            
            await message.reply('\n\n'.join(lines))

        @self.dp.message_handler(commands=["appeal"])
        async def cmd_appeal(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            if await self.check_ban(message): return
            
            args = message.text.split(maxsplit=2) if message.text else []
            if len(args) < 3:
                await message.reply('Использование: /appeal <id> <ответ>')
                return
            
            appeal_id, response = args[1], args[2]
            try:
                appeal = await self.user_repo.get_appeal(appeal_id)
                if not appeal:
                    await message.reply('Апелляция не найдена.')
                    return
                
                if appeal[6] != 'pending':
                    await message.reply('Эта апелляция уже рассмотрена.')
                    return
                
                # Отвечаем на апелляцию
                await self.user_repo.respond_to_appeal(appeal_id, user_id, getattr(message.from_user, 'username', None), response)
                
                # Отправляем ответ пользователю
                try:
                    await self.bot.send_message(
                        appeal[1], 
                        f'📝 Ответ на вашу апелляцию #{appeal_id}:\n\n{response}'
                    )
                except Exception:
                    pass
                
                await message.reply('Ответ на апелляцию отправлен.')
                
            except Exception as e:
                await message.reply(f'Ошибка: {e}')

        @self.dp.message_handler(commands=["all_answer"])
        async def cmd_all_answer(message: types.Message):
            print('ALL_ANSWER TRIGGERED', getattr(message.from_user, 'id', None), getattr(message.from_user, 'username', None))
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 2:
                await message.reply('Недостаточно прав.')
                return
            # Получаем страницу из callback или текста
            page = 1
            m = re.search(r'/all_answer(\s+(\d+))?', message.text or "")
            if m and m.group(2):
                page = int(m.group(2))
            PAGE_SIZE = 10
            offset = (page - 1) * PAGE_SIZE
            # Получаем вопросы
            questions = await self.user_repo.get_support_questions(offset, PAGE_SIZE)
            total = await self.user_repo.count_support_questions()
            if not questions:
                await message.reply('Нет вопросов поддержки.')
                return
            lines = []
            for q in questions:
                # Обрабатываем разные структуры данных (с topic и без)
                if len(q) >= 8:  # Новая структура с topic
                    qid, uid, uname, text, topic, created, status, answer, answered_by = q[:9]
                    topic_str = f"\nТема: {topic}" if topic else ""
                else:  # Старая структура без topic
                    qid, uid, uname, text, created, status, answer, answered_by = q[:8]
                    topic_str = ""
                
                status_str = 'ожидает ответа' if not answer else 'отвечено'
                answer_str = answer if answer else '—'
                lines.append(f'#{qid} от @{uname} ({created[:16]}){topic_str}\nВопрос: {text}\nОтвет: {answer_str}\nСтатус: {status_str}\n')
            text_out = '\n'.join(lines)
            # Кнопки навигации
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            buttons = []
            if page > 1:
                buttons.append(InlineKeyboardButton(text=f'⬅️ Стр. {page-1}', callback_data=f'all_answer:{page-1}'))
            if offset + PAGE_SIZE < total:
                buttons.append(InlineKeyboardButton(text=f'Стр. {page+1} ➡️', callback_data=f'all_answer:{page+1}'))
            if buttons:
                markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
                await message.reply(text_out, reply_markup=markup)
            else:
                await message.reply(text_out)

        @self.dp.message_handler(commands=["amount"])
        async def cmd_amount(message: types.Message):
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id)
            if not user or user[2] < 3:
                await message.reply('Недостаточно прав. Требуется уровень 3 админа.')
                return
            if await self.check_ban(message): return
            args = message.text.split()
            if len(args) < 4:
                await message.reply('Использование: /amount <plan_id> <percent> <срок: 1d-30d>')
                return
            plan_id, percent_str, period = args[1], args[2], args[3]
            try:
                percent = int(percent_str)
            except Exception:
                await message.reply('Процент должен быть целым числом.')
                return
            # Определяем срок скидки
            import datetime
            tariff = await self.user_repo.get_tariff(plan_id)
            if not tariff:
                await message.reply('Тариф с таким id не найден.')
                return
            if period.endswith('d'):
                value = int(period[:-1])
                delta = datetime.timedelta(days=value)
            elif period.endswith('h'):
                value = int(period[:-1])
                delta = datetime.timedelta(hours=value)
            else:
                await message.reply('Срок должен быть в формате 1d-30d или 1h-24h.')
                return
            now = datetime.datetime.now()
            end_time = now + delta
            await self.user_repo.set_discount(plan_id, percent, now.isoformat(), end_time.isoformat())
            await self.user_repo.log_admin_action(user_id, getattr(message.from_user, 'username', None), f'set discount {plan_id} {percent}% {period}')
            await message.reply(f'Скидка {percent}% на тариф {plan_id} установлена до {end_time.strftime("%d.%m.%Y %H:%M")}!')
            # Постраничная рассылка всем пользователям
            from aiogram.utils.exceptions import BotBlocked
            page = 1
            page_size = 1000
            tariff_title = tariff[1] if tariff else plan_id
            while True:
                users = await self.user_repo.get_users_page(page=page, page_size=page_size)
                if not users:
                    break
                for u in users:
                    try:
                        await safe_send_message(self.bot, u[0], f'🔥 Внимание! На тариф "{tariff_title}" действует скидка {percent}% до {end_time.strftime("%d.%m.%Y %H:%M")}!')
                    except Exception:
                        pass
                page += 1

        # --- Исправляю отправку длинных сообщений в handle_links ---
        @self.dp.message_handler(lambda m: re.search(r'https?://', m.text or ""))
        async def handle_links(message: types.Message):
            if await self.check_ban(message): return
            user_id = getattr(message.from_user, 'id', None)
            user = await self.user_repo.get_user(user_id) if user_id is not None else None
            if not user:
                await message.reply('Пожалуйста, нажмите СТАРТ для начала работы.')
                return
            sub = user[3] or 0
            sub_rank = user[4] or 0
            limit_month = user[7] if user[7] is not None else (5 if sub == 0 else (30 if sub_rank == 1 else 9999))
            user_lang = user[9] if user and len(user) > 9 and user[9] else 'ru'
            lang_code = None if user_lang == 'other' else user_lang
            if sub == 0:
                max_links = 5
            elif sub_rank == 1:
                max_links = 10
            elif sub_rank == 2:
                max_links = 10
            else:
                max_links = 5
            links = re.findall(r'https?://[^\s]+', message.text or "")
            # Логируем факт получения ссылки
            self.log_test_event("LINKS_RECEIVED", user_id, links=links, count=len(links), text=message.text)
            if len(links) > max_links:
                await message.reply(f'Слишком много ссылок! Максимум {max_links} ссылок за раз.', reply_markup=self.get_main_keyboard())
                return
            progress_msg = await message.reply('Обрабатываю ссылки, это может занять несколько минут...')
            total_duration = 0
            all_texts = []
            for i, link in enumerate(links):
                link_start = datetime.datetime.now()
                self.log_test_event("LINK_PROCESSING_START", user_id, link=link, index=i+1)
                try:
                    await progress_msg.edit_text(f'Обрабатываю ссылку {i+1}/{len(links)}...')
                    file_path, _ = self.file_handler.download_from_url(link)
                    if not file_path:
                        await progress_msg.edit_text(f'Не удалось обработать ссылку {i+1}: возможно, видео защищено или недоступно для скачивания.')
                        self.log_test_event("LINK_PROCESSING_ERROR", user_id, link=link, index=i+1, error="file not downloaded", processing_time=(datetime.datetime.now()-link_start).total_seconds(), success=False)
                        all_texts.append(f'[Ссылка {i+1}] Не удалось обработать: возможно, видео защищено или недоступно для скачивания.\n')
                        continue
                    if file_path:
                        duration = self.transcriber.get_duration(file_path)
                        total_duration += duration
                        if sub == 0 and total_duration > 7200:  # 2 часа
                            await progress_msg.edit_text('Превышен лимит времени для бесплатного тарифа!')
                            self.log_test_event("LINK_LIMIT_EXCEEDED", user_id, link=link, index=i+1, total_duration=total_duration)
                            return
                        elif sub_rank == 1 and total_duration > 14400:  # 4 часа
                            await progress_msg.edit_text('Превышен лимит времени для базового тарифа!')
                            self.log_test_event("LINK_LIMIT_EXCEEDED", user_id, link=link, index=i+1, total_duration=total_duration)
                            return
                        async def progress_callback(percent):
                            try:
                                await progress_msg.edit_text(f'Обрабатываю ссылку {i+1}/{len(links)}... {percent}%')
                            except Exception:
                                pass
                        options = Config.WHISPER_OPTIONS.copy()
                        if lang_code:
                            options['language'] = lang_code
                        text = await self.transcriber.transcribe_long_file_with_progress(file_path, options, progress_callback)
                        all_texts.append(f'[Ссылка {i+1}]\n{text}\n')
                        os.remove(file_path)
                        link_end = datetime.datetime.now()
                        self.log_test_event("LINK_PROCESSED", user_id, link=link, index=i+1, duration=duration, processing_time=(link_end-link_start).total_seconds(), success=True)
                except Exception as e:
                    all_texts.append(f'[Ссылка {i+1}] Ошибка обработки: {str(e)}\n')
                    link_end = datetime.datetime.now()
                    self.log_test_event("LINK_PROCESSING_ERROR", user_id, link=link, index=i+1, error=str(e), processing_time=(link_end-link_start).total_seconds(), success=False)
            # Логируем итоговую статистику по всем ссылкам
            self.log_test_event("LINKS_PROCESSING_SUMMARY", user_id, count=len(links), total_duration=total_duration, all_success=all(t['event_type']=="LINK_PROCESSED" for t in self.test_logs if t.get('user_id')==user_id and t.get('event_type') in ["LINK_PROCESSED","LINK_PROCESSING_ERROR"]))
            if all_texts:
                combined_text = '\n'.join(all_texts)
                info_text = ""
                if sub == 0:
                    info_text = f"У вас осталось бесплатных транскрибаций: {limit_month}\nРекомендуем приобрести подписку!\n"
                elif sub_rank == 1:
                    try:
                        sub_time = user[5] if user and user[5] else None
                        if sub_time:
                            days_left = (datetime.datetime.fromisoformat(sub_time) - datetime.datetime.now()).days
                        else:
                            days_left = '-'
                    except Exception:
                        days_left = '-'
                    info_text = f"У вас осталось часов: {limit_month}\nДо конца подписки: {days_left} дней\n\n"
                elif sub_rank == 2:
                    try:
                        sub_time = user[5] if user and user[5] else None
                        if sub_time:
                            days_left = (datetime.datetime.fromisoformat(sub_time) - datetime.datetime.now()).days
                        else:
                            days_left = '-'
                    except Exception:
                        days_left = '-'
                    info_text = f"У вас осталось часов: Безлимит\nДо конца подписки: {days_left} дней\n\n"
                combined_text = info_text + combined_text
                combined_text += "\n\nСоздано нами "
                import uuid
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
                file_id = str(uuid.uuid4())
                lang_code = user[9] if user and len(user) > 9 and user[9] else 'ru'
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Добавить таймкоды", callback_data=f"add_timestamps:{file_id}:{lang_code}")]
                    ]
                )
                if not hasattr(self, 'user_files'):
                    self.user_files = {}
                last_file_path = None
                last_orig_name = None
                for i, link in enumerate(links[::-1]):
                    try:
                        file_path, orig_name = self.file_handler.download_from_url(link)
                        last_file_path = file_path
                        last_orig_name = orig_name
                        break
                    except Exception:
                        continue
                if last_file_path:
                    self.user_files[(user_id, file_id)] = (last_file_path, last_orig_name)
                await progress_msg.edit_text('Обработка завершена!')
                # --- ВОССТАНОВЛЕНИЕ: если длительность больше 2 минут, отправлять как txt файл ---
                if total_duration > 120:  # 2 минуты
                    txt_path = f"/tmp/transcript_{file_id}.txt"
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(combined_text)
                    await self.bot.send_document(message.chat.id, InputFile(txt_path), caption="Результат транскрибации длинного видео", reply_markup=markup)
                    os.remove(txt_path)
                else:
                    await safe_send_message(self.bot, message.chat.id, combined_text, reply_markup=markup)
            else:
                await progress_msg.edit_text('Не удалось обработать ссылки.', reply_markup=self.get_main_keyboard())



    async def handle_file(self, message, file_obj):
        user_id = getattr(message.from_user, 'id', None)
        username = getattr(message.from_user, 'username', None)
        user = await self.user_repo.get_user(user_id) if user_id is not None else None
        if not user:
            if user_id is not None:
                await self.user_repo.upsert_user(user_id, username or "-")
                user = await self.user_repo.get_user(user_id)
        if not user:
            await message.reply('Ошибка пользователя. Попробуйте позже.')
            return
            
        # Логируем начало обработки файла
        start_time = datetime.datetime.now()
        self.log_test_event("FILE_PROCESSING_START", user_id, 
                           username=username, 
                           file_name=getattr(file_obj, 'file_name', 'unknown'),
                           file_size=getattr(file_obj, 'file_size', 0),
                           mime_type=getattr(file_obj, 'mime_type', 'unknown'),
                           start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'))
        
        sub = user[3] or 0
        sub_rank = user[4] or 0
        limit_month = user[7] if user[7] is not None else (5 if sub == 0 else (30 if sub_rank == 1 else 9999))
        lang_code = user[9] or 'ru'
        # --- определяем лимит размера файла по тарифу ---
        tariff_id = user[10] if len(user) > 10 and user[10] else None
        if sub == 0:
            file_limit_mb = Config.FREE_FILE_LIMIT_MB
        else:
            tariff = await self.user_repo.get_tariff(tariff_id) if tariff_id else None
            if tariff and len(tariff) > 10 and tariff[10] is not None:
                file_limit_mb = tariff[10]
            else:
                if sub_rank == 1:
                    file_limit_mb = 350
                elif sub_rank == 2:
                    file_limit_mb = 2048
                else:
                    file_limit_mb = Config.FREE_FILE_LIMIT_MB
        # --- конец определения лимита ---
        if sub == 0:
            max_files = 5
            max_hours = 2
        elif sub_rank == 1:
            max_files = limit_month
            max_hours = 4
        elif sub_rank == 2:
            max_files = limit_month
            max_hours = 9999
        else:
            max_files = limit_month
            max_hours = 2
        file_size_mb = file_obj.file_size / (1024 * 1024)
        print(f"[DEBUG] user_id={user_id}, тариф={sub_rank}, file_size={getattr(file_obj, 'file_size', None)}, file_size_mb={file_size_mb}, file_limit_mb={file_limit_mb}, file_name={getattr(file_obj, 'file_name', None)}, mime_type={getattr(file_obj, 'mime_type', None)}")
        if file_size_mb > file_limit_mb:
            print(f"[DEBUG] ЛИМИТ ПРЕВЫШЕН: file_size_mb={file_size_mb}, file_limit_mb={file_limit_mb}")
            await message.reply(f'Файл слишком большой! Максимальный размер — {file_limit_mb} МБ.', reply_markup=self.get_main_keyboard())
            return
        file_ext = file_obj.file_name.split('.')[-1].lower() if hasattr(file_obj, 'file_name') else 'mp4'
        if file_ext not in Config.SUPPORTED_AUDIO + Config.SUPPORTED_VIDEO:
            await message.reply('Неподдерживаемый формат файла.', reply_markup=self.get_main_keyboard())
            return
        # Имя файла для txt/docx
        orig_name = file_obj.file_name.rsplit('.', 1)[0] if hasattr(file_obj, 'file_name') else 'transcription'
        
        # Логируем информацию о файле
        print(f'[DEBUG] file_obj: {file_obj}, type: {type(file_obj)}, size: {getattr(file_obj, "file_size", None)}, file_name: {getattr(file_obj, "file_name", None)}, mime_type: {getattr(file_obj, "mime_type", None)}')
        is_document = hasattr(message, 'document') and message.document is not None
        is_video = hasattr(message, 'video') and message.video is not None
        print(f'[DEBUG] is_document: {is_document}, is_video: {is_video}')
        # Скачиваем файл из Telegram
        file_ext = file_obj.file_name.split('.')[-1].lower() if hasattr(file_obj, 'file_name') else 'mp4'
        try:
            file_path = await self.file_handler.download(file_obj, file_ext)
        except Exception as e:
            print(f'[ERROR] Ошибка при скачивании файла: {e}')
            # Логируем ошибку скачивания
            self.log_test_event("FILE_DOWNLOAD_ERROR", user_id,
                               error=str(e),
                               file_name=getattr(file_obj, 'file_name', 'unknown'),
                               file_size=getattr(file_obj, 'file_size', 0))
            if "file is too big" in str(e) or "Bad Request" in str(e):
                await message.reply(f'Файл слишком большой для обработки! Максимальный размер — {file_limit_mb} МБ.\n\nТип файла: {"документ" if is_document else "видео" if is_video else "другое"}.\n\nЕсли ваш файл меньше лимита, но не проходит — попробуйте переслать его себе в ЛС и отправить боту ещё раз. Telegram иногда ограничивает скачивание некоторых файлов.\n\nЕсли вы отправляете видео, попробуйте отправить его как документ (через скрепку → Файл).', reply_markup=self.get_main_keyboard())
                return
            else:
                await message.reply('Ошибка при обработке файла. Попробуйте позже.\n\nЕсли файл меньше лимита, но не проходит — попробуйте переслать его себе в ЛС и отправить боту ещё раз.', reply_markup=self.get_main_keyboard())
                return
        
        duration = self.transcriber.get_duration(file_path)
        progress_msg = await message.reply('Распознаю текст, это может занять несколько минут...')
        async def progress_callback(percent):
            try:
                await progress_msg.edit_text(f'Распознаю текст... {percent}%')
            except Exception:
                pass
        options = Config.WHISPER_OPTIONS.copy()
        if lang_code:
            options['language'] = lang_code
        if duration > 300:
            # Длинный файл — транскрипция в txt с прогрессом
            text = await self.transcriber.transcribe_long_file_with_progress(file_path, options, progress_callback)
            import tempfile
            txt_path = os.path.join(tempfile.gettempdir(), f'{orig_name}_transcript.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            file_id = getattr(file_obj, 'file_id', None)
            if not file_id:
                file_id = str(uuid.uuid4())
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить таймкоды", callback_data=f"add_timestamps:{file_id}:{lang_code}")]
                ]
            )
            if not hasattr(self, 'user_files'):
                self.user_files = {}
            self.user_files[(user_id, file_id)] = (file_path, orig_name)
            await progress_msg.edit_text('Транскрипция завершена! Отправляю файл...')
            await message.reply_document(InputFile(txt_path), caption='Ваша транскрипция без таймкодов. Для таймкодов нажмите кнопку ниже.', reply_markup=markup)
            os.remove(txt_path)
            # Не удаляем file_path - он нужен для кнопки "Добавить таймкоды"
        else:
            # Короткий файл — обычный текст с кнопкой
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self.transcriber.transcribe, file_path, lang_code)
            text = str(text)
            if text.strip():
                info_text = ""
                if sub == 0:
                    info_text = f"У вас осталось бесплатных транскрибаций: {limit_month}\nРекомендуем приобрести подписку!\n"
                elif sub_rank == 1:
                    try:
                        sub_time = user[5] if user and user[5] else None
                        if sub_time:
                            days_left = (datetime.datetime.fromisoformat(sub_time) - datetime.datetime.now()).days
                        else:
                            days_left = '-'
                    except Exception:
                        days_left = '-'
                    info_text = f"У вас осталось часов: {limit_month}\nДо конца подписки: {days_left} дней\n\n"
                elif sub_rank == 2:
                    try:
                        sub_time = user[5] if user and user[5] else None
                        if sub_time:
                            days_left = (datetime.datetime.fromisoformat(sub_time) - datetime.datetime.now()).days
                        else:
                            days_left = '-'
                    except Exception:
                        days_left = '-'
                    info_text = f"У вас осталось часов: Безлимит\nДо конца подписки: {days_left} дней\n\n"
                text = info_text + text
                text += "\n\nСоздано нами 📝"
                if sub == 0:
                    await self.user_repo.decrement_transcribe_count(user_id)
                    user = await self.user_repo.get_user(user_id)
                    limit_month = user[7] if user and user[7] is not None else 0
                    if limit_month > 0:
                        text += f"\n\n⏰ У вас осталось {limit_month} бесплатных попыток в месяц"
                        text += "\n💳 Хотите больше? Приобретите подписку!"
                    else:
                        text += "\n\n⏰ Месячный лимит исчерпан"
                        text += "\n💳 Приобретите подписку для продолжения работы!"
                elif sub_rank == 1:
                    text += f"\n\n⏰ У вас осталось {limit_month} часов в месяц"
                file_id = getattr(file_obj, 'file_id', None)
                if not file_id:
                    file_id = str(uuid.uuid4())
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Добавить таймкоды", callback_data=f"add_timestamps:{file_id}:{lang_code}")]
                    ]
                )
                print(f"[DEBUG] Отправляю транскрипцию с кнопкой для user_id={user_id}, file_id={file_id}")
                await progress_msg.edit_text('Транскрипция завершена!')
                sent = await message.reply(text if text.strip() else 'Не удалось распознать текст.', reply_markup=markup)
                if not hasattr(self, 'user_files'):
                    self.user_files = {}
                self.user_files[(user_id, file_id)] = (file_path, orig_name)
                # Не удаляем file_path - он нужен для кнопки "Добавить таймкоды"
            else:
                await message.reply('Не удалось распознать текст.', reply_markup=self.get_main_keyboard())
                os.remove(file_path)  # Удаляем временный файл только при ошибке

        # Логируем завершение обработки файла
        end_time = datetime.datetime.now()
        processing_duration = (end_time - start_time).total_seconds()
        self.log_test_event("FILE_PROCESSING_END", user_id,
                           end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                           processing_duration_seconds=processing_duration,
                           duration_minutes=round(processing_duration/60, 2),
                           file_duration=duration,
                           success=True)

    async def check_ban(self, message):
        user_id = getattr(message.from_user, 'id', None)
        if user_id is not None and await self.user_repo.is_banned(user_id):
            # Получаем информацию о бане
            user = await self.user_repo.get_user(user_id)
            ban_reason = user[10] if user and user[10] else "Не указана"
            
            # Проверяем, есть ли уже апелляция
            existing_appeal = await self.user_repo.get_user_appeal(user_id)
            
            if existing_appeal and existing_appeal[6] == 'pending':
                # Апелляция уже подана и на рассмотрении
                await message.reply(
                    'Вы заблокированы до окончания срока блокировки. Обратитесь в поддержку, если это ошибка.\n\n'
                    'Ваша апелляция на рассмотрении, ждите. Это может занимать до 48 часов.',
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝 Подать апелляцию", callback_data="appeal_already_submitted")]
                    ])
                )
            else:
                # Можно подать апелляцию
                await message.reply(
                    f'Вы заблокированы до окончания срока блокировки.\nПричина: {ban_reason}\n\n'
                    'Если вы считаете, что блокировка была применена по ошибке, вы можете подать апелляцию.',
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝 Подать апелляцию", callback_data="submit_appeal")]
                    ])
                )
            return True
        return False

    def run(self):
        # Для Windows: корректная event loop policy
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        async def main():
            try:
                print("MAIN STARTED")
                await self.init()
                print("INIT COMPLETED")
                await self.dp.start_polling(self.bot)
            except Exception as e:
                log_error_with_traceback(e, "в методе main")
                print(f"Exception in main: {e}")
        try:
            asyncio.run(main())
        except Exception as e:
            log_error_with_traceback(e, "в asyncio.run")
            print(f"Exception in asyncio.run: {e}")

    async def activate_subscription(self, user_id, tariff_id):
        # Получаем тариф из базы данных
        tariff = await self.user_repo.get_tariff(tariff_id)
        if not tariff:
            return False
        months = tariff[6] if len(tariff) > 6 else 1  # months
        sub_rank = tariff[5] if len(tariff) > 5 else 1  # sub_rank
        now = datetime.datetime.now()
        until = now + datetime.timedelta(days=30*months)
        await self.user_repo.set_subscription(user_id, sub_rank, until.isoformat(), tariff_id)
        try:
            title = tariff[1] if len(tariff) > 1 else tariff_id  # title
            await self.bot.send_message(user_id, f'Ваша подписка "{title}" активирована до {until.strftime("%d.%m.%Y")}!')
        except Exception:
            pass
        return True

class CryptoBotClient:
    """Клиент для работы с CryptoBot API"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://pay.crypt.bot/api"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def create_invoice(self, amount, currency="USDT", description="", paid_btn_name="", paid_btn_url="", payload=""):
        """Создает инвойс для оплаты"""
        if not self.api_key:
            raise ValueError("API ключ не установлен")
        
        url = f"{self.base_url}/createInvoice"
        headers = {
            "Crypto-Pay-API-Token": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "amount": str(amount),
            "asset": currency,
            "description": description,
            "paid_btn_name": paid_btn_name,
            "paid_btn_url": paid_btn_url,
            "payload": payload
        }
        
        async with self.session.post(url, headers=headers, json=data) as response:
            result = await response.json()
            if response.status == 200 and result.get("ok"):
                return result["result"]
            else:
                error_msg = result.get("error", {}).get("message", "Unknown error")
                raise Exception(f"CryptoBot API error: {error_msg}\nCryptoBot API response: {result}")
    
    async def get_invoice(self, invoice_id):
        """Получает информацию об инвойсе"""
        if not self.api_key:
            raise ValueError("API ключ не установлен")
        
        url = f"{self.base_url}/getInvoice"
        headers = {
            "Crypto-Pay-API-Token": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {"invoice_id": invoice_id}
        
        async with self.session.post(url, headers=headers, json=data) as response:
            result = await response.json()
            if response.status == 200 and result.get("ok"):
                return result["result"]
            else:
                error_msg = result.get("error", {}).get("message", "Unknown error")
                raise Exception(f"CryptoBot API error: {error_msg}")
    
    async def get_exchange_rates(self):
        """Получает курсы валют"""
        if not self.api_key:
            raise ValueError("API ключ не установлен")
        
        url = f"{self.base_url}/getExchangeRates"
        headers = {
            "Crypto-Pay-API-Token": self.api_key,
            "Content-Type": "application/json"
        }
        
        async with self.session.post(url, headers=headers) as response:
            result = await response.json()
            if response.status == 200 and result.get("ok"):
                return result["result"]
            else:
                error_msg = result.get("error", {}).get("message", "Unknown error")
                raise Exception(f"CryptoBot API error: {error_msg}")

class LemonSqueezyClient:
    """Клиент для работы с Lemon Squeezy API"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://api.lemonsqueezy.com/v1"
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def create_checkout(self, product_id, user_id, tariff_id, amount_usd, description=""):
        """Создает checkout ссылку для оплаты"""
        import aiohttp
        
        print(f"[LemonSqueezy] Создание checkout:")
        print(f"  - product_id: {product_id}")
        print(f"  - user_id: {user_id}")
        print(f"  - tariff_id: {tariff_id}")
        print(f"  - amount_usd: {amount_usd}")
        print(f"  - description: {description}")
        print(f"  - API key: {'Установлен' if self.api_key else 'НЕ УСТАНОВЛЕН'}")
        
        if not self.api_key:
            raise ValueError("API ключ Lemon Squeezy не установлен")
        
        if not product_id:
            raise ValueError("Product ID не указан")
        
        if amount_usd <= 0:
            raise ValueError(f"Некорректная сумма: {amount_usd}")
        
        url = f"{self.base_url}/checkouts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        data = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "custom_price": int(amount_usd * 100),  # В центах
                    "product_options": {
                        "name": description,
                        "description": f"Подписка для пользователя {user_id}"
                    },
                    "checkout_options": {
                        "embed": True,
                        "media": False,
                        "logo": False
                    },
                    "checkout_data": {
                        "custom": {
                            "user_id": str(user_id),
                            "tariff_id": str(tariff_id),
                            "amount_rub": str(int(amount_usd * 100))  # Сохраняем оригинальную цену в рублях
                        }
                    }
                },
                "relationships": {
                    "store": {
                        "data": {
                            "type": "stores",
                            "id": "198522"  # Store ID из вашего аккаунта
                        }
                    },
                    "variant": {
                        "data": {
                            "type": "variants",
                            "id": str(product_id)
                        }
                    }
                }
            }
        }
        
        print(f"[LemonSqueezy] Отправка запроса:")
        print(f"  - URL: {url}")
        print(f"  - Headers: {headers}")
        print(f"  - Data: {data}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                
                print(f"[LemonSqueezy] Ответ от API:")
                print(f"  - Status: {response.status}")
                print(f"  - Response: {result}")
                
                if response.status != 201:
                    # Улучшенная обработка ошибок
                    error_detail = "Unknown error"
                    
                    if 'errors' in result and result['errors']:
                        error_obj = result['errors'][0]
                        if 'detail' in error_obj:
                            error_detail = error_obj['detail']
                        elif 'title' in error_obj:
                            error_detail = error_obj['title']
                        elif 'message' in error_obj:
                            error_detail = error_obj['message']
                    elif 'error' in result:
                        error_detail = result['error']
                    elif 'message' in result:
                        error_detail = result['message']
                    
                    # Если ошибка содержит шаблон {0}, заменяем на более понятное сообщение
                    if "{0}" in error_detail:
                        error_detail = error_detail.replace("{0}", "обязательное поле")
                    
                    print(f"[LemonSqueezy] Ошибка API: {error_detail}")
                    raise Exception(f"Lemon Squeezy API error: {error_detail}")
                
                print(f"[LemonSqueezy] Checkout создан успешно: {result['data']['id']}")
                return result['data']
    
    async def get_order(self, order_id):
        """Получает информацию о заказе"""
        import aiohttp
        
        print(f"[LemonSqueezy] Получение заказа: {order_id}")
        
        if not self.api_key:
            raise ValueError("API ключ Lemon Squeezy не установлен")
        
        url = f"{self.base_url}/orders/{order_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        
        print(f"[LemonSqueezy] Отправка запроса:")
        print(f"  - URL: {url}")
        print(f"  - Headers: {headers}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                
                print(f"[LemonSqueezy] Ответ от API:")
                print(f"  - Status: {response.status}")
                print(f"  - Response: {result}")
                
                if response.status != 200:
                    # Улучшенная обработка ошибок
                    error_detail = "Unknown error"
                    
                    if 'errors' in result and result['errors']:
                        error_obj = result['errors'][0]
                        if 'detail' in error_obj:
                            error_detail = error_obj['detail']
                        elif 'title' in error_obj:
                            error_detail = error_obj['title']
                        elif 'message' in error_obj:
                            error_detail = error_obj['message']
                    elif 'error' in result:
                        error_detail = result['error']
                    elif 'message' in result:
                        error_detail = result['message']
                    
                    # Если ошибка содержит шаблон {0}, заменяем на более понятное сообщение
                    if "{0}" in error_detail:
                        error_detail = error_detail.replace("{0}", "обязательное поле")
                    
                    print(f"[LemonSqueezy] Ошибка API: {error_detail}")
                    raise Exception(f"Lemon Squeezy API error: {error_detail}")
                
                print(f"[LemonSqueezy] Заказ получен успешно")
                return result['data']
    
    async def get_stores(self):
        """Получает список stores"""
        import aiohttp
        
        print(f"[LemonSqueezy] Получение списка stores...")
        
        if not self.api_key:
            raise ValueError("API ключ Lemon Squeezy не установлен")
        
        url = f"{self.base_url}/stores"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        
        print(f"[LemonSqueezy] Отправка запроса:")
        print(f"  - URL: {url}")
        print(f"  - Headers: {headers}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                
                print(f"[LemonSqueezy] Ответ от API:")
                print(f"  - Status: {response.status}")
                print(f"  - Response: {result}")
                
                if response.status != 200:
                    error_detail = "Unknown error"
                    
                    if 'errors' in result and result['errors']:
                        error_obj = result['errors'][0]
                        if 'detail' in error_obj:
                            error_detail = error_obj['detail']
                        elif 'title' in error_obj:
                            error_detail = error_obj['title']
                        elif 'message' in error_obj:
                            error_detail = error_obj['message']
                    elif 'error' in result:
                        error_detail = result['error']
                    elif 'message' in result:
                        error_detail = result['message']
                    
                    print(f"[LemonSqueezy] Ошибка API: {error_detail}")
                    raise Exception(f"Lemon Squeezy API error: {error_detail}")
                
                print(f"[LemonSqueezy] Stores получены успешно")
                return result['data']
    
    async def get_variants(self):
        """Получает список variants"""
        import aiohttp
        
        print(f"[LemonSqueezy] Получение списка variants...")
        
        if not self.api_key:
            raise ValueError("API ключ Lemon Squeezy не установлен")
        
        url = f"{self.base_url}/variants"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        
        print(f"[LemonSqueezy] Отправка запроса:")
        print(f"  - URL: {url}")
        print(f"  - Headers: {headers}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                
                print(f"[LemonSqueezy] Ответ от API:")
                print(f"  - Status: {response.status}")
                print(f"  - Response: {result}")
                
                if response.status != 200:
                    error_detail = "Unknown error"
                    
                    if 'errors' in result and result['errors']:
                        error_obj = result['errors'][0]
                        if 'detail' in error_obj:
                            error_detail = error_obj['detail']
                        elif 'title' in error_obj:
                            error_detail = error_obj['title']
                        elif 'message' in error_obj:
                            error_detail = error_obj['message']
                    elif 'error' in result:
                        error_detail = result['error']
                    elif 'message' in result:
                        error_detail = result['message']
                    
                    print(f"[LemonSqueezy] Ошибка API: {error_detail}")
                    raise Exception(f"Lemon Squeezy API error: {error_detail}")
                
                print(f"[LemonSqueezy] Variants получены успешно")
                return result['data']




