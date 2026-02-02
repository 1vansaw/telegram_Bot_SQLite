from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton)


main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='📝 Добавить запись'),
         KeyboardButton(text='📜 История за сутки')],

        [KeyboardButton(text='✏️ Изменить запись'),
         KeyboardButton(text='🔍 Поиск записи')],

        [KeyboardButton(text='🛠️ Редактор'),
         KeyboardButton(text='👑 Админ меню')],

        [KeyboardButton(text='📚 Руководства'),
         KeyboardButton(text='⚡ Электросхемы')]
    ],
    resize_keyboard=True,
    input_field_placeholder='Выберите пункт'
)

inline_main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ]
)
