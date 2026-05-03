import asyncio
import logging
import random
from datetime import datetime, date, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite
import pytz  # Для работы с часовыми поясами

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("TOKEN") # Бот возьмет токен из настроек Railway
DB_NAME = "club.db"
MSK_TZ = pytz.timezone('Europe/Moscow')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- МАШИНА СОСТОЯНИЙ (FSM) ---
class SportWizard(StatesGroup):
    energy = State()       
    time = State()         
    inventory = State()    
    position = State()     
    zone = State()         

class WeightState(StatesGroup):
    waiting_for_weight = State()

class PhotoState(StatesGroup):
    waiting_for_photo = State()

# --- ФРАЗЫ ПОДДЕРЖКИ ---
SUPPORT_PHRES = [
    "Ты сияешь! Каждый день ты становишься лучше! ✨",
    "Я восхищаюсь твоим упорством! 🌸",
    "Твое тело благодарит тебя за заботу! 💖",
    "Ты делаешь огромные шаги к своей мечте! 👣",
    "Помни: ты прекрасна в любом весе! 🦋",
    "Твой прогресс — это твоя личная победа! 🏆",
    "С каждым днем ты всё ближе к цели! 🎯",
    "Ты заслуживаешь любви и заботы прямо сейчас! 🌷",
    "Твои усилия не пройдут даром! Верь в себя! 🌟",
    "Ты сильная, красивая и невероятная! 💪",
    "Маленькие шаги приводят к большим результатам! 🐢➡️🏁",
    "Ты вдохновляешь меня! Продолжай в том же духе! 🔥",
    "Твое здоровье — главный приоритет, и ты справляешься! 🍏",
    "Посмотри, какой путь ты уже прошла! Гордись собой! 🛤️",
    "Ты — чудо! Не забывай об этом! 🧚‍♀️"
]

# --- БАЗА ДАННЫХ ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id BIGINT UNIQUE,
                name TEXT,
                username TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                habit_type TEXT,
                target_value TEXT,
                reminder_hours INTEGER,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                log_date DATE,
                log_type TEXT,
                value TEXT,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        await db.commit()
    print("База данных готова! 🌿")

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💧 Трекер воды", callback_data="habit_water")
    builder.button(text="🧘‍♀️ Фитнес-помощник", callback_data="habit_sport")
    builder.button(text="⚖️ Мой вес", callback_data="results_weight")
    builder.button(text="📸 Фото-дневник", callback_data="results_photo")
    builder.button(text="🖼️ Мой архив фото", callback_data="photo_archive")
    builder.button(text="🌸 Профиль", callback_data="profile")
    builder.adjust(2, 2, 2)
    return builder.as_markup()

def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="main_menu")
    return builder.adjust(1).as_markup()

def get_energy_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔋 Полна энергии!", callback_data="sport_energy_high")
    builder.button(text="😌 Спокойствие", callback_data="sport_energy_low")
    builder.button(text="😴 Устала/Боль", callback_data="sport_energy_rest")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_time_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⏱ 5-10 мин", callback_data="sport_time_short")
    builder.button(text="⏱ 15-20 мин", callback_data="sport_time_medium")
    builder.button(text="⏱ 30+ мин", callback_data="sport_time_long")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_inventory_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🧘‍♀️ Только коврик/пол", callback_data="sport_inv_none")
    builder.button(text="🏋️ Гантели/Бутылки", callback_data="sport_inv_weights")
    builder.button(text="🎀 Резинки", callback_data="sport_inv_bands")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_position_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛌 Лежа", callback_data="sport_pos_lying")
    builder.button(text="🧍 Стоя", callback_data="sport_pos_standing")
    builder.button(text="🪑 Сидя", callback_data="sport_pos_sitting")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_zone_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🦵 Ноги и ягодицы", callback_data="sport_zone_legs")
    builder.button(text="🧠 Спина и шея", callback_data="sport_zone_back")
    builder.button(text="🔥 Пресс", callback_data="sport_zone_abs")
    builder.button(text="🌀 Все тело", callback_data="sport_zone_full")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# --- ПРОВЕРКА НОЧНОГО РЕЖИМА (МСК) ---
def is_night_time():
    now_msk = datetime.now(MSK_TZ)
    return now_msk.hour >= 22 or now_msk.hour < 8

# --- БЕЗОПАСНОЕ РЕДАКТИРОВАНИЕ ---
async def safe_edit_message(callback: CallbackQuery, text: str, markup=None, parse_mode="HTML"):
    try:
        if markup:
            await callback.message.edit_text(text, reply_markup=markup, parse_mode=parse_mode)
        else:
            await callback.message.edit_text(text, parse_mode=parse_mode)
    except Exception as e:
        error_str = str(e)
        if "message is not modified" in error_str:
            pass 
        elif "there is no text" in error_str:
            if markup:
                await callback.message.answer(text, reply_markup=markup, parse_mode=parse_mode)
            else:
                await callback.message.answer(text, parse_mode=parse_mode)
        else:
            logging.error(f"Ошибка редактирования: {e}")
            await callback.answer("Обновляю...", show_alert=False)

# --- АВТОМАТИЧЕСКИЕ РАССЫЛКИ ---
async def send_weekly_report():
    """Отчет каждое воскресенье в 20:00 МСК"""
    async with aiosqlite.connect(DB_NAME) as db:
        res = await db.execute("SELECT telegram_id FROM users")
        users = await res.fetchall()
    
    today = date.today()
    # Начало недели (понедельник)
    start_of_week = today - timedelta(days=today.weekday())
    
    for (user_id,) in users:
        try:
            # Вода за неделю
            res_w = await db.execute(
                "SELECT COUNT(*) FROM logs WHERE user_id=? AND log_type='water' AND log_date>=?",
                (user_id, start_of_week.isoformat())
            )
            water_count = (await res_w.fetchone())[0]
            
            # Спорт за неделю
            res_s = await db.execute(
                "SELECT COUNT(*) FROM logs WHERE user_id=? AND log_type='sport' AND log_date>=?",
                (user_id, start_of_week.isoformat())
            )
            sport_count = (await res_s.fetchone())[0]
            
            # Вес (последний за неделю)
            res_wt = await db.execute(
                "SELECT value FROM logs WHERE user_id=? AND log_type='weight' AND log_date>=? ORDER BY log_date DESC LIMIT 1",
                (user_id, start_of_week.isoformat())
            )
            last_weight_row = await res_wt.fetchone()
            weight_text = f"{last_weight_row[0]} кг" if last_weight_row else "нет записей"

            text = (
                f"🌸 <b>Итоги недели!</b>\n\n"
                f"Ты большая молодец! Вот что удалось за эти 7 дней:\n"
                f"💧 Выпито воды: {water_count} стаканов\n"
                f"🧘‍♀️ Тренировок: {sport_count}\n"
                f"⚖️ Последний вес: {weight_text}\n\n"
                f"Продолжай сиять! ✨"
            )
            await bot.send_message(user_id, text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка отправки недельного отчета пользователю {user_id}: {e}")

async def send_monthly_report():
    """Отчет 1-го числа каждого месяца"""
    async with aiosqlite.connect(DB_NAME) as db:
        res = await db.execute("SELECT telegram_id FROM users")
        users = await res.fetchall()
    
    today = date.today()
    # Первый день текущего месяца
    start_of_month = today.replace(day=1)
    
    for (user_id,) in users:
        try:
            # Вода за месяц
            res_w = await db.execute(
                "SELECT COUNT(*) FROM logs WHERE user_id=? AND log_type='water' AND log_date>=?",
                (user_id, start_of_month.isoformat())
            )
            water_count = (await res_w.fetchone())[0]
            
            # Спорт за месяц
            res_s = await db.execute(
                "SELECT COUNT(*) FROM logs WHERE user_id=? AND log_type='sport' AND log_date>=?",
                (user_id, start_of_month.isoformat())
            )
            sport_count = (await res_s.fetchone())[0]
            
            # Вес
            res_wt = await db.execute(
                "SELECT value FROM logs WHERE user_id=? AND log_type='weight' AND log_date>=? ORDER BY log_date DESC LIMIT 1",
                (user_id, start_of_month.isoformat())
            )
            last_weight_row = await res_wt.fetchone()
            weight_text = f"{last_weight_row[0]} кг" if last_weight_row else "нет записей"

            text = (
                f"🗓️ <b>Отчет за месяц!</b>\n\n"
                f"Новый месяц — новые победы! Твои результаты:\n"
                f"💧 Выпито воды: {water_count} стаканов\n"
                f"🧘‍♀️ Тренировок: {sport_count}\n"
                f"⚖️ Вес: {weight_text}\n\n"
                f"Горжусь тобой! 🏆"
            )
            await bot.send_message(user_id, text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка отправки месячного отчета пользователю {user_id}: {e}")

async def scheduler():
    """Фоновая задача для проверки времени рассылок"""
    while True:
        now_msk = datetime.now(MSK_TZ)
        
        # Проверка: Воскресенье (weekday 6) и 20:00
        if now_msk.weekday() == 6 and now_msk.hour == 20 and now_msk.minute == 0:
            logging.info("Запуск недельного отчета...")
            await send_weekly_report()
            await asyncio.sleep(65) # Ждем минуту, чтобы не отправить дважды
            
        # Проверка: 1-е число месяца и 09:00 (утром приятнее читать)
        if now_msk.day == 1 and now_msk.hour == 9 and now_msk.minute == 0:
            logging.info("Запуск месячного отчета...")
            await send_monthly_report()
            await asyncio.sleep(65)
            
        await asyncio.sleep(30) # Проверяем каждые 30 секунд

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, name, username) VALUES (?, ?, ?)",
            (message.from_user.id, message.from_user.first_name, message.from_user.username)
        )
        await db.commit()
    text = (
        f"Привет, {message.from_user.first_name}! 🌸\n\n"
        f"Добро пожаловать в твой личный сад красоты.\n"
        f"Здесь мы бережно формируем привычки и отслеживаем результаты.\n\n"
        f"Выбери, чем займемся сегодня:"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "main_menu")
async def go_main(callback: CallbackQuery):
    text = "Главное меню. Выбери действие:"
    await safe_edit_message(callback, text, get_main_keyboard())

# ================= ВОДА =================

@dp.callback_query(F.data == "habit_water")
async def water_habit(callback: CallbackQuery):
    user_id = callback.from_user.id
    # Используем дату в формате YYYY-MM-DD для сравнения
    today = date.today().isoformat()
    
    async with aiosqlite.connect(DB_NAME) as db:
        # Считаем количество записей за сегодня
        res = await db.execute(
            "SELECT COUNT(*) FROM logs WHERE user_id = ? AND log_date = ? AND log_type = 'water'",
            (user_id, today)
        )
        count = (await res.fetchone())[0]
        
        # Статистика за неделю (с понедельника)
        today_obj = date.today()
        start_week = today_obj - timedelta(days=today_obj.weekday())
        res_week = await db.execute(
            "SELECT COUNT(*) FROM logs WHERE user_id = ? AND log_type = 'water' AND log_date >= ?",
            (user_id, start_week.isoformat())
        )
        count_week = (await res_week.fetchone())[0]

        # Статистика за месяц (с 1 числа)
        start_month = today_obj.replace(day=1)
        res_month = await db.execute(
            "SELECT COUNT(*) FROM logs WHERE user_id = ? AND log_type = 'water' AND log_date >= ?",
            (user_id, start_month.isoformat())
        )
        count_month = (await res_month.fetchone())[0]
    
    text = (
        f"💧 <b>Трекер воды</b>\n\n"
        f"🥤 Сегодня: {count} стаканов\n"
        f"📅 За неделю: {count_week} стаканов\n"
        f"🗓️ За месяц: {count_month} стаканов\n\n"
        f"Цель на день: 8 стаканов."
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🥤 +1 Стакан", callback_data="water_add_1")
    if count > 0:
        kb.button(text="↩️ Отменить последний", callback_data="water_remove_1")
    kb.button(text="🔙 Назад", callback_data="main_menu")
    kb.adjust(1)
    
    await safe_edit_message(callback, text, kb.as_markup())

@dp.callback_query(F.data == "water_add_1")
async def water_add(callback: CallbackQuery):
    user_id = callback.from_user.id
    today = date.today().isoformat()
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO logs (user_id, log_date, log_type, value) VALUES (?, ?, 'water', '1')",
            (user_id, today)
        )
        await db.commit()
    
    await callback.answer("Записала! Ты молодец! 💧", show_alert=True)
    await water_habit(callback)

@dp.callback_query(F.data == "water_remove_1")
async def water_remove(callback: CallbackQuery):
    user_id = callback.from_user.id
    today = date.today().isoformat()
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM logs WHERE rowid = (SELECT MAX(rowid) FROM logs WHERE user_id = ? AND log_date = ? AND log_type = 'water')",
            (user_id, today)
        )
        await db.commit()
        
    await callback.answer("Удалила последний стакан.", show_alert=True)
    await water_habit(callback)

# ================= СПОРТ =================
# (Логика спорта без изменений, кроме импортов)

@dp.callback_query(F.data == "habit_sport")
async def sport_start(callback: CallbackQuery):
    if is_night_time():
        text = (
            "🌙 <b>Тихий час</b>\n\n"
            "Уже поздно, чтобы не беспокоить тебя, я могу сохранить заявку на утро.\n"
            "Хочешь запланировать тренировку на 08:00?"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Да, разбуди меня", callback_data="sport_schedule_morning")
        kb.button(text="❌ Нет, просто меню", callback_data="sport_menu_now")
        kb.button(text="🔙 Назад", callback_data="main_menu")
        kb.adjust(1)
        await safe_edit_message(callback, text, kb.as_markup())
    else:
        text = "🧘‍♀️ <b>Фитнес-помощник</b>\n\nКак ты себя чувствуешь прямо сейчас?"
        await safe_edit_message(callback, text, get_energy_keyboard())

@dp.callback_query(F.data == "sport_schedule_morning")
async def sport_schedule(callback: CallbackQuery):
    await safe_edit_message(callback, "✨ Договорились! Напомню завтра в 08:00. Спокойной ночи! 🌙")

@dp.callback_query(F.data == "sport_menu_now")
async def sport_menu_now(callback: CallbackQuery):
    text = "🧘‍♀️ <b>Фитнес-помощник</b>\n\nКак ты себя чувствуешь прямо сейчас?"
    await safe_edit_message(callback, text, get_energy_keyboard())

@dp.callback_query(F.data.startswith("sport_energy_"))
async def sport_set_energy(callback: CallbackQuery, state: FSMContext):
    await state.update_data(energy=callback.data)
    text = "Отлично! Сколько времени ты готова уделить себе?"
    await safe_edit_message(callback, text, get_time_keyboard())
    await state.set_state(SportWizard.time)

@dp.callback_query(SportWizard.time, F.data.startswith("sport_time_"))
async def sport_set_time(callback: CallbackQuery, state: FSMContext):
    await state.update_data(time=callback.data)
    text = "Что есть под рукой из инвентаря?"
    await safe_edit_message(callback, text, get_inventory_keyboard())
    await state.set_state(SportWizard.inventory)

@dp.callback_query(SportWizard.inventory, F.data.startswith("sport_inv_"))
async def sport_set_inventory(callback: CallbackQuery, state: FSMContext):
    await state.update_data(inventory=callback.data)
    text = "Где тебе удобнее заниматься?"
    await safe_edit_message(callback, text, get_position_keyboard())
    await state.set_state(SportWizard.position)

@dp.callback_query(SportWizard.position, F.data.startswith("sport_pos_"))
async def sport_set_position(callback: CallbackQuery, state: FSMContext):
    await state.update_data(position=callback.data)
    text = "На какой зоне сделаем акцент?"
    await safe_edit_message(callback, text, get_zone_keyboard())
    await state.set_state(SportWizard.zone)

@dp.callback_query(SportWizard.zone, F.data.startswith("sport_zone_"))
async def sport_finish(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    if not all(k in data for k in ['energy', 'time', 'inventory', 'position', 'zone']):
        await callback.answer("Ошибка данных, начни сначала 😔", show_alert=True)
        await state.clear()
        await sport_start(callback)
        return

    energy_map = {
        "sport_energy_high": "🔋 Энергия",
        "sport_energy_low": "😌 Спокойствие",
        "sport_energy_rest": "😴 Восстановление"
    }
    time_map = {
        "sport_time_short": "5-10 мин",
        "sport_time_medium": "15-20 мин",
        "sport_time_long": "30+ мин"
    }
    zone_map = {
        "sport_zone_legs": "Ноги и ягодицы",
        "sport_zone_back": "Спина и шея",
        "sport_zone_abs": "Пресс",
        "sport_zone_full": "Все тело"
    }
    
    summary = (
        f"✨ <b>Твой план готов!</b>\n\n"
        f"• Настроение: {energy_map.get(data['energy'], '...')}\n"
        f"• Время: {time_map.get(data['time'], '...')}\n"
        f"• Поза: {data['position']}\n"
        f"• Зона: {zone_map.get(data['zone'], '...')}\n\n"
        f"Подбираю видео... 🎥"
    )
    
    await safe_edit_message(callback, summary)
    
    user_id = callback.from_user.id
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO logs (user_id, log_date, log_type, comment) VALUES (?, ?, 'sport', ?)",
            (user_id, today, summary)
        )
        await db.commit()

    await asyncio.sleep(2)
    
    final_text = (
        "Вот твоя тренировка! 💖\n\n"
        "<i>(Здесь будет ссылка на видео)</i>\n\n"
        "Напиши смайлик, если понравилось!"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 В главное меню", callback_data="main_menu")
    kb.adjust(1)
    
    await callback.message.answer(final_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.clear()

# ================= ВЕС =================

@dp.callback_query(F.data == "results_weight")
async def weight_log_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        res_last = await db.execute(
            "SELECT value, log_date FROM logs WHERE user_id = ? AND log_type = 'weight' ORDER BY log_date DESC LIMIT 1",
            (user_id,)
        )
        last_row = await res_last.fetchone()
        
        res_first = await db.execute(
            "SELECT value, log_date FROM logs WHERE user_id = ? AND log_type = 'weight' ORDER BY log_date ASC LIMIT 1",
            (user_id,)
        )
        first_row = await res_first.fetchone()

    text = "⚖️ <b>Дневник веса</b>\n\n"
    
    if last_row:
        last_weight = float(last_row[0])
        last_date_str = last_row[1]
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
        days_passed = (date.today() - last_date).days
        
        phrase = random.choice(SUPPORT_PHRES)
        
        if first_row and first_row[0] != last_row[0]:
            first_weight = float(first_row[0])
            diff = last_weight - first_weight
            sign = "+" if diff > 0 else ""
            stat_text = (
                f"📊 <b>Твоя статистика:</b>\n"
                f"Ты начала: {first_weight} кг ({first_row[1]})\n"
                f"Ты сейчас: {last_weight} кг\n"
                f"Разница: {sign}{diff:.1f} кг\n"
                f"Прошло дней с последней записи: {days_passed}\n\n"
                f"💌 {phrase}"
            )
        else:
            stat_text = (
                f"📊 <b>Твоя статистика:</b>\n"
                f"Ты начала: {last_weight} кг\n"
                f"Ты сейчас: {last_weight} кг\n"
                f"Прошло дней с последней записи: {days_passed}\n\n"
                f"💌 {phrase}"
            )
        text += stat_text
    else:
        text += "Пока нет записей. Давай начнем прямо сейчас!"

    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Записать новый вес", callback_data="weight_enter_new")
    
    support_link_text = "Я из клуба Лучшая подружка, мне нужна поддержка..."
    full_support_url = f"https://t.me/Lyokorps?text={support_link_text.replace(' ', '%20').replace('«', '').replace('»', '')}"
    
    kb.button(text="🆘 Мне нужна поддержка", url=full_support_url)
    kb.button(text="🔙 Назад", callback_data="main_menu")
    kb.adjust(1)
    
    await safe_edit_message(callback, text, kb.as_markup())

@dp.callback_query(F.data == "weight_enter_new")
async def weight_ask_input(callback: CallbackQuery, state: FSMContext):
    text = "👇 Напиши свой текущий вес цифрами (например, 54.5):"
    await safe_edit_message(callback, text)
    await state.set_state(WeightState.waiting_for_weight)

@dp.message(WeightState.waiting_for_weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight_val = float(message.text.replace(',', '.'))
        user_id = message.from_user.id
        today = date.today().isoformat()
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO logs (user_id, log_date, log_type, value) VALUES (?, ?, 'weight', ?)",
                (user_id, today, str(weight_val))
            )
            await db.commit()
        
        phrase = random.choice(SUPPORT_PHRES)
        response_text = f"Записала: {weight_val} кг. {phrase}\n\nЯ восхищаюсь тобой!"
        
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 В меню", callback_data="main_menu")
        
        await message.answer(response_text, reply_markup=kb.as_markup())
        await state.clear()
    except ValueError:
        await message.answer("Пожалуйста, введи число (например, 54.5). Попробуй еще раз:")

# ================= ФОТО =================

@dp.callback_query(F.data == "results_photo")
async def photo_log_start(callback: CallbackQuery, state: FSMContext):
    text = "📸 <b>Фото-дневник</b>\n\nОтправь мне свое фото сегодня, я сохраню его в архив."
    await safe_edit_message(callback, text, get_back_keyboard())
    await state.set_state(PhotoState.waiting_for_photo)

@dp.message(PhotoState.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    user_id = message.from_user.id
    today = date.today().isoformat()
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO logs (user_id, log_date, log_type, value) VALUES (?, ?, 'photo', ?)",
            (user_id, today, photo_id)
        )
        await db.commit()
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 В меню", callback_data="main_menu")
    
    # Отправляем фото ОДНИМ сообщением с подписью
    await message.answer_photo(
        photo=photo_id, 
        caption="Фото сохранено в твой дневник! 🌸 Ты прекрасна!", 
        reply_markup=kb.as_markup()
    )
    await state.clear()

@dp.message(PhotoState.waiting_for_photo)
async def process_photo_wrong(message: Message):
    await message.answer("Это не фото 😔 Пожалуйста, отправь именно картинку.")

# ================= АРХИВ ФОТО =================

@dp.callback_query(F.data == "photo_archive")
async def view_photo_archive(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        res = await db.execute(
            "SELECT value, log_date FROM logs WHERE user_id = ? AND log_type = 'photo' ORDER BY log_date DESC",
            (user_id,)
        )
        photos = await res.fetchall()
    
    if not photos:
        text = "🖼️ <b>Твой фото-архив пуст</b>\n\nЗдесь будут храниться все твои фотографии «До» и «В процессе». Начни заполнять его сегодня!"
        kb = InlineKeyboardBuilder()
        kb.button(text="📸 Добавить первое фото", callback_data="results_photo")
        kb.button(text="🔙 Назад", callback_data="main_menu")
        kb.adjust(1)
        await safe_edit_message(callback, text, kb.as_markup())
    else:
        text = f"🖼️ <b>Твой архив</b>\n\nВсего фото: {len(photos)}. Отправляю их ниже 👇\n<i>(Каждое фото отдельным сообщением)</i>"
        await safe_edit_message(callback, text)
        
        # Отправляем фото по одному (как и просили)
        for file_id, log_date in photos:
            kb = InlineKeyboardBuilder()
            kb.button(text="🔙 В меню", callback_data="main_menu")
            try:
                await callback.message.answer_photo(
                    photo=file_id,
                    caption=f"📅 Дата: {log_date}",
                    reply_markup=kb.as_markup()
                )
                # Небольшая пауза, чтобы Telegram не заблокировал за спам
                await asyncio.sleep(0.5)
            except Exception as e:
                logging.error(f"Не удалось отправить фото: {e}")
                await callback.message.answer("⚠️ Одно из фото не удалось загрузить.")

# ================= ПРОФИЛЬ =================

@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        res_water = await db.execute("SELECT COUNT(*) FROM logs WHERE user_id = ? AND log_type = 'water'", (user_id,))
        total_water = (await res_water.fetchone())[0]
        
        res_sport = await db.execute("SELECT COUNT(*) FROM logs WHERE user_id = ? AND log_type = 'sport'", (user_id,))
        total_sport = (await res_sport.fetchone())[0]
        
        res_weight = await db.execute("SELECT value FROM logs WHERE user_id = ? AND log_type = 'weight' ORDER BY log_date DESC LIMIT 1", (user_id,))
        last_weight_row = await res_weight.fetchone()
        last_weight = last_weight_row[0] if last_weight_row else "Не указан"

    text = (
        f"🌸 <b>Твой профиль</b>\n\n"
        f"ID: {callback.from_user.id}\n"
        f"Имя: {callback.from_user.first_name}\n\n"
        f"<b>Статистика:</b>\n"
        f"💧 Всего стаканов (все время): {total_water}\n"
        f"🧘‍♀️ Тренировок: {total_sport}\n"
        f"⚖️ Последний вес: {last_weight} кг"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="main_menu")
    kb.adjust(1)
    
    await safe_edit_message(callback, text, kb.as_markup())

# --- ЗАПУСК ---
async def main():
    await init_db()
    print("Бот запущен... 🌸")
    
    # Запускаем планировщик фоновой задачей
    asyncio.create_task(scheduler())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
