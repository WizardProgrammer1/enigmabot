import aiosqlite
import datetime
from src.config import Config

class UserRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DATABASE_PATH

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    user_name TEXT,
                    a_rank INTEGER,
                    sub INTEGER,
                    sub_rank INTEGER,
                    sub_time TEXT,
                    max_hours INTEGER,
                    limit_month INTEGER,
                    limit_links INTEGER,
                    banned_until TEXT DEFAULT NULL,
                    ban_reason TEXT DEFAULT NULL,
                    language TEXT DEFAULT 'ru'
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS support_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    text TEXT,
                    created_at TEXT,
                    status TEXT,
                    answer TEXT,
                    answered_by INTEGER
                )
            ''')
            
            # Миграция: добавляем столбец topic если его нет
            try:
                await db.execute('ALTER TABLE support_questions ADD COLUMN topic TEXT DEFAULT NULL')
            except Exception:
                # Столбец уже существует, игнорируем ошибку
                pass
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS support_notify_off (
                    user_id INTEGER PRIMARY KEY
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    tariff_id TEXT,
                    amount INTEGER,
                    currency TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    paid_at TEXT,
                    invoice_payload TEXT,
                    telegram_payment_charge_id TEXT,
                    telegram_payment_provider_charge_id TEXT,
                    payment_method TEXT DEFAULT 'yookassa',
                    external_id TEXT
                )
            ''')
            
            # Миграция: добавляем новые столбцы если их нет
            try:
                await db.execute('ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT "yookassa"')
            except Exception:
                # Столбец уже существует, игнорируем ошибку
                pass
            
            try:
                await db.execute('ALTER TABLE orders ADD COLUMN external_id TEXT')
            except Exception:
                # Столбец уже существует, игнорируем ошибку
                pass
            await db.execute('''
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    admin_username TEXT,
                    action TEXT,
                    action_time TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS appeals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    ban_reason TEXT,
                    appeal_text TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'pending',
                    admin_response TEXT DEFAULT NULL,
                    reviewed_by INTEGER DEFAULT NULL,
                    reviewed_at TEXT DEFAULT NULL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    user_name TEXT,
                    a_rank INTEGER,
                    sub INTEGER,
                    sub_rank INTEGER,
                    sub_time TEXT,
                    max_hours INTEGER,
                    limit_month INTEGER,
                    limit_links INTEGER,
                    banned_until TEXT DEFAULT NULL,
                    ban_reason TEXT DEFAULT NULL,
                    language TEXT DEFAULT 'ru'
                )
            ''')
            # Миграция: добавляем столбец language если его нет
            try:
                await db.execute('ALTER TABLE users ADD COLUMN language TEXT DEFAULT "ru"')
            except Exception:
                pass
            
            # --- Тарифы и скидки ---
            await db.execute('''
                CREATE TABLE IF NOT EXISTS tariffs (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    amount INTEGER,
                    currency TEXT,
                    sub_rank INTEGER,
                    months INTEGER,
                    max_hours INTEGER,
                    limit_month INTEGER,
                    limit_links INTEGER,
                    file_limit_mb INTEGER
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS discounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id TEXT,
                    percent INTEGER,
                    start_time TEXT,
                    end_time TEXT
                )
            ''')
            
            await db.commit()
            await self.add_test_admins()

    async def add_test_admins(self):
        # Добавляем админа из конфигурации
        admin_id = Config.ADMIN_USER_ID
        if admin_id:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR IGNORE INTO users (id, user_name, a_rank, sub, sub_rank, sub_time, max_hours, limit_month, limit_links, banned_until)
                    VALUES (?, ?, 3, 1, 2, '2030-12-31', 9999, 9999, 50, NULL)
                ''', (admin_id, 'Admin'))
                await db.commit()

    async def get_user(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM users WHERE id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row

    async def get_user_by_username(self, username):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM users WHERE user_name = ?', (username,)) as cursor:
                row = await cursor.fetchone()
                return row

    async def upsert_user(self, user_id, user_name, language=None):
        async with aiosqlite.connect(self.db_path) as db:
            if user_id == Config.ADMIN_USER_ID:
                await db.execute('''
                    INSERT INTO users (id, user_name, a_rank, sub, sub_rank, sub_time, max_hours, limit_month, limit_links, banned_until, language)
                    VALUES (?, ?, 3, 1, 2, '2030-12-31', 9999, 9999, 50, NULL, COALESCE(?, 'ru'))
                    ON CONFLICT(id) DO UPDATE SET user_name=excluded.user_name, a_rank=3, sub=1, sub_rank=2, sub_time='2030-12-31', max_hours=9999, limit_month=9999, limit_links=50, language=COALESCE(excluded.language, users.language)
                ''', (user_id, user_name, language))
            else:
                await db.execute('''
                    INSERT INTO users (id, user_name, a_rank, sub, sub_rank, sub_time, max_hours, limit_month, limit_links, banned_until, language)
                    VALUES (?, ?, 0, 0, 0, '', 2, 5, 5, NULL, COALESCE(?, 'ru'))
                    ON CONFLICT(id) DO UPDATE SET user_name=excluded.user_name, language=COALESCE(excluded.language, users.language)
                ''', (user_id, user_name, language))
            await db.commit()

    async def update_subscription(self, user_id, sub, sub_rank, sub_time, max_hours, limit_month, limit_links):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users SET sub=?, sub_rank=?, sub_time=?, max_hours=?, limit_month=?, limit_links=? WHERE id=?
            ''', (sub, sub_rank, sub_time, max_hours, limit_month, limit_links, user_id))
            await db.commit()

    async def update_admin(self, user_id, a_rank):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET a_rank=? WHERE id=?', (a_rank, user_id))
            await db.commit()

    async def update_limits(self, user_id, max_hours, limit_month, limit_links):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET max_hours=?, limit_month=?, limit_links=? WHERE id=?', (max_hours, limit_month, limit_links, user_id))
            await db.commit()

    async def decrement_month_limit(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET limit_month = limit_month - 1 WHERE id=?', (user_id,))
            await db.commit()

    async def decrement_month_limit_by(self, user_id, hours):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET limit_month = limit_month - ? WHERE id=?', (hours, user_id))
            await db.commit()

    async def ban_user(self, user_id, until, reason):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET banned_until=?, ban_reason=? WHERE id=?', (until, reason, user_id))
            await db.commit()

    async def unban_user(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET banned_until=NULL, ban_reason=NULL WHERE id=?', (user_id,))
            await db.commit()

    async def is_banned(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT banned_until FROM users WHERE id=?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    try:
                        banned_until = datetime.datetime.fromisoformat(row[0])
                        return banned_until > datetime.datetime.now()
                    except Exception:
                        return False
                return False

    async def count_subs(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT COUNT(*) FROM users WHERE sub > 0') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def count_users(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT COUNT(*) FROM users') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_admins(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT id, user_name, a_rank FROM users WHERE a_rank > 0') as cursor:
                return await cursor.fetchall()

    async def get_all_subs(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT id, user_name, sub_rank, sub_time FROM users WHERE sub > 0') as cursor:
                return await cursor.fetchall()

    async def remove_sub(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET sub=0, sub_rank=0, sub_time="" WHERE id=?', (user_id,))
            await db.commit()

    async def set_sub(self, user_id, sub_rank, sub_time):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET sub=1, sub_rank=?, sub_time=? WHERE id=?', (sub_rank, sub_time, user_id))
            await db.commit()

    async def add_support_question(self, user_id, username, text, topic=None):
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, есть ли столбец topic в таблице
            try:
                await db.execute('''
                    INSERT INTO support_questions (user_id, username, text, topic, created_at, status)
                    VALUES (?, ?, ?, ?, ?, 'open')
                ''', (user_id, username, text, topic, datetime.datetime.now().isoformat()))
            except Exception:
                # Если столбца topic нет, вставляем без него
                await db.execute('''
                    INSERT INTO support_questions (user_id, username, text, created_at, status)
                    VALUES (?, ?, ?, ?, 'open')
                ''', (user_id, username, text, datetime.datetime.now().isoformat()))
            
            await db.commit()
            async with db.execute('SELECT last_insert_rowid()') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def get_support_question(self, qid):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM support_questions WHERE id=?', (qid,)) as cursor:
                return await cursor.fetchone()

    async def answer_support_question(self, qid, answer, admin_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE support_questions SET answer=?, answered_by=?, status='closed' WHERE id=?
            ''', (answer, admin_id, qid))
            await db.commit()

    async def set_support_notify(self, user_id, off=True):
        async with aiosqlite.connect(self.db_path) as db:
            if off:
                await db.execute('INSERT OR IGNORE INTO support_notify_off (user_id) VALUES (?)', (user_id,))
            else:
                await db.execute('DELETE FROM support_notify_off WHERE user_id=?', (user_id,))
            await db.commit()

    async def get_admins_with_notify(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT id FROM users WHERE a_rank > 0 AND id NOT IN (SELECT user_id FROM support_notify_off)
            ''') as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def get_support_questions(self, offset=0, limit=10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM support_questions ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset)) as cursor:
                return await cursor.fetchall()

    async def count_support_questions(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT COUNT(*) FROM support_questions') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    # Методы для работы с заказами
    async def create_order(self, user_id, tariff_id, amount, currency, invoice_payload):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO orders (user_id, tariff_id, amount, currency, created_at, invoice_payload)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, tariff_id, amount, currency, datetime.datetime.now().isoformat(), invoice_payload))
            await db.commit()
            async with db.execute('SELECT last_insert_rowid()') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def get_order(self, order_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM orders WHERE id=?', (order_id,)) as cursor:
                return await cursor.fetchone()

    async def update_order_payment(self, order_id, telegram_payment_charge_id, telegram_payment_provider_charge_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE orders SET 
                    status='paid', 
                    paid_at=?, 
                    telegram_payment_charge_id=?, 
                    telegram_payment_provider_charge_id=?
                WHERE id=?
            ''', (datetime.datetime.now().isoformat(), telegram_payment_charge_id, telegram_payment_provider_charge_id, order_id))
            await db.commit()

    async def get_user_orders(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC', (user_id,)) as cursor:
                return await cursor.fetchall()

    async def get_pending_orders(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM orders WHERE status="pending"') as cursor:
                return await cursor.fetchall()

    async def get_all_orders(self, limit=10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT ?', (limit,)) as cursor:
                return await cursor.fetchall()

    async def get_paid_orders(self, limit=10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM orders WHERE status="paid" ORDER BY paid_at DESC LIMIT ?', (limit,)) as cursor:
                return await cursor.fetchall()

    async def decrement_transcribe_count(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET limit_month = limit_month - 1 WHERE id=?', (user_id,))
            await db.commit()

    async def log_admin_action(self, admin_id, admin_username, action):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO admin_logs (admin_id, admin_username, action, action_time)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, admin_username, action, datetime.datetime.now().isoformat()))
            await db.commit()

    async def get_admin_logs(self, offset=0, limit=10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT admin_id, admin_username, action, action_time FROM admin_logs ORDER BY action_time DESC LIMIT ? OFFSET ?
            ''', (limit, offset)) as cursor:
                return await cursor.fetchall()

    async def get_users_page(self, page=1, page_size=10):
        offset = (page - 1) * page_size
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT id, user_name, sub, sub_rank FROM users ORDER BY id LIMIT ? OFFSET ?', (page_size, offset)) as cursor:
                return await cursor.fetchall()

    async def get_banned_users(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем всех забаненных пользователей
            async with db.execute('SELECT id, user_name, banned_until, ban_reason FROM users WHERE banned_until IS NOT NULL') as cursor:
                users = await cursor.fetchall()
            # Для каждого ищем кто забанил (последний лог ban)
            result = []
            for u in users:
                uid, uname, banned_until, reason = u
                async with db.execute("""
                    SELECT admin_id, admin_username, action_time FROM admin_logs
                    WHERE action LIKE ? AND action LIKE ?
                    ORDER BY action_time DESC LIMIT 1
                """, (f'%ban {uid}%', '%причина:%')) as c2:
                    log = await c2.fetchone()
                    if log:
                        admin_id, admin_username, action_time = log
                    else:
                        admin_id, admin_username, action_time = None, None, None
                result.append((uid, uname, banned_until, reason, admin_id, admin_username, action_time))
            return result

    # Методы для работы с апелляциями
    async def create_appeal(self, user_id, username, ban_reason, appeal_text):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO appeals (user_id, username, ban_reason, appeal_text, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, ban_reason, appeal_text, datetime.datetime.now().isoformat()))
            await db.commit()
            async with db.execute('SELECT last_insert_rowid()') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def get_user_appeal(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM appeals WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (user_id,)) as cursor:
                return await cursor.fetchone()

    async def get_all_appeals(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM appeals ORDER BY created_at DESC') as cursor:
                return await cursor.fetchall()

    async def get_pending_appeals(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM appeals WHERE status = "pending" ORDER BY created_at DESC') as cursor:
                return await cursor.fetchall()

    async def respond_to_appeal(self, appeal_id, admin_id, admin_username, response):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE appeals SET 
                    status = 'reviewed',
                    admin_response = ?,
                    reviewed_by = ?,
                    reviewed_at = ?
                WHERE id = ?
            ''', (response, admin_id, datetime.datetime.now().isoformat(), appeal_id))
            await db.commit()

    async def get_appeal(self, appeal_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM appeals WHERE id = ?', (appeal_id,)) as cursor:
                return await cursor.fetchone()

    async def save_payment(self, user_id, payment_id, tariff_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO orders (user_id, tariff_id, amount, currency, status, created_at, invoice_payload)
                VALUES (?, ?, 0, 'RUB', 'pending', ?, ?)
            ''', (user_id, tariff_id, datetime.datetime.now().isoformat(), payment_id))
            await db.commit()

    async def get_user_by_payment_id(self, payment_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT user_id, tariff_id FROM orders WHERE invoice_payload = ?', (payment_id,)) as cursor:
                return await cursor.fetchone()

    async def set_subscription(self, user_id, sub_rank, until, tariff_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users SET sub=1, sub_rank=?, sub_time=?, tariff_id=? WHERE id=?
            ''', (sub_rank, until, tariff_id, user_id))
            await db.commit()

    async def update_language(self, user_id, language):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET language=? WHERE id=?', (language, user_id))
            await db.commit() 

    # --- Функции для тарифов и скидок ---
    async def upsert_tariff(self, tariff):
        async with aiosqlite.connect(self.db_path) as db:
            # Универсальная обработка: поддержка dict и tuple
            if isinstance(tariff, dict):
                values = (
                    tariff['id'], tariff['title'], tariff['description'], tariff['amount'], tariff['currency'],
                    tariff['sub_rank'], tariff['months'], tariff['max_hours'], tariff['limit_month'],
                    tariff['limit_links'], tariff.get('file_limit_mb')
                )
            else:
                # tuple: (id, title, description, amount, currency, sub_rank, months, max_hours, limit_month, limit_links, file_limit_mb)
                values = tuple(tariff)
            await db.execute('''
                INSERT INTO tariffs (id, title, description, amount, currency, sub_rank, months, max_hours, limit_month, limit_links, file_limit_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    amount=excluded.amount,
                    currency=excluded.currency,
                    sub_rank=excluded.sub_rank,
                    months=excluded.months,
                    max_hours=excluded.max_hours,
                    limit_month=excluded.limit_month,
                    limit_links=excluded.limit_links,
                    file_limit_mb=excluded.file_limit_mb
            ''', values)
            await db.commit()

    async def get_tariff(self, plan_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM tariffs WHERE id=?', (plan_id,)) as cursor:
                row = await cursor.fetchone()
                return row

    async def get_all_tariffs(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM tariffs') as cursor:
                rows = list(await cursor.fetchall())
                return rows

    async def set_discount(self, plan_id, percent, start_time, end_time):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO discounts (plan_id, percent, start_time, end_time)
                VALUES (?, ?, ?, ?)
            ''', (plan_id, percent, start_time, end_time))
            await db.commit()

    async def get_active_discount(self, plan_id, now=None):
        import datetime
        now = now or datetime.datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT percent FROM discounts WHERE plan_id=? AND start_time<=? AND end_time>=? ORDER BY end_time DESC LIMIT 1
            ''', (plan_id, now, now)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_all_discounts(self):
        """Получает все скидки из базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT id, plan_id, percent, start_time, end_time FROM discounts ORDER BY id DESC') as cursor:
                return await cursor.fetchall()

    async def delete_discount(self, discount_id):
        """Удаляет скидку по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM discounts WHERE id = ?', (discount_id,))
            await db.commit()

    # --- Методы для работы с платежами ---
    async def create_payment(self, user_id, tariff_id, amount, currency, payment_method, external_id=None):
        """Создает новый платеж в базе данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO orders (user_id, tariff_id, amount, currency, status, created_at, invoice_payload, payment_method, external_id)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            ''', (user_id, tariff_id, amount, currency, datetime.datetime.now().isoformat(), f"payment_{user_id}_{tariff_id}", payment_method, external_id))
            await db.commit()
            async with db.execute('SELECT last_insert_rowid()') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def get_payment(self, payment_id):
        """Получает информацию о платеже по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM orders WHERE id = ?', (payment_id,)) as cursor:
                return await cursor.fetchone()

    async def update_payment_status(self, payment_id, status):
        """Обновляет статус платежа"""
        async with aiosqlite.connect(self.db_path) as db:
            paid_at = datetime.datetime.now().isoformat() if status == "paid" else None
            await db.execute('''
                UPDATE orders SET status = ?, paid_at = ? WHERE id = ?
            ''', (status, paid_at, payment_id))
            await db.commit() 

    async def get_appeals_for_current_ban(self, user_id, ban_start):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM appeals WHERE user_id = ? AND created_at >= ? ORDER BY created_at DESC', (user_id, ban_start)) as cursor:
                return await cursor.fetchall() 

    async def get_last_appeal_for_ban(self, user_id, ban_start):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM appeals WHERE user_id = ? AND created_at >= ? ORDER BY status = "pending" DESC, created_at DESC LIMIT 1', (user_id, ban_start)) as cursor:
                return await cursor.fetchone() 