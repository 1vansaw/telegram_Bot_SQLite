import json
import logging
from app.config import settings
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, Message, CallbackQuery
import asyncio
from datetime import datetime
import time
import shutil
import re
import aiosqlite
from reportlab.lib.pagesizes import A4, landscape
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from collections import deque
from aiogram.fsm.context import FSMContext
from zipfile import ZipFile
from pathlib import Path
from math import ceil
import aiohttp
import aiofiles
import pytz




logger = logging.getLogger(__name__)


# Регистрируем шрифт DejaVu Sans (предполагаем, что файл DejaVuSans.ttf в корне проекта)
pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))

# Создаём стиль для параграфов с поддержкой кириллицы (для ячеек таблицы)
styles = getSampleStyleSheet()
normal_style = ParagraphStyle(
    'Normal',
    parent=styles['Normal'],
    fontName='DejaVuSans',  # Используем зарегистрированный шрифт
    fontSize=7,  # Уменьшаем шрифт для компактности
    leading=8,  # Межстрочный интервал
)

# Создаём стиль для заголовка (центрированный, больший шрифт, с отступами)
title_style = ParagraphStyle(
    'Title',
    parent=styles['Title'],  # Или 'Normal', если 'Title' не определён
    # Можно заменить на 'DejaVuSans-Bold' если есть файл DejaVuSans-Bold.ttf
    fontName='DejaVuSans',
    fontSize=12,  # Увеличенный шрифт для заголовка
    alignment=1,  # 1 = центр (0 = лево, 2 = право)
    spaceAfter=20,  # Отступ после заголовка (в pt, для разделения от таблицы)
    spaceBefore=0,  # Отступ перед заголовком (0 = без отступа сверху)
    textColor=colors.red,  # Цвет текста
)


def load_auto_backup_settings():
    if not os.path.exists(settings.SETTINGS_FILE):
        return {"enabled": False, "interval": "off", "last_backup": 0, "notify": True}  # по умолчанию уведомления включены
    with open(settings.SETTINGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if "notify" not in data:  # для старых настроек
            data["notify"] = True
        return data


def save_auto_backup_settings(setting):
    with open(settings.SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(setting, f, ensure_ascii=False, indent=4)


# Функция проверки правильности введенного ID
def validate_user_id(user_id: str) -> tuple[bool, str]:
    """Валидирует ID пользователя и возвращает (валидно ли, сообщение)."""
    user_id = user_id.strip()
    if not user_id:
        return False, "Поле не может быть пустым. Пожалуйста, введите корректное название."
    if not user_id.isdigit():
        return False, "ID пользователя может состоять только из цифр. Пожалуйста, введите корректное название."
    if len(user_id) < 9 or len(user_id) > 11:
        return False, "ID пользователя должен содержать от 9 до 11 цифр. Пожалуйста, введите корректный ID."
    if user_id.startswith("0"):
        return False, "ID пользователя не может начинаться с нуля. Введите корректный ID."
    return True, ""

# Функция для загрузки данных из JSON файла


def load_access_data():
    """Загружает данные пользователей из JSON-файла или создает структуру, если файл пуст/не существует."""
    try:
        with open(settings.FILE_PATH_ACCESS, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(
            f"Файл {settings.FILE_PATH_ACCESS} не найден или поврежден, создаем новый: {e}")
        return {
            "main_admins": [],
            "admins": [],
            "users": []
        }

# Функция для сохранения данных в JSON файл


def save_access_data(data):
    try:
        with open(settings.FILE_PATH_ACCESS, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        logger.info("Данные о пользователях успешно сохранены.")
    except (IOError, OSError) as e:
        logger.error(
            f"Ошибка при записи в файл {settings.FILE_PATH_ACCESS}: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при сериализации данных в JSON: {e}")
    except Exception as e:
        logger.error(
            f"Произошла непредвиденная ошибка при сохранении данных: {e}")

# Функция для загрузки данных из файла


def load_machines_data():
    if os.path.exists(settings.FILE_PATH):
        with open(settings.FILE_PATH, 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        logger.warning(f"Файл {settings.FILE_PATH} не найден, создаем новый.")
        return {
            "maschines_1": [],
            "maschines_2": [],
            "maschines_3": [],
            "maschines_11": [],
            "maschines_15": [],
            "maschines_17": [],
            "maschines_20": [],
            "maschines_26": [],
            "maschines_kmt": [],
        }

# Функция для сохранения данных в файл


def save_machines_data(data):
    try:
        with open(settings.FILE_PATH, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        logger.info("Данные о станках успешно сохранены.")
    except (IOError, OSError) as e:
        logger.error(f"Ошибка при записи в файл {settings.FILE_PATH}: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при сериализации данных в JSON: {e}")
    except Exception as e:
        logger.error(
            f"Произошла непредвиденная ошибка при сохранении данных: {e}")

# функция определения уровня доступа


def get_user_role(user_id, data):
    if user_id in data['main_admins']:
        return "👑 Главный администратор!"
    elif user_id in data['admins']:
        return "🛠 Администратор!"
    elif user_id in data['users']:
        return "👥 Пользователь"
    return None


def delete_user_from_access(user_id):
    """Удаляет пользователя по ID, если он есть в списке, и обновляет JSON-файл."""
    access_data = load_access_data()
    if user_id in access_data["users"]:
        access_data["users"].remove(user_id)
        try:
            save_access_data(access_data)
            logger.info(
                f"Пользователь {user_id} удален из списка пользователей")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
            return False
    logger.warning(f"Попытка удалить несуществующего пользователя {user_id}.")
    return False


def generate_users_keyboard():
    """Создает клавиатуру с ID пользователей."""
    access_data = load_access_data()
    users = access_data.get("users", [])
    if not users:
        logger.info("Список пользователей пуст; клавиатура не создана.")
        return None  # Если список пуст, клавиатуру не создаем
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for user in users:
        row.append(InlineKeyboardButton(
            text=str(user), callback_data=f"deletes_{user}"))
        if len(row) == 3:  # 3 кнопки в ряд
            keyboard.inline_keyboard.append(row)
            row = []
    if row:  # Добавляем оставшиеся кнопки, если их меньше 3
        keyboard.inline_keyboard.append(row)
    return keyboard


def delete_admins_from_access(user_id):
    """Удаляет пользователя по ID, если он есть в списке, и обновляет JSON-файл."""
    access_data = load_access_data()
    if user_id in access_data["admins"]:
        access_data["admins"].remove(user_id)  # Удаляем ID
        try:
            save_access_data(access_data)  # Сохраняем обновленный файл
            logger.info(
                f"Администратор {user_id} удален из списка администраторов.")
            return True  # Успешное удаление
        except Exception as e:
            logger.error(f"Ошибка при удалении администратора {user_id}: {e}")
            return False
    logger.warning(
        f"Попытка удалить несуществующего администратора {user_id}.")
    return False


async def init_db():
    """Инициализация базы данных и создание таблицы tasks со всеми колонками."""
    async with aiosqlite.connect(settings.DB_FILE) as db:
        # Создание таблицы со всеми колонками
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                workers TEXT NOT NULL,
                machine TEXT NOT NULL,
                shift TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                work_description TEXT,
                work_solution TEXT,
                fault_status TEXT,
                duration TEXT,
                inventory_number TEXT
            )
        ''')
        await db.commit()
    logger.info("База данных инициализирована.")
    
    
def cleanup_old_files():
    """Удаляет файлы из TEMP_DIR старше 24 часов."""
    if not os.path.exists(settings.TEMP_DIR):
        return

    now = time.time()
    for filename in os.listdir(settings.TEMP_DIR):
        if filename.endswith('.pdf'):
            file_path = os.path.join(settings.TEMP_DIR, filename)
            file_time = os.path.getctime(file_path)
            if now - file_time > 86400:
                os.remove(file_path)
                logger.info(f'Файл {filename} удален.')
      
      
                
# async def auto_backup_loop():
#     while True:
#         setting = load_auto_backup_settings()

#         if setting["enabled"]:
#             now = time.time()
#             interval_seconds = settings.INTERVAL_SECONDS[setting["interval"]]

#             if now - setting["last_backup"] >= interval_seconds:
#                 try:
#                     filename = await create_backup()
#                     setting["last_backup"] = now
#                     save_auto_backup_settings(setting)
#                     logger.info(f"Автокопирование: создана копия {filename}")
#                 except Exception as e:
#                     logger.error(f"Ошибка автокопирования: {e}")

#         await asyncio.sleep(10)


async def auto_backup_loop(bot):
    while True:
        setting = load_auto_backup_settings()

        if setting["enabled"]:
            now = time.time()
            interval_seconds = settings.INTERVAL_SECONDS[setting["interval"]]

            if now - setting["last_backup"] >= interval_seconds:
                try:
                    filename = await create_backup()

                    try:
                        disk_msg = await upload_to_yadisk(
                            os.path.join(settings.DIR_DB, filename),
                            f"/Backups/{filename}"
                        )
                        yadisk_count = await count_yadisk_backups()
                    except Exception as e:
                        logger.error(f"Ошибка загрузки на Яндекс.Диск: {e}")
                        disk_msg = "⚠️ Не удалось загрузить на Яндекс.Диск."
                        yadisk_count = 0

                    setting["last_backup"] = now
                    save_auto_backup_settings(setting)

                    access_data = load_access_data()
                    main_admins = access_data.get("main_admins", [])
                    moscow_tz = pytz.timezone("Europe/Moscow")
                    moscow_time = datetime.now(tz=moscow_tz).strftime('%d.%m.%Y %H:%M')

                    logger.info(f"Автокопирование: создана локальная копия {filename} | {disk_msg}")

                    if setting.get("notify_admin", True) and main_admins:
                        try:
                            await bot.send_message(
                                main_admins[0],
                                f"🟢 Автокопирование завершено!\n\n"
                                f"📄 Файл: `{filename}`\n"
                                f"💾 Локальных копий: {len([f for f in os.listdir(settings.DIR_DB) if f.startswith('Копия_БД_') and f.endswith('.db')])}/5\n"
                                f"☁️ Копий на Яндекс.Диске: {yadisk_count}/5\n"
                                f"{disk_msg}\n"
                                f"🕒 Дата создания: {moscow_time}",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"Не удалось отправить уведомление админу: {e}")

                except Exception as e:
                    logger.error(f"Ошибка автокопирования: {e}")

        await asyncio.sleep(10)




def generate_admins_keyboard():
    """Создает клавиатуру с ID пользователей."""
    access_data = load_access_data()
    admins = access_data.get("admins", [])

    if not admins:
        logger.info("Список администраторов пуст; клавиатура не создана.")
        return None  # Если список пуст, клавиатуру не создаем

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for admin in admins:
        row.append(InlineKeyboardButton(
            text=str(admin), callback_data=f"deletes_{admin}"))
        if len(row) == 3:  # 3 кнопки в ряд
            keyboard.inline_keyboard.append(row)
            row = []
    if row:  # Добавляем оставшиеся
        keyboard.inline_keyboard.append(row)
    return keyboard


# async def create_backup():
#     if not os.path.exists(settings.DB_FILE):
#         raise FileNotFoundError("Исходная база данных не найдена")

#     if not os.path.exists(settings.DIR_DB):
#         os.makedirs(settings.DIR_DB)

#     # Ротация
#     backup_files = [
#         f for f in os.listdir(settings.DIR_DB)
#         if f.startswith('Копия_БД_') and f.endswith('.db')
#     ]

#     if len(backup_files) >= 5:
#         backup_files.sort(key=lambda x: os.path.getctime(
#             os.path.join(settings.DIR_DB, x)))
#         os.remove(os.path.join(settings.DIR_DB, backup_files[0]))

#     timestamp = datetime.now().strftime("%d.%m.%Y_%H-%M-%S")
#     backup_filename = f"Копия_БД_{timestamp}.db"
#     backup_path = os.path.join(settings.DIR_DB, backup_filename)
#     shutil.copy2(settings.DB_FILE, backup_path)
#     return backup_filename


async def create_backup():
    if not os.path.exists(settings.DB_FILE):
        raise FileNotFoundError("Исходная база данных не найдена")

    os.makedirs(settings.DIR_DB, exist_ok=True)
    timestamp = datetime.now().strftime("%d.%m.%Y_%H-%M-%S")
    backup_filename = f"Копия_БД_{timestamp}.db"
    backup_path = os.path.join(settings.DIR_DB, backup_filename)
    shutil.copy2(settings.DB_FILE, backup_path)
    
    # Ротация
    backup_files = [
        f for f in os.listdir(settings.DIR_DB)
        if f.startswith('Копия_БД_') and f.endswith('.db')
    ]
    if len(backup_files) > 5:
        backup_files.sort(key=lambda x: os.path.getctime(os.path.join(settings.DIR_DB, x)))
        while len(backup_files) > 5:
            os.remove(os.path.join(settings.DIR_DB, backup_files[0]))
            backup_files.pop(0)

    return backup_filename




# Функция выполнения восстановления


async def perform_database_restore(file_path: str) -> bool:
    try:
        # Проверяем существование файла резервной копии
        if not os.path.exists(file_path):
            logger.error(f"Файл резервной копии не найден: {file_path}")
            return False

        # Восстанавливаем из выбранной копии
        shutil.copy2(file_path, settings.DB_FILE)
        return True
    except Exception as e:
        logger.error(f"Ошибка восстановления БД: {e}")
        return False


def normalize(s: str) -> str:
    if s is None:
        return ""
    s = re.sub(r'[^0-9A-Za-zА-Яа-я]', '', s)
    return s.lower()


def save_drive_files(files_list):
    """Сохраняет список файлов в JSON."""
    with open(settings.DRIVE_FILES_PATH, "w", encoding="utf-8") as file:
        json.dump(files_list, file, ensure_ascii=False, indent=4)


async def register_normalize_function(db: aiosqlite.Connection):
    await db.create_function("normalize", 1, normalize)


async def search_data(phrase: str):
    async with aiosqlite.connect(settings.DB_FILE) as db:
        await register_normalize_function(db)

        normalized = normalize(phrase)
        like = f"%{normalized}%"

        query = """
        SELECT id, date, workers, work_description, work_solution, fault_status,
               start_time, end_time, duration, shift, machine, inventory_number
        FROM tasks
        WHERE normalize(date)             LIKE ?
           OR normalize(workers)          LIKE ?
           OR normalize(work_description) LIKE ?
           OR normalize(work_solution)    LIKE ?
           OR normalize(fault_status)     LIKE ?
           OR normalize(machine)          LIKE ?
           OR normalize(inventory_number) LIKE ?
           OR normalize(shift)            LIKE ?
        ORDER BY id DESC
        """

        params = (like, like, like, like, like, like, like, like)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]





async def add_data(
    user_id: int,
    date: str,
    workers: str,
    work_description: str,
    work_solution: str,
    fault_status: str,
    start_time: str,
    end_time: str,
    duration: str,
    shift: str,
    machine: str,
    inventory_number: str = None
):
    """Добавление новой задачи в БД с расширенными полями."""
    async with aiosqlite.connect(settings.DB_FILE) as db:
        await db.execute('''
            INSERT INTO tasks (
                user_id, date, workers, work_description, work_solution, fault_status,
                start_time, end_time, duration, shift, machine, inventory_number
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, date, workers, work_description, work_solution, fault_status,
            start_time, end_time, duration, shift, machine, inventory_number
        ))
        await db.commit()
    logger.info(f"Задача добавлена для пользователя {user_id}.")


async def get_today_history():
    """Получение истории задач за последние 24 часа и форматирование в строку."""

    async with aiosqlite.connect(settings.DB_FILE) as db:
        cursor = await db.execute('''
            SELECT id, date, workers, work_description, work_solution, fault_status, start_time, end_time, duration, shift, machine, inventory_number
            FROM tasks
            WHERE datetime(substr(end_time, 7, 4) || '-' || substr(end_time, 4, 2) || '-' || substr(end_time, 1, 2) || ' ' || substr(end_time, 12, 5)) 
                  >= datetime('now', '-1 day')
            ORDER BY date DESC
        ''')
        rows = await cursor.fetchall()

    if not rows:
        return []

    messages = []
    for row in rows:
        id_, date, workers, work_description, work_solution, fault_status, start_time, end_time, duration, shift, machine, inventory_number = row

        result_message = (
            f"🚀 <b>ЗАЯВКА</b> <code>#{id_}</code>\n"
            f"📅 <b>Дата:</b> {date}\n"
            f"📌 <b>Исполнители работ:</b> {workers}\n"
            f"📝 <b>Описание проблемы:</b> {work_description}\n"
            f"📝 <b>Решение:</b> {work_solution}\n"
            f"📝 <b>Статус неисправности:</b> {fault_status}\n"
            f"📅 <b>Дата начала:</b> {start_time}\n"
            f"📅 <b>Дата окончания:</b> {end_time}\n"
            f"⏳ <b>Затраченное время:</b> {duration}\n"
            f"🏭 <b>Цех:</b> {shift}\n"
            f"🔧 <b>Станок:</b> {machine}\n"
            f"🔢 <b>Инвентарный номер:</b> {inventory_number}\n"
        )
        messages.append(result_message)

    #separator = "\n---------------------------------------------\n"
    return messages

async def load_db_data():
    """Загружает все записи из БД (асинхронно)."""
    return await search_data("")


async def run_search(phrase):
    results = await search_data(phrase)
    # Добавляем индекс строки, если нужно (для редактирования)
    for idx, row in enumerate(results):
        row["__row"] = idx + 1  # Нумерация с 1
    return results


# # Функция создания PDF файла
def create_pdf_file(results, filename):
    """Создает PDF файл с результатами поиска и возвращает путь к нему."""
    if not results:
        return None

    # Создаём папку, если её нет
    os.makedirs(settings.TEMP_DIR, exist_ok=True)

    # Полный путь к файлу
    file_path = os.path.join(settings.TEMP_DIR, filename)

    # Создаём DataFrame из результатов
    df = pd.DataFrame(results)

    column_rename = {
        'date': 'Дата',
        'workers': 'Исполнители работ',
        'work_description': 'Описание проблемы',
        'work_solution': 'Решение',
        'fault_status': 'Статус неисправности',
        'start_time': 'Дата начала',
        'end_time': 'Дата окончания',
        'duration': 'Затраченное время',
        'shift': 'Цех',
        'machine': 'Станок',
        'inventory_number': 'Инвентарный номер'
    }
    # Удаляем столбец id, если он есть (не нужен в выводе)
    if 'id' in df.columns:
        df = df.drop(columns=['id'])
    df = df.rename(columns=column_rename)

    # Создаём PDF документ с ландшафтной ориентацией для большего пространства
    doc = SimpleDocTemplate(file_path, pagesize=landscape(A4))
    elements = []

    # Заголовок
    search_phrase = filename.split('_')[2].replace(
        '_', ' ') if len(filename.split('_')) > 2 else 'Запрос'
    title = Paragraph(f"Результаты поиска: '{search_phrase}'", title_style)
    elements.append(title)
    
    # --- Подсветка текста ---
    def highlight_text(text, phrase):
        if not phrase:
            return str(text)
        # Регистр-независимая замена
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        return pattern.sub(lambda m: f"<font color='red'>{m.group(0)}</font>", str(text))

    # Преобразуем DataFrame в список списков с Paragraph для каждой ячейки
    data = []
    for row in [df.columns.tolist()] + df.values.tolist():  # Заголовки + данные
        data_row = []
        for cell in row:
            cell_text = str(cell) if cell is not None else ""
            # Подсвечиваем только данные, не заголовки
            if row != df.columns.tolist():
                cell_text = highlight_text(cell_text, search_phrase)
            data_row.append(Paragraph(cell_text, normal_style))
        data.append(data_row)

    # Создаём таблицу с фиксированной шириной столбцов
    num_cols = len(df.columns)
    col_widths = [60, 50, 180, 180, 80, 40, 40, 40,
                  30, 40, 40]  # Расширенные настройки ширины

    # Автоподбор ширины для очень длинных таблиц
    total_width = sum(col_widths)
    page_width = 770  # Ширина страницы A4 в ландшафтном режиме (примерно)
    table = Table(data, colWidths=col_widths)

    # Стиль таблицы
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # Автоматический перенос текста в ячейках
        ('WORDWRAP', (0, 0), (-1, -1), True),
    ])
    table.setStyle(style)

    elements.append(table)

    # Генерируем PDF
    doc.build(elements)

    return file_path





def load_contacts():
    try:
        with open(settings.FILE_CONTACTS, 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "name": [],
            "phone": [],
            "email": [],
            "position": []
        }


def save_contacts(contacts):
    with open(settings.FILE_CONTACTS, 'w', encoding='utf-8') as file:
        json.dump(contacts, file, ensure_ascii=False, indent=4)


def create_keyboard_contact(machine_list):
    buttons = []
    for i in range(0, len(machine_list), 2):
        row = []
        # Добавляем первую кнопку в ряд
        row.append(InlineKeyboardButton(
            text=machine_list[i]['name'], callback_data=f"contact_{machine_list[i]['phone']}"))
        # Проверяем, есть ли следующая кнопка
        if i + 1 < len(machine_list):
            row.append(InlineKeyboardButton(
                text=machine_list[i + 1]['name'], callback_data=f"contact_{machine_list[i + 1]['phone']}"))
        else:
            # Если следующей кнопки нет, добавляем пустую кнопку
            row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_keyboard(machine_list):
    buttons = []
    for i in range(0, len(machine_list), 2):
        row = []
        # Добавляем первую кнопку в ряд
        row.append(InlineKeyboardButton(
            text=machine_list[i]['name'], callback_data=machine_list[i]['name']))
        # Проверяем, есть ли следующая кнопка
        if i + 1 < len(machine_list):
            row.append(InlineKeyboardButton(
                text=machine_list[i + 1]['name'], callback_data=machine_list[i + 1]['name']))
        else:
            # Если следующей кнопки нет, добавляем пустую кнопку
            row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        buttons.append(row)
    # Добавляем кнопку "Назад" на всю ширину
    buttons.append([InlineKeyboardButton(
        text=" ↩️ Назад", callback_data='back_2')])
    # Создаем и возвращаем InlineKeyboardMarkup с кнопками
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_all_user_ids():
    """
    Читает access_user.json и возвращает set уникальных telegram_id из всех ролей.
    """
    try:
        with open('json/access_user.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        user_ids = set()
        for role in ['main_admins', 'admins', 'users']:
            user_ids.update(data.get(role, []))
        return user_ids
    except FileNotFoundError:
        logging.error("Файл json/access_user.json не найден.")
        return set()
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка чтения JSON: {e}")
        return set()

# Функция для получения информации о пользователе


async def get_user_info(bot, user_id):
    try:
        user = await bot.get_chat(user_id)
        return user.first_name, user.last_name, user.id
    except Exception as e:
        print(f"Ошибка при получении информации о пользователе {user_id}: {e}")
        return None, None, user_id  # Возвращаем ID, если не удалось получить информацию


def get_last_lines(log_file: str, num_lines: int) -> str:
    """
    Эффективно читает последние num_lines строк из файла.
    """
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = deque(f, maxlen=num_lines)
        return ''.join(lines)
    except Exception as e:
        logging.error(f"Ошибка чтения последних строк из {log_file}: {e}")
        return "Ошибка чтения файла."


async def send_last_lines(message: Message, log_file: str, num_lines: int):
    """
    Отправляет последние строки как файл.
    """
    try:
        last_lines = get_last_lines(log_file, num_lines)
        temp_file = 'temp_last_logs.txt'
        with open(temp_file, 'w', encoding='utf-8') as temp:
            temp.write(last_lines)

        document = FSInputFile(
            temp_file, filename=f'last_{num_lines}_lines_{os.path.basename(log_file)}')
        await message.answer_document(document, caption=f"Последние {num_lines} строк из {os.path.basename(log_file)} (файл большой, отправлен только конец).")
        logging.info(
            f"Админ {message.from_user.id} скачал последние {num_lines} строк из {log_file}.")

        os.remove(temp_file)
    except Exception as e:
        logging.error(
            f"Ошибка отправки последних строк из {log_file} админу {message.from_user.id}: {e}")
        await message.answer("Не удалось отправить последние строки логов.")


async def send_full_log_file(message: Message, log_file: str):
    """
    Отправляет полный файл логов.
    """
    try:
        document = FSInputFile(
            log_file, filename=f'{os.path.basename(log_file)}_full.txt')
        await message.answer_document(document, caption=f"Полные логи из {os.path.basename(log_file)} (файл маленький, отправлен целиком).")
        logging.info(
            f"Админ {message.from_user.id} скачал полный файл {log_file}.")
    except Exception as e:
        logging.error(
            f"Ошибка отправки полного файла {log_file} админу {message.from_user.id}: {e}")
        await message.answer("Не удалось отправить файл логов.")


async def update_record_in_db(record_id, updated_data):
    """
    Асинхронно обновляет запись в SQLite по id.

    :param record_id: int — ID записи для обновления.
    :param updated_data: dict — Словарь с полями для обновления.
    """
    try:
        conn = await aiosqlite.connect('bot_data.db')  # Путь к вашей БД
        cursor = await conn.cursor()

        # Формируем SET-часть запроса динамически
        set_clause = ', '.join([f"{k} = ?" for k in updated_data.keys()])
        values = list(updated_data.values()) + [record_id]  # Добавляем ID

        # Выполняем UPDATE
        query = f"UPDATE tasks SET {set_clause} WHERE id = ?"
        await cursor.execute(query, values)

        # Сохраняем изменения
        await conn.commit()

        # Логируем успех
        logger.info(f"Запись с ID {record_id} обновлена: {updated_data}")

    except aiosqlite.Error as e:
        logger.error(f"Ошибка при обновлении записи ID {record_id}: {e}")
        raise  # Перебрасываем для обработки
    finally:
        if conn:
            await conn.close()


async def show_record(message: Message, state: FSMContext):
    data = await state.get_data()
    results = data["search_results"]
    index = data["current_index"]
    record = results[index].copy()

    total = len(results)
    msg_text = (
        f"🚀 <b>ЗАЯВКА</b> <code>#{record['id']}</code>\n"
        f"📱 <b>СТРАНИЦА:</b> <code>{index + 1}/{total}</code>\n"
        f"{'•' * 30}\n"
        f"📅 <b>Дата:</b> {record['date']}\n"
        f"📌 <b>Исполнители работ:</b> {record['workers']}\n"
        f"📝 <b>Описание проблемы:</b> {record['work_description']}\n"
        f"📝 <b>Решение:</b> {record['work_solution']}\n"
        f"📝 <b>Статус неисправности:</b> {record['fault_status']}\n"
        f"📅 <b>Дата начала:</b> {record['start_time']}\n"
        f"📅 <b>Дата окончания:</b> {record['end_time']}\n"
        f"⏳ <b>Затраченное время:</b> {record['duration']}\n"
        f"🏭 <b>Цех:</b> {record['shift']}\n"
        f"🔧 <b>Станок:</b> {record['machine']}\n"
        f"🔢 <b>Инвентарный номер:</b> {record['inventory_number']}"
    )
    user_id = message.from_user.id
    user_role = get_user_role(user_id, load_access_data())
    keyboard = build_navigation_buttons(index, total, user_role=user_role)
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(msg_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(msg_text, reply_markup=keyboard, parse_mode="HTML")


def build_navigation_buttons(current_index, total, user_role =None):
    buttons = []

    # Кнопки редактирования
    edit_buttons = [
        [InlineKeyboardButton(text="🔧 Изм. проблему", callback_data="edit_problem"),
         InlineKeyboardButton(text="🛠 Изм. решение", callback_data="edit_solution")],
        [InlineKeyboardButton(text="📊 Изм. статус", callback_data="edit_status"),
         InlineKeyboardButton(text="👷 Изм. исполнителей", callback_data="edit_workers")]
    ]
    buttons.extend(edit_buttons)

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Предыдущая", callback_data="prev_record"))
    if current_index < total - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="➡️ Следующая", callback_data="next_record"))

    if nav_buttons:
        buttons.append(nav_buttons)
        
    if user_role == "👑 Главный администратор!":
        buttons.append([InlineKeyboardButton(text="❌ Удалить запись", callback_data="delete_record")])

    buttons.append([InlineKeyboardButton(
        text="🔙 Главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Функция для создания клавиатуры с цифрами 0-9
def number_keyboard(stage):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=str(i), callback_data=f"{stage}_{i}") for i in range(1, 4)],
        [InlineKeyboardButton(
            text=str(i), callback_data=f"{stage}_{i}") for i in range(4, 7)],
        [InlineKeyboardButton(
            text=str(i), callback_data=f"{stage}_{i}") for i in range(7, 10)],
        [InlineKeyboardButton(text="0", callback_data=f"{stage}_0")],
        [InlineKeyboardButton(text="⬅️ Удалить", callback_data=f"{stage}_del"),
         InlineKeyboardButton(text="✅ Готово", callback_data=f"{stage}_done")],
        [InlineKeyboardButton(
            text="↩️ Назад", callback_data="back_from_time")]
    ])
    return kb



COLUMN_HEADERS = {
    "id": "ID",
    "user_id": "ID пользователя",
    "date": "Дата",
    "workers": "Исполнители работ",
    "machine": "Станок",
    "shift": "Цех",
    "start_time": "Дата начала",
    "end_time": "Дата окончания",
    "work_description": "Описание проблемы",
    "work_solution": "Решение",
    "fault_status": "Статус неисправности",
    "duration": "Затраченное время",
    "inventory_number": "Инвентарный номер"
}



async def export_to_excel_and_send(message, db_file=settings.DB_FILE):
    temp_dir = Path(settings.TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # --- Получаем данные ---
    async with aiosqlite.connect(db_file) as db:
        cursor = await db.execute("SELECT * FROM tasks")
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]

    if not rows:
        await message.answer("❌ В базе нет записей для экспорта.")
        return

    # --- Создаём DataFrame ---
    df = pd.DataFrame(rows, columns=columns)
    df.rename(columns=COLUMN_HEADERS, inplace=True)

    # --- Создаём Excel ---
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    excel_filename = temp_dir / f"tasks_export_{timestamp}.xlsx"

    with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Tasks')
        workbook = writer.book
        worksheet = writer.sheets['Tasks']

        # Форматирование: перенос текста, выравнивание по центру, верхнее выравнивание, границы
        cell_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'vcenter',   # вертикальное центрирование
            'align': 'center',     # горизонтальное центрирование
            'border': 1
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'text_wrap': True,
            'valign': 'vcenter',   # вертикальное центрирование заголовка
            'align': 'center',     # горизонтальное центрирование
            'border': 1
        })

        # Применяем формат к заголовкам
        for col_num, value in enumerate(df.columns):
            worksheet.write(0, col_num, value, header_format)

        # Автоширина колонок, максимум 40
        for i, col in enumerate(df.columns):
            max_len = min(max(df[col].astype(str).map(len).max(), len(col)) + 2, 40)
            worksheet.set_column(i, i, max_len, cell_format)

    # --- Проверяем размер файла ---
    file_size_mb = excel_filename.stat().st_size / (1024 * 1024)
    if file_size_mb > 50:
        zip_filename = excel_filename.with_suffix(".zip")
        with ZipFile(zip_filename, 'w') as zipf:
            zipf.write(excel_filename, arcname=excel_filename.name)
        send_file = FSInputFile(zip_filename)
        caption = f"📦 Экспорт данных (архив) — {file_size_mb:.1f} МБ"
        os.remove(excel_filename)
    else:
        send_file = FSInputFile(excel_filename)
        caption = f"📄 Экспорт данных — {file_size_mb:.1f} МБ"

    # --- Отправка ---
    await message.answer_document(send_file, caption=caption)
    # --- Удаляем временный файл ---
    if send_file.path.exists():
        os.remove(send_file.path)


async def delete_record_from_db(record_id: int):
    """Удаляет запись из таблицы tasks по ее id"""
    try:
        async with aiosqlite.connect(settings.DB_FILE) as db:
            await db.execute("DELETE FROM tasks WHERE id = ?", (record_id,))
            await db.commit()
        logger.info(f"Запись {record_id} успешно удалена из базы данных.")
    except Exception as e:
        logger.error(f"Ошибка при удалении записи {record_id}: {e}")
        raise
    
    
    
def manuals_keyboard(files: list[str], page: int) -> InlineKeyboardMarkup:
    
    
    total_pages = ceil(len(files) / settings.MANUALS_PER_PAGE)
    page = max(1, min(page, total_pages))

    start = (page - 1) * settings.MANUALS_PER_PAGE
    end = start + settings.MANUALS_PER_PAGE
    page_files = files[start:end]

    keyboard = []

    # 📄 Файлы (2 в ряд)
    for i in range(0, len(page_files), settings.BUTTONS_IN_ROW):
        row = [
            InlineKeyboardButton(
                text=f"📄 {os.path.splitext(f)[0][:30]}",
                callback_data=f"manual:{f}"
            )
            for f in page_files[i:i + settings.BUTTONS_IN_ROW]
        ]
        keyboard.append(row)

    # ⬅️ ➡️ Навигация
    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"manuals_page:{page - 1}")
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(text="Следующая ➡️", callback_data=f"manuals_page:{page + 1}")
        )
    if nav:
        keyboard.append(nav)

    # 🧮 Калькулятор
    keyboard.append([
        InlineKeyboardButton(text="🧮 Калькулятор ошибок", callback_data="error_calculator")
    ])

    # 🔙 Главное меню
    keyboard.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Формирование клавиатуры для удаления
def delete_manuals_keyboard(files: list[str]) -> InlineKeyboardMarkup:
    keyboard = []
    buttons_in_row = settings.BUTTONS_IN_ROW

    for start in range(0, len(files), buttons_in_row):
        row = []
        for offset, f in enumerate(files[start:start + buttons_in_row]):
            global_index = start + offset  # правильный индекс файла в списке
            row.append(
                InlineKeyboardButton(
                    text=f"🗑 {os.path.splitext(f)[0][:30]}",
                    callback_data=f"manual_delete:{global_index}"
                )
            )
        keyboard.append(row)

    # Отмена
    #keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="manual_delete_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def upload_to_yadisk(local_file_path: str, remote_path: str, max_backups: int = 5):
    """
    Загружает файл на Яндекс.Диск с ротацией.
    Удаляет старые файлы, если их больше max_backups.
    """
    headers = {"Authorization": f"OAuth {settings.YANDEX_DISK_TOKEN}"}
    base_dir = "/Backups"

    async with aiohttp.ClientSession() as session:
        # 1. Получаем список файлов в папке /Backups
        async with session.get(
            "https://cloud-api.yandex.net/v1/disk/resources",
            headers=headers,
            params={"path": base_dir, "fields": "_embedded.items"}
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Ошибка получения списка файлов с Яндекс.Диска: {text}")
            data = await resp.json()
            items = data.get("_embedded", {}).get("items", [])
            backup_files = [
                f for f in items
                if f["name"].startswith("Копия_БД_") and f["type"] == "file"
            ]

        # 2. Если файлов больше max_backups - удаляем самый старый
        if len(backup_files) >= max_backups:
            # сортируем по дате создания
            backup_files.sort(key=lambda x: x.get("created", ""))
            oldest = backup_files[0]["name"]
            async with session.delete(
                "https://cloud-api.yandex.net/v1/disk/resources",
                headers=headers,
                params={"path": f"{base_dir}/{oldest}"}
            ) as del_resp:
                if del_resp.status not in (204, 202):
                    text = await del_resp.text()
                    logger.warning(f"Не удалось удалить старый файл на Яндекс.Диске {oldest}: {text}")
                else:
                    logger.info(f"Удален старый файл на Яндекс.Диске: {oldest}")

        # 3. Получаем URL для загрузки нового файла
        async with session.get(
            "https://cloud-api.yandex.net/v1/disk/resources/upload",
            headers=headers,
            params={"path": remote_path, "overwrite": "true"}
        ) as resp:
            data = await resp.json()
            upload_url = data.get("href")
            if not upload_url:
                raise Exception(f"Не удалось получить URL для загрузки: {data}")

        # 4. Загружаем файл
        async with aiofiles.open(local_file_path, "rb") as f:
            file_data = await f.read()
        async with session.put(upload_url, data=file_data) as upload_resp:
            if upload_resp.status not in (201, 202):
                text = await upload_resp.text()
                raise Exception(f"Ошибка загрузки: {upload_resp.status}, {text}")

    return f"✅ Файл успешно загружен на Яндекс.Диск: {remote_path}"


async def count_yadisk_backups():
    """
    Считает количество бэкапов базы данных на Яндекс.Диске в папке /Backups
    """
    headers = {"Authorization": f"OAuth {settings.YANDEX_DISK_TOKEN}"}
    url = "https://cloud-api.yandex.net/v1/disk/resources"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params={"path": "/Backups", "fields": "_embedded.items"}) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Ошибка получения списка файлов с Яндекс.Диска: {text}")

            data = await resp.json()
            items = data.get("_embedded", {}).get("items", [])
            backup_files = [
                f for f in items
                if f["name"].startswith("Копия_БД_") and f["type"] == "file"
            ]
            return len(backup_files)
        
        
async def download_yadisk_backup(filename):
    headers = {"Authorization": f"OAuth {settings.YANDEX_DISK_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        # Получаем ссылку для скачивания
        async with session.get(
            "https://cloud-api.yandex.net/v1/disk/resources/download",
            headers=headers,
            params={"path": f"/Backups/{filename}"}
        ) as resp:
            data = await resp.json()
            download_url = data.get("href")
            if not download_url:
                raise Exception("Не удалось получить ссылку для скачивания")

        # Скачиваем файл
        async with session.get(download_url) as download_resp:
            file_path = os.path.join(settings.DIR_DB, filename)
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(await download_resp.read())
            return file_path
        
async def list_yadisk_backups():
    """
    Возвращает список резервных копий на Яндекс.Диске.
    Каждый элемент — словарь с полями 'name' и 'created'.
    """
    headers = {"Authorization": f"OAuth {settings.YANDEX_DISK_TOKEN}"}
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    params = {"path": "/Backups", "fields": "_embedded.items"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Ошибка получения списка файлов с Яндекс.Диска: {text}")

            data = await resp.json()
            items = data.get("_embedded", {}).get("items", [])
            
            # Фильтруем только файлы бэкапов
            backups = [
                {"name": f["name"], "created": f["created"]}
                for f in items
                if f["name"].startswith("Копия_БД_") and f["type"] == "file"
            ]

            # Сортировка по дате создания (новые сверху)
            backups.sort(key=lambda x: x["created"], reverse=True)
            return backups

def history_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    keyboard = []

    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"history_page:{page - 1}")
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(text="Следующая ➡️", callback_data=f"history_page:{page + 1}")
        )

    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
