import asyncio
import json
from asyncio import to_thread 
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import Command

# 🔑 Токен твоего бота
BOT_TOKEN = "7661498802:AAECvAeOcHcx-o66cPYyL82oUMilV5WN41s"

# 🛑 ID ЧАТА ПРЕПОДАВАТЕЛЯ
INSTRUCTOR_CHAT_ID = -5017535091 

# Файл для хранения данных
DATA_FILE = "bot_data.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Константы ---
SCHEDULE_DAYS = [
    "Среда 17:00",
    "Четверг 13:00",
    "Суббота 17:00",
    "Воскресенье 14:00"
]
MAX_PEOPLE = 9

# --- Глобальные переменные для хранения данных ---
# user_info теперь хранит: {user_id: {"name": "Имя Фамилия", "contact": "@username", "goal": "...", "day": "...", "time": "...", "activity": "..."}}
user_info = {} 
schedule = {}  
user_state = {} 

# --- Состояния для Анкеты ---
SURVEY_STATES = {
    "q1_name": "survey_q1_name", # Ввод имени
    "q2_goal": "survey_q2_goal", # Цель
    "q3_day": "survey_q3_day",   # День
    "q4_time": "survey_q4_time", # Время
    "q5_activity": "survey_q5_activity", # Активность
    "q1_contact": "survey_q1_contact" # Ввод контакта (если нет username)
}

# --- Клавиатуры для Анкеты ---
start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Вперед!")]],
    resize_keyboard=True, one_time_keyboard=True
)

goals_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сесть на шпагат"), KeyboardButton(text="Тандюкать как балерина!")],
        [KeyboardButton(text="Стать стройнее и подтянутее"), KeyboardButton(text="Стать сильнее и выносливее")],
        [KeyboardButton(text="Хочу все и сразу!")],
    ],
    resize_keyboard=True, one_time_keyboard=True
)

day_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Выходные дни"), KeyboardButton(text="Будние дни")],
        [KeyboardButton(text="Могу в любой день!")],
    ],
    resize_keyboard=True, one_time_keyboard=True
)

time_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Вечер(18-20часов)"), KeyboardButton(text="Обеденное время(12-13часов)")],
        [KeyboardButton(text="День(14-16)"), KeyboardButton(text="Всегда готов!")],
    ],
    resize_keyboard=True, one_time_keyboard=True
)

activity_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Пуанты"), KeyboardButton(text="Растяжка")],
        [KeyboardButton(text="Силовые тренировки"), KeyboardButton(text="Занятия на валике МФР")],
    ],
    resize_keyboard=True, one_time_keyboard=True
)

# --- Главная клавиатура (ОБНОВЛЕНА) ---
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🩰 Записаться на занятие"), KeyboardButton(text="⭐ Индивидуальное занятие")], 
        [KeyboardButton(text="❌ Отменить запись"), KeyboardButton(text="💰 Узнать стоимость")] # НОВАЯ КНОПКА
    ],
    resize_keyboard=True
)

# --- <--- ФУНКЦИИ ДЛЯ ХРАНЕНИЯ ДАННЫХ (JSON) ---> ---

def load_data():
    """
    Загружает данные из файла.
    Важно: Преобразует строковые ключи user_id в числа (int) для корректной работы.
    """
    global user_info, schedule
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            loaded_user_info = data.get("user_info", {})
            # ПРЕОБРАЗОВАНИЕ: Ключи-ID из строки (JSON) в число (Python)
            user_info = {int(k): v for k, v in loaded_user_info.items()} 
            
            schedule = data.get("schedule", {day: [] for day in SCHEDULE_DAYS})
            for day in SCHEDULE_DAYS:
                if day not in schedule:
                    schedule[day] = []
    except FileNotFoundError:
        print("Файл данных не найден, создаю новые структуры.")
        user_info = {}
        schedule = {day: [] for day in SCHEDULE_DAYS}
    except Exception as e:
        print(f"Ошибка при чтении JSON: {e}")
        user_info = {}
        schedule = {day: [] for day in SCHEDULE_DAYS}

def save_data():
    """Сохраняет данные в файл."""
    global user_info, schedule
    data = {"user_info": user_info, "schedule": schedule}
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        # indent=4 для красивого форматирования файла
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- <--- ФУНКЦИИ УДАЛЕНИЯ И ОТЧЕТОВ ---> ---

def delete_user_from_all(user_id: int):
    """Синхронно удаляет пользователя из user_info и всех записей в schedule, затем сохраняет."""
    global user_info, schedule
    
    # 1. Удаляем из анкет
    if user_id in user_info:
        del user_info[user_id]
    
    # 2. Удаляем из расписания
    for day in schedule:
        if user_id in schedule[day]:
            schedule[day].remove(user_id)
            
    # 3. Сохраняем данные
    save_data()

async def get_instructor_report(action: str, day: str, user_id: int):
    """Формирует и отправляет отчет преподавателю о единичном событии (запись/отмена/заявка)."""
    global user_info, schedule
    
    profile = user_info.get(user_id, {"name": "Неизвестный пользователь", "contact": "Нет контакта"})
    name = profile['name']
    contact = profile['contact']
    
    if action == "ИНДИВИДУАЛЬНАЯ ЗАЯВКА":
        report_text = f"⭐ *НОВАЯ ЗАЯВКА НА ИНДИВИДУАЛЬНОЕ ЗАНЯТИЕ* ⭐\n\n"
        report_text += f"**Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report_text += f"**Клиент:** {name}\n"
        report_text += f"**Контакт:** {contact}\n\n"
        report_text += f"Напишите клиенту в ЛС для обсуждения деталей."
    
    else: 
        current_attendees = [user_info.get(uid, {}).get("name", "N/A") for uid in schedule.get(day, [])]
        count = len(current_attendees)
        
        report_text = f"🚨 *НОВОЕ СОБЫТИЕ: {action}* 🚨\n\n"
        report_text += f"**Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report_text += f"**Занятие:** {day}\n"
        report_text += f"**Клиент:** {name} ({contact})\n"
        
        if action == "ЗАПИСЬ":
            report_text += f"✅ **СТАТУС:** Записан успешно\n"
            report_text += f"**Мест занято:** {count}/{MAX_PEOPLE}\n\n"
        elif action == "ОТМЕНА":
            report_text += f"❌ **СТАТУС:** Запись отменена\n"
            report_text += f"**Мест занято:** {count}/{MAX_PEOPLE}\n\n"
            
        report_text += f"--- *Текущий список на {day}* ---\n"
        if current_attendees:
            for i, att_name in enumerate(current_attendees, 1):
                report_text += f"{i}. {att_name}\n"
        else:
            report_text += "Список пуст.\n"

    if INSTRUCTOR_CHAT_ID != 000000000:
        try:
            await bot.send_message(
                chat_id=INSTRUCTOR_CHAT_ID,
                text=report_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка при отправке отчета преподавателю: {e}")

async def send_survey_report(user_id: int):
    """Формирует и отправляет полный отчет анкеты преподавателю."""
    global user_info
    
    profile = user_info.get(user_id, {})
    
    report_text = f"📄 *НОВАЯ АНКЕТА ЗАПОЛНЕНА* 📄\n\n"
    report_text += f"**Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report_text += f"**----------------------------------------**\n"
    
    report_text += f"**1. Имя и фамилия:** {profile.get('name', 'N/A')}\n"
    report_text += f"**2. Контакт (username/тел):** {profile.get('contact', 'N/A')}\n"
    report_text += f"**3. Цели от тренировок:** {profile.get('goal', 'N/A')}\n"
    report_text += f"**4. Подходящий день:** {profile.get('day', 'N/A')}\n"
    report_text += f"**5. Подходящее время:** {profile.get('time', 'N/A')}\n"
    report_text += f"**6. Что хочется попробовать:** {profile.get('activity', 'N/A')}\n"
    
    report_text += f"**----------------------------------------**\n"
    
    if INSTRUCTOR_CHAT_ID != 000000000:
        try:
            await bot.send_message(
                chat_id=INSTRUCTOR_CHAT_ID,
                text=report_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка при отправке отчета анкеты преподавателю: {e}")


async def generate_full_report_text():
    # ... (функция generate_full_report_text без изменений, кроме одного: убрано "Мест свободно" в if count == 0)
    global user_info, schedule
    
    total_registrations = sum(len(ids) for ids in schedule.values())
    report_parts = [f"📊 *ПОЛНЫЙ ОТЧЕТ ПО ЗАПИСЯМ* 📊\n"]
    report_parts.append(f"Дата создания отчета: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    if total_registrations == 0:
        report_parts.append("\n*Активных записей нет.*")
        return "\n".join(report_parts)

    for day in SCHEDULE_DAYS:
        attendees = schedule.get(day, [])
        count = len(attendees)
        
        report_parts.append("\n" + "-" * 30)
        report_parts.append(f"**{day} ({count}/{MAX_PEOPLE})**")
        report_parts.append("-" * 30)
        
        if count == 0:
            report_parts.append("Никто не записан")
        else:
            for i, user_id in enumerate(attendees, 1):
                profile = user_info.get(user_id, {})
                name = profile.get("name", "N/A")
                contact = profile.get("contact", "N/A")
                
                report_parts.append(f"{i}. {name} | Контакт: {contact}")
        

    return "\n".join(report_parts)

# --- <--- ХЕНДЛЕР СЕКРЕТНОЙ КОМАНДЫ (ТОЛЬКО ДЛЯ ПРЕПОДАВАТЕЛЯ) ---> ---

@dp.message(Command("report"))
async def instructor_report_cmd(message: types.Message):
    # Фильтр: работает только для INSTRUCTOR_CHAT_ID
    if message.chat.id != INSTRUCTOR_CHAT_ID:
        await message.answer("Неизвестная команда.")
        return

    report_text = await generate_full_report_text()
    
    await message.answer(
        report_text,
        parse_mode="Markdown"
    )
    await message.answer("👆 Это актуальный отчет. Просто используйте команду `/report` в любой момент.")


@dp.message(Command("deluser"))
async def deluser_cmd(message: types.Message):
    # Фильтр: работает только для INSTRUCTOR_CHAT_ID
    if message.chat.id != INSTRUCTOR_CHAT_ID:
        await message.answer("Неизвестная команда.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Пожалуйста, укажи имя, фамилию или контакт (например, @username) для удаления.\n\n"
            "Пример: `/deluser Иван Смирнов` или `/deluser @ivan_s`",
            parse_mode="Markdown"
        )
        return

    search_query = args[1].strip().lower()
    user_to_delete_id = None
    user_name = None
    
    # Ищем пользователя по имени/контакту
    for user_id, profile in user_info.items():
        name = profile.get("name", "").lower()
        contact = profile.get("contact", "").lower()
        
        if search_query == name or search_query == contact:
            user_to_delete_id = user_id
            user_name = profile.get("name")
            break

    if user_to_delete_id:
        await asyncio.to_thread(delete_user_from_all, user_to_delete_id)
        
        await message.answer(
            f"✅ Пользователь *{user_name}* (ID: `{user_to_delete_id}`) успешно удален из списка клиентов и из всех записей.",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"❌ Пользователь по запросу '{search_query}' не найден в базе данных. Проверьте правильность написания.",
            parse_mode="Markdown"
        )


# --- <--- ОСНОВНЫЕ ХЭНДЛЕРЫ БОТА ---> ---

# --- /start (ОБНОВЛЕН) ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    
    # Проверка: если у пользователя есть цель ("goal"), значит, он завершил анкету
    if user_id in user_info and user_info[user_id].get("goal"): 
        await message.answer(
            "Привет! С возвращением! Выберите действие ниже 👇",
            reply_markup=main_kb
        )
    else:
        # Новый пользователь или не завершил анкету
        user_state[user_id] = {"state": "initial_start", "temp_profile": {}}
        
        await message.answer(
            "Привет! Я бот для записи на занятия балетом *FONDU, Кать!* 💃\n\n"
            "Пожалуйста, ответьте на несколько вопросов!",
            reply_markup=start_kb,
            parse_mode="Markdown"
        )

# --- "⭐ Индивидуальное занятие" ---
@dp.message(F.text == "⭐ Индивидуальное занятие")
async def handle_individual_request(message: types.Message):
    user_id = message.from_user.id
    user_profile = user_info.get(user_id)
    
    if not (user_id in user_info and user_info[user_id].get("goal")):
        await message.answer("Сначала, пожалуйста, заполните анкету через команду /start.")
        return

    if user_profile:
        await send_individual_request(message, user_id, user_profile)
    else:
        # Это не должно произойти после анкеты, но как защита
        await message.answer("Ваши данные не найдены. Попробуйте команду /start.")


async def send_individual_request(message: types.Message, user_id: int, user_profile: dict):
    """Отправляет заявку преподавателю и подтверждение пользователю."""
    
    await get_instructor_report("ИНДИВИДУАЛЬНАЯ ЗАЯВКА", "N/A", user_id)
    
    await message.answer(
        f"✅ *{user_profile['name']}*, Ваша заявка на индивидуальное занятие отправлена преподавателю!\n\n"
        "Ожидайте, скоро с Вами свяжутся для уточнения деталей. 🩰",
        parse_mode="Markdown",
        reply_markup=main_kb
    )

# --- "Записаться на занятие" ---
@dp.message(F.text == "🩰 Записаться на занятие")
async def choose_day(message: types.Message):
    user_id = message.from_user.id

    if not (user_id in user_info and user_info[user_id].get("goal")):
        await message.answer("Сначала, пожалуйста, заполните анкету через команду /start.")
        return
        
    buttons = []
    
    my_registrations = await asyncio.to_thread(get_user_registrations, user_id)
    
    for day in SCHEDULE_DAYS:
        attendees = schedule.get(day, [])
        count = len(attendees)
        
        text = f"{day} ({count}/{MAX_PEOPLE})"
        
        if day in my_registrations:
            text += " (Вы записаны ✅)"
            
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"day_{day}")])

    ikb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите день занятия:", reply_markup=ikb)

# --- "💰 Узнать стоимость" (НОВЫЙ ХЕНДЛЕР) ---
@dp.message(F.text == "💰 Узнать стоимость")
async def show_prices(message: types.Message):
    user_id = message.from_user.id
    if not (user_id in user_info and user_info[user_id].get("goal")):
        await message.answer("Сначала, пожалуйста, заполните анкету через команду /start.")
        return

    # Инлайн-кнопка "Назад"
    back_ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main_menu")]
    ])

    price_text = (
        "▫️ *Первое занятие* — бесплатно!\n"
        "▫️ *Групповое занятие* — 600₽\n"
        "▫️ *Индивидуальное занятие* — 1600₽\n"
    )
    
    await message.answer(price_text, reply_markup=back_ikb, parse_mode="Markdown")


# --- "Отменить запись" и остальные хендлеры (без изменений) ---

@dp.message(F.text == "❌ Отменить запись")
async def show_cancellations(message: types.Message):
    user_id = message.from_user.id

    if not (user_id in user_info and user_info[user_id].get("goal")):
        await message.answer("Сначала, пожалуйста, заполните анкету через команду /start.")
        return

    my_registrations = await asyncio.to_thread(get_user_registrations, user_id)
    
    if not my_registrations:
        await message.answer("У Вас нет активных записей.", reply_markup=main_kb)
        return

    buttons = []
    for day in my_registrations:
        buttons.append([InlineKeyboardButton(
            text=f"Отменить: {day}", 
            callback_data=f"cancel_{day}"
        )])
    
    ikb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Какую запись Вы хотите отменить?", reply_markup=ikb)

@dp.callback_query(F.data.startswith("day_"))
async def handle_day_choice(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    day = callback.data.replace("day_", "")

    if not (user_id in user_info and user_info[user_id].get("goal")):
        await callback.message.answer("Сначала, пожалуйста, заполните анкету через команду /start.")
        await callback.answer()
        return

    if day not in SCHEDULE_DAYS:
        await callback.message.answer("Этот день больше не доступен.")
        await callback.answer()
        return

    attendees = schedule.get(day, [])
    if len(attendees) >= MAX_PEOPLE:
        await callback.message.answer(f"🚫 На {day} мест больше нет!")
        await callback.answer()
        return
        
    if user_id in attendees:
        await callback.message.answer(f"⚠️ Вы уже записаны на {day} 😊")
        await callback.answer()
        return

    user_state[user_id] = {"current_day": day}
    user_profile = user_info.get(user_id)
    
    # После анкеты user_profile всегда будет полным
    await callback.message.answer(f"Записываю Вас (как {user_profile['name']}) на {day}...")
    await finalize_registration(callback.message, user_id, user_profile) 
    
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_"))
async def handle_cancel_choice(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    day = callback.data.replace("cancel_", "")

    attendees = schedule.get(day, [])
    
    if user_id in attendees:
        attendees.remove(user_id)
        await asyncio.to_thread(save_data)
        
        user_profile = user_info.get(user_id)
        name = user_profile['name'] if user_profile else "Вы"
            
        await callback.message.edit_text(f"✅ *{name}*, Ваша запись на {day} отменена.", parse_mode="Markdown")
        await callback.answer("Запись отменена!")
        
        await get_instructor_report("ОТМЕНА", day, user_id)
        
        registrations_list_text = await asyncio.to_thread(get_registrations_text_for_user, user_id)
        
        await callback.message.answer(
            registrations_list_text,
            parse_mode="Markdown",
            reply_markup=main_kb
        )
        
    else:
        await callback.message.edit_text("Вашей записи на этот день уже нет.")
        await callback.answer("Запись уже отменена")


# --- "Назад" из меню "Узнать стоимость" (НОВЫЙ КОЛБЭК) ---
@dp.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery):
    # 1. Удаляем сообщение с ценами
    await callback.message.delete()
    
    # 2. Возвращаем сообщение с главным меню
    await callback.message.answer(
        "Теперь Вы можете записаться на занятия(временное расписание) или оставить заявку на индивидуальный урок 👇",
        reply_markup=main_kb
    )
    
    # 3. Отвечаем на колбэк
    await callback.answer()


# --- Получаем ответы Анкеты (ОБНОВЛЕН) ---
@dp.message(F.text)
async def process_user_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # 🛑 Разрешаем преподавателю использовать команды /report и /deluser
    if user_id == INSTRUCTOR_CHAT_ID:
        if text == "/report":
            await instructor_report_cmd(message)
            return
        if text.startswith("/deluser"):
            await deluser_cmd(message)
            return

    if user_id not in user_state or "state" not in user_state[user_id]:
        # Если нет активного состояния анкеты или записи
        await message.answer("Я не понял. Воспользуйтесь кнопками 👇", reply_markup=main_kb)
        return

    state = user_state[user_id]["state"]

    # --- 0. Начало анкеты: Нажата кнопка "Вперед!" ---
    if state == "initial_start" and text == "Вперед!":
        user_state[user_id]["state"] = SURVEY_STATES["q1_name"]
        # Используем ReplyKeyboardRemove, чтобы убрать кнопку "Вперед!"
        await message.answer("Отлично! Введите, пожалуйста, Ваше *имя и фамилию* :", 
                             reply_markup=ReplyKeyboardRemove(),
                             parse_mode="Markdown")
        return

    # --- Q1. Ввод Имени и Фамилии ---
    if state == SURVEY_STATES["q1_name"]:
        user_state[user_id]["temp_profile"]["name"] = text
        username = message.from_user.username
        
        if username:
            user_state[user_id]["temp_profile"]["contact"] = f"@{username}"
            user_state[user_id]["state"] = SURVEY_STATES["q2_goal"]
            
            # Переход к Q2
            await message.answer("Спасибо! Что Вы хотите получить от наших тренировок? (выберите вариант ниже)",
                                 reply_markup=goals_kb)
        else:
            user_state[user_id]["state"] = SURVEY_STATES["q1_contact"]
            await message.answer("У Вас нет username. Пожалуйста, отправьте номер телефона 📞")
        return

    # --- Q1-Contact. Ввод Контакта (если нет username) ---
    if state == SURVEY_STATES["q1_contact"]:
        phone = text
        if phone.startswith("+") and phone[1:].isdigit():
            user_state[user_id]["temp_profile"]["contact"] = phone
            user_state[user_id]["state"] = SURVEY_STATES["q2_goal"]
            
            # Переход к Q2
            await message.answer("Спасибо! Что Вы хотите получить от наших тренировок? (выберите вариант ниже)",
                                 reply_markup=goals_kb)
        else:
            await message.answer("❌ Номер некорректен. Попробуйте снова, например: +79123456789")
        return

    # --- Q2. Выбор Цели ---
    if state == SURVEY_STATES["q2_goal"] and text in [b.text for row in goals_kb.keyboard for b in row]:
        user_state[user_id]["temp_profile"]["goal"] = text
        user_state[user_id]["state"] = SURVEY_STATES["q3_day"]
        
        # Переход к Q3
        await message.answer("Какой день Вам удобнее заниматься?", reply_markup=day_kb)
        return

    # --- Q3. Выбор Дня ---
    if state == SURVEY_STATES["q3_day"] and text in [b.text for row in day_kb.keyboard for b in row]:
        user_state[user_id]["temp_profile"]["day"] = text
        user_state[user_id]["state"] = SURVEY_STATES["q4_time"]

        # Переход к Q4
        await message.answer("В какое время Вам удобно заниматься?", reply_markup=time_kb)
        return

    # --- Q4. Выбор Времени ---
    if state == SURVEY_STATES["q4_time"] and text in [b.text for row in time_kb.keyboard for b in row]:
        user_state[user_id]["temp_profile"]["time"] = text
        user_state[user_id]["state"] = SURVEY_STATES["q5_activity"]

        # Переход к Q5
        await message.answer("Что бы хотелось включить в тренировку?", reply_markup=activity_kb)
        return
    
    # --- Q5. Выбор Активности (Завершение) ---
    if state == SURVEY_STATES["q5_activity"] and text in [b.text for row in activity_kb.keyboard for b in row]:
        user_state[user_id]["temp_profile"]["activity"] = text
        
        # 1. Финализация данных и сохранение
        user_info[user_id] = user_state[user_id]["temp_profile"]
        user_state.pop(user_id) # Очищаем состояние
        await asyncio.to_thread(save_data)
        
        # 2. Отчет преподавателю
        await send_survey_report(user_id)
        
        # 3. Сообщение пользователю и переход к основному меню
        await message.answer("Ура! Анкета заполнена! 🎉", reply_markup=ReplyKeyboardRemove())
        await message.answer(
            "Теперь Вы можете записаться на занятия(временное расписание) или оставить заявку на индивидуальный урок 👇",
            reply_markup=main_kb
        )
        return

    # Если бот ожидает ответа кнопкой, но получил неверный текст
    if state in [SURVEY_STATES["q2_goal"], SURVEY_STATES["q3_day"], SURVEY_STATES["q4_time"], SURVEY_STATES["q5_activity"]]:
        await message.answer("Пожалуйста, выберите один из предложенных вариантов на клавиатуре.")
        return
        
    await message.answer("Непонятное действие. Используйте кнопки.", reply_markup=main_kb)


# --- Вспомогательная функция (формирует текст) ---
def get_registrations_text_for_user(user_id: int) -> str:
    """Собирает список всех записей пользователя в виде текста."""
    my_registrations = get_user_registrations(user_id)
    
    if not my_registrations:
        return "У Вас не осталось активных записей."
        
    response_text = "--- *Ваши текущие записи* ---\n"
    for reg_day in my_registrations:
        response_text += f"• {reg_day}\n"
    return response_text

# --- Вспомогательная функция (ищет записи) ---
def get_user_registrations(user_id: int) -> list:
    """Возвращает список дней, на которые записан юзер."""
    global schedule
    days = []
    for day, user_id_list in schedule.items():
        if user_id in user_id_list:
            days.append(day)
    return sorted(days)


# --- Завершение регистрации ---
async def finalize_registration(message: types.Message, user_id: int, user_profile: dict):
    if user_id not in user_state or "current_day" not in user_state[user_id]:
        await message.answer("Произошла ошибка, попробуйте выбрать день заново.", reply_markup=main_kb)
        return

    day = user_state[user_id].pop("current_day") 
    
    attendees = schedule.get(day, [])
    if len(attendees) >= MAX_PEOPLE or user_id in attendees:
        await message.answer(f"⚠️ Вы уже записаны или мест больше нет на {day} 😊", reply_markup=main_kb)
        return

    schedule[day].append(user_id)
    
    await asyncio.to_thread(save_data)
    
    count = len(schedule[day])
    
    await get_instructor_report("ЗАПИСЬ", day, user_id)
    
    registrations_list_text = get_registrations_text_for_user(user_id)
            
    response_text = (
        f"✅ *{user_profile['name']}*, Вы успешно записаны на {day}!\n"
        f"Мест занято на {day}: {count}/{MAX_PEOPLE}.\n\n"
        f"{registrations_list_text}"
    )
    
    await message.answer(
        response_text,
        parse_mode="Markdown",
        reply_markup=main_kb 
    )

# --- Функция синхронного сохранения перед остановкой ---
def on_shutdown_sync():
    """Синхронно сохраняет данные при получении сигнала остановки (Ctrl+C)."""
    print("--- Бот завершает работу. Синхронно сохраняю последние данные... ---")
    save_data()
    print("--- Данные сохранены. Завершение. ---")


# --- Запуск ---
async def main():
    print("Бот запущен...")
    
    # 1. Загружаем данные из JSON при старте
    await to_thread(load_data)
    print(f"✅ Данные загружены. Пользователей: {len(user_info)}. Расписание: {sum(len(v) for v in schedule.values())} записей.")
    
    # 2. Регистрируем хук для сохранения данных при остановке 
    dp.shutdown.register(on_shutdown_sync)
    
    # 3. Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())