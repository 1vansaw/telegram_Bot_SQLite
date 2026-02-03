import asyncio
from aiogram import Bot, Dispatcher
from app.handlers import router
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
import logging
from logging.handlers import RotatingFileHandler
from app.config import settings
import app.utils.funcs as fs


logging.basicConfig(
    level=logging.INFO,  # Уровень: DEBUG для подробностей, INFO для основного, ERROR для ошибок
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[RotatingFileHandler('logs/bot.log', encoding='utf-8', maxBytes=5 * 1024*1024, backupCount=3), logging.StreamHandler()])

logger = logging.getLogger(__name__)

async def set_main_menu(bot: Bot):
    # Создаем список с командами и их описанием для кнопки menu
    main_menu_commands = [
        BotCommand(command='/start',
                   description='🏡 Главное меню'),
        BotCommand(command='/upload_excel',
               description='📊 Экспорт базы в Excel'),
        BotCommand(command='/check_access',
                   description='🔒 Ваши данные')]

    await bot.set_my_commands(main_menu_commands)

storage = MemoryStorage()
session = AiohttpSession(session=settings.DOWNLOAD_TIMEOUT)  # proxy="http://proxy.server:3128"
bot = Bot(token=settings.BOT_TOKEN, session=session)
dp = Dispatcher(storage=storage)
dp.include_router(router)



# функция удаления файлов истории
async def periodic_cleanup():
    while True:
        logging.info("Запуск периодической очистки...")
        fs.cleanup_old_files()
        await asyncio.sleep(settings.CLEANUP_INTERVAL)


async def main():
    await fs.init_db()  # Инициализация базы данных SQLite
    dp.startup.register(set_main_menu)
    asyncio.create_task(periodic_cleanup())
    asyncio.create_task(fs.auto_backup_loop(bot))
    await dp.start_polling(bot)
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
