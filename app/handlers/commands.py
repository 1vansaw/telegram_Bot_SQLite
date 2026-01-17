from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from app.keyboards import main
from aiogram.types import Message
from app.states import Register
import app.utils.funcs as fs
from app.config import settings
import logging


commands_router = Router()  # локальный роутер для команд
logger = logging.getLogger(__name__)


# обработка команды start
@commands_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Register.main_menu)

    data = fs.load_access_data()
    user_id = message.from_user.id
    role = fs.get_user_role(user_id, data)

    if role is None:
        role_text = (
            "⛔ **Доступ запрещен**\n\n"
            "➖ Функции вам недоступны\n"
            "➖ Обратитесь к администратору для получения прав"
        )
        foo_text = ""
    else:
        role_text = f"🛡 **Ваш уровень доступа:**\n{role}"
        foo_text = "📌 Выберите действие в меню ниже"

    text = (
        f"👋 **Добро пожаловать, {message.from_user.full_name}!**\n\n"
        f"{role_text}\n\n"
        f"{foo_text}"
    )

    await message.answer(
        text,
        reply_markup=main,
        parse_mode="Markdown"
    )

    logger.info(
        f"Пользователь {user_id} ({message.from_user.full_name}) запустил бота."
    )




@commands_router.message(Command('check_access'))
async def get_access(message: Message, state: FSMContext):
    await state.clear()
    data = fs.load_access_data()
    user_id = message.from_user.id  # Получаем ID пользователя
    role = fs.get_user_role(user_id, data)
    if role == "👑 Главный администратор!":
        role_display = "👑 Главный администратор!"
        note = "Все функции доступны ✅"
    elif role == "🛠 Администратор!":
        role_display = "🛠 Администратор!"
        note = "Доступны все функции кроме админ-меню ⚠️"
    elif role == "👥 Пользователь":
        role_display = "👥 Пользователь"
        note = "Доступны только базовые функции ⚠️"
    else:
        role_display = "⛔ Доступ отсутствует"
        note = "Свяжитесь с администратором для получения прав ❗"

    await message.answer(
        f"👤 Пользователь: {message.from_user.full_name}\n"
        f"🆔 Ваш ID: {user_id}\n"
        f"🔒 Уровень доступа: {role_display}\n\n"
        f"{note}"
    )


# @commands_router.message(Command('help'))
# async def cmd_help(message: Message, state: FSMContext):
#     await state.clear()
#     text = """В данном боте существует 3 уровня доступа:
# - 🧑‍💻 <strong>Пользователь</strong>: Имеет доступ к добавлению записей, просмотру контактов и просмотру истории.
# - 🛠️ <strong>Администратор</strong>: Пользователь + доступ к меню 'Редактор' (за исключением добавления/удаления админа и данных о пользователях), просмотр файла.
# - 👑 <strong>Главный администратор</strong>: Имеет доступ ко всем функциям."""

#     await message.answer(text, parse_mode='HTML')
#     await message.answer(f'Прочитайте [руководство]({settings.HELP}), там ответы на большую часть ваших вопросов.',
#                          disable_web_page_preview=True, parse_mode='Markdown')


@commands_router.message(Command('secret'))
async def send_photo(message: Message):
    await message.reply_photo(photo=settings.PHOTO_SECRET, caption="Это невозмутимый воин")


# @commands_router.message(Command('id'))
# async def send_user_id(message: Message, state: FSMContext):
#     await state.clear()
#     user_id = message.from_user.id
#     full_name = message.from_user.full_name

#     await message.answer(
#         f"👤 **Пользователь:** {full_name}\n"
#         f"🆔 **Ваш ID:** {user_id}",
#         parse_mode="Markdown"
#     )


# @router.message(Command("url"))
# async def send_url(message: Message):
#     data = load_access_data()
#     user_id = message.from_user.id  # Получаем ID пользователя
#     role = get_user_role(user_id, data)
#     if role in ["👑 Главный администратор!", "🛠 Администратор!"]:
#         # Логика для авторизованных пользователей
#         keyboard = InlineKeyboardMarkup(
#             inline_keyboard=[[InlineKeyboardButton(
#                 text="Перейти по ссылке", url=cfg.LIST_URL)]])
#         await message.answer("Нажмите на кнопку ниже, чтобы перейти по ссылке:", reply_markup=keyboard)
#     else:
#         await message.answer('⛔ У вас нет доступа')


# Обработка нажатия кнопки "Контакты"
@commands_router.message(Command('contacts'))
async def show_contacts(message: Message, state: FSMContext):
    await state.clear()
    data = fs.load_access_data()  # Загружаем данные о пользователях
    user_id = message.from_user.id  # Получаем ID пользователя
    # Определяем роль пользователя
    role = fs.get_user_role(user_id, data)
    if role in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
        contacts_info = "Вот наши контакты:\n"
        contacts = fs.load_contacts()
        for contact in contacts:
            # Форматируем строку для вывода
            contacts_info += f"👤 {contact['name']}\n💼 Должность: {contact['position']}\n📞 Телефон: {contact['phone']}\n✉️ Email: {contact['email']}\n"
            contacts_info += "--------------------------------------\n"  # Добавляем разделитель
        # Удаляем последний разделитель
        contacts_info = contacts_info.rstrip("---------\n")
        await message.answer(contacts_info)
    else:
        await message.answer("⛔ У вас нет доступа.")
        

@commands_router.message(Command("upload_excel"))
async def upload_excel_command(message: Message, state: FSMContext):
    """
    Хендлер команды /upload_excel.
    Создаёт Excel из базы и отправляет пользователю.
    Доступ только для администратора и главного администратора.
    """
    await state.clear()
    
    data = fs.load_access_data()  # Загружаем данные о пользователях
    user_id = message.from_user.id
    role = fs.get_user_role(user_id, data)

    if role not in ["👑 Главный администратор!", "🛠 Администратор!"]:
        await message.answer("⛔ У вас нет доступа для экспорта данных.")
        return

    # --- Отправляем сообщение о прогрессе ---
    progress_msg = await message.answer("⏳ Формирую файл для экспорта, подождите...")

    try:
        await fs.export_to_excel_and_send(message)  # Excel или ZIP отправляется пользователю

        # --- После отправки редактируем сообщение ---
        await progress_msg.edit_text("✅ Файл успешно сформирован и отправлен!")

    except Exception as e:
        await progress_msg.edit_text(f"❌ Ошибка при формировании файла: {e}")
        logging.error(f"Ошибка при выгрузке Excel: {e}")