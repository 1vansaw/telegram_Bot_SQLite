import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from app.states import Register
import logging
from app.keyboards import edit_mashines, main, confirm_edit_mashines, confirm_edit_users, del_users, inline_main_menu, workshops
import app.utils.funcs as fs
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import os
from app.config import settings
from pathlib import Path
import aiofiles
import aiohttp
import time
import ssl
import certifi


editor_router = Router()
logger = logging.getLogger(__name__)

# Загружаем данные при старте
machines_data = fs.load_machines_data()

CHUNK_SIZE = 512 * 1024  # 512 KB за раз


@editor_router.message(F.text == '🛠️ Редактор')
async def to_edit(message: Message):
    data = fs.load_access_data()
    user_id = message.from_user.id  # Получаем ID пользователя
    role = fs.get_user_role(user_id, data)
    if role in ["👑 Главный администратор!", "🛠 Администратор!"]:
        await message.answer("Выберите действие (только для администраторов)", reply_markup=edit_mashines)
    else:
        await message.answer('⛔ У вас нет доступа')


@editor_router.message((F.text == '↩️ В главное меню'))
async def cmd_clear_no(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(f"Привет, {message.from_user.full_name}!",
                         reply_markup=main)


@editor_router.message(F.text == '✅ Добавить станок')
async def add_maschine_name(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Register.awaiting_machine_name)
    await message.answer("🔧 Выберите цех для добавления нового станка:",reply_markup=workshops)


@editor_router.message(F.text == '🗑 Удалить станок')
async def remove_maschine_name(message: Message, state: FSMContext):
    await state.set_state(Register.delete_machine)
    await message.answer("🗑 Выберите цех, чтобы удалить станок:",reply_markup=workshops)


@editor_router.message(F.text == '✅ Доб.пользователя')
async def add_users(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Register.add_user)
    await message.answer("👤 Введите ID нового пользователя:", reply_markup=ReplyKeyboardRemove())


@editor_router.message(Register.add_user)
async def get_machine_name_1(message: Message, state: FSMContext):
    user_id = message.text.strip()  # Убираем пробелы по краям
    is_valid, error_msg = fs.validate_user_id(user_id)
    if not is_valid:
        await message.answer(f"❌ {error_msg}")
        return

    # Загружаем текущие данные из JSON
    access_data = fs.load_access_data()
    user_id_int = int(user_id)  # Преобразуем ID к числу

    # Проверяем, есть ли ID в администраторах и пользователях
    existing_main_admins = set(map(int, access_data.get("main_admins", [])))
    existing_admins = set(map(int, access_data.get("admins", [])))
    existing_users = set(map(int, access_data.get("users", [])))

    if user_id_int in existing_main_admins or user_id_int in existing_admins:
        await message.answer(f"👑 Этот пользователь уже является администратором и не требует добавления в список пользователей.")
        return

    if user_id_int in existing_users:
        await message.answer(f"👤 Пользователь с ID {user_id} уже существует в списке пользователей.")
        return

    # Подтверждение добавления
    await message.answer(
        f"✅ Вы хотите сохранить пользователя с ID: {user_id}?",
        reply_markup=confirm_edit_users
    )

    # Сохраняем временно ID в FSM
    await state.update_data(users_id=user_id)


@editor_router.callback_query(F.data == "confirm_yes_users")
async def confirm_yes_users(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('users_id')

    # Загружаем текущие данные из JSON
    access_data = fs.load_access_data()

    # Добавляем нового пользователя
    access_data['users'].append(int(user_id))
    fs.save_access_data(access_data)

    logger.info(
        f"👤 Пользователь {user_id} добавлен администратором {callback.from_user.id}."
    )

    # Отправляем сообщение о результате
    await callback.message.edit_text(
        f"✅ Пользователь с ID {user_id} успешно добавлен в список пользователей!"
    )

    # Завершаем FSM и возвращаем в главное меню
    await state.clear()
    await state.set_state(Register.main_menu)
    await callback.message.answer(
        "🏠 Вы вернулись в главное меню",
        reply_markup=main
    )
    await callback.answer()  # чтобы Telegram закрыл спиннер callback



@editor_router.callback_query(F.data == "confirm_no_users")
async def confirm_no_users(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления пользователя"""
    await callback.message.edit_text("❌ Добавление пользователя отменено.",)
    await callback.message.answer(
        "🛠 Выберите действие:",
        reply_markup=edit_mashines
    )
    await callback.answer()  # закрываем спиннер кнопки


@editor_router.message(F.text == '🗑 Удал. пользователя')
async def show_users_to_delete(message: Message):
    """Показывает список пользователей для удаления"""
    logger.info(
        f"👤 Пользователь {message.from_user.id} запросил просмотр списка пользователей для удаления."
    )

    keyboard = fs.generate_users_keyboard()
    if keyboard:
        await message.answer(
            "🗑 Выберите пользователя для удаления:",
            reply_markup=keyboard
        )
    else:
        await message.answer("ℹ️ Список пользователей пуст, удалять нечего!")


@editor_router.callback_query(F.data.startswith("delete_"))
async def confirm_delete_user(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления выбранного пользователя."""
    user_id = int(callback.data.split("_")[1])  # Получаем ID из callback_data

    logger.info(
        f"👤 Пользователь {callback.from_user.id} выбрал пользователя {user_id} для удаления."
    )

    # Сохраняем выбранного пользователя в FSM
    await state.update_data(user_id_access=user_id)

    # Сообщение с подтверждением и эмодзи
    await callback.message.edit_text(
        f"❌ Вы уверены, что хотите удалить пользователя с ID {user_id}?",
        reply_markup=del_users
    )

    # Закрываем спиннер callback
    await callback.answer()


@editor_router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_user_1(callback: CallbackQuery, state: FSMContext):
    """Удаляет пользователя после подтверждения."""
    user_data = await state.get_data()
    user_id = user_data.get('user_id_access')
    if fs.delete_user_from_access(user_id):
        logger.info(
            f"Пользователь {callback.from_user.id} подтвердил удаление пользователя {user_id}.")
        await callback.message.edit_text(f"✅ Пользователь с ID {user_id} удален!")
    else:
        logger.warning(
            f"Пользователь {callback.from_user.id} не смог удалить пользователя {user_id}.")
        await callback.message.edit_text(f"❌ Ошибка: пользователь с ID {user_id} не найден.")


@editor_router.callback_query(F.data == "cancel_delete_users")
async def cancel_delete_users(callback: CallbackQuery):
    """Отмена удаления пользователя."""
    logger.info(
        f"Пользователь {callback.from_user.id} отменил удаление пользователя.")
    await callback.message.edit_text("❌ Удаление отменено.")


# функция обработки имени станка из сообщения пользователя
@editor_router.message(Register.awaiting_machine_name)
async def get_machine_name(message: Message, state: FSMContext):
    machine_name = message.text.strip()  # Убираем пробелы по краям

    # Проверка, что название станка не пустое
    if not machine_name:
        logger.warning(
            f"⚠️ Пользователь {message.from_user.id} ввел пустое название станка."
        )
        await message.answer(
            "❌ Название станка не может быть пустым. Пожалуйста, введите корректное название."
        )
        return

    # Получаем выбранный цех из состояния
    user_data = await state.get_data()
    shop = user_data.get('selected_shop')
    shop_number = shop.split('-')[0]

    # Загружаем данные о станках
    machines_data = fs.load_machines_data()
    existing_machines = machines_data.get(f'maschines_{shop_number}', [])

    # Проверка на дубли
    if any(machine['name'].lower() == machine_name.lower() for machine in existing_machines):
        logger.warning(
            f"⚠️ Пользователь {message.from_user.id} ввел дублирующее название станка '{machine_name}' в цехе {shop_number}."
        )
        await message.answer(
            f"❌ Станок с таким названием уже существует в цехе {shop_number}. Пожалуйста, введите другое название."
        )
        return

    # Сохраняем имя станка в FSM
    await state.update_data(machine_name=machine_name)

    # Переходим к следующему шагу
    await state.set_state(Register.awaiting_machine_inventory)
    await message.answer("🆔 Введите инвентарный номер станка:")

# функция обработки инвентарного номера станка из сообщения пользователя


@editor_router.message(Register.awaiting_machine_inventory)
async def add_machine_inventory(message: Message, state: FSMContext):
    inventory_number = message.text.strip()  # Убираем пробелы по краям

    # Получаем данные из FSM
    user_data = await state.get_data()
    machine_name = user_data.get("machine_name")
    shop = user_data.get('selected_shop')
    shop_number = shop.split('-')[0]

    # Загружаем данные о станках
    machines_data = fs.load_machines_data()
    existing_machines = machines_data.get(f'maschines_{shop_number}', [])

    # Проверка на дублирование инвентарного номера
    if any(machine['inventory_number'] == inventory_number for machine in existing_machines):
        logger.warning(
            f"⚠️ Пользователь {message.from_user.id} ввел дублирующий инвентарный номер '{inventory_number}' в цехе {shop_number}."
        )
        await message.answer(
            f"❌ Станок с таким инвентарным номером уже существует в цехе {shop_number}. Пожалуйста, введите другой номер."
        )
        return

    # Создаем объект нового станка
    new_machine = {"name": machine_name, "inventory_number": inventory_number}

    # Сохраняем данные в FSM для следующего шага
    await state.update_data(new_machine=new_machine, shop_number=shop_number)

    # Подтверждение добавления
    confirmation_text = (
        f"✅ Вы хотите сохранить станок:\n"
        f"🔹 Название: {machine_name}\n"
        f"🆔 Инвентарный номер: {inventory_number}\n"
        f"🏭 Цех: {shop}"
    )

    await message.answer(
        confirmation_text,
        reply_markup=confirm_edit_mashines
    )


# Обработчик для кнопки "ДА" добавления станка
@editor_router.callback_query(F.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    new_machine = user_data.get("new_machine")
    shop_number = user_data.get("shop_number")

    machines_data = fs.load_machines_data()
    existing_machines = machines_data.get(f'maschines_{shop_number}', [])

    # Проверка на дублирование имени или инвентарного номера
    if any(machine['name'].lower() == new_machine['name'].lower() or
           machine['inventory_number'] == new_machine['inventory_number']
           for machine in existing_machines):
        logger.warning(
            f"⚠️ Пользователь {callback.from_user.id} подтвердил добавление дублирующего станка в цехе {shop_number}."
        )
        await callback.message.answer(
            f"❌ Станок с таким названием или инвентарным номером уже существует в цехе {shop_number}."
        )
        await callback.answer()  # закрываем спиннер кнопки
        return

    # Добавляем станок
    machines_data[f'maschines_{shop_number}'].append(new_machine)

    try:
        fs.save_machines_data(machines_data)
        logger.info(
            f"✅ Пользователь {callback.from_user.id} добавил станок '{new_machine['name']}' в цех {shop_number}."
        )

        # Сообщение с подтверждением добавления
        await callback.message.edit_text(
            f"✅ Станок успешно добавлен!\n"
            f"🔹 Название: {new_machine['name']}\n"
            f"🆔 Инвентарный номер: {new_machine['inventory_number']}\n"
            f"🏭 Цех: {shop_number}"
        )

    except Exception as e:
        logger.error(
            f"❌ Ошибка при добавлении станка пользователем {callback.from_user.id}: {e}"
        )
        await callback.message.edit_text("❌ Произошла ошибка при сохранении данных.")
        await callback.answer()
        return

    # Завершаем FSM и возвращаем пользователя в главное меню
    await state.clear()
    await state.set_state(Register.main_menu)
    await callback.message.answer(
        "🏠 Возврат в главное меню",
        reply_markup=main
    )
    await callback.answer()  # закрываем спиннер кнопки


# Кнопка отмены добавления станка
@editor_router.callback_query(F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    logger.info(
        f"❌ Пользователь {callback.from_user.id} отменил добавление станка."
    )

    # Сообщение об отмене с эмодзи
    await callback.message.answer("❌ Добавление станка отменено.")
    await callback.message.answer(
        "🛠 Выберите действие:",
        reply_markup=edit_mashines
    )

    # Закрываем спиннер callback
    await callback.answer()


# Кнопка подтверждения удаления станка
@editor_router.callback_query(lambda callback: callback.data == "confirm_delete")
async def confirm_delete(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    machine_to_remove = user_data.get('machine_to_remove')  # Получаем станок для удаления

    if machine_to_remove:
        shop_number = user_data.get('selected_shop').split('-')[0]  # Номер цеха
        machines_data = fs.load_machines_data()  # Загружаем данные
        machines = machines_data.get(f'maschines_{shop_number}', [])

        # Удаляем станок
        machines.remove(machine_to_remove)
        try:
            fs.save_machines_data(machines_data)
            logger.info(
                f"🗑 Пользователь {callback.from_user.id} удалил станок '{machine_to_remove['name']}' из цеха {shop_number}."
            )

            # Подтверждение пользователю
            await callback.message.edit_text(
                f"✅ Станок <b>{machine_to_remove['name']}</b> успешно удалён из цеха {shop_number}.",
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(
                f"❌ Ошибка при удалении станка пользователем {callback.from_user.id}: {e}"
            )
            await callback.message.edit_text("❌ Ошибка при удалении станка.")

        # Завершаем FSM и возвращаем в главное меню
        await state.clear()
        await state.set_state(Register.main_menu)
        await callback.message.answer(
            "🏠 Возврат в главное меню",
            reply_markup=main
        )

    else:
        logger.warning(
            f"⚠️ Пользователь {callback.from_user.id} подтвердил удаление несуществующего станка."
        )
        await callback.message.edit_text("❌ Станок не найден для удаления.")

    # Закрываем спиннер callback
    await callback.answer()


# Кнопка отмены удаления станка
@editor_router.callback_query(lambda callback: callback.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    logger.info(
        f"❌ Пользователь {callback.from_user.id} отменил удаление станка."
    )

    # Сообщение об отмене с эмодзи
    await callback.message.edit_text("❌ Операция удаления станка отменена.")

    # Завершаем FSM
    await state.clear()

    # Отправляем меню действий
    await callback.message.answer(
        "🛠 Выберите действие:",
        reply_markup=edit_mashines
    )

    # Закрываем спиннер callback
    await callback.answer()


# @editor_router.message(F.text == '✅ Добавить контакт')
# async def add_contacts(message: Message, state: FSMContext):
#     await state.clear()
#     await message.answer(
#         "📇 Введите контакт в формате:\n"
#         "ФИО, Телефон, Email, Должность\n\n"
#         "Пример:\n"
#         "Иванов Иван Иванович, +1234567890, example@example.com, директор",
#         reply_markup=ReplyKeyboardRemove())
#     await state.set_state(Register.add_contact)


# # Обработчик для получения контактной информации
# @editor_router.message(Register.add_contact)
# async def receive_contact(message: Message, state: FSMContext):
#     # Регулярные выражения для проверки формата
#     name_pattern = r'^[A-Za-zА-Яа-яЁё\s-]+$'          # ФИО: буквы, пробелы и дефисы
#     phone_pattern = r'^\+?[0-9\s()-]{7,15}$'          # Телефон: +, цифры, пробелы, скобки, дефисы
#     email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'       # Email: стандартный формат
#     position_pattern = r'^[A-Za-zА-Яа-яЁё\s-]+$'      # Должность: буквы, пробелы, дефисы

#     contact_info = message.text.split(", ")
#     contacts = fs.load_contacts()  # Загрузка существующих контактов

#     if len(contact_info) == 4:
#         name, phone, email, position = contact_info

#         # Проверка формата ФИО
#         if not re.match(name_pattern, name):
#             await message.answer("❌ Неправильный формат ФИО. Используйте только буквы и пробелы.")
#             return

#         # Проверка формата телефона
#         if not re.match(phone_pattern, phone):
#             await message.answer("❌ Неправильный формат телефона. Пример: +1234567890")
#             return

#         # Проверка формата email
#         if not re.match(email_pattern, email):
#             await message.answer("❌ Неправильный формат email. Пример: example@example.com")
#             return

#         # Проверка формата должности
#         if not re.match(position_pattern, position):
#             await message.answer("❌ Неправильный формат должности. Используйте только буквы и пробелы.")
#             return

#         # Проверка на дубликаты
#         for contact in contacts:
#             if contact['phone'] == phone or contact['email'] == email:
#                 await message.answer("⚠️ Контакт с таким номером телефона или email уже существует.")
#                 return

#         # Сохраняем контакт во временные данные FSM
#         await state.update_data(contact_info=contact_info)

#         # Подтверждение добавления
#         await message.answer(
#             f"✅ Вы хотите добавить контакт?\n\n"
#             f"👤 ФИО: {name}\n"
#             f"📞 Телефон: {phone}\n"
#             f"✉️ Email: {email}\n"
#             f"💼 Должность: {position}",
#             reply_markup=add_contact
#         )

#     else:
#         await message.answer(
#             "❌ <b>Неправильный формат контакта!</b>\n\n"
#             "📌 Пожалуйста, используйте формат:\n"
#             "ФИО, Телефон, Email, Должность\n\n"
#             "📝 <b>Пример:</b>\n"
#             "Иванов Иван Иванович, +1234567890, example@example.com, директор\n\n"
#             "ℹ️ Или нажмите кнопку ниже, чтобы вернуться в главное меню.",
#             reply_markup=inline_main_menu,
#             parse_mode="HTML"
#         )


# @editor_router.callback_query(F.data == "confirm_yes_contact")
# async def confirm_add_contact(callback_query: CallbackQuery, state: FSMContext):
#     # Получаем данные из FSM
#     data = await state.get_data()
#     contact = data.get('contact_info')
#     name, phone, email, position = contact

#     # Загрузка существующих контактов
#     contacts = fs.load_contacts()

#     # Добавляем новый контакт
#     contacts.append({
#         "name": name,
#         "phone": phone,
#         "email": email,
#         "position": position
#     })
#     fs.save_contacts(contacts)

#     # Логируем успешное добавление
#     logger.info(
#         f"✅ Пользователь {callback_query.from_user.id} добавил контакт: {name}, {phone}, {email}, {position}"
#     )

#     # Очищаем состояние и возвращаем в главное меню
#     await state.clear()
#     await state.set_state(Register.main_menu)

#     # Сообщение о результате с эмодзи
#     await callback_query.message.edit_text(
#         f"✅ Контакт успешно добавлен!\n\n"
#         f"👤 ФИО: {name}\n"
#         f"📞 Телефон: {phone}\n"
#         f"✉️ Email: {email}\n"
#         f"💼 Должность: {position}"
#     )

#     await callback_query.message.answer(
#         "🏠 Возврат в главное меню",
#         reply_markup=main
#     )

#     # Закрываем спиннер callback
#     await callback_query.answer()


# @editor_router.callback_query(F.data == "confirm_no_contact")
# async def cancel_add_contact(callback_query: CallbackQuery, state: FSMContext):
#     logger.info(f"❌ Пользователь {callback_query.from_user.id} отменил добавление контакта.")

#     # Сообщение об отмене с эмодзи
#     await callback_query.message.edit_text("❌ Добавление контакта отменено.")

#     # Отправляем меню действий
#     await callback_query.message.answer(
#         "🛠 Выберите действие (только для администраторов):",
#         reply_markup=edit_mashines
#     )

#     # Очищаем состояние FSM
#     await state.clear()

#     # Закрываем спиннер callback
#     await callback_query.answer()


# @editor_router.message(F.text == '🗑 Удалить контакт')
# async def delete_contact(message: Message, state: FSMContext):
#     await state.set_state(Register.delete_contact)

#     contacts = fs.load_contacts()
#     keyboard = fs.create_keyboard_contact(contacts)

#     if contacts:
#         await message.answer(
#             "🗑 Выберите контакт для удаления:",
#             reply_markup=keyboard
#         )
#     else:
#         await message.answer("ℹ️ Список контактов пуст, удалять нечего!")


# @editor_router.callback_query(F.data.startswith("contact_"))
# async def confirm_delete_contact(callback_query: CallbackQuery, state: FSMContext):
#     contact_id = callback_query.data.split('_')[1]
#     await state.update_data(contacts_id=contact_id)

#     contacts = fs.load_contacts()
#     for contact in contacts:
#         if contact['phone'] == contact_id:
#             await callback_query.message.edit_text(
#                 f"❌ Вы уверены, что хотите удалить контакт:\n\n"
#                 f"👤 {contact['name']}\n"
#                 f"📞 {contact['phone']}\n"
#                 f"✉️ {contact['email']}\n"
#                 f"💼 {contact['position']}",
#                 reply_markup=del_contact
#             )
#             break

#     # Закрываем спиннер callback
#     await callback_query.answer()
#     #         contacts.remove(contacts.index(i))
#     # save_contacts(contacts)


# # Подтверждение удаления контакта
# @editor_router.callback_query(F.data == "confirm_delet_contact")
# async def confirm_deletes_contact(callback_query: CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     contact_id = data.get('contacts_id')
#     contacts = fs.load_contacts()

#     # Удаляем контакт по телефону
#     for i in contacts:
#         if i['phone'] == contact_id:
#             contacts.remove(i)
#             contact_name = i['name']
#             break

#     fs.save_contacts(contacts)
#     logger.info(f"🗑 Пользователь {callback_query.from_user.id} удалил контакт {contact_name} ({contact_id})")

#     # Сообщение об успешном удалении
#     await callback_query.message.edit_text(f"✅ Контакт {contact_name} удалён.")

#     # Отправляем меню действий
#     await callback_query.message.answer(
#         "🛠 Выберите действие (только для администраторов):",
#         reply_markup=edit_mashines
#     )

#     # Очищаем состояние FSM
#     await state.clear()
#     await callback_query.answer()  # Закрываем спиннер


# # Отмена удаления контакта
# @editor_router.callback_query(F.data == "cancel_delet_contacts")
# async def cancel_delete(callback_query: CallbackQuery, state: FSMContext):
#     logger.info(f"❌ Пользователь {callback_query.from_user.id} отменил удаление контакта.")

#     # Сообщение об отмене
#     await callback_query.message.edit_text("❌ Удаление контакта отменено.")

#     # Отправляем меню действий
#     await callback_query.message.answer(
#         "🛠 Выберите действие (только для администраторов):",
#         reply_markup=edit_mashines
#     )

#     # Очищаем состояние FSM
#     await state.clear()
#     await callback_query.answer()  # Закрываем спиннер


# Хендлер нажатия кнопки "Удал. руководство"
@editor_router.message(lambda message: message.text == '🗑 Удал. руководство')
async def delete_manual_prompt(message: Message):
    if not os.path.exists(settings.MANUALS_DIR):
        await message.answer("📚 Руководства отсутствуют.")
        return

    files = sorted(f for f in os.listdir(settings.MANUALS_DIR) if f.lower().endswith(('.pdf', '.txt')))
    if not files:
        await message.answer("📚 Руководства отсутствуют.")
        return

    keyboard = fs.delete_manuals_keyboard(files)
    await message.answer(
        "🗑 <b>Удаление руководства</b>\n\n"
        "⬇️ Выберите руководство из списка ниже для удаления",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


    
@editor_router.callback_query(lambda c: c.data.startswith("manual_delete:"))
async def manual_delete_confirm(callback: CallbackQuery):
    index = int(callback.data.split(":")[1])
    files = sorted(f for f in os.listdir(settings.MANUALS_DIR) if f.lower().endswith(('.pdf', '.txt')))
    filename = files[index]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"manual_delete_yes:{index}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="manual_delete_cancel")
        ]
    ])

    await callback.message.edit_text(
        f"⚠️ <b>Подтвердите удаление</b>\n\n"
        f"Вы действительно хотите удалить руководство:\n"
        f"📄 <b>{filename}</b>?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

    
@editor_router.callback_query(lambda c: c.data.startswith("manual_delete_yes:"))
async def delete_manual_execute(callback: CallbackQuery):
    index = int(callback.data.split(":", 1)[1])  # получаем индекс файла
    files = sorted(f for f in os.listdir(settings.MANUALS_DIR) if f.lower().endswith(('.pdf', '.txt')))
    
    if index < 0 or index >= len(files):
        await callback.message.edit_text("❌ Файл не найден.")
        await callback.answer()
        return

    filename = files[index]
    filepath = os.path.join(settings.MANUALS_DIR, filename)

    try:
        os.remove(filepath)
        await callback.message.edit_text(
            f"✅ <b>Руководство удалено</b>\n\n"
            f"📄 <b>{filename}</b> успешно удалено из базы.",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при удалении файла:\n<code>{e}</code>", parse_mode="HTML")
    await callback.answer()


@editor_router.callback_query(lambda c: c.data == "manual_delete_cancel")
async def delete_manual_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ <b>Удаление отменено</b>\n\n", parse_mode="HTML")
    await callback.answer()
    
    
    
@editor_router.message(lambda message: message.text == '✅ Доб. руководство')
async def add_manual_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📂 <b>Пожалуйста, отправьте файл руководства.</b>\n\n"
        f"⚖️ <b>Максимальный размер файла:</b> {settings.MAX_FILE_SIZE_MB} МБ\n"
        f"📝 <b>Имя файла не должно превышать</b> {settings.MAX_FILENAME_LENGTH} символов.\n"
        "ℹ️ <i>Файл должен быть только в формате PDF или TXT !</i>",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(Register.waiting_file)
    
@editor_router.message(Register.waiting_file, F.document)
async def receive_manual(message: Message, state: FSMContext):
    document = message.document
    filename = document.file_name
    size_mb = document.file_size / (1024 * 1024)

    # Проверки
    if not filename.lower().endswith(settings.ALLOWED_EXTENSIONS):
        await message.answer("❌ <b>Недопустимый формат файла!</b> Разрешены только <b>PDF</b> и <b>TXT</b>.", parse_mode="HTML")
        return

    if size_mb > settings.MAX_FILE_SIZE_MB:
        await message.answer(f"❌ <b>Файл слишком большой ({size_mb:.1f} МБ)!</b> Максимальный размер — {settings.MAX_FILE_SIZE_MB} МБ.", parse_mode="HTML")
        return

    if len(Path(filename).stem) > settings.MAX_FILENAME_LENGTH:
        await message.answer(f"❌ <b>Имя файла слишком длинное!</b> Максимум {settings.MAX_FILENAME_LENGTH} символов без расширения.", parse_mode="HTML")
        return

    # Сохраняем временно информацию о файле в FSM
    await state.update_data(file=document)
    await state.update_data(filename=filename)

    # Подтверждение
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="manual_add_yes"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="manual_add_cancel")
    ]])

    await message.answer(
        f"📄 <b>Вы хотите добавить руководство:</b> <i>{filename}</i>?\n\n"
        "⚠️ Убедитесь, что всё верно, перед подтверждением.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(Register.confirm_upload)
    
    
@editor_router.callback_query(lambda c: c.data == "manual_add_yes", Register.confirm_upload)
async def manual_add_execute(callback: CallbackQuery, state: FSMContext):

    user_id = callback.from_user.id
    user_name = callback.from_user.full_name

    data = await state.get_data()
    document = data.get("file")
    filename = data.get("filename")

    if not document:
        await callback.message.edit_text(
            "❌ Файл не найден. Пожалуйста, отправьте его снова.",
            reply_markup=inline_main_menu
        )
        await state.clear()
        return

    filepath = os.path.join(settings.MANUALS_DIR, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if os.path.exists(filepath):
        await callback.message.edit_text(
            f"⚠️ <b>Файл {filename}</b> уже существует!\n"
            "❌ Загрузка отменена, выберите другой файл или выйдите в главное меню",
            parse_mode="HTML",
            reply_markup=inline_main_menu
        )
        await state.set_state(Register.waiting_file)
        return

    size_mb = document.file_size / (1024 * 1024)
    if size_mb > 45:
        await callback.message.edit_text(
            f"❌ Файл слишком большой ({size_mb:.1f} МБ). "
            "Telegram не позволит загрузить файл больше 50 МБ через бота.",
            reply_markup=inline_main_menu
        )
        logger.warning(f"Файл {filename} от пользователя {user_id} ({user_name}) слишком большой для загрузки")
        await state.clear()
        return

    loading_msg = await callback.message.edit_text(
        f"⏳ <b>Загрузка файла:</b> <i>{filename}</i>\n"
        f"📊 [{'░'*20}]\n"
        f"📄 <b>Загружено:</b> 0.00/{size_mb:.2f} МБ (0%)\n"
        f"⚡ <b>Скорость:</b> 0 МБ/с",
        parse_mode="HTML"
    )

    try:
        tg_file = await callback.bot.get_file(document.file_id)
        url = f"https://api.telegram.org/file/bot{callback.bot.token}/{tg_file.file_path}"

        chunk_size = 1024 * 1024  # 1 MB
        downloaded = 0
        last_percent = -1
        start_time = time.time()
        BAR_LENGTH = 12

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(url) as resp:
                async with aiofiles.open(filepath, "wb") as f:
                    async for chunk in resp.content.iter_chunked(chunk_size):
                        await f.write(chunk)
                        downloaded += len(chunk)

                        percent = int(downloaded / document.file_size * 100)
                        elapsed = max(time.time() - start_time, 0.001)
                        speed = downloaded / (1024*1024) / elapsed
                        downloaded_mb = downloaded / (1024*1024)

                        if percent != last_percent:
                            filled_length = int(BAR_LENGTH * percent // 100)
                            bar = "█" * filled_length + "░" * (BAR_LENGTH - filled_length)

                            await loading_msg.edit_text(
                                f"⏳ <b>Загрузка файла:</b> <i>{filename}</i>\n"
                                f"📊 [{bar}] {percent}%\n"
                                f"📄 <b>Загружено:</b> {downloaded_mb:.2f}/{size_mb:.2f} МБ\n"
                                f"⚡ <b>Скорость:</b> {speed:.2f} МБ/с",
                                parse_mode="HTML"
                            )
                            last_percent = percent

        await loading_msg.edit_text(
            f"✅ <b>Руководство:</b> <i>{filename}</i> <b>успешно добавлено!</b> 🎉\n\n"
            "📂 Оно теперь доступно для использования.",
            parse_mode="HTML",
            reply_markup=inline_main_menu
        )

        logger.info(f"Файл {filename} успешно загружен пользователем {user_id} ({user_name})")

    except Exception as e:
        logger.error(f"Ошибка при загрузке файла {filename} пользователем {user_id} ({user_name}): {e}")
        await loading_msg.edit_text(
            f"❌ Произошла ошибка при загрузке файла:\n<i>{e}</i>",
            parse_mode="HTML",
            reply_markup=inline_main_menu
        )

    await state.clear()



# Отмена
@editor_router.callback_query(lambda c: c.data == "manual_add_cancel", Register.confirm_upload)
async def manual_add_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ <b>Добавление руководства отменено!</b>", parse_mode="HTML", reply_markup=inline_main_menu)
    await state.clear()
