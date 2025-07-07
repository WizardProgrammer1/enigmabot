import asyncio
from src.user_repository import UserRepository

async def main():
    repo = UserRepository()
    await repo.init_db()
    print('База данных инициализирована (все таблицы созданы).')

if __name__ == '__main__':
    asyncio.run(main()) 