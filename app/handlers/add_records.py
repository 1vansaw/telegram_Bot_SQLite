import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback, get_user_locale
from app.states import Register
import logging
from app.keyboards import workshops, del_machines, markup, inline_main_menu
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from datetime import datetime
import app.utils.funcs as fs
from datetime import datetime, time
from app.data_shops import shops
import asyncio


add_router = Router()
logger = logging.getLogger(__name__)



@add_router.message(F.text == '📝 Добавить запись')
async def add_record(message: Message, state: FSMContext):
    data = fs.load_access_data()
    user_id = message.from_user.id  # Получаем ID пользователя
    role = fs.get_user_role(user_id, data)
    if role in ["👑 Главный администратор!", "🛠 Администратор!", "👥 Пользователь"]:
        await state.set_state(Register.shop_selection)
        #temp_msg = await message.answer("⌛ Подготавливаю список цехов...",reply_markup=ReplyKeyboardRemove())
        #await asyncio.sleep(0.6)
        #await temp_msg.delete()
        await message.answer('🏭 Выберите цех', reply_markup=workshops)
    else:
        await message.answer('⛔ У вас нет доступа')
        
        
# функция формирования кнопок из файла json в зависимости от состояния
@add_router.callback_query(F.data.regexp(r'(.+?)-shop'))
async def shops_1(callback: CallbackQuery, state: FSMContext):
    # Извлекаем номер цеха из данных колбэка
    # Получаем номер или название цеха
    shop_number = callback.data.split('-')[0]
    machines_data = fs.load_machines_data()
    machines = machines_data.get(f'maschines_{shop_number}', [])
    # Обновляем состояние пользователя
    await state.update_data(selected_shop=callback.data)
    logger.info(
        f"Пользователь {callback.from_user.id} выбрал цех {shop_number}.")
    if await state.get_state() == Register.shop_selection.state:
        # Устанавливаем состояние в зависимости от номера цеха
        await state.set_state(getattr(Register, f'machine_selection_{shop_number}'))
        # Генерируем клавиатуру с станками
        keyboard = fs.create_keyboard(machines)
        await callback.message.edit_text("⚙️ Выберите станок:", reply_markup=keyboard)
    elif await state.get_state() == Register.awaiting_machine_name.state:
        await callback.message.edit_text("✏️ Введите название станка:")
        await state.set_state(Register.awaiting_machine_name)
    elif await state.get_state() == Register.delete_machine.state:
        # Устанавливаем состояние в зависимости от номера цеха
        await state.set_state(getattr(Register, f'machine_selection_{shop_number}'))
        keyboard = fs.create_keyboard(machines)
        await callback.message.edit_text("🗑 Выберите станок для удаления:", reply_markup=keyboard)
        await state.set_state(Register.delete_machine_1)




# функция для работы после выбора станка в зависимости от состояния
@add_router.callback_query(lambda callback: any(machine['name'] in callback.data for machines in fs.load_machines_data().values() for machine in machines))
async def reg(callback: CallbackQuery, state: FSMContext):
    await state.update_data(selected_machine=callback.data)
    if await state.get_state() == Register.delete_machine_1.state:
        user_data = await state.get_data()
        shop_number = user_data.get('selected_shop').split('-')[0]
        machine_name = user_data.get('selected_machine')  # Получаем имя станка
        machines_data = fs.load_machines_data()
        machines = machines_data.get(f'maschines_{shop_number}', [])
        machine_to_remove = next(
            (machine for machine in machines if machine['name'] == machine_name), None)
        if machine_to_remove:
            # Показываем пользователю кнопки подтверждения
            await callback.message.edit_text(
                f"❌ Вы уверены, что хотите удалить станок:\n\n"
                f"⚙️ {machine_name}?",
                reply_markup=del_machines
            )
            # Сохраняем станок для удаления в состояние
            await state.update_data(machine_to_remove=machine_to_remove)
        else:
            logger.warning(
                f"Пользователь {callback.from_user.id} выбрал несуществующий станок '{machine_name}' в цехе {shop_number}.")
            await callback.answer("❌ Станок не найден.")
    else:
        # Сохраняем текущее состояние перед переходом к новому
        await state.update_data(previous_state=await state.get_state())
        await state.set_state(Register.date_start)
        await callback.message.edit_text(
            "📅 Пожалуйста, выберите дату начала работ:",
            reply_markup=await SimpleCalendar(
                locale=await get_user_locale(callback.from_user)).start_calendar())





# simple calendar usage - filtering callbacks of calendar format
@add_router.callback_query(SimpleCalendarCallback.filter())
async def process_simple_calendar(callback_query: CallbackQuery, callback_data: CallbackData, state: FSMContext):
    logger.info(
        f"Пользователь {callback_query.from_user.id} взаимодействует с календарем.")
    calendar = SimpleCalendar(
        locale=await get_user_locale(callback_query.from_user),
        show_alerts=True)
    calendar.set_dates_range(datetime(2022, 1, 1), datetime(
        datetime.now().year + 1, 12, 31))
    result = await calendar.process_selection(callback_query, callback_data, state)
    if result is not None:
        selected, date = result
        if date is None:
            date = datetime.now()
        if selected:
            if await state.get_state() == Register.date_start.state:
                await state.update_data(selected_date_start=date)
                user_data = await state.get_data()
                selected_date_start = user_data.get("selected_date_start")
                await callback_query.message.edit_text(f'📅 Выбрать дату {selected_date_start.strftime("%d.%m.%Y")}?', reply_markup=markup)
                await state.set_state(Register.date_end)
                logger.info(
                    f"Пользователь {callback_query.from_user.id} выбрал дату начала: {selected_date_start.strftime('%d.%m.%Y')}.")
            elif await state.get_state() == Register.confirm_dates.state:
                await state.update_data(selected_date_end=date)
                await callback_query.message.edit_text(
                    f"📅 Вы выбрали дату окончания: {date.strftime('%d.%m.%Y')}\n"
                    "✅ Подтвердите выбор?",
                    reply_markup=markup
                )
                logger.info(
                    f"Пользователь {callback_query.from_user.id} выбрал дату окончания: {date.strftime('%d.%m.%Y')}.")


# привязка к кнопке назад
@add_router.callback_query(F.data == "back_to_calendar")
async def back_to_calendar(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Пользователь {callback.from_user.id} вернулся к календарю.")
    current_state = await state.get_state()
    user_data = await state.get_data()
    if current_state == Register.today_date.state or current_state == Register.date_end.state:
        await callback.message.edit_text(
            "📅 Пожалуйста, выберите дату начала работ:",
            reply_markup=await SimpleCalendar(
                locale=await get_user_locale(callback.from_user)).start_calendar())
        # Возвращаемся к выбору даты начала
        await state.set_state(Register.date_start)
    elif current_state == Register.confirm_dates.state:
        await callback.message.edit_text(
            f'📅 Вы выбрали дату начала: {user_data.get("selected_date_start").strftime("%d.%m.%Y")}\n ➡️ Пожалуйста, выберите дату завершения.',
            reply_markup=await SimpleCalendar(locale=await get_user_locale(callback.from_user)).start_calendar())


# привязка к кнопке подтвердить
@add_router.callback_query(F.data == "confirm_date")
async def confirm_date(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == Register.date_end.state or current_state == Register.today_date.state:
        data = await state.get_data()
        await callback.message.edit_text(
            f'📅 Вы выбрали дату начала: {data.get("selected_date_start").strftime("%d.%m.%Y")}\n ➡️ Пожалуйста, выберите дату завершения.',
            reply_markup=await SimpleCalendar(locale=await get_user_locale(callback.from_user)).start_calendar())
        # Устанавливаем состояние на выбор даты окончания
        await state.set_state(Register.confirm_dates)
        logger.info(
            f"Пользователь {callback.from_user.id} подтвердил дату начала и перешел к выбору даты окончания.")
    elif current_state == Register.confirm_dates.state:
        data = await state.get_data()
        if data.get("selected_date_end").date() < data.get("selected_date_start").date():
            logger.warning(
                f"Пользователь {callback.from_user.id} выбрал некорректную дату окончания (раньше начала).")
            await callback.message.edit_text(
                f'❌ Дата завершения должна быть больше или равна дате начала. 📅 Пожалуйста, выберите другую дату (дата начала: {data.get("selected_date_start").strftime("%d.%m.%Y")}).',
                reply_markup=await SimpleCalendar(locale=await get_user_locale(callback.from_user)).start_calendar())
        else:
            # Устанавливаем состояние
            await state.set_state(Register.date_to_time)
            logger.info(
                f"Пользователь {callback.from_user.id} подтвердил даты: начало {data.get('selected_date_start').strftime('%d.%m.%Y')}, окончание {data.get('selected_date_end').strftime('%d.%m.%Y')}.")
            # ✅ Отправляем сообщение сразу, чтобы вызвать `start_cmd`
            await start_cmd(callback.message, state)
            
# привязка к 2 кнопке назад
@add_router.callback_query(F.data == 'back_2')
async def shops_back_2(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('🏭 Выберите цех', reply_markup=workshops)
    await state.set_state(Register.shop_selection)
    


@add_router.callback_query(F.data == 'back_from_time')
async def back_time(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == Register.time_start.state:
        await callback.message.edit_text(
            "📅 Пожалуйста выберите дату начала работ: ",
            reply_markup=await SimpleCalendar(
                locale=await get_user_locale(callback.from_user)).start_calendar())
        await state.set_state(Register.date_start)
    elif current_state == Register.confirm_time:
        await start_cmd(callback.message, state)
        await state.set_state(Register.time_start)


@add_router.message(Register.date_to_time)
async def start_cmd(message: Message, state: FSMContext):
    data = await state.get_data()
    # ✅ Храним данные в FSMContext
    selected_date_start = data.get("selected_date_start")
    selected_date_end = data.get("selected_date_end")
    await state.update_data(hours_start="", minutes_start="")
    await message.edit_text(
        f"📅 Период работ:\n"
        f"🟢 Начало: {selected_date_start.date().strftime('%d.%m.%Y')}\n"
        f"🔴 Конец: {selected_date_end.date().strftime('%d.%m.%Y')}\n\n"
        f"⏰ Введите часы начала работ (00-23):",
        reply_markup=fs.number_keyboard("hourstart")
    )
    await state.set_state(Register.time_start)



@add_router.callback_query(F.data.startswith('hourstart_'))
async def enter_hours_start(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    data = await state.get_data()
    hours_start = data.get("hours_start", "")

    if len(hours_start) >= 2 and action not in ["del", "done"]:
        await callback.answer("⏰ Вы не можете ввести более 2 символов для часов!")
        return

    if action == "del":
        hours_start = hours_start[:-1]
    elif action == "done":
        if hours_start == "" or int(hours_start) > 23:
            await callback.answer("❌ Введите корректные часы (00-23)!")
            return
        # Минуты = 00
        await state.update_data(hours_start=hours_start, minutes_start="00")
        await callback.message.edit_text(
            f"🟢 Вы выбрали время начала: {hours_start}:00\n"
            "⏰ Теперь введите часы окончания работ (00-23):",
            reply_markup=fs.number_keyboard("hourend")
        )
        await state.set_state(Register.time_end)
        return
    else:
        if len(hours_start) < 2:
            hours_start += action

    await state.update_data(hours_start=hours_start)
    await callback.message.edit_text(f"⏰ Часы начала: {hours_start}", reply_markup=fs.number_keyboard("hourstart"))

# Ввод минут начала работ
# @router_time.callback_query(F.data.startswith('minutestart_'))
# async def enter_minutes_start(callback: types.CallbackQuery, state: FSMContext):
#     action = callback.data.split("_")[1]
#     data = await state.get_data()  # ✅ Получаем данные из FSMContext
#     minutes_start = data.get("minutes_start", "")

#     if len(minutes_start) >= 2 and action not in ["del", "done"]:
#         await callback.answer("Вы не можете ввести более 2 символов для минут!")
#         return
#     if action == "del":
#         if minutes_start:
#             minutes_start = minutes_start[:-1]
#     elif action == "done":
#         if minutes_start == "" or int(minutes_start) > 59:
#             await callback.answer("Введите корректные минуты (00-59)!")
#             return
#         await state.set_state(Register.time_end)
#         await end_time_func(callback, state)
#         return
#     else:
#         if len(minutes_start) < 2:
#             minutes_start += action
#     # ✅ Обновляем данные в FSMContext
#     await state.update_data(minutes_start=minutes_start)
#     await callback.message.edit_text(f"Минуты: {minutes_start}", reply_markup=number_keyboard("minutestart"))


# @router_time.callback_query(StateFilter(Register.time_end))
# async def end_time_func(callback: CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     # ✅ Храним данные в FSMContext
#     await state.update_data(hours_end="", minutes_end="")
#     await callback.message.edit_text(f"Начало: {datetime.combine(data.get('selected_date_start').date(), time(int(data.get('hours_start')), int(data.get('minutes_start')))).strftime('%d.%m.%Y %H:%M')} Конец: {data.get('selected_date_end').date().strftime('%d.%m.%Y')}\n"
#                                      f"Введите часы окончания работ (00-23):",
#                                      reply_markup=number_keyboard("hourend"))
#     await state.set_state(Register.confirm_time)


# Ввод часов окончания работ
# @router_time.callback_query(F.data.startswith('hourend_'))
# async def enter_hours_end(callback: types.CallbackQuery, state: FSMContext):
#     action = callback.data.split("_")[1]
#     data = await state.get_data()  # ✅ Получаем данные из FSMContext
#     hours_end = data.get("hours_end", "")
#     hours_start = data.get('hours_start', '00')

#     if len(hours_end) >= 2 and action not in ["del", "done"]:
#         await callback.answer("Вы не можете ввести более 2 символов для часов!")
#         return
#     if action == "del":
#         if hours_end:
#             hours_end = hours_end[:-1]
#     elif action == "done":
#         if hours_end == "" or int(hours_end) > 23:
#             await callback.answer("Введите корректные часы (00-23)!")
#             return
#         if data.get("selected_date_start").date() == data.get("selected_date_end").date():
#             if int(hours_end) < int(hours_start):
#                 await callback.answer(
#                     f"Неверный ввод (часы начала: {hours_start})")
#                 return
#         # ✅ Сохраняем в FSMContext
#         await state.update_data(hours_end=hours_end)
#         await callback.message.edit_text(f"Вы выбрали {hours_end} часов. Теперь введите минуты (00-59):",
#                                          reply_markup=number_keyboard("minuteend"))
#         return
#     else:
#         if len(hours_end) < 2:
#             hours_end += action

#     # ✅ Обновляем данные в FSMContext
#     await state.update_data(hours_end=hours_end)
#     await callback.message.edit_text(f"Часы: {hours_end}",
#                                      reply_markup=number_keyboard("hourend"))


# Вспомогательная функция для кнопок подтверждения/отмены
def confirm_cancel_keyboard(confirm_data, cancel_data):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data)
        ]
    ])


@add_router.callback_query(F.data.startswith('hourend_'))
async def enter_hours_end(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    data = await state.get_data()
    hours_end = data.get("hours_end", "")
    hours_start = data.get('hours_start', '00')

    if len(hours_end) >= 2 and action not in ["del", "done"]:
        await callback.answer("⏰ Вы не можете ввести более 2 символов для часов!")
        return

    if action == "del":
        hours_end = hours_end[:-1]
    elif action == "done":
        if hours_end == "" or int(hours_end) > 23:
            await callback.answer("❌ Введите корректные часы (00-23)!")
            return
        if int(hours_end) < int(hours_start) and data.get("selected_date_start").date() == data.get("selected_date_end").date():
            await callback.answer(f"❌ Часы окончания не могут быть меньше часов начала ({hours_start})!")
            return

        # Минуты = 00
        await state.update_data(hours_end=hours_end, minutes_end="00")
        await callback.message.edit_text("📝 Введите исполнителей работ")
        await state.set_state(Register.personal)
        return
    else:
        if len(hours_end) < 2:
            hours_end += action

    await state.update_data(hours_end=hours_end)
    await callback.message.edit_text(f"⏰ Часы окончания: {hours_end}", reply_markup=fs.number_keyboard("hourend"))

# ввод минут окончания работ
# @router_time.callback_query(F.data.startswith('minuteend_'))
# async def enter_minutes_end(callback: types.CallbackQuery, state: FSMContext):
#     action = callback.data.split("_")[1]
#     data = await state.get_data()  # ✅ Получаем данные из FSMContext
#     minutes_end = data.get("minutes_end", "")
#     selected_date_start = data.get("selected_date_start")  # datetime
#     selected_date_end = data.get("selected_date_end")  # datetime
#     hours_start = data.get('hours_start', '00')
#     hours_end = data.get("hours_end", "")
#     minutes_start = data.get('minutes_start', '00')

#     if len(minutes_end) >= 2 and action not in ["del", "done"]:
#         await callback.answer("Вы не можете ввести более 2 символов для минут!")
#         return

#     if action == "del":
#         if minutes_end:
#             minutes_end = minutes_end[:-1]
#     elif action == "done":
#         if minutes_end == "" or int(minutes_end) > 59:
#             await callback.answer("Введите корректные минуты (00-59)!")
#             return
#         if selected_date_start.date() == selected_date_end.date():
#             if int(hours_start) == int(hours_end):
#                 if int(minutes_end) <= int(minutes_start):
#                     await callback.answer(
#                         f"Неверный ввод (минуты начала: {minutes_start})")
#                     return
#         await callback.message.edit_text('Введите исполнителей работ')
#         await state.set_state(Register.personal)
#         return
#     else:
#         if len(minutes_end) < 2:
#             minutes_end += action
#     # ✅ Обновляем данные в FSMContext
#     await state.update_data(minutes_end=minutes_end)
#     await callback.message.edit_text(f"Минуты: {minutes_end}",
#                                      reply_markup=number_keyboard("minuteend"))


# Шаг 1: Ввод исполнителей работ
@add_router.message(Register.personal)
async def save_workers(message: Message, state: FSMContext):
    workers_input = message.text.strip()
    if not workers_input:
        await message.answer("❗ Пожалуйста, введите хотя бы одного исполнителя.")
        return
    workers_list = [w.strip() for w in workers_input.split(',')]
    await state.update_data(workers=workers_list)

    # Показываем кнопки подтверждения/отмены
    keyboard = confirm_cancel_keyboard("confirm_workers", "cancel_workers")
    await message.answer(
        f"👥 Исполнители: {', '.join(workers_list)}\n"
        "✅ Сохранить или ❌ Отменить?",
        reply_markup=keyboard
    )


@add_router.callback_query(F.data == "confirm_workers")
async def confirm_workers(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()  # удаляем кнопки
    await callback.message.answer("📝 Опишите проблему или неисправность: ")
    await state.set_state(Register.working)


@add_router.callback_query(F.data == "cancel_workers")
async def cancel_workers(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        "❗ Вы отменили выбор исполнителей.\n"
        "👥 Пожалуйста, введите исполнителей работ заново (через запятую):")
    await state.set_state(Register.personal)


# Шаг 2: Описание проблемы
@add_router.message(Register.working)
async def save_work_description(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("❗ Пожалуйста, введите описание проблемы.")
        return
    await state.update_data(work_description=text)

    keyboard = confirm_cancel_keyboard("confirm_work", "cancel_work")
    await message.answer(
        f"📝 Описание проблемы:\n{text}\n\n✅ Сохранить или ❌ Отменить?",
        reply_markup=keyboard
    )
    
    
@add_router.callback_query(F.data == "confirm_work")
async def confirm_work(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("🛠 Введите решение проблемы.")
    await state.set_state(Register.working_solution)


@add_router.callback_query(F.data == "cancel_work")
async def cancel_work(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        "❗ Вы отменили предыдущий ввод.\n"
        "📝 Пожалуйста, опишите проблему: "
    )
    await state.set_state(Register.working)


def get_inventory_number(item_name, items):
    for item in items:
        if item['name'] == item_name:
            return item['inventory_number']
    return None  # Если имя не найдено


# Шаг 3: Решение проблемы
@add_router.message(Register.working_solution)
async def save_work_solution(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("❗ Пожалуйста, введите решение проблемы.")
        return
    await state.update_data(work_solution=text)

    keyboard = confirm_cancel_keyboard("confirm_solution", "cancel_solution")
    await message.answer(
        f"🛠 Решение проблемы:\n{text}\n\n✅ Сохранить или ❌ Отменить?",
        reply_markup=keyboard
    )


@add_router.callback_query(F.data == "confirm_solution")
async def confirm_solution(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("⚙️ Введите статус неисправности.")
    await state.set_state(Register.fault_status)


@add_router.callback_query(F.data == "cancel_solution")
async def cancel_solution(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        "❗ Вы отменили предыдущий ввод.\n"
        "🛠 Пожалуйста, введите решение проблемы заново: ")
    await state.set_state(Register.working_solution)


# Новый handler для fault_status


@add_router.message(Register.fault_status)
async def save_fault_status(message: Message, state: FSMContext):
    fault_status = message.text.strip()
    if not fault_status:  # Валидация: не пустой и не только пробелы
        await message.answer("❗ Пожалуйста, введите статус неисправности (не пустой и без лишних пробелов).")
        return

    await state.update_data(fault_status=fault_status)  # Сохраняем статус
    keyboard = confirm_cancel_keyboard("save_data_fault_status", "cancel_data_fault_status")
    await message.answer(
        f"⚙️ Статус неисправности: {fault_status}\n\n✅ Сохранить или ❌ Отменить?",
        reply_markup=keyboard
    )
    
# Обновленный callback для сохранения после fault_status (переименован из confirm_save_data для "save_data_solution")


@add_router.callback_query(F.data == "save_data_fault_status")
async def confirm_save_data_fault_status(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    workers = data.get('workers', [])
    workers_str = ', '.join(workers) if workers else "Не указаны"
    work_description = data.get('work_description', "Не указано")
    work_solution = data.get('work_solution', 'Не указано')
    fault_status = data.get('fault_status', 'Не указано')
    hours_start = data.get('hours_start', '00')
    minutes_start = data.get('minutes_start', '00')
    hours_end = data.get('hours_end', '00')
    minutes_end = data.get('minutes_end', '00')
    selected_shop = data.get('selected_shop', "Не указан")
    selected_machine = data.get('selected_machine', "Не указан")
    selected_date_start = data.get('selected_date_start')
    selected_date_end = data.get('selected_date_end')

    shop_number = selected_shop.split('-')[0]
    machines_data = fs.load_machines_data()
    existing_machines = machines_data.get(f'maschines_{shop_number}', [])
    inventory_number = get_inventory_number(
        selected_machine, existing_machines)

    start_time = time(int(hours_start), int(minutes_start))
    end_time = time(int(hours_end), int(minutes_end))
    start_datetime = datetime.combine(selected_date_start.date(), start_time)
    end_datetime = datetime.combine(selected_date_end.date(), end_time)
    start_datetime_str = start_datetime.strftime('%d.%m.%Y %H:%M')
    end_datetime_str = end_datetime.strftime('%d.%m.%Y %H:%M')

    duration = end_datetime - start_datetime
    if duration.days < 1:
        duration_hours = duration.total_seconds() // 3600
        duration_minutes = (duration.total_seconds() % 3600) // 60
        result_duration = f"{int(duration_hours)} час {int(duration_minutes)} мин"
    else:
        duration_days = duration.days
        duration_hours = (duration.total_seconds() %
                          (duration_days * 86400)) // 3600
        duration_minutes = (duration.total_seconds() % 3600) // 60
        result_duration = f"{duration_days} дн. {int(duration_hours)} час. {int(duration_minutes)} мин"

    result_message = (
        f"Вы ввели данные: \n"
        f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"📌 <b>Исполнители работ:</b> {workers_str}\n"
        f"📝 <b>Описание проблемы:</b> {work_description}\n"
        f"📝 <b>Решение:</b> {work_solution}\n"
        f"📝 <b>Статус неисправности:</b> {fault_status}\n"
        f"📅 <b>Дата начала:</b> {start_datetime_str}\n"
        f"📅 <b>Дата окончания:</b> {end_datetime_str}\n"
        f"⏳ <b>Затраченное время:</b> {result_duration}\n"
        f"🏭 <b>Цех:</b> {shops.get(selected_shop, 'Не указан')}\n"
        f"🔧 <b>Станок:</b> {selected_machine}\n"
        f"🔢 <b>Инвентарный номер:</b> {inventory_number}\n"
    )

    await callback.message.edit_text(result_message, parse_mode="HTML")


    # Сохранение в SQLite через add_data (асинхронно)
    try:
        await fs.add_data(
            user_id=callback.from_user.id,
            date=datetime.now().strftime('%d.%m.%Y'),
            workers=workers_str, 
            work_description=work_description,
            work_solution=work_solution,
            fault_status=fault_status,
            start_time=start_datetime_str,
            end_time=end_datetime_str,
            duration=result_duration,
            shift=shops.get(selected_shop, 'Не указан'),
            machine=selected_machine,
            inventory_number=inventory_number
        )
        await callback.message.answer("✅ Данные успешно сохранены в базе!", reply_markup=inline_main_menu)
    except Exception as e:
        await callback.message.answer(f"Ошибка сохранения: {e}")

    await state.clear()



# Handler для отмены после fault_status
@add_router.callback_query(F.data == "cancel_data_fault_status")
async def cancel_save_data_fault_status(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()  # Удаляем кнопки
    await callback.message.answer(
        "❗ Вы отменили предыдущий ввод.\n"
        "⚙️ Пожалуйста, введите статус неисправности заново: ")
    await state.set_state(Register.fault_status)
