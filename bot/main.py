"""Телеграм-бот «Счётчик сигарет» — интерактивный, с кнопками.

Управление кнопками внизу экрана и пошаговыми диалогами: бот спрашивает —
пользователь отвечает. Команды через «/» тоже работают как дубль.

Подход без морализаторства: просто показываем правду в цифрах — сколько денег
и времени «в дым», как давно не куришь (интервалы), и тренд неделя-к-неделе.
Рейтинг — «у кого спокойнее» (меньше за неделю — выше). Данные в SQLite.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from . import charts, db

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO
)
log = logging.getLogger("cigarette-bot")

PHOTO_DIR = os.environ.get("PHOTO_DIR", "/data/photos")
MIN_PER_CIG = 5  # средняя длительность одной сигареты, минут (для оценки времени)

# ── Кнопки (подписи) ─────────────────────────────────────────────
BTN_ADD = "🚬 Записать перекур"
BTN_CHART = "📈 График"
BTN_DAYS = "📊 По дням"
BTN_MONEY = "💸 Сожжено"
BTN_INTERVALS = "⏱ Интервалы"
BTN_TREND = "📉 Тренд"
BTN_STATS = "📋 Статистика"
BTN_TOP = "🏆 Рейтинг"
BTN_EDIT = "✏️ Изменить записи"
BTN_SETTINGS = "⚙️ Настройки"
BTN_NAME = "🙍 Сменить имя"
BTN_HELP = "ℹ️ Помощь"
BTN_CANCEL = "❌ Отмена"
BTN_SKIP = "⏭ Пропустить"

MAIN_KB = ReplyKeyboardMarkup(
    [
        [BTN_ADD],
        [BTN_CHART, BTN_DAYS],
        [BTN_MONEY, BTN_INTERVALS],
        [BTN_TREND, BTN_STATS],
        [BTN_TOP, BTN_EDIT],
        [BTN_SETTINGS, BTN_NAME],
        [BTN_HELP],
    ],
    resize_keyboard=True,
)
CANCEL_KB = ReplyKeyboardMarkup([[BTN_CANCEL]], resize_keyboard=True)
SKIP_KB = ReplyKeyboardMarkup([[BTN_SKIP]], resize_keyboard=True)
CUR_KB = ReplyKeyboardMarkup([["грн", "₽"], ["$", "€"], [BTN_CANCEL]], resize_keyboard=True)
PACK_KB = ReplyKeyboardMarkup([["20"], [BTN_CANCEL]], resize_keyboard=True)

# ── Состояния диалогов ───────────────────────────────────────────
ADD_COUNT, NAME, EDIT_VALUE, SET_CUR, SET_PRICE, SET_PACK = range(6)

HELP = (
    "🚬 <b>Счётчик сигарет</b>\n\n"
    "Пользуйся кнопками внизу 👇\n\n"
    "• <b>Записать перекур</b> — бот спросит, сколько сигарет ты выкурил\n"
    "• <b>График</b> — линейный график по перекурам\n"
    "• <b>По дням</b> — гистограмма: сколько в какой день\n"
    "• <b>Сожжено</b> 💸 — сколько денег и времени ушло «в дым»\n"
    "• <b>Интервалы</b> ⏱ — как давно не куришь, самый длинный перерыв\n"
    "• <b>Тренд</b> 📉 — эта неделя против прошлой (±%)\n"
    "• <b>Статистика</b> — сводка цифрами\n"
    "• <b>Рейтинг</b> — у кого спокойнее за неделю (меньше — выше)\n"
    "• <b>Изменить записи</b> — выбрать запись и исправить/удалить\n"
    "• <b>Настройки</b> ⚙️ — цена и размер пачки (для подсчёта денег)\n"
    "• <b>Сменить имя</b> — как тебя показывать в рейтинге\n\n"
    "📷 После перекура можешь прислать фото — оно сохранится и привяжется "
    "к последней записи."
)


# ── Вспомогательные функции ──────────────────────────────────────
def week_bounds(offset: int = 0) -> tuple[str, str]:
    """Границы ISO-недели [понедельник, следующий понедельник) как YYYY-MM-DD.
    offset=0 — текущая неделя, 1 — прошлая и т.д."""
    today = date.today()
    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=offset)
    return monday.isoformat(), (monday + timedelta(days=7)).isoformat()


def fmt_money(value: float, currency: str) -> str:
    s = f"{value:,.0f}" if abs(value - round(value)) < 0.005 else f"{value:,.1f}"
    return s.replace(",", " ") + f" {currency}"


def fmt_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    d, rem = divmod(total, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"{d} дн {h} ч {m} мин"
    if h:
        return f"{h} ч {m} мин"
    return f"{m} мин"


# ── Регистрация / смена имени ────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    is_new = not db.user_exists(u.id)
    db.upsert_user(u.id, u.username, u.first_name)
    if is_new:
        await update.message.reply_html(
            "Привет! 👋 Я считаю твои сигареты.\n\n"
            "Как тебя записать в рейтинге? Напиши имя "
            "или нажми «Пропустить», чтобы оставить имя из Telegram.",
            reply_markup=SKIP_KB,
        )
        return NAME
    name = db.get_display_name(u.id) or u.first_name
    await update.message.reply_html(
        f"С возвращением, <b>{name}</b>! 🚬\n\n{HELP}", reply_markup=MAIN_KB
    )
    return ConversationHandler.END


async def setname_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    current = db.get_display_name(u.id) or u.first_name
    await update.message.reply_html(
        f"Сейчас ты записан как <b>{current}</b>.\n"
        "Напиши новое имя или нажми «Пропустить».",
        reply_markup=SKIP_KB,
    )
    return NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (update.message.text or "").strip()
    if text == BTN_SKIP:
        name = db.get_display_name(u.id) or u.first_name
        await update.message.reply_html(
            f"Ок, оставил имя <b>{name}</b>. 👍\n\n{HELP}", reply_markup=MAIN_KB
        )
        return ConversationHandler.END
    if not text or len(text) > 32:
        await update.message.reply_text(
            "Имя должно быть от 1 до 32 символов. Попробуй ещё раз.",
            reply_markup=SKIP_KB,
        )
        return NAME
    db.set_display_name(u.id, text)
    await update.message.reply_html(
        f"Готово! Теперь ты — <b>{text}</b>. 🎉\n\n{HELP}", reply_markup=MAIN_KB
    )
    return ConversationHandler.END


# ── Добавление перекура (диалог) ──────────────────────────────────
async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    await update.message.reply_html(
        "Сколько сигарет ты выкурил за этот перекур? 🚬\nНапиши число:",
        reply_markup=CANCEL_KB,
    )
    return ADD_COUNT


async def add_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (update.message.text or "").strip()
    if text == BTN_CANCEL:
        return await cancel(update, context)
    try:
        count = int(text)
    except ValueError:
        await update.message.reply_text(
            "Это не число 🤔 Напиши, сколько раз выкурил (например, 20), "
            "или нажми «Отмена».",
            reply_markup=CANCEL_KB,
        )
        return ADD_COUNT
    if count <= 0 or count > 10000:
        await update.message.reply_text(
            "Введи разумное число от 1 до 10000.", reply_markup=CANCEL_KB
        )
        return ADD_COUNT

    db.add_set(u.id, count)
    total = db.total_count(u.id)
    today = db.today_count(u.id)
    await update.message.reply_html(
        f"✅ Записал перекур: <b>{count}</b>\n"
        f"Сегодня: <b>{today}</b>  ·  Всего: <b>{total}</b>\n"
        f"📷 Можешь прислать фото к этому перекуру.",
        reply_markup=MAIN_KB,
    )
    return ConversationHandler.END


# ── Редактирование (диалог: выбор кнопкой → новое значение) ───────
async def edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    rows = db.recent_sets(u.id, limit=10)
    if not rows:
        await update.message.reply_text(
            "Пока нет записей. Сначала запиши перекур 🚬", reply_markup=MAIN_KB
        )
        return ConversationHandler.END

    buttons = []
    for set_id, ts, count in rows:
        when = ts.replace("T", " ")[5:16]  # MM-DD HH:MM
        buttons.append(
            [InlineKeyboardButton(f"№{set_id} · {when} · {count} раз",
                                  callback_data=f"pick:{set_id}:{count}")]
        )
    await update.message.reply_text(
        "Какую запись изменить? Выбери её:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    await update.message.reply_text(
        "…или нажми «Отмена».", reply_markup=CANCEL_KB
    )
    return EDIT_VALUE  # ждём либо нажатие кнопки, либо отмену


async def edit_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запись выбрана — предлагаем: изменить число или удалить целиком."""
    query = update.callback_query
    await query.answer()
    _, set_id, count = query.data.split(":")
    set_id = int(set_id)

    if db.set_owner(set_id) != query.from_user.id:
        await query.edit_message_text("Это не твоя запись 🙅")
        return ConversationHandler.END

    context.user_data["edit_id"] = set_id
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ Изменить число", callback_data=f"chg:{set_id}:{count}")],
            [InlineKeyboardButton("🗑 Удалить запись", callback_data=f"del:{set_id}")],
        ]
    )
    await query.edit_message_text(
        f"Запись №{set_id} (сейчас: {count} раз). Что сделать?", reply_markup=kb
    )
    return EDIT_VALUE


async def edit_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажали «Изменить число» — просим новое значение."""
    query = update.callback_query
    await query.answer()
    _, set_id, count = query.data.split(":")
    context.user_data["edit_id"] = int(set_id)
    await query.edit_message_text(
        f"Запись №{set_id} (сейчас: {count} раз).\nНапиши новое число:"
    )
    return EDIT_VALUE


async def edit_delete_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажали «Удалить» — спрашиваем подтверждение."""
    query = update.callback_query
    await query.answer()
    set_id = int(query.data.split(":")[1])
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"delok:{set_id}")],
            [InlineKeyboardButton("↩️ Нет, оставить", callback_data="delno")],
        ]
    )
    await query.edit_message_text(
        f"Точно удалить запись №{set_id} целиком?", reply_markup=kb
    )
    return EDIT_VALUE


async def edit_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_id = int(query.data.split(":")[1])
    if db.set_owner(set_id) != query.from_user.id:
        await query.edit_message_text("Это не твоя запись 🙅")
        return ConversationHandler.END
    db.delete_set(set_id)
    context.user_data.pop("edit_id", None)
    await query.edit_message_text(f"🗑 Запись №{set_id} удалена.")
    await query.message.reply_html(
        f"Всего теперь: <b>{db.total_count(query.from_user.id)}</b>",
        reply_markup=MAIN_KB,
    )
    return ConversationHandler.END


async def edit_delete_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("edit_id", None)
    await query.edit_message_text("Ок, ничего не удалял. 👌")
    await query.message.reply_text("Главное меню 👇", reply_markup=MAIN_KB)
    return ConversationHandler.END


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (update.message.text or "").strip().lower()
    if text == BTN_CANCEL.lower():
        return await cancel(update, context)

    set_id = context.user_data.get("edit_id")
    if set_id is None:
        # пользователь написал текст, не выбрав запись кнопкой
        await update.message.reply_text(
            "Сначала выбери запись кнопкой выше 👆 или нажми «Отмена».",
            reply_markup=CANCEL_KB,
        )
        return EDIT_VALUE

    if db.set_owner(set_id) != u.id:
        await update.message.reply_text("Это не твоя запись 🙅", reply_markup=MAIN_KB)
        context.user_data.pop("edit_id", None)
        return ConversationHandler.END

    if text in ("удалить", "удали", "delete"):
        db.delete_set(set_id)
        context.user_data.pop("edit_id", None)
        await update.message.reply_html(
            f"🗑 Запись №{set_id} удалена. Всего теперь: <b>{db.total_count(u.id)}</b>",
            reply_markup=MAIN_KB,
        )
        return ConversationHandler.END

    try:
        count = int(text)
    except ValueError:
        await update.message.reply_text(
            "Напиши новое число или слово «удалить».", reply_markup=CANCEL_KB
        )
        return EDIT_VALUE
    if count <= 0 or count > 10000:
        await update.message.reply_text(
            "Введи разумное число от 1 до 10000.", reply_markup=CANCEL_KB
        )
        return EDIT_VALUE

    db.edit_set(set_id, count)
    context.user_data.pop("edit_id", None)
    await update.message.reply_html(
        f"✏️ Запись №{set_id} изменена на <b>{count}</b>. "
        f"Всего теперь: <b>{db.total_count(u.id)}</b>",
        reply_markup=MAIN_KB,
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("edit_id", None)
    await update.message.reply_text("Отменил. 👌", reply_markup=MAIN_KB)
    return ConversationHandler.END


# ── Информационные действия (кнопки и команды) ───────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(HELP, reply_markup=MAIN_KB)


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_html(
        f"Сегодня ты выкурил <b>{db.today_count(u.id)}</b> раз 🚬",
        reply_markup=MAIN_KB,
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    total = db.total_count(u.id)
    n = db.sets_count(u.id)
    days = db.per_day(u.id)
    avg = round(total / n, 1) if n else 0
    best = max((v for _, v in days), default=0)
    per_day_avg = round(total / len(days), 1) if days else 0

    lines = [
        "📊 <b>Статистика</b>",
        f"Всего сигарет: <b>{total}</b>",
        f"Перекуров: <b>{n}</b>",
        f"Дней с курением: <b>{len(days)}</b>",
        f"В среднем за день: <b>{per_day_avg}</b>",
        f"Больше всего за день: <b>{best}</b>",
    ]

    s = db.get_settings(u.id)
    if s["price_per_pack"]:
        cost = s["price_per_pack"] / s["pack_size"]
        lines.append(f"💸 Потрачено всего: <b>{fmt_money(total * cost, s['currency'])}</b>")
    lines.append(f"⏱ Времени «в дым»: <b>{fmt_duration(timedelta(minutes=total * MIN_PER_CIG))}</b>")

    await update.message.reply_html("\n".join(lines), reply_markup=MAIN_KB)


async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    data = db.sessions(u.id)
    if not data:
        await update.message.reply_text(
            "Пока нет данных. Нажми «Записать перекур» 🚬", reply_markup=MAIN_KB
        )
        return
    img = charts.line_chart(data, "График сигарет по перекурам")
    await update.message.reply_photo(img, caption="Твои перекуры 📈")


async def total_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    data = db.sessions(u.id)
    total = db.total_count(u.id)
    if not data:
        await update.message.reply_text(
            "Пока нет данных. Нажми «Записать перекур» 🚬", reply_markup=MAIN_KB
        )
        return
    img = charts.cumulative_chart(data, total)
    await update.message.reply_photo(img, caption=f"Всего сигарет: {total} 🔥")


async def days_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    data = db.per_day(u.id)
    if not data:
        await update.message.reply_text(
            "Пока нет данных. Нажми «Записать перекур» 🚬", reply_markup=MAIN_KB
        )
        return
    img = charts.days_bar_chart(data, "Сигареты по дням")
    await update.message.reply_photo(img, caption="Сколько в какой день 📊")


async def money_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    s = db.get_settings(u.id)
    total = db.total_count(u.id)
    if total == 0:
        await update.message.reply_text(
            "Пока нет данных. Нажми «Записать перекур» 🚬", reply_markup=MAIN_KB
        )
        return
    time_lost = fmt_duration(timedelta(minutes=total * MIN_PER_CIG))

    if not s["price_per_pack"]:
        await update.message.reply_html(
            f"⏱ Времени «в дым»: <b>{time_lost}</b> ({total} шт по ~{MIN_PER_CIG} мин)\n\n"
            "💸 Чтобы считать деньги, задай цену пачки в «⚙️ Настройки».",
            reply_markup=MAIN_KB,
        )
        return

    cost = s["price_per_pack"] / s["pack_size"]
    days = db.per_day(u.id)
    days_money = [(d, cnt * cost) for d, cnt in days]
    img = charts.money_bar_chart(days_money, s["currency"], "Деньги «в дым» по дням")
    await update.message.reply_photo(
        img,
        caption=(
            f"💸 Всего сожжено: {fmt_money(total * cost, s['currency'])}\n"
            f"🚬 Сигарет: {total} (≈{total / s['pack_size']:.1f} пачек)\n"
            f"⏱ Времени: {time_lost}"
        ),
    )


async def intervals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    sess = db.sessions(u.id)
    if not sess:
        await update.message.reply_text(
            "Пока нет данных. Нажми «Записать перекур» 🚬", reply_markup=MAIN_KB
        )
        return
    times = [datetime.fromisoformat(ts) for ts, _ in sess]
    now = datetime.now()
    since_last = now - times[-1]

    lines = [
        "⏱ <b>Интервалы</b>",
        f"Не куришь уже: <b>{fmt_duration(since_last)}</b>",
    ]
    if len(times) >= 2:
        diffs = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        longest = max(diffs)
        avg = sum(diffs, timedelta()) / len(diffs)
        lines.append(f"Самый длинный перерыв: <b>{fmt_duration(longest)}</b>")
        lines.append(f"В среднем между перекурами: <b>{fmt_duration(avg)}</b>")
    else:
        lines.append("<i>Сделай ещё пару записей — покажу перерывы и средний интервал.</i>")
    await update.message.reply_html("\n".join(lines), reply_markup=MAIN_KB)


async def trend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    this = db.range_total(u.id, *week_bounds(0))
    last = db.range_total(u.id, *week_bounds(1))

    if this == 0 and last == 0:
        await update.message.reply_text(
            "Пока нет данных за последние две недели 🙂", reply_markup=MAIN_KB
        )
        return

    if last == 0:
        verdict = "📈 На прошлой неделе записей не было — не с чем сравнить."
    else:
        diff = this - last
        pct = diff / last * 100
        if diff < 0:
            verdict = f"📉 Меньше на <b>{-pct:.0f}%</b> ({diff} шт). Так держать! 👏"
        elif diff > 0:
            verdict = f"📈 Больше на <b>{pct:.0f}%</b> (+{diff} шт)."
        else:
            verdict = "➖ Столько же, что и на прошлой неделе."

    await update.message.reply_html(
        f"📊 <b>Тренд по неделям</b>\n"
        f"Эта неделя: <b>{this}</b> сигарет\n"
        f"Прошлая неделя: <b>{last}</b> сигарет\n\n{verdict}",
        reply_markup=MAIN_KB,
    )


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board = db.leaderboard_week(*week_bounds(0))
    if not board:
        await update.message.reply_text(
            "Пока никто ничего не записал 🙂", reply_markup=MAIN_KB
        )
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        "🏆 <b>Рейтинг за эту неделю</b>",
        "<i>у кого спокойнее (меньше — выше)</i>",
        "",
    ]
    for i, (name, week) in enumerate(board):
        mark = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{mark} <b>{name}</b> — {week} за неделю")
    await update.message.reply_html("\n".join(lines), reply_markup=MAIN_KB)


# ── Настройки стоимости (диалог) ─────────────────────────────────
async def settings_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    s = db.get_settings(u.id)
    cur = s["currency"]
    now = (
        f"Сейчас: пачка {fmt_money(s['price_per_pack'], cur)} на {s['pack_size']} шт."
        if s["price_per_pack"]
        else "Сейчас цена пачки не задана."
    )
    await update.message.reply_html(
        f"⚙️ <b>Настройки стоимости</b>\n{now}\n\nВыбери валюту:",
        reply_markup=CUR_KB,
    )
    return SET_CUR


async def settings_cur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text == BTN_CANCEL:
        return await cancel(update, context)
    if len(text) > 8:
        await update.message.reply_text("Слишком длинно. Выбери валюту кнопкой.", reply_markup=CUR_KB)
        return SET_CUR
    context.user_data["s_cur"] = text
    await update.message.reply_html(
        f"Сколько стоит пачка? Напиши число (в {text}):", reply_markup=CANCEL_KB
    )
    return SET_PRICE


async def settings_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().replace(",", ".")
    if text == BTN_CANCEL.replace(",", "."):
        return await cancel(update, context)
    try:
        price = float(text)
    except ValueError:
        await update.message.reply_text("Это не число. Напиши цену пачки, например 75.", reply_markup=CANCEL_KB)
        return SET_PRICE
    if price <= 0 or price > 100000:
        await update.message.reply_text("Введи разумную цену.", reply_markup=CANCEL_KB)
        return SET_PRICE
    context.user_data["s_price"] = price
    await update.message.reply_html(
        "Сколько сигарет в пачке? (обычно 20)", reply_markup=PACK_KB
    )
    return SET_PACK


async def settings_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (update.message.text or "").strip()
    if text == BTN_CANCEL:
        return await cancel(update, context)
    try:
        pack = int(text)
    except ValueError:
        await update.message.reply_text("Напиши число, например 20.", reply_markup=PACK_KB)
        return SET_PACK
    if pack < 1 or pack > 100:
        await update.message.reply_text("Введи число от 1 до 100.", reply_markup=PACK_KB)
        return SET_PACK

    cur = context.user_data.pop("s_cur", "грн")
    price = context.user_data.pop("s_price", 0)
    db.set_settings(u.id, cur, price, pack)
    cost = price / pack
    await update.message.reply_html(
        f"✅ Готово! Пачка {fmt_money(price, cur)} на {pack} шт.\n"
        f"Одна сигарета ≈ <b>{fmt_money(cost, cur)}</b>.\n"
        "Теперь «💸 Сожжено» и статистика считают деньги.",
        reply_markup=MAIN_KB,
    )
    return ConversationHandler.END


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    set_id = db.last_set_id(u.id)
    if set_id is None:
        await update.message.reply_text(
            "Сначала запиши перекур, потом пришли фото 🚬", reply_markup=MAIN_KB
        )
        return
    user_dir = os.path.join(PHOTO_DIR, str(u.id))
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"set_{set_id}.jpg")
    tg_file = await update.message.photo[-1].get_file()
    await tg_file.download_to_drive(path)
    db.attach_photo(set_id, path)
    await update.message.reply_text(
        "📷 Фото сохранено и привязано к перекуру!", reply_markup=MAIN_KB
    )


def _btn(label: str) -> filters.BaseFilter:
    """Точное совпадение текста кнопки."""
    import re
    return filters.Regex(f"^{re.escape(label)}$")


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Не задан BOT_TOKEN (см. .env.example)")

    db.init_db()
    os.makedirs(PHOTO_DIR, exist_ok=True)

    app = Application.builder().token(token).build()

    # Регистрация / смена имени
    name_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("setname", setname_entry),
            MessageHandler(_btn(BTN_NAME), setname_entry),
        ],
        states={NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)]},
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_btn(BTN_CANCEL), cancel)],
    )

    # Добавление перекура
    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_entry),
            MessageHandler(_btn(BTN_ADD), add_entry),
        ],
        states={ADD_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_count)]},
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_btn(BTN_CANCEL), cancel)],
    )

    # Редактирование
    edit_conv = ConversationHandler(
        entry_points=[
            CommandHandler("edit", edit_entry),
            MessageHandler(_btn(BTN_EDIT), edit_entry),
        ],
        states={
            EDIT_VALUE: [
                CallbackQueryHandler(edit_picked, pattern=r"^pick:"),
                CallbackQueryHandler(edit_change, pattern=r"^chg:"),
                CallbackQueryHandler(edit_delete_ask, pattern=r"^del:"),
                CallbackQueryHandler(edit_delete_ok, pattern=r"^delok:"),
                CallbackQueryHandler(edit_delete_no, pattern=r"^delno$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_btn(BTN_CANCEL), cancel)],
    )

    # Настройки стоимости (валюта → цена → размер пачки)
    settings_conv = ConversationHandler(
        entry_points=[
            CommandHandler("settings", settings_entry),
            MessageHandler(_btn(BTN_SETTINGS), settings_entry),
        ],
        states={
            SET_CUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_cur)],
            SET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_price)],
            SET_PACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_pack)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_btn(BTN_CANCEL), cancel)],
    )

    app.add_handler(name_conv)
    app.add_handler(add_conv)
    app.add_handler(edit_conv)
    app.add_handler(settings_conv)

    # Информационные кнопки + команды-дубли
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(_btn(BTN_HELP), help_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(_btn(BTN_STATS), stats))
    app.add_handler(CommandHandler("chart", chart_cmd))
    app.add_handler(MessageHandler(_btn(BTN_CHART), chart_cmd))
    app.add_handler(CommandHandler("total", total_cmd))
    app.add_handler(CommandHandler("days", days_cmd))
    app.add_handler(MessageHandler(_btn(BTN_DAYS), days_cmd))
    app.add_handler(CommandHandler("money", money_cmd))
    app.add_handler(MessageHandler(_btn(BTN_MONEY), money_cmd))
    app.add_handler(CommandHandler("intervals", intervals_cmd))
    app.add_handler(MessageHandler(_btn(BTN_INTERVALS), intervals_cmd))
    app.add_handler(CommandHandler("trend", trend_cmd))
    app.add_handler(MessageHandler(_btn(BTN_TREND), trend_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(MessageHandler(_btn(BTN_TOP), top_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    log.info("Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
