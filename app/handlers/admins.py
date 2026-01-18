from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.keyboards import admin_menu, del_admins, main, confirm_edit_admins, auto_backup_menu, confirm_menu, backup_db_confirm_kb, source_keyboard
import app.utils.funcs as fs
import asyncio
import os
from datetime import datetime
from app.states import Register
import logging
from aiogram.fsm.context import FSMContext
from app.config import settings
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, FSInputFile
from aiogram.filters import StateFilter


admin_router = Router()  # <-- локальный роутер
logger = logging.getLogger(__name__)


@admin_router.message(F.text == '👑 Админ меню')
async def admino_menu(message: Message):
    data = fs.load_access_data()
    user_id = message.from_user.id  # Получаем ID пользователя
    role = fs.get_user_role(user_id, data)
    if role == "👑 Главный администратор!":
        await message.answer(
            "👑 Добро пожаловать в админ меню!\nВыберите действие:",
            reply_markup=admin_menu)
    else:
        await message.answer('⛔ У вас нет доступа')


@admin_router.message(F.text == '💾 Резервная копия БД')
async def backup_database_request(message: Message):
    """Запрос подтверждения перед созданием бэкапа"""
    await message.answer(
        "⚠️ Вы уверены, что хотите создать резервную копию базы данных?",
        reply_markup=backup_db_confirm_kb
    )

@admin_router.callback_query(F.data == "backup_db_confirm")
async def backup_db_confirm_handler(callback: CallbackQuery):
    await callback.message.edit_text("⏳ Создаю резервную копию базы данных...")
    
    try:
        backup_filename = await fs.create_backup()
        current_count = len([
            f for f in os.listdir(settings.DIR_DB)
            if f.startswith('Копия_БД_') and f.endswith('.db')
        ])
        
        try:
            disk_msg = await fs.upload_to_yadisk(
                os.path.join(settings.DIR_DB, backup_filename),
                f"/Backups/{backup_filename}"
            )
        except Exception as e:
            logger.error(f"Ошибка загрузки на Яндекс.Диск: {e}")
            disk_msg = "⚠️ Не удалось загрузить на Яндекс.Диск."

        yadisk_count = await fs.count_yadisk_backups()

        await callback.message.edit_text(
            f"✅ Резервная копия базы данных успешно создана!\n\n"
            f"📄 Файл: `{backup_filename}`\n"
            f"💾 Локальных копий: {current_count}/5\n"
            f"☁️ Копий на Яндекс.Диске: {yadisk_count}\n\n"
            f"{disk_msg}\n\n"
            f"🕒 Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
            parse_mode="HTML"
        )

        logger.info(f"Создана резервная копия: {backup_filename} ({current_count}/5)")

    except FileNotFoundError:
        await callback.message.edit_text("❌ Ошибка: исходная база данных не найдена!")
        logger.error("Резервная копия: исходная база данных не найдена.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при создании резервной копии: {str(e)}")
        logger.error(f"Ошибка резервного копирования: {e}")


# -------------------- Отмена создания --------------------
@admin_router.callback_query(F.data == "backup_db_cancel")
async def backup_db_cancel_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚠️ Создание резервной копии базы данных отменено.")



@admin_router.message(F.text == '🕒 Автокопирование БД')
async def auto_backup_settings(message: Message):
    setting = fs.load_auto_backup_settings()
    interval = setting["interval"]

    # Статус автокопирования слева
    status_icon = "🟢" if setting["enabled"] else "🔴"
    status_text = "Включено" if setting["enabled"] else "Выключено"

    # Иконки для интервалов
    interval_icon = {
        "daily": "🔁 Ежедневно",
        "weekly": "📅 Еженедельно",
        "monthly": "🗓 Ежемесячно",
        "off": "❌ Выключено"
    }.get(interval, "❔")

    # Статус уведомлений (правильный ключ)
    notify_icon = "🟢" if setting.get("notify", True) else "🔴"
    notify_text = "Включены" if setting.get("notify", True) else "Выключены"

    text = (
        f"📄 **Автокопирование БД:** {status_icon} {status_text}\n"
        f"⏱ Текущее состояние: {interval_icon}\n"
        f"📣 Уведомления админу: {notify_icon} {notify_text}\n\n"
        f"⬇️ Выберите новый интервал ниже:"
    )

    await message.answer(
        text,
        reply_markup=auto_backup_menu,
        parse_mode="Markdown"
    )


pending_changes = {}


@admin_router.message(F.text.in_({
    '🔁 Раз в день',
    '📅 Раз в неделю',
    '🗓 Раз в месяц',
    '❌ Отключить автокопирование'
}))
async def auto_backup_interval_handler(message: Message):
    setting = fs.load_auto_backup_settings()

    # Определяем новый интервал
    if message.text == '🔁 Раз в день':
        new_interval = "daily"
    elif message.text == '📅 Раз в неделю':
        new_interval = "weekly"
    elif message.text == '🗓 Раз в месяц':
        new_interval = "monthly"
    elif message.text == '❌ Отключить автокопирование':
        new_interval = "off"

    old_interval = setting["interval"]

    # Сохраняем запрос
    pending_changes[message.from_user.id] = new_interval

    old_name = settings.INTERVAL_NAMES[old_interval]
    new_name = settings.INTERVAL_NAMES[new_interval]

    # Формируем текст подтверждения
    if old_interval == "off" and new_interval != "off":
        text = f"🟢 Вы хотите включить автокопирование **{new_name}**?"
    elif new_interval == "off":
        text = f"🔴 Вы уверены, что хотите **отключить автокопирование**?"
    else:
        text = (
                f"🔄 Изменение интервала автокопирования:\n\n"
                f"⏰ Текущий: **{old_name}**\n"
                f"➡️ Новый: **{new_name}**\n\n"
                "Вы подтверждаете?"
            )

    await message.answer(
        text,
        reply_markup=confirm_menu,
        parse_mode="Markdown"
    )


@admin_router.message(F.text == '✔ Да')
async def confirm_auto_backup_change(message: Message):
    user_id = message.from_user.id

    if user_id not in pending_changes:
        await message.answer("Нет изменений для подтверждения.", reply_markup=admin_menu)
        return

    new_interval = pending_changes.pop(user_id)
    setting = fs.load_auto_backup_settings()

    setting["interval"] = new_interval
    setting["enabled"] = (new_interval != "off")

    fs.save_auto_backup_settings(setting)

    if new_interval == "off":
        text = "🔴 Автокопирование отключено."
    else:
        text = f"🟢 Автокопирование включено: **{settings.INTERVAL_NAMES[new_interval]}**."

    await message.answer(
        text,
        reply_markup=admin_menu,
        parse_mode="Markdown"
    )


@admin_router.message(F.text == '✖ Отмена')
async def cancel_auto_backup_change(message: Message):
    pending_changes.pop(message.from_user.id, None)

    await message.answer(
        "⚠️ Изменение автокопирования отменено.",
        reply_markup=admin_menu
    )



@admin_router.message(F.text == '🔄 Восстановить БД из копии')
async def restore_database_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите источник резервной копии:", reply_markup=source_keyboard)


# Обработчик выбора резервной копии
@admin_router.callback_query(F.data.startswith("restore_source_"))
async def select_restore_source(callback: CallbackQuery, state: FSMContext):
    source = callback.data.split("_")[-1]  # "local" или "yadisk"
    await state.update_data(source=source)

    backup_files = []

    if source == "local":
        if not os.path.exists(settings.DIR_DB):
            await callback.message.edit_text("❌ Папка с резервными копиями не найдена!")
            return

        files = [
            f for f in os.listdir(settings.DIR_DB)
            if f.startswith('Копия_БД_') and f.endswith('.db')
        ]
        
        if not files:  # Если нет локальных копий
            await callback.message.edit_text("❌ Резервные копии не найдены в папке!")
            return

        files.sort(key=lambda x: os.path.getctime(os.path.join(settings.DIR_DB, x)), reverse=True)
        files = files[:5]  # Ограничиваем 5 последними
        # Формируем список словарей для единообразия
        backup_files = [{"name": f, "created": datetime.fromtimestamp(os.path.getctime(os.path.join(settings.DIR_DB, f))).strftime("%d.%m.%Y %H:%M")} for f in files]

    else:  # yadisk
        # Показываем сообщение о подготовке файлов
        status_message = await callback.message.edit_text("⏳ Подготавливаю файлы с Яндекс.Диска...")

        backup_files_data = await fs.list_yadisk_backups()
        if not backup_files_data:
            await status_message.edit_text("❌ Резервные копии на Яндекс Диске не найдены!")
            return
        backup_files = backup_files_data  # Ожидаем [{"name": "Копия_БД_01.db", "created": "2026-01-17 12:00"}]

    # Клавиатура для выбора копии
    keyboard = [
        [InlineKeyboardButton(
            text=f"#{i+1} 🕒 {b['created']}",
            callback_data=f"restore_select_{i}"
        )] for i, b in enumerate(backup_files)
    ]
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="restore_cancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await state.update_data(restore_files=backup_files)
    await state.set_state(Register.choosing_backup)
    await callback.message.edit_text("📋 Выберите резервную копию для восстановления:", reply_markup=markup)



@admin_router.callback_query(F.data.startswith("restore_select_"))
async def select_backup_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    backup_files = data.get('restore_files', [])
    source = data.get('source', 'local')

    index = int(callback.data.split("_")[2])
    if index < 0 or index >= len(backup_files):
        await callback.answer("❌ Некорректный выбор", show_alert=True)
        return

    selected = backup_files[index]
    await state.update_data(selected_file=selected, step='confirming_restore')
    await state.set_state(Register.confirming_restore)

    file_time = selected["created"]
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="restore_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="restore_cancel")]
    ])

    await callback.message.edit_text(
        f"⚠️ ВНИМАНИЕ!\n\n"
        f"Вы собираетесь восстановить базу данных из копии:\n"
        f"📄 {selected['name']}\n"
        f"📅 {file_time}\n\n"
        f"Текущие данные будут заменены. Это действие нельзя отменить!\n\n"
        f"Подтвердите восстановление:",
        reply_markup=confirm_keyboard
    )
    await callback.answer()




# --- Подтверждение восстановления ---
@admin_router.callback_query(F.data == "restore_confirm")
async def confirm_restore_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_file = data.get('selected_file')
    source = data.get('source', 'local')

    if not selected_file:
        await callback.answer("❌ Сессия истекла, начните заново", show_alert=True)
        return

    try:
        # Показываем сообщение о начале восстановления
        status_message = await callback.message.edit_text("⏳ Начинаем восстановление базы данных...")

        if source == "yadisk":
            # Сообщение о загрузке с Яндекс.Диска
            await status_message.edit_text(f"⬇️ Скачиваем резервную копию с Яндекс.Диска: {selected_file['name']} ...")
            file_path = await fs.download_yadisk_backup(selected_file['name'])
        else:
            file_path = os.path.join(settings.DIR_DB, selected_file['name'])

        # Проверка на существование файла после скачивания
        if not os.path.exists(file_path):
            await status_message.edit_text(f"❌ Файл не найден: {file_path}")
            return

        # Сообщение о начале восстановления
        await status_message.edit_text(f"⚙️ Восстанавливаем базу данных из: {selected_file['name']} ...")
        result = await fs.perform_database_restore(file_path)

        if result:
            await status_message.edit_text("✅ База данных успешно восстановлена из резервной копии!")
        else:
            await status_message.edit_text("❌ Ошибка при восстановлении базы данных!")

        await state.clear()
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка восстановления базы данных: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")
        await state.clear()
        await callback.answer(show_alert=True)


# --- Отмена восстановления ---
@admin_router.callback_query(F.data == "restore_cancel")
async def cancel_restore_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("↩️ Восстановление отменено.")
    await callback.answer()




@admin_router.message(F.text == '↩️ В админ меню')
async def auto_backup_back_handler(message: Message):
    await message.answer(
        "Выберите действие:",
        reply_markup=admin_menu
    )


@admin_router.message(F.text == '✅ Добавить админа')
async def add_admins(message: Message, state: FSMContext):
    await state.set_state(Register.add_admins)
    await message.answer("👤 Введите ID администратора")



@admin_router.message(Register.add_admins)
async def add_admins_id(message: Message, state: FSMContext):
    user_id = message.text.strip()  # Убираем пробелы по краям
    is_valid, error_msg = fs.validate_user_id(user_id)
    if not is_valid:
        await message.answer(f"❌ {error_msg}")
        return

    # Загружаем текущие данные из JSON
    access_data = fs.load_access_data()
    user_id_int = int(user_id)  # Преобразуем ID к числу
    # Приводим все ID к int
    # Проверяем, есть ли ID в администраторах
    existing_main_admins = set(map(int, access_data.get("main_admins", [])))
    existing_admins = set(map(int, access_data.get("admins", [])))
    existing_users = set(map(int, access_data.get("users", [])))
    if user_id_int in existing_main_admins:
        await message.answer(f"👑 Пользователь уже является главным администратором и не требует добавления.")
        return
    if user_id_int in existing_admins:
        await message.answer(f"🛠 Пользователь с ID {user_id} уже добавлен в список администраторов.")
        return

    await message.answer(
        f"✅ Вы хотите добавить пользователя с ID {user_id} в список администраторов?",
        reply_markup=confirm_edit_admins
    )
    await state.update_data(admins_id=user_id)


@admin_router.callback_query(F.data == "confirm_yes_admins")
async def confirm_yes_admins(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('admins_id')
    access_data = fs.load_access_data()
    access_data['admins'].append(int(user_id))
    if int(user_id) in access_data['users']:
        access_data['users'].remove(int(user_id))
    logger.info(
        f"Пользователь {callback.from_user.id} успешно добавил {user_id}.")
    fs.save_access_data(access_data)
    await callback.message.edit_text(f"✅ Пользователь с ID {user_id} успешно добавлен в список администраторов!")
    await state.clear()  # Завершение состояния после успешного добавления
    await state.set_state(Register.main_menu)
    await callback.message.answer('Возврат в начальное меню', reply_markup=main)


@admin_router.callback_query(F.data == "confirm_no_admins")
async def confirm_no_admins(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("❌ Добавление администратора отменено.")
    await callback.message.answer("Выберите действие", reply_markup=admin_menu)


@admin_router.message(F.text == '❌ Удалить админа')
async def show_admins_to_delete(message: Message, state: FSMContext):
    keyboard = fs.generate_admins_keyboard()
    if keyboard:
        await message.answer("⚠️ Выберите администратора для удаления:", reply_markup=keyboard)
    else:
        await message.answer("Список пользователей пуст, удалять некого!")



@admin_router.callback_query(F.data.startswith("deletes_"))
async def confirm_delete_admins(callback: CallbackQuery, state: FSMContext):
    """Удаляет выбранного пользователя."""
    user_id = int(callback.data.split("_")[1])  # Получаем ID из callback_data
    await state.update_data(admins_id_access=user_id)
    await callback.message.edit_text(f'✅ Вы уверены что хотите удалить администратора {user_id}?', reply_markup=del_admins)


@admin_router.callback_query(F.data.startswith("confirm_deletes_"))
async def confirm_delete_admins_1(callback: CallbackQuery, state: FSMContext):
    """Удаляет администратора после подтверждения."""
    user_data = await state.get_data()
    user_id = user_data.get('admins_id_access')
    if fs.delete_admins_from_access(user_id):
        logger.info(
            f"Пользователь {callback.from_user.id} подтвердил удаление администратора {user_id}.")
        await callback.message.edit_text(f"✅ Пользователь с ID {user_id} удален!")
    else:
        logger.warning(
            f"Пользователь {callback.from_user.id} не смог удалить администратора {user_id}.")
        await callback.message.edit_text(f"❌ Ошибка: пользователь с ID {user_id} не найден.")


@admin_router.callback_query(F.data == "cancel_deletes_admins")
async def cancel_delete_admins(callback: CallbackQuery):
    """Отмена удаления пользователя."""
    logger.info(
        f"Пользователь {callback.from_user.id} отменил удаление администратора.")
    await callback.message.edit_text("❌ Удаление отменено.")



@admin_router.message(F.text == '👥 Пользователи')
async def send_user_list(message: Message, state: FSMContext):
    data = fs.load_access_data()
    bot = message.bot
    user_id = message.from_user.id  # Получаем ID пользователя
    role = fs.get_user_role(user_id, data)
    user_list = {
        "👑 Главный администратор": [],
        "🛠 Администраторы": [],
        "👥 Пользователи": []
    }

    if role == "👑 Главный администратор!":
        # Обрабатываем списки пользователей
        for user_id in data['main_admins']:
            first_name, last_name, uid = await fs.get_user_info(bot, user_id)
            name_display = f"{first_name or 'Недоступен'} {last_name or ''}".strip(
            )
            user_role = fs.get_user_role(uid, data)
            user_list["👑 Главный администратор"].append(
                f"{name_display}, ID: {uid}, Уровень доступа: {user_role}")

        for user_id in data['admins']:
            first_name, last_name, uid = await fs.get_user_info(bot, user_id)
            name_display = f"{first_name or 'Недоступен'} {last_name or ''}".strip(
            )
            user_role = fs.get_user_role(uid, data)
            user_list["🛠 Администраторы"].append(
                f"{name_display}, ID: {uid}, Уровень доступа: {user_role}")

        for user_id in data['users']:
            first_name, last_name, uid = await fs.get_user_info(bot, user_id)
            name_display = f"{first_name or 'Недоступен'} {last_name or ''}".strip(
            )
            user_role = fs.get_user_role(uid, data)
            user_list["👥 Пользователи"].append(
                f"{name_display}, ID: {uid}, Уровень доступа: {user_role}")

        # Формируем ответ
        response = []
        for group, members in user_list.items():
            response.append(group + ":")
            if members:
                response.append("\n".join(members))
            else:
                response.append("Список пуст.")
            response.append("-----------------------------------------------")
        await message.answer('Ваш список: ', reply_markup=admin_menu)
        await message.answer("\n".join(response))
        await state.clear()

    else:
        # Отправляем сообщение, если у пользователя нет доступа
        await message.answer("⛔ У вас нет доступа для выполнения этой команды.")


@admin_router.message(F.text == '📄 Посмотреть логи')
async def view_logs_menu(message: Message, state: FSMContext):
    """
    Показывает меню для выбора файла логов.
    """

    try:
        available_files = [f for f in settings.LOG_FILES if os.path.exists(f)]
        if not available_files:
            await message.answer("Файлы логов не найдены. Проверьте настройки логирования.")
            logging.warning(f"Админ {message.from_user.id} попытался просмотреть логи, но файлы отсутствуют.")
            return

        # Сохраняем список файлов в state для текущего пользователя
        await state.update_data(log_files=available_files)

        # Создаём клавиатуру с индексами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{'🟢 Текущие' if i==0 else f'📁 Архив {i}'} ({os.path.basename(f)})",
                callback_data=f"logs:{i}"
            )]
            for i, f in enumerate(available_files)
        ])

        #await message.answer("Выберите файл логов для просмотра:", reply_markup=keyboard)
        await message.answer(
            "📂 **Меню логов**\n\n"
            "Выберите файл для просмотра:\n"
            "🟢 — текущий лог\n"
            "📁 — архивные логи",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        logging.info(f"Админ {message.from_user.id} открыл меню логов.")

    except Exception as e:
        logging.error(f"Ошибка при показе меню логов админу {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@admin_router.callback_query(F.data.startswith("logs:"))
async def view_selected_logs(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    log_files = data.get("log_files", [])

    index = int(callback.data.split(":", 1)[1])
    if index >= len(log_files):
        await callback.answer("❌ Файл не найден.", show_alert=True)
        return

    log_file = log_files[index]

    if not os.path.exists(log_file):
        await callback.answer("❌ Файл больше не существует.", show_alert=True)
        return

    if os.path.getsize(log_file) == 0:
        await callback.message.answer("⚠️ Файл логов пуст.")
        await callback.answer()
        return

    loading_msg = await callback.message.answer("⏳ Загружаю логи…")
    try:
        # Шаг 2: Отправляем файл
        document = FSInputFile(log_file, filename=f"{os.path.basename(log_file)}.txt")
        caption = f"📋 Логи из {os.path.basename(log_file)}"
        if os.path.getsize(log_file) > 1024*1024:
            caption += " (файл большой, рекомендуется скачать)"

        await callback.message.answer_document(document, caption=caption)

    except Exception as e:
        logging.error(f"Ошибка при отправке логов {log_file}: {e}")
        await callback.message.answer("❌ Ошибка при отправке файла. Попробуйте позже.")

    finally:
        # Шаг 3: Удаляем сообщение о загрузке
        await loading_msg.delete()
        await callback.answer()




@admin_router.message(F.text == '📢 Рассылка')
async def start_broadcast(message: Message, state: FSMContext):
    await state.set_state(Register.waiting_text)
    await message.answer(
        "📣 **Начало рассылки**\n\n"
        "Введите текст для рассылки всем пользователям.\n"
        "После ввода появится **preview** сообщения и кнопки подтверждения.\n\n"
        "✏️ *Совет: используйте короткий и понятный текст, можно добавить эмодзи для наглядности*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove())
    logger.info(f"Админ {message.from_user.id} начал рассылку")



@admin_router.message(StateFilter(Register.waiting_text))
async def handle_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="broadcast:confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")]
    ])

    await message.answer(
        "📢 **Preview рассылки** 📢\n\n"
        f"💬 {message.text}\n\n"
        "Вы уверены, что хотите отправить это сообщение всем пользователям?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@admin_router.callback_query(F.data.startswith("broadcast:"))
async def handle_broadcast_confirmation(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data_state = await state.get_data()
    broadcast_text = data_state.get("text")

    if not broadcast_text:
        await callback.answer("Процесс рассылки не активен.", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]

    if action == "confirm":
        await state.clear()

        user_ids = fs.get_all_user_ids()
        total_users = len(user_ids)

        if total_users == 0:
            report_text = "⚠️ Нет пользователей для рассылки (файл пуст или ошибка чтения)."
            await callback.message.answer(report_text, reply_markup=admin_menu)
            logger.info(
                f"Главный админ {user_id} попытался отправить рассылку, но пользователей нет."
            )
            await callback.answer("Рассылка не отправлена (нет пользователей).")
            return

        sent_count = 0
        failed_count = 0

        for uid in user_ids:
            if uid == user_id:
                continue
            try:
                await callback.bot.send_message(chat_id=uid, text=broadcast_text)
                sent_count += 1
            except Exception as e:
                logging.warning(
                    f"Не удалось отправить рассылку пользователю {uid}: {e}"
                )
                failed_count += 1

        report_text = (
            f"📣 **Рассылка завершена!** 📣\n\n"
            f"👥 Всего пользователей: {total_users - 1}\n"
            f"✅ Успешно отправлено: {sent_count}\n"
            f"❌ Не удалось: {failed_count}\n\n"
            f"💬 **Текст рассылки:**\n{broadcast_text}"
        )

        await callback.message.answer(report_text, reply_markup=admin_menu)
        await callback.message.delete()

        logger.info(
            f"Главный админ {user_id} подтвердил и отправил рассылку: "
            f"'{broadcast_text}' ({sent_count} успешно, {failed_count} неудач)."
        )

        await callback.answer("Рассылка отправлена!")

    elif action == "cancel":
        await state.clear()

        report_text = "❌ Рассылка отменена."
        await callback.message.answer(report_text, reply_markup=admin_menu)
        await callback.message.delete()

        logger.info(f"Главный админ {user_id} отменил рассылку.")
        await callback.answer("Отменено.")


@admin_router.message(F.text == '🔔 Включить/выключить уведомления')
async def toggle_auto_backup_notifications(message: Message):
    setting = fs.load_auto_backup_settings()
    setting["notify"] = not setting.get("notify", True)
    fs.save_auto_backup_settings(setting)

    status = "🟢 Включены" if setting["notify"] else "🔴 Выключены"
    await message.answer(f"🔔 Уведомления об автокопировании {status}.",
                         reply_markup=auto_backup_menu)
    
