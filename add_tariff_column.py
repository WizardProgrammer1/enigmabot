import asyncio
import aiosqlite

TARIFFS = [
    # MDL тарифы
    {
        'id': 'basic_1',
        'title': 'Базовый (1 месяц)',
        'description': '30 часов в месяц, видео до 4 часов, 10 ссылок',
        'amount': 9300,
        'currency': 'MDL',
        'sub_rank': 1,
        'months': 1,
        'max_hours': 30,
        'limit_month': 30,
        'limit_links': 10,
        'file_limit_mb': None
    },
    {
        'id': 'basic_3',
        'title': 'Базовый (3 месяца)',
        'description': '30 часов в месяц, видео до 4 часов, 10 ссылок',
        'amount': 27900,
        'currency': 'MDL',
        'sub_rank': 1,
        'months': 3,
        'max_hours': 30,
        'limit_month': 30,
        'limit_links': 10,
        'file_limit_mb': None
    },
    {
        'id': 'basic_6',
        'title': 'Базовый (6 месяцев)',
        'description': '30 часов в месяц, видео до 4 часов, 10 ссылок',
        'amount': 55900,
        'currency': 'MDL',
        'sub_rank': 1,
        'months': 6,
        'max_hours': 30,
        'limit_month': 30,
        'limit_links': 10,
        'file_limit_mb': None
    },
    {
        'id': 'basic_12',
        'title': 'Базовый (12 месяцев)',
        'description': '30 часов в месяц, видео до 4 часов, 10 ссылок',
        'amount': 111600,  # 12*9300
        'currency': 'MDL',
        'sub_rank': 1,
        'months': 12,
        'max_hours': 30,
        'limit_month': 30,
        'limit_links': 10,
        'file_limit_mb': None
    },
    {
        'id': 'pro_1',
        'title': 'Про (1 месяц)',
        'description': 'Безлимитная генерация, видео до 4 часов, 10 ссылок',
        'amount': 24500,
        'currency': 'MDL',
        'sub_rank': 2,
        'months': 1,
        'max_hours': 9999,
        'limit_month': 9999,
        'limit_links': 10,
        'file_limit_mb': None
    },
    {
        'id': 'pro_3',
        'title': 'Про (3 месяца)',
        'description': 'Безлимитная генерация, видео до 4 часов, 10 ссылок',
        'amount': 73500,
        'currency': 'MDL',
        'sub_rank': 2,
        'months': 3,
        'max_hours': 9999,
        'limit_month': 9999,
        'limit_links': 10,
        'file_limit_mb': None
    },
    {
        'id': 'pro_6',
        'title': 'Про (6 месяцев)',
        'description': 'Безлимитная генерация, видео до 4 часов, 10 ссылок',
        'amount': 147000,
        'currency': 'MDL',
        'sub_rank': 2,
        'months': 6,
        'max_hours': 9999,
        'limit_month': 9999,
        'limit_links': 10,
        'file_limit_mb': None
    },
    {
        'id': 'pro_12',
        'title': 'Про (12 месяцев)',
        'description': 'Безлимитная генерация, видео до 4 часов, 10 ссылок',
        'amount': 294000,  # 12*24500
        'currency': 'MDL',
        'sub_rank': 2,
        'months': 12,
        'max_hours': 9999,
        'limit_month': 9999,
        'limit_links': 10,
        'file_limit_mb': None
    },
    # RUB тарифы
    {
        'id': 'basic_1',
        'title': 'Базовый (1 месяц)',
        'description': '30 часов в месяц, видео до 4 часов, 10 ссылок',
        'amount': 49000,
        'currency': 'RUB',
        'sub_rank': 1,
        'months': 1,
        'max_hours': 30,
        'limit_month': 30,
        'limit_links': 10,
        'file_limit_mb': 350
    },
    {
        'id': 'basic_3',
        'title': 'Базовый (3 месяца)',
        'description': '30 часов в месяц, видео до 4 часов, 10 ссылок',
        'amount': 147000,
        'currency': 'RUB',
        'sub_rank': 1,
        'months': 3,
        'max_hours': 30,
        'limit_month': 30,
        'limit_links': 10,
        'file_limit_mb': 350
    },
    {
        'id': 'basic_6',
        'title': 'Базовый (6 месяцев)',
        'description': '30 часов в месяц, видео до 4 часов, 10 ссылок',
        'amount': 294000,
        'currency': 'RUB',
        'sub_rank': 1,
        'months': 6,
        'max_hours': 30,
        'limit_month': 30,
        'limit_links': 10,
        'file_limit_mb': 350
    },
    {
        'id': 'basic_12',
        'title': 'Базовый (12 месяцев)',
        'description': '30 часов в месяц, видео до 4 часов, 10 ссылок',
        'amount': 588000,  # 12*49000
        'currency': 'RUB',
        'sub_rank': 1,
        'months': 12,
        'max_hours': 30,
        'limit_month': 30,
        'limit_links': 10,
        'file_limit_mb': 350
    },
    {
        'id': 'pro_1',
        'title': 'Про (1 месяц)',
        'description': 'Безлимитная генерация, видео до 4 часов, 10 ссылок',
        'amount': 129000,
        'currency': 'RUB',
        'sub_rank': 2,
        'months': 1,
        'max_hours': 9999,
        'limit_month': 9999,
        'limit_links': 10,
        'file_limit_mb': 2048
    },
    {
        'id': 'pro_3',
        'title': 'Про (3 месяца)',
        'description': 'Безлимитная генерация, видео до 4 часов, 10 ссылок',
        'amount': 387000,
        'currency': 'RUB',
        'sub_rank': 2,
        'months': 3,
        'max_hours': 9999,
        'limit_month': 9999,
        'limit_links': 10,
        'file_limit_mb': 2048
    },
    {
        'id': 'pro_6',
        'title': 'Про (6 месяцев)',
        'description': 'Безлимитная генерация, видео до 4 часов, 10 ссылок',
        'amount': 774000,
        'currency': 'RUB',
        'sub_rank': 2,
        'months': 6,
        'max_hours': 9999,
        'limit_month': 9999,
        'limit_links': 10,
        'file_limit_mb': 2048
    },
    {
        'id': 'pro_12',
        'title': 'Про (12 месяцев)',
        'description': 'Безлимитная генерация, видео до 4 часов, 10 ссылок',
        'amount': 1548000,  # 12*129000
        'currency': 'RUB',
        'sub_rank': 2,
        'months': 12,
        'max_hours': 9999,
        'limit_month': 9999,
        'limit_links': 10,
        'file_limit_mb': 2048
    },
]

async def main():
    async with aiosqlite.connect('users.db') as db:
        for t in TARIFFS:
            await db.execute('''
                INSERT OR REPLACE INTO tariffs (id, title, description, amount, currency, sub_rank, months, max_hours, limit_month, limit_links, file_limit_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                t['id'], t['title'], t['description'], t['amount'], t['currency'], t['sub_rank'], t['months'], t['max_hours'], t['limit_month'], t['limit_links'], t['file_limit_mb']
            ))
        await db.commit()
    print('Тарифы успешно добавлены в базу данных.')

if __name__ == '__main__':
    asyncio.run(main()) 