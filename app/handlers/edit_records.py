from aiogram import F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from app.states import Register
import logging
from app.keyboards import inline_main_menu, main
import asyncio
import app.utils.funcs as fs


edit_router = Router()  # локальный роутер
logger = logging.getLogger(__name__)


@edit_router.message(F.text == '✏️ Изменить запись')
async def start_edit(message: Message, state: FSMContext):
    data = fs.load_access_data()
    user_id = message.from_user.id
    role = fs.get_user_role(user_id, data)

    if role is None:
        await message.answer("⛔ Доступ запрещён.")
        return

    logger.info(f"Пользователь {user_id} начал редактирование записи.")

    await message.answer(
        "✏️ **Редактирование записи**\n\n"
        "🔍 Введите слово или фразу для поиска: \n"
        "ℹ️ Запрос не может быть пустым.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

    await state.set_state(Register.waiting_for_search_phrase)


@edit_router.message(StateFilter(Register.waiting_for_search_phrase))
async def process_search_phrase(message: Message, state: FSMContext):
    phrase = message.text.strip()

    if not phrase:
        return await message.answer("⚠️ Пустой запрос.\nВведите слово или фразу для поиска:")

    if len(phrase) < 3:
        return await message.answer(
            "❌ **Слишком короткий запрос**\n\n"
            "Минимальная длина — 3 символа.\n"
            "Введите запрос заново или вернитесь в «🔙 Главное меню»",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="⚠️ Почему нельзя?", callback_data="short_query_info")],
                    *inline_main_menu.inline_keyboard]))

    # Отправляем первое сообщение о прогрессе
    progress_msg = await message.answer("🔍 Идёт поиск, пожалуйста подождите...")

    try:
        results = await fs.run_search(phrase)
        await asyncio.sleep(0.5)
        await progress_msg.edit_text("⏳ Обработка результатов...")
        await asyncio.sleep(0.5)  # Пауза после обработки

        if not results:
            await progress_msg.delete()
            return await message.answer(
                f"🔍 По запросу '<code>{phrase}</code>' ничего не найдено.\n\n"
                f"• Попробуйте ввести другой запрос\n"
                f"• Или вернитесь в главное меню",
                reply_markup=inline_main_menu,
                parse_mode="HTML"
            )

        # Сохраняем результаты и начинаем показ первой записи
        await state.update_data(search_results=results, current_index=0, search_phrase=phrase)
        await progress_msg.edit_text("📄 Подготовка к показу результатов...")
        await asyncio.sleep(0.3)  # Небольшая пауза перед открытием
        await progress_msg.delete()
        await fs.show_record(message, state)
        await state.set_state(Register.viewing_record)

    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        await progress_msg.edit_text("❌ Ошибка при обработке запроса.")
        await state.clear()
        await message.answer(
            f"Ошибка: {str(e)}. Попробуйте позже.",
            reply_markup=inline_main_menu
        )

# Обработка перехода между записями


@edit_router.callback_query(F.data.in_({"prev_record", "next_record"}))
async def navigate_records(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["current_index"]
    total = len(data["search_results"])

    if callback.data == "prev_record" and index > 0:
        await state.update_data(current_index=index - 1)
    elif callback.data == "next_record" and index < total - 1:
        await state.update_data(current_index=index + 1)
    else:
        await callback.answer()
        return

    await fs.show_record(callback, state)
    await callback.answer()


# Обработка начала редактирования поля
@edit_router.callback_query(F.data.startswith("edit_"))
async def start_field_edit(callback: CallbackQuery, state: FSMContext):
    field_map = {
        "edit_problem": ("work_description", "Введите новое описание проблемы:"),
        "edit_solution": ("work_solution", "Введите новое решение:"),
        "edit_status": ("fault_status", "Введите новый статус:"),
        "edit_workers": ("workers", "Введите новых исполнителей работ:")
    }

    field_key, prompt = field_map[callback.data]
    data = await state.get_data()
    current_index = data["current_index"]
    records = data["search_results"]
    old_value = records[current_index][field_key]

    await state.update_data(editing_field=field_key, old_value=old_value)

    # Создаем кнопку для копирования старого текста
    copy_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Скопировать текущий текст", callback_data="copy_old_text")],
        [InlineKeyboardButton(
            text="❌ Отмена", callback_data="cancel_edit_field")]
    ])

    await callback.message.answer(
        "✅ Текст готов к копированию!\n\n"
        "🔹 <b>Что делать дальше:</b>\n"
        "• Нажмите кнопку 'Скопировать' ниже\n"
        "• Скопируйте текст нажатием на текст\n"
        "• Вставьте его в поле ввода ниже ⬇️\n"
        "• Внесите необходимые изменения\n"
        "• Отправьте сообщение и подтвердите для сохранения\n\n"
        "<i>Или просто введите новую информацию вручную</i>",
        reply_markup=copy_kb,
        parse_mode="HTML"
    )
    await callback.answer()


# Обработка отмены редактирования поля
@edit_router.callback_query(F.data == "cancel_edit_field")
async def cancel_field_edit(callback: CallbackQuery, state: FSMContext):
    # Очищаем данные редактирования
    await state.update_data(editing_field=None, old_value=None, new_value=None)

    # Возвращаемся к просмотру записи
    await state.set_state(Register.viewing_record)
    await fs.show_record(callback, state)
    await callback.answer()


# Обработка копирования старого текста
@edit_router.callback_query(F.data == "copy_old_text")
async def copy_old_text(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    old_value = data["old_value"]

    # Отправляем старый текст как сообщение, которое пользователь может скопировать
    await callback.message.edit_text(
        f"\n\n<code>{old_value}</code>\n\n",
        parse_mode="HTML"
    )

    # Убираем кнопки и ждем ввода нового значения
    await state.set_state(Register.editing_field)
    await callback.answer()


# Обработка нового значения поля
@edit_router.message(StateFilter(Register.editing_field))
async def save_edited_field(message: Message, state: FSMContext):
    new_value = message.text.strip()
    if not new_value:
        return await message.answer("Значение не может быть пустым. Попробуйте ещё раз:")

    data = await state.get_data()
    field_to_update = data["editing_field"]
    old_value = data["old_value"]

    # Сохраняем новое значение временно
    await state.update_data(new_value=new_value)

    # Создаём кнопки подтверждения
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить",
                              callback_data="confirm_save")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_save")]
    ])

    await message.answer(
        f"Вы хотите изменить поле на:\n\n<b>{new_value}</b>\n\nВыберите действие:",
        reply_markup=confirm_kb,
        parse_mode="HTML"
    )
    await state.set_state(Register.confirming_edit)

# Подтверждение сохранения изменений


@edit_router.callback_query(F.data == "confirm_save", StateFilter(Register.confirming_edit))
async def confirm_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    field_to_update = data["editing_field"]
    new_value = data["new_value"]
    current_index = data["current_index"]
    records = data["search_results"]
    record = records[current_index]

    # Обновляем значение в памяти
    record[field_to_update] = new_value
    records[current_index] = record
    await state.update_data(search_results=records)

    # Сохраняем в БД
    try:
        await fs.update_record_in_db(record["id"], {field_to_update: new_value})
        await callback.message.edit_text("✅ Поле успешно обновлено!", reply_markup=None)
    except Exception as e:
        logger.error(f"Ошибка при обновлении записи: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при сохранении.", reply_markup=None)

    await state.set_state(Register.viewing_record)
    await fs.show_record(callback, state)
    await callback.answer()


# Отмена сохранения изменений
@edit_router.callback_query(F.data == "cancel_save", StateFilter(Register.confirming_edit))
async def cancel_save(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("↩️ Изменения отменены.", reply_markup=None)
    await state.set_state(Register.viewing_record)
    await fs.show_record(callback, state)
    await callback.answer()


@edit_router.callback_query(lambda c: c.data == "main_menu")
async def go_to_main_menu(callback: CallbackQuery, state: FSMContext):
    try:
        # Удаляем сообщение с PDF и кнопкой
        await callback.message.delete()
    except Exception as e:
        # Иногда сообщение может быть уже удалено, тогда просто логируем
        logger.warning(f"Не удалось удалить сообщение: {e}")

    # Отправляем главное меню
    await callback.message.answer(
        "Главное меню:",
        reply_markup=main
    )
    await state.clear()

# Кнопка "Удалить запись"
@edit_router.callback_query(F.data == "delete_record")
async def confirm_delete_record(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    role = fs.get_user_role(user_id, fs.load_access_data())
    
    if role != "👑 Главный администратор!":
        await callback.answer("⛔ У вас нет прав на удаление записи", show_alert=True)
        return
    
    data = await state.get_data()
    index = data["current_index"]
    result = data.get("search_results", [])
    
    if not result or index >= len(result):
        await callback.answer("❌ Запись не найдена", show_alert=True)
        
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data="delete_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="delete_cancel")]
    ])
    
    await callback.message.edit_text(
        f"⚠️ Вы уверены, что хотите удалить запись #{result[index]['id']}?",
        reply_markup=confirm_kb)
    await callback.answer()
    
# Подтверждение удаления записи
@edit_router.callback_query(F.data == "delete_confirm")
async def perform_delete_record(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["current_index"]
    results = data.get("search_results", [])
    
    if not results or index >= len(results):
        await callback.answer("❌ Запись уже удалена или не найдена", show_alert=True)
        
    record_id = results[index]["id"]
    
    try:
        await fs.delete_record_from_db(record_id)
        
        results.pop(index)
        await state.update_data(search_results=results)
        
        if index >= len(results):
            index = len(results) - 1
            await state.update_data(current_index=max(index, 0))
        
        if results:
            await callback.answer("✅ Запись удалена")
            await fs.show_record(callback, state)
        else:
            await callback.message.edit_text(
                "🗑 Все записи удалены или больше не найдены.",
                reply_markup=inline_main_menu
            )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при удалении записи {record_id}: {e}")
        await callback.answer("❌ Произошла ошибка при удалении", show_alert=True)
        
# Отмена удаления записи
@edit_router.callback_query(F.data == "delete_cancel")
async def cancel_delete_record(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("↩️ Удаление отменено")
    await state.set_state(Register.viewing_record)
    await fs.show_record(callback, state)
    await callback.answer()