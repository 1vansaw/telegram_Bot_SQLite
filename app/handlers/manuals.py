import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from app.states import Register
import logging
import json
from app.keyboards import inline_main_menu, main
from aiogram.types import ReplyKeyboardRemove, FSInputFile
from app.config import settings
import app.utils.funcs as fs
import os
from math import ceil
from aiogram.exceptions import TelegramBadRequest



manuals_router = Router()
logger = logging.getLogger(__name__)



# @manuals_router.message(F.text == '📚 Руководства')
# async def manuals(message: Message):
#     data = fs.load_access_data()
#     user_id = message.from_user.id
#     role = fs.get_user_role(user_id, data)

#     if role in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
#         text = (
#     			"Выберите руководство:\n\n"
#     			f"📄 <a href=\"{settings.MD}\">Параметры MD</a>\n"
#     			f"🔧 <a href=\"{settings.PLC_ALARM}\">PLC Alarm</a>\n"
#     			f"⚙️ <a href=\"{settings.H_COMMAND}\">H Command</a>"
# 				)

#         if not text:
#             await message.answer("Руководства пока не добавлены.")
#             return

#         # Создаём inline-клавиатуру с кнопками для калькулятора и возврата в главное меню
#         keyboard = InlineKeyboardMarkup(inline_keyboard=[
#             [InlineKeyboardButton(text="🧮 Калькулятор ошибок", callback_data="error_calculator")],
#             [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
#         ])
#         await message.answer(text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=keyboard)
#     else:
#         await message.answer('⛔ У вас нет доступа')

@manuals_router.message(F.text == '📚 Руководства')
async def manuals(message: Message):
    data = fs.load_access_data()  # Загружаем данные о пользователях
    user_id = message.from_user.id
    role = fs.get_user_role(user_id, data)
    if role in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
        if not os.path.exists(settings.MANUALS_DIR):
            await message.answer("📚 Руководства отсутствуют.")
            return

        files = sorted(
            f for f in os.listdir(settings.MANUALS_DIR)
            if f.lower().endswith(('.pdf', '.txt'))
        )

        if not files:
            await message.answer("📚 Руководства отсутствуют.")
            return

        page = 1
        total_pages = ceil(len(files) / settings.MANUALS_PER_PAGE)

        text = (
                "📚 <b>Руководства</b>\n\n"
                f"📱 <b>Страница:</b> <code>{page}/{total_pages}</code>\n"
                f"{'•' * 30}\n"
                "⬇️ Выберите руководство"
            )

        keyboard = fs.manuals_keyboard(files, page)

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer("⛔ У вас нет доступа.")
    
    
    
@manuals_router.callback_query(F.data.startswith("manuals_page:"))
async def manuals_page(callback: CallbackQuery):
    if not os.path.exists(settings.MANUALS_DIR):
        await callback.answer("📚 Руководства отсутствуют.", show_alert=True)
        return

    try:
        page = int(callback.data.split(":")[1])
    except ValueError:
        await callback.answer()
        return

    files = sorted(
        f for f in os.listdir(settings.MANUALS_DIR)
        if f.lower().endswith(('.pdf', '.txt'))
    )

    if not files:
        await callback.message.edit_text("📚 Руководства отсутствуют.")
        await callback.answer()
        return

    total_pages = ceil(len(files) / settings.MANUALS_PER_PAGE)
    page = max(1, min(page, total_pages))

    text = (
        "📚 <b>Руководства</b>\n\n"
        f"📱 <b>Страница:</b> <code>{page}/{total_pages}</code>\n"
        f"{'•' * 30}\n"
        "⬇️ Выберите руководство"
    )

    keyboard = fs.manuals_keyboard(files, page)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@manuals_router.callback_query(F.data.startswith("manual:"))
async def send_manual(callback: CallbackQuery):
    filename = callback.data.split(":", 1)[1]

    # Валидация
    if '..' in filename or filename.startswith('/'):
        await callback.answer("❌ Недопустимое имя файла.", show_alert=True)
        return

    filepath = os.path.join(settings.MANUALS_DIR, filename)
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        await callback.answer("❌ Файл не найден.", show_alert=True)
        return

    # ✅ Сразу подтверждаем callback, чтобы убрать "часики"
    await callback.answer()
    await callback.message.delete()

    # Просто отправляем сообщение о начале загрузки (не будем редактировать)
    loading_msg = await callback.message.answer(
        "⏳ Идёт отправка файла...\n"
        "ℹ️ Время загрузки зависит от размера файла и скорости вашего интернета.",
        reply_markup=ReplyKeyboardRemove())

    try:
        file_input = FSInputFile(filepath)
        display_name = os.path.splitext(filename)[0]

        
        
        await callback.message.answer_document(
            document=file_input,
            caption=f"📄 {display_name[:100]}",reply_markup=inline_main_menu
        )

    except Exception as e:
        logger.error(f"Ошибка при отправке файла {filename}: {e}")
        await callback.message.answer("❌ Ошибка при отправке файла.")
    finally:
        await loading_msg.delete()

        
@manuals_router.callback_query(F.data == 'error_calculator_828D')
async def start_error_calculator_828(callback: CallbackQuery, state: FSMContext):
    data = fs.load_access_data()
    user_id = callback.from_user.id
    role = fs.get_user_role(user_id, data)

    if role in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
        await callback.answer()

        # Пытаемся удалить сообщение с кнопками руководств
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение с руководствами: {e}")

        # Отправляем запрос на ввод ошибки
        await callback.message.answer(
            "🧮 **Калькулятор ошибок**\n\n"
            "❗ Введите номер ошибки:",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        await state.set_state(Register.error_code_828)
    else:
        await callback.answer()
        await callback.message.answer('⛔ У вас нет доступа')
        
        
@manuals_router.message(Register.error_code_828)
async def process_error_code_828(message: Message, state: FSMContext):
    try:
        error_code = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❗ Введите корректный <b>числовой</b> код ошибки:",
            parse_mode="HTML"
        )
        return

    # Проверяем диапазон
    if not (700000 <= error_code < 700248):
        await message.answer(
            "🚫 <b>Код вне допустимого диапазона</b>\n\n"
            "📌 Допустимый диапазон: <code>700000 – 700247</code>\n\n"
            "🔁 Попробуйте снова или выйдите в меню:",
            parse_mode="HTML",
            reply_markup=inline_main_menu
        )
        return  # ❗ состояние НЕ очищаем

    # Если всё корректно
    result = fs.return_bits_828D(error_code)

    await message.answer(result, parse_mode="HTML",reply_markup=inline_main_menu)

    # ✅ Очищаем состояние только после успешного ввода
    await state.clear()
        
        
        

@manuals_router.callback_query(F.data == 'error_calculator')
async def start_error_calculator(callback: CallbackQuery, state: FSMContext):
    data = fs.load_access_data()
    user_id = callback.from_user.id
    role = fs.get_user_role(user_id, data)

    if role in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
        await callback.answer()

        # Пытаемся удалить сообщение с кнопками руководств
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение с руководствами: {e}")

        # Отправляем запрос на ввод ошибки
        await callback.message.answer(
            "🧮 **Калькулятор ошибок**\n\n"
            "❗ Введите номер ошибки:",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        await state.set_state(Register.error_code)
    else:
        await callback.answer()
        await callback.message.answer('⛔ У вас нет доступа')


# Хендлер для обработки введенного номера ошибки
@manuals_router.message(Register.error_code)
async def process_error_code(message: Message, state: FSMContext):
    error_code = message.text.strip()  # Получаем введенный текст и убираем лишние пробелы

    try:
        with open(settings.FILE_ALARM, 'r', encoding='utf-8') as f:
            errors = json.load(f)

        if error_code in errors:
            # Возвращаем полный бит (весь errors[error_code], например, "DB2.DBX 0.0")
            bit = errors[error_code]
            await message.answer(
                f"🧮 **Результат поиска**\n\n"
                f"🔢 **Код ошибки:** `{error_code}`\n"
                f"⚙️ **Бит:** `{bit}`\n\n"
                "➡️ Введите следующий номер ошибки\n"
                "или нажмите **«🔙 Главное меню»**",
                reply_markup=inline_main_menu,
                parse_mode="Markdown"
            )
        else:
           await message.answer(
                "❌ **Ошибка не найдена**\n\n"
                "Проверьте номер ошибки и попробуйте ещё раз.\n"
                "📌 Пример: `700000`\n"
                "или нажмите «🔙 Главное меню»",
                reply_markup=inline_main_menu,
                parse_mode="Markdown"
            )
    except FileNotFoundError:
        await message.answer(
            "⚠️ **Файл с ошибками не найден**\n"
            "Сообщите администратору.",
            reply_markup=inline_main_menu,
            parse_mode="Markdown"
        )
    except json.JSONDecodeError:
        await message.answer(
            "⚠️ **Ошибка чтения файла ошибок**\n"
            "Формат файла повреждён.",
            reply_markup=inline_main_menu,
            parse_mode="Markdown"
        )




    
    
# Callback-хендлер для возврата в главное меню
@manuals_router.callback_query(F.data == "main_menu")
async def go_to_main_menu(callback: CallbackQuery, state: FSMContext):
    try:
        # Удаляем сообщение с PDF и кнопкой
        await callback.message.delete()
    except Exception as e:
        # Иногда сообщение может быть уже удалено, тогда просто логируем
        logger.warning(f"Не удалось удалить сообщение: {e}")

    # Сбрасываем FSM состояние, чтобы выйти из режима калькулятора
    await state.clear()

    # Отправляем главное меню
    await callback.message.answer(
        "Главное меню:",
        reply_markup=main
    )

    # Заканчиваем callback
    await callback.answer()
