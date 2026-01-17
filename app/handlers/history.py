import logging
from aiogram import Router, F
from aiogram.types import Message
import app.utils.funcs as fs
import asyncio



history_router = Router(name=__name__)
logger = logging.getLogger(__name__)


@history_router.message(F.text == '📜 История за сутки')
async def historys(message: Message):
    data = fs.load_access_data()
    user_id = message.from_user.id  # Получаем ID пользователя
    role = fs.get_user_role(user_id, data)
    if role in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
        temp_message = await message.answer("⏳ Получаю историю за сутки...")
        try:
            await asyncio.sleep(1)
            today_history = await fs.get_today_history()
            await temp_message.edit_text(today_history, parse_mode="HTML")
            logger.info(
                f"Пользователь {message.from_user.id} ({message.from_user.full_name}) запросил историю за сутки.")
        except Exception as e:
            logger.error(
                f"Ошибка при получении истории для пользователя {message.from_user.id}: {e}")
            await message.answer("❌ Произошла ошибка при получении истории. Попробуйте позже или обратитесь к администратору.")
    else:
        await message.answer('⛔ У вас нет доступа')
