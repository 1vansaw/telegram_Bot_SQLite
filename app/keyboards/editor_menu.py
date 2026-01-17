from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton)




edit_mashines = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='✅ Добавить станок'),
         KeyboardButton(text='🗑 Удалить станок')],
        [KeyboardButton(text='✅ Добавить контакт'),
         KeyboardButton(text='🗑 Удалить контакт')],
        [KeyboardButton(text='✅ Доб.пользователя'),
         KeyboardButton(text='🗑 Удал. пользователя')],
        [KeyboardButton(text='✅ Доб. руководство'),
         KeyboardButton(text='🗑 Удал. руководство')], 
        [KeyboardButton(text='↩️ В главное меню')]
    ],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие'
)


del_contact = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Подтвердить",
                         callback_data="confirm_delet_contact"),
    InlineKeyboardButton(text='❌ Отмена', callback_data="cancel_delet_contacts")]])

del_users = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Подтвердить",
                         callback_data="confirm_delete_users"),
    InlineKeyboardButton(text='❌ Отмена', callback_data="cancel_delete_users")]])


del_machines = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_delete"),
    InlineKeyboardButton(text='❌ Отмена', callback_data="cancel_delete")]])


confirm_edit_mashines = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_yes"),
    InlineKeyboardButton(text='❌ Отмена', callback_data="confirm_no")]])


confirm_edit_users = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Подтвердить",
                         callback_data="confirm_yes_users"),
    InlineKeyboardButton(text='❌ Отмена', callback_data="confirm_no_users")]])


add_contact = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Подтвердить",
                         callback_data="confirm_yes_contact"),
    InlineKeyboardButton(text='❌ Отмена', callback_data="confirm_no_contact")]])


personal_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='⚡ Электрики', callback_data='electric')],
    [InlineKeyboardButton(text='🔧 Механики', callback_data='mechanic')],
    [InlineKeyboardButton(text='💻 Электроники', callback_data='electron')],
    [InlineKeyboardButton(text="↩️ Назад", callback_data="back_category")]
])