from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='✅ Добавить админа'),
         KeyboardButton(text='❌ Удалить админа')],
        [KeyboardButton(text='👥 Пользователи'),
         KeyboardButton(text='📢 Рассылка')],
        [KeyboardButton(text='📄 Посмотреть логи'),
         KeyboardButton(text='💾 Резервная копия БД')],
        [KeyboardButton(text='🕒 Автокопирование БД'),
        KeyboardButton(text='🔄 Восстановить БД из копии')],
        [KeyboardButton(text='↩️ В главное меню')]
    ],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие'
)


auto_backup_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='🔁 Раз в день'),
        KeyboardButton(text='📅 Раз в неделю')],
        [KeyboardButton(text='🗓 Раз в месяц'),
        KeyboardButton(text='❌ Отключить автокопирование')],
        [KeyboardButton(text='🔔 Включить/выключить уведомления')],
        [KeyboardButton(text='↩️ В админ меню')]],
    resize_keyboard=True,
    input_field_placeholder='Выберите интервал'
)


confirm_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='✔ Да'), KeyboardButton(text='✖ Отмена')]
    ],
    resize_keyboard=True
)

source_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💾 Локальная копия", callback_data="restore_source_local")],
    [InlineKeyboardButton(text="☁️ Яндекс Диск", callback_data="restore_source_yadisk")],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="restore_cancel")]
])

# Создаем клавиатуру с кнопками "Подтвердить" и "Назад"
markup = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_calendar"),
    InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_date")]])


clear_chat = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='✅ Да'), KeyboardButton(
    text='❌ Нет')]], resize_keyboard=True, input_field_placeholder='Выберите пункт')


del_admins = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Подтвердить",
                         callback_data="confirm_deletes_admins"),
    InlineKeyboardButton(text='❌ Отмена', callback_data="cancel_deletes_admins")]])


confirm_edit_admins = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Подтвердить",
                         callback_data="confirm_yes_admins"),
    InlineKeyboardButton(text='❌ Отмена', callback_data="confirm_no_admins")]])

# --- Кнопки подтверждения для создания бэкапа ---
backup_db_confirm_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Создать", callback_data="backup_db_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="backup_db_cancel")
        ]
    ]
)
