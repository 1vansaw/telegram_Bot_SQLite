from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Кнопки цехов (электросхемы)
workshops_schemes = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='🔧 1 цех', callback_data='schemes_shop:1'),
        InlineKeyboardButton(text='⚙️ 2 цех', callback_data='schemes_shop:2'),
        InlineKeyboardButton(text='🏭 3 цех', callback_data='schemes_shop:3')
    ],
    [
        InlineKeyboardButton(text='📦 11 цех', callback_data='schemes_shop:11'),
        InlineKeyboardButton(text='🔬 15 цех', callback_data='schemes_shop:15'),
        InlineKeyboardButton(text='🔥 17 цех', callback_data='schemes_shop:17')
    ],
    [
        InlineKeyboardButton(text='💡 20 цех', callback_data='schemes_shop:20'),
        InlineKeyboardButton(text='🛠️ 26 цех', callback_data='schemes_shop:26'),
        InlineKeyboardButton(text='⚙️ КМТ', callback_data='schemes_shop:kmt')
    ],
    [
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    ]
])
