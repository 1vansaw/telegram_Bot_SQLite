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

    logger.info(
        f"Пользователь {user_id} запросил историю за сутки | роль: {role}"
    )

    if role not in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
        logger.warning(
            f"Отказ в доступе пользователю {user_id} | роль: {role}"
        )
        await message.answer("⛔ У вас нет доступа")
        return

    temp_message = await message.answer("⏳ Получаю историю за сутки...")
    await asyncio.sleep(1)

    history = await fs.get_today_history()

    logger.info(
        f"История за сутки получена | пользователь: {user_id} | записей: {len(history) if history else 0}"
    )

    if not history:
        await callback.message.edit_text(
            "📭 <b>История пуста</b>\n\n"
            "За последние <b>24 часа</b> записей не найдено.",
            parse_mode="HTML"
        )
        return

    if len(history) == 1:
        logger.debug(
            f"Пользователю {user_id} показана единственная запись истории"
        )
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
    user_id = callback.from_user.id

    try:
        page = int(callback.data.split(":")[1])
    except ValueError:
        logger.error(
            f"Некорректные данные callback history_page | пользователь: {user_id} | данные: {callback.data}"
        )
        await callback.answer()
        return

    history = await fs.get_today_history()

    if not history:
        logger.info(
            f"История пуста при переключении страницы | пользователь: {user_id}"
        )
        await callback.message.edit_text(
            "📭 <b>История пуста</b>\n\n"
            "За последние <b>24 часа</b> записей не найдено.",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    total_pages = len(history)
    page = max(1, min(page, total_pages))

    logger.debug(
        f"Пользователь {user_id} переключил страницу истории на {page}/{total_pages}"
    )

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
