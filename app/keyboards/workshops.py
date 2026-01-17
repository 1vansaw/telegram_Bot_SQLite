from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import app.utils.funcs as fs

# Кнопки цеха
workshops = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🔧 1 цех', callback_data='1-shop'),
     InlineKeyboardButton(text='⚙️ 2 цех', callback_data='2-shop'),
     InlineKeyboardButton(text='🏭 3 цех', callback_data='3-shop')],
    [InlineKeyboardButton(text='📦 11 цех', callback_data='11-shop'),
     InlineKeyboardButton(text='🔬 15 цех', callback_data='15-shop'),
     InlineKeyboardButton(text='🔥 17 цех', callback_data='17-shop')],
    [InlineKeyboardButton(text='💡 20 цех', callback_data='20-shop'),
     InlineKeyboardButton(text='🛠️ 26 цех', callback_data='26-shop'),
     InlineKeyboardButton(text='⚙️ КМТ', callback_data='kmt-shop')],
    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]])




# Загружаем данные о станках из JSON файла
machines_data = fs.load_machines_data()
# Создаем клавиатуры для каждого цеха
shops_1 = fs.create_keyboard(fs.load_machines_data()['maschines_1'])
shops_2 = fs.create_keyboard(fs.load_machines_data()['maschines_2'])
shops_3 = fs.create_keyboard(fs.load_machines_data()['maschines_3'])
shops_11 = fs.create_keyboard(fs.load_machines_data()['maschines_11'])
shops_15 = fs.create_keyboard(fs.load_machines_data()['maschines_15'])
shops_17 = fs.create_keyboard(fs.load_machines_data()['maschines_17'])
shops_20 = fs.create_keyboard(fs.load_machines_data()['maschines_20'])
shops_26 = fs.create_keyboard(fs.load_machines_data()['maschines_26'])
shops_kmt = fs.create_keyboard(fs.load_machines_data()['maschines_kmt'])