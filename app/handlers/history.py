import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
import app.utils.funcs as fs
import asyncio



history_router = Router(name=__name__)
logger = logging.getLogger(__name__)


@history_router.message(F.text == '📜 История за сутки')
async def historys(message: Message):
    data = fs.load_access_data()
    user_id = message.from_user.id
    role = fs.get_user_role(user_id, data)

    if role not in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
        await message.answer("⛔ У вас нет доступа")
        return

    temp_message = await message.answer("⏳ Получаю историю за сутки...")
    await asyncio.sleep(1)

    history = await fs.get_today_history()

    if not history:
        await temp_message.edit_text("За последние 24 часа записей не найдено.")
        return

    # если одна заявка — просто выводим
    if len(history) == 1:
        await temp_message.edit_text(history[0], parse_mode="HTML")
        return

    page = 1
    total_pages = len(history)

    text = (
        "📜 <b>История за сутки</b>\n\n"
        f"📱 <b>Страница:</b> <code>{page}/{total_pages}</code>\n"
        f"{'•' * 30}\n\n"
        f"{history[page - 1]}"
    )

    keyboard = fs.history_keyboard(page, total_pages)

    await temp_message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@history_router.callback_query(F.data.startswith("history_page:"))
async def history_page(callback: CallbackQuery):
    try:
        page = int(callback.data.split(":")[1])
    except ValueError:
        await callback.answer()
        return

    history = await fs.get_today_history()

    if not history:
        await callback.message.edit_text("За последние 24 часа записей не найдено.")
        await callback.answer()
        return

    total_pages = len(history)
    page = max(1, min(page, total_pages))

    text = (
        "📜 <b>История за сутки</b>\n\n"
        f"📱 <b>Страница:</b> <code>{page}/{total_pages}</code>\n"
        f"{'•' * 30}\n\n"
        f"{history[page - 1]}"
    )

    keyboard = fs.history_keyboard(page, total_pages)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()
