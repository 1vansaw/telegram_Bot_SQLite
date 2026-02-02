import logging
import asyncio
from math import ceil
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from app.keyboards import workshops_schemes, inline_main_menu
import app.utils.funcs as fs
from app.config import settings
import os
import time
import aiohttp
import aiofiles
import uuid


electroschemes_router = Router(name=__name__)
logger = logging.getLogger(__name__)



@electroschemes_router.message(F.text == "⚡ Электросхемы")
async def open_electroschemes_menu(message: Message):
    data = fs.load_access_data()
    user_id = message.from_user.id
    role = fs.get_user_role(user_id, data)
    allowed_roles = ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]

    if role not in allowed_roles:
        await message.answer("⛔ У вас нет доступа")
        return

    logger.info(f"Пользователь {user_id} открыл меню Электросхемы | роль: {role}")
    await message.answer("Выберите цех:", reply_markup=workshops_schemes)


@electroschemes_router.callback_query(F.data == "back_to_shops")
async def back_to_shops(query: CallbackQuery):
    await query.message.edit_text("Выберите цех:", reply_markup=workshops_schemes)
    await query.answer()
    
    

# -------------------------------
# 2️⃣ Выбор цеха
# callback: schemes_shop:{shop}
# -------------------------------
@electroschemes_router.callback_query(F.data.startswith("schemes_shop:"))
async def handle_shop_choice(query: CallbackQuery):
    """
    Обработчик выбора цеха. Показывает список файлов с пагинацией.
    """
    _, shop = query.data.split(":")
    files = await fs.list_yadisk_electroschemes(shop)

    page = 1
    total_pages = max(1, ceil(len(files) / settings.PER_PAGE))
    keyboard = fs.build_schemes_keyboard(files, shop, page=page, per_page=settings.PER_PAGE)

    # Красивое оформление текста
    if not files:
        msg_text = (
            f"📂 <b>Схемы цеха {shop}</b>\n"
            f"⚠️ Файлов нет.\n\n"
            f"Нажмите кнопку ниже, чтобы вернуться к выбору цеха."
        )
    else:
        msg_text = (
            f"📂 <b>Схемы цеха {shop}</b>\n"
            f"📄 Страница: <code>{page}/{total_pages}</code>\n"
            f"{'•' * 30}"
        )

    await query.message.edit_text(
        msg_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await query.answer()


# -------------------------------
# 3️⃣ Навигация по страницам
# callback: schemes_nav:{shop}:{page}
# -------------------------------
@electroschemes_router.callback_query(F.data.startswith("schemes_nav:"))
async def handle_navigation(query: CallbackQuery):
    _, shop, page_str = query.data.split(":")
    page = int(page_str)
    files = await fs.list_yadisk_electroschemes(shop)
    total_pages = max(1, ceil(len(files)/settings.PER_PAGE))
    page = max(1, min(page, total_pages))  # защита от выхода за пределы

    keyboard = fs.build_schemes_keyboard(files, shop, page=page, per_page=settings.PER_PAGE)

    await query.message.edit_text(
        f"📂 Схемы цеха {shop}\nСтраница {page}/{total_pages}",
        reply_markup=keyboard
    )
    await query.answer()


# -------------------------------
# 4️⃣ Выбор файла для отправки
# callback: schemes_file:{shop}:{file_index}
# -------------------------------
@electroschemes_router.callback_query(F.data.startswith("schemes_file:"))
async def handle_file_selection(query: CallbackQuery):
    await query.answer()  # подтверждаем callback без текста

    try:
        _, shop, file_index_str = query.data.split(":")
        file_index = int(file_index_str)
        files = await fs.list_yadisk_electroschemes(shop)

        if file_index < 0 or file_index >= len(files):
            await query.answer("❌ Файл не найден", show_alert=True)
            return

        filename = files[file_index]

        # --- Генерируем уникальное имя временного файла ---
        unique_filename = f"{uuid.uuid4()}_{filename}"
        temp_path = os.path.join(settings.TEMP_DIR, unique_filename)

        # --- Начальное сообщение о скачивании ---
        loading_msg = await query.message.edit_text(
            f"⏳ <b>Скачивание файла с Яндекс.Диска:</b>\n<i>{filename}</i>\n"
            f"📊 [{'░'*12}] 0%\n"
            f"📄 <b>Загружено:</b> 0 МБ\n"
            f"⚡ <b>Скорость:</b> 0 МБ/с",
            parse_mode="HTML"
        )

        # --- Получаем ссылку на скачивание ---
        headers = {"Authorization": f"OAuth {settings.YANDEX_DISK_TOKEN}"}
        url_api = "https://cloud-api.yandex.net/v1/disk/resources/download"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url_api,
                headers=headers,
                params={"path": f"/electroschemes/{shop}/{filename}"}
            ) as resp:
                data = await resp.json()
                download_url = data.get("href")
                if not download_url:
                    await loading_msg.edit_text("❌ Не удалось получить ссылку для скачивания.")
                    return

        chunk_size = 1024 * 1024  # 1 MB
        downloaded = 0
        last_percent = -1
        start_time = time.time()
        BAR_LENGTH = 12

        # --- Скачиваем файл с прогресс-баром и обработкой ошибок ---
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as resp:
                    total_size = int(resp.headers.get("Content-Length", 0))
                    async with aiofiles.open(temp_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(chunk_size):
                            try:
                                await f.write(chunk)
                                downloaded += len(chunk)
                            except Exception as e:
                                raise RuntimeError(f"Ошибка записи файла: {e}")

                            percent = int(downloaded / total_size * 100) if total_size else 0
                            elapsed = max(time.time() - start_time, 0.001)
                            speed = downloaded / (1024*1024) / elapsed
                            size_mb = total_size / (1024*1024)
                            downloaded_mb = downloaded / (1024*1024)

                            # --- Адаптивное обновление прогресс-бара ---
                            if size_mb <= 30:
                                update = percent != last_percent
                            else:
                                update = (percent != last_percent) and (percent % 3 == 0 or percent == 100)

                            if update:
                                filled_length = int(BAR_LENGTH * percent // 100)
                                bar = "█" * filled_length + "░" * (BAR_LENGTH - filled_length)

                                await loading_msg.edit_text(
                                    f"⏳ <b>Скачивание файла:</b> <i>{filename}</i>\n"
                                    f"📊 [{bar}] {percent}%\n"
                                    f"📄 <b>Загружено:</b> {downloaded_mb:.2f}/{size_mb:.2f} МБ\n"
                                    f"⚡ <b>Скорость:</b> {speed:.2f} МБ/с",
                                    parse_mode="HTML"
                                )
                                last_percent = percent
        except Exception as e:
            logger.error(f"Ошибка при скачивании файла {filename}: {e}")
            await loading_msg.edit_text(
                f"❌ Ошибка при скачивании файла {filename}.\n"
                f"Причина: {e}\nПопробуйте позже."
            )
            # удаляем частично скачанный файл
            try:
                os.remove(temp_path)
            except Exception:
                pass
            return  # прекращаем выполнение

        # --- Файл скачан, подготовка к отправке ---
        file_size_mb = os.path.getsize(temp_path) / (1024*1024)
        approx_speed = 0.1  # МБ/с, средняя скорость upload
        approx_time = max(int(file_size_mb / approx_speed), 1)

        await loading_msg.edit_text(
            f"✅ <b>Файл {filename} успешно загружен!</b>\n\n"
            f"🔄 <b>Подготовка к отправке...</b>\n"
            f"📄 Размер: {file_size_mb:.2f} МБ\n"
            f"⏱ Примерное время отправки: ~{approx_time} сек\n"
            f"⚠️ Время ориентировочное, зависит от скорости сети и Telegram",
            parse_mode="HTML"
        )

        # --- Отправка файла ---
        try:
            document = FSInputFile(path=temp_path)
            await query.message.answer_document(document=document, caption=filename, reply_markup=inline_main_menu)
        except Exception as e:
            logger.error(f"Ошибка при отправке файла: {e}")
            await loading_msg.edit_text(
                f"❌ Не удалось отправить файл {filename}.\n"
                f"Причина: {e}\nПопробуйте позже или скачайте файл напрямую.",
                parse_mode="HTML"
            )
            # файл оставляем для возможной повторной попытки
            return

        # --- Очистка временного файла ---
        try:
            os.remove(temp_path)
            logger.info(f"Временный файл {temp_path} удалён после отправки.")
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {temp_path}: {e}")

        # --- Удаляем сообщение о загрузке ---
        try:
            await loading_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        try:
            await query.answer(f"❌ Произошла ошибка: {e}", show_alert=True)
        except Exception:
            pass
