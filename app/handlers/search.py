from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from app.states import Register
from app.keyboards import inline_main_menu, main
import app.utils.funcs as fs
import asyncio
import logging
from datetime import datetime
from aiogram.types import FSInputFile


search_router = Router()  # локальный роутер
logger = logging.getLogger(__name__)



# Обработчик кнопки "🔍 Поиск записи" — запрашивает фразу и переходит в состояние
@search_router.message(F.text == '🔍 Поиск записи')
async def start_search(message: Message, state: FSMContext):
    data = fs.load_access_data()
    user_id = message.from_user.id
    role = fs.get_user_role(user_id, data)

    if role is None:
        await message.answer("⛔ **Доступ запрещён**", parse_mode="Markdown")
        return

    logger.info(f"Пользователь {user_id} ({role}) начал поиск записи.")

    await message.answer(
        "🔍 **Поиск записи**\n\n"
        "🔍 Введите слово или фразу для поиска: \n"
        "ℹ️ Запрос не может быть пустым.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

    await state.set_state(Register.search_record)


@search_router.message(StateFilter(Register.search_record))
async def process_search_phrase(message: Message, state: FSMContext):
    phrase = message.text.strip()
    if not phrase:
        return await message.answer(
        "⚠️ Пустой запрос.\nВведите слово или фразу для поиска:",
        reply_markup=ReplyKeyboardRemove())

    if len(phrase) < 3:
        return await message.answer(
            "❌ **Слишком короткий запрос**\n\n"
            "Минимальная длина — 3 символа.\n"
            "Введите запрос заново или вернитесь в «🔙 Главное меню»",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⚠️ Почему нельзя?", callback_data="short_query_info")],
                    *inline_main_menu.inline_keyboard]))



    # Отправляем первое сообщение о прогрессе
    progress_msg = await message.answer("🔍 Идёт поиск, пожалуйста подождите...")

    try:
        # Этап 1 — поиск (используем нашу функцию search_data вместо run_search)
        results = await fs.search_data(phrase)
        await asyncio.sleep(0.5)
        await progress_msg.edit_text("⏳ Обработка результатов...")

        if not results:
            await progress_msg.delete()
            await message.answer(
                f"🔍 **Ничего не найдено**\n\n"
                f"По запросу «{phrase}» нет совпадений.\n"
                "Введите новую фразу или вернитесь в «🔙 Главное меню»",
                reply_markup=inline_main_menu
            )
            return

        # Этап 2 — создание PDF
        await asyncio.sleep(0.5)
        await progress_msg.edit_text("📄 Формирую файл с результатами...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Результат_{message.from_user.id}_{phrase}_{timestamp}.pdf"  # Изменил на .pdf, так как создаём PDF
        file_path = fs.create_pdf_file(results, filename)

        # Этап 3 — финал
        await asyncio.sleep(0.5)
        await progress_msg.edit_text("🧾 Подготавливаю отправку результата...")

        # Удаляем индикатор
        await progress_msg.delete()

        # Отправляем PDF
        await message.answer_document(
            document=FSInputFile(file_path),
            caption=f"По запросу '{phrase}' найдено {len(results)} результатов.",
            reply_markup=inline_main_menu
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")  # Логируем для отладки
        await progress_msg.edit_text("❌ Ошибка при обработке запроса.")
        await state.clear()
        await message.answer(
            f"❌ **Произошла ошибка**\n\n"
            "Запрос не удалось обработать. Попробуйте позже или измените запрос.",
            reply_markup=inline_main_menu
        )

@search_router.callback_query(F.data == "short_query_info")
async def short_query_alert(callback: CallbackQuery):
    """
    Показывает пользователю предупреждение, если запрос слишком короткий.
    """
    await callback.answer(
        "⚠️ Короткие запросы дают слишком много результатов и сильно нагружают базу. "
        "Введите 3 или более символов для корректного поиска.",
        show_alert=True
    )


