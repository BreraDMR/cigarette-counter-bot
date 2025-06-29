"""Телеграм-бот «Счётчик сигарет» — интерактивный, с кнопками.

Логика простая: одна сигарета = один перекур. Нажал «Перекур +1» — записал.
Статистика спрятана под одной кнопкой, внутри — разные срезы (по часам суток,
по дням недели, динамика, интервалы, тренд). Деньги считаются не «по пачке»,
а по реальным расходникам: табак / бумага / фильтры / пачка сигарет — открыл
упаковку (записал цену), кончилась — отметил. Данные в SQLite.
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

from . import charts, db, rates

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO
)
log = logging.getLogger("cigarette-bot")

PHOTO_DIR = os.environ.get("PHOTO_DIR", "/data/photos")
MIN_PER_CIG = 5  # средняя длительность одной сигареты, минут (для оценки времени)

# ── Типы расходников ─────────────────────────────────────────────
KINDS = {
    "tobacco": "🌿 Табак",
    "paper": "📄 Бумага",
    "filters": "⚪️ Фильтры",
    "cigs": "🚬 Пачка сигарет",
}

# ── Кнопки главного меню (подписи) ───────────────────────────────
BTN_ADD = "🚬 Перекур +1"
BTN_DELLAST = "🗑 Удалить последний"
BTN_STATS = "📊 Статистика"
BTN_EXPENSES = "💸 Расходы"
BTN_TOP = "🏆 Рейтинг"
BTN_SETTINGS = "⚙️ Настройки"
BTN_HELP = "ℹ️ Помощь"
BTN_CANCEL = "❌ Отмена"
BTN_SKIP = "⏭ Пропустить"

MAIN_KB = ReplyKeyboardMarkup(
    [
        [BTN_ADD],
        [BTN_DELLAST],
        [BTN_STATS, BTN_EXPENSES],
        [BTN_TOP, BTN_SETTINGS],
        [BTN_HELP],
    ],
    resize_keyboard=True,
)

# Кнопки главного меню одним фильтром — чтобы выйти из любого «залипшего» диалога.
_MAIN_BUTTONS = [BTN_ADD, BTN_DELLAST, BTN_STATS, BTN_EXPENSES, BTN_TOP, BTN_SETTINGS, BTN_HELP]
CANCEL_KB = ReplyKeyboardMarkup([[BTN_CANCEL]], resize_keyboard=True)
SKIP_KB = ReplyKeyboardMarkup([[BTN_SKIP]], resize_keyboard=True)

# Инлайн-меню статистики
STATS_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("📋 Сводка", callback_data="st:summary")],
        [InlineKeyboardButton("🕐 По часам суток", callback_data="st:hours"),
         InlineKeyboardButton("📅 По дням недели", callback_data="st:weekday")],
        [InlineKeyboardButton("📈 Динамика по дням", callback_data="st:days"),
         InlineKeyboardButton("🔥 Накопительно", callback_data="st:cumul")],
        [InlineKeyboardButton("⏱ Интервалы", callback_data="st:intervals"),
         InlineKeyboardButton("📉 Тренд по неделям", callback_data="st:trend")],
    ]
)

# ── Состояния диалогов ───────────────────────────────────────────
NAME, EDIT_VALUE, EX_PRICE = range(3)

HELP = (
    "🚬 <b>Счётчик сигарет</b>\n\n"
    "Пользуйся кнопками внизу 👇\n\n"
    "• <b>🚬 Перекур +1</b> — записывает одну сигарету. Один перекур = одна сигарета.\n"
    "• <b>🗑 Удалить последний</b> — быстро убрать последний перекур (если нажал зря).\n"
    "• <b>📊 Статистика</b> — всё в одном меню: сводка, по часам суток "
    "(когда тянет чаще), по дням недели, динамика, интервалы, тренд.\n"
    "• <b>💸 Расходы</b> — учёт расходников: табак, бумага, фильтры или пачка "
    "сигарет. Открыл упаковку — записал цену; кончилась — отметил. Бот посчитает, "
    "сколько денег ушло «в дым» и куда именно.\n"
    "• <b>🏆 Рейтинг</b> — у кого спокойнее за неделю (меньше — выше).\n"
    "• <b>⚙️ Настройки</b> — сменить имя, валюту и поправить/удалить записи.\n\n"
    "📷 После перекура можешь прислать фото — оно привяжется к последней записи."
)


# ── Вспомогательные функции ──────────────────────────────────────
def week_bounds(offset: int = 0) -> tuple[str, str]:
    """Границы ISO-недели [понедельник, следующий понедельник) как YYYY-MM-DD."""
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


def user_currency(user_id: int) -> str:
    return db.get_settings(user_id)["currency"]


def total_spent_converted(user_id: int) -> float:
    """Все траты, сконвертированные в текущую валюту пользователя."""
    cur = user_currency(user_id)
    return sum(
        rates.convert(price, item_cur or cur, cur)
        for _, price, item_cur in db.all_consumables(user_id)
    )


def spent_by_kind_converted(user_id: int) -> list[tuple[str, float]]:
    """Траты по типам в текущей валюте: [(kind, сумма), ...] по убыванию."""
    cur = user_currency(user_id)
    agg: dict[str, float] = {}
    for kind, price, item_cur in db.all_consumables(user_id):
        agg[kind] = agg.get(kind, 0.0) + rates.convert(price, item_cur or cur, cur)
    return sorted(agg.items(), key=lambda kv: kv[1], reverse=True)


# ── Регистрация / смена имени ────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    is_new = not db.user_exists(u.id)
    db.upsert_user(u.id, u.username, u.first_name)
    if is_new:
        await update.message.reply_html(
            "Привет! 👋 Я считаю твои сигареты. Один перекур — одна сигарета.\n\n"
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


async def setname_from_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    db.upsert_user(u.id, u.username, u.first_name)
    current = db.get_display_name(u.id) or u.first_name
    await query.message.reply_html(
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
            f"Ок, оставил имя <b>{name}</b>. 👍", reply_markup=MAIN_KB
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
        f"Готово! Теперь ты — <b>{text}</b>. 🎉", reply_markup=MAIN_KB
    )
    return ConversationHandler.END


# ── Перекур: просто +1 ────────────────────────────────────────────
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    db.add_set(u.id, 1)
    total = db.total_count(u.id)
    today = db.today_count(u.id)
    now = datetime.now().strftime("%H:%M")
    await update.message.reply_html(
        f"✅ Перекур записан в {now} 🚬\n"
        f"Сегодня: <b>{today}</b>  ·  Всего: <b>{total}</b>\n"
        f"📷 Можешь прислать фото к этому перекуру.",
        reply_markup=MAIN_KB,
    )


# ── Быстрое удаление последнего перекура ─────────────────────────
async def dellast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    rows = db.recent_sets(u.id, limit=1)
    if not rows:
        await update.message.reply_text(
            "Нет записей — удалять нечего 🤷", reply_markup=MAIN_KB
        )
        return
    set_id, ts, _ = rows[0]
    when = ts.replace("T", " ")[5:16]  # MM-DD HH:MM
    db.delete_set(set_id)
    await update.message.reply_html(
        f"🗑 Удалил последний перекур (№{set_id} · {when}).\n"
        f"Сегодня: <b>{db.today_count(u.id)}</b>  ·  Всего: <b>{db.total_count(u.id)}</b>",
        reply_markup=MAIN_KB,
    )


# ── Статистика (одна кнопка → меню) ──────────────────────────────
async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "📊 <b>Статистика</b>\nЧто показать?", reply_markup=STATS_MENU
    )


async def stats_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    what = query.data.split(":", 1)[1]
    msg = query.message

    total = db.total_count(u.id)
    if total == 0:
        await msg.reply_text(
            "Пока нет данных. Нажми «🚬 Перекур +1» 🚬", reply_markup=MAIN_KB
        )
        return

    if what == "summary":
        await _send_summary(msg, u.id)
    elif what == "hours":
        img = charts.hours_chart(db.by_hour(u.id))
        await msg.reply_photo(img, caption="🕐 В какое время суток тянет чаще")
    elif what == "weekday":
        img = charts.weekday_chart(db.by_weekday(u.id))
        await msg.reply_photo(img, caption="📅 По дням недели")
    elif what == "days":
        img = charts.days_bar_chart(db.per_day(u.id), "Сигареты по дням")
        await msg.reply_photo(img, caption="📈 Сколько в какой день")
    elif what == "cumul":
        img = charts.cumulative_chart(db.sessions(u.id), total)
        await msg.reply_photo(img, caption=f"🔥 Всего сигарет: {total}")
    elif what == "intervals":
        await _send_intervals(msg, u.id)
    elif what == "trend":
        await _send_trend(msg, u.id)


async def _send_summary(msg, user_id: int):
    total = db.total_count(user_id)
    n = db.sets_count(user_id)
    days = db.per_day(user_id)
    per_day_avg = round(total / len(days), 1) if days else 0
    best = max((v for _, v in days), default=0)
    hrs = db.by_hour(user_id)
    peak_h = max(range(24), key=lambda i: hrs[i]) if any(hrs) else None

    lines = [
        "📋 <b>Сводка</b>",
        f"Всего сигарет: <b>{total}</b>",
        f"Перекуров: <b>{n}</b>",
        f"Дней с курением: <b>{len(days)}</b>",
        f"В среднем за день: <b>{per_day_avg}</b>",
        f"Больше всего за день: <b>{best}</b>",
    ]
    if peak_h is not None:
        lines.append(f"Чаще всего куришь около <b>{peak_h:02d}:00</b>")

    spent = total_spent_converted(user_id)
    cur = user_currency(user_id)
    if spent > 0:
        lines.append(f"💸 Потрачено на расходники: <b>{fmt_money(spent, cur)}</b>")
    lines.append(
        f"⏱ Времени «в дым»: <b>{fmt_duration(timedelta(minutes=total * MIN_PER_CIG))}</b>"
    )
    await msg.reply_html("\n".join(lines), reply_markup=MAIN_KB)


async def _send_intervals(msg, user_id: int):
    sess = db.sessions(user_id)
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
    await msg.reply_html("\n".join(lines), reply_markup=MAIN_KB)


async def _send_trend(msg, user_id: int):
    this = db.range_total(user_id, *week_bounds(0))
    last = db.range_total(user_id, *week_bounds(1))
    if this == 0 and last == 0:
        await msg.reply_text("Пока нет данных за последние две недели 🙂", reply_markup=MAIN_KB)
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
    await msg.reply_html(
        f"📉 <b>Тренд по неделям</b>\n"
        f"Эта неделя: <b>{this}</b> сигарет\n"
        f"Прошлая неделя: <b>{last}</b> сигарет\n\n{verdict}",
        reply_markup=MAIN_KB,
    )


# ── Расходы (расходники) ─────────────────────────────────────────
def expenses_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🆕 Открыть упаковку", callback_data="ex:new")],
            [InlineKeyboardButton("✅ Упаковка кончилась", callback_data="ex:close")],
            [InlineKeyboardButton("📊 Куда ушли деньги", callback_data="ex:chart")],
        ]
    )


def _expenses_text(user_id: int) -> str:
    cur = user_currency(user_id)
    spent = total_spent_converted(user_id)
    total_cigs = db.total_count(user_id)
    lines = ["💸 <b>Расходы</b>"]
    open_items = db.open_consumables(user_id)
    if open_items:
        lines.append("\nСейчас открыто:")
        for kind, price, c, _ in open_items:
            shown = fmt_money(rates.convert(price, c or cur, cur), cur)
            # если покупал в другой валюте — подскажем исходную цену
            if c and c != cur:
                shown += f" <i>({fmt_money(price, c)})</i>"
            lines.append(f"• {KINDS.get(kind, kind)} — {shown}")
    else:
        lines.append("\n<i>Открытых упаковок нет.</i>")
    if spent > 0:
        lines.append(f"\nВсего потрачено: <b>{fmt_money(spent, cur)}</b>")
        if total_cigs:
            lines.append(f"Цена одной сигареты ≈ <b>{fmt_money(spent / total_cigs, cur)}</b>")
    else:
        lines.append("\n<i>Открой первую упаковку и запиши её цену — начну считать деньги.</i>")
    return "\n".join(lines)


async def expenses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    await update.message.reply_html(
        _expenses_text(u.id), reply_markup=expenses_menu_kb()
    )


def _kind_kb(prefix: str, kinds: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(KINDS[k], callback_data=f"{prefix}:{k}")] for k in kinds]
    return InlineKeyboardMarkup(rows)


async def expenses_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопки меню расходов, КРОМЕ «открыть» (та — отдельный диалог)."""
    query = update.callback_query
    await query.answer()
    u = query.from_user
    action = query.data.split(":", 1)[1]

    if action == "close":
        open_items = db.open_consumables(u.id)
        if not open_items:
            await query.edit_message_text("Сейчас нет открытых упаковок 🤷")
            await query.message.reply_text("Главное меню 👇", reply_markup=MAIN_KB)
            return
        kinds = [k for k, *_ in open_items]
        await query.edit_message_text(
            "Какая упаковка закончилась?", reply_markup=_kind_kb("exclose", kinds)
        )
    elif action == "chart":
        by_kind = spent_by_kind_converted(u.id)
        if not by_kind:
            await query.message.reply_text(
                "Пока нет трат. Открой упаковку и запиши цену 💸", reply_markup=MAIN_KB
            )
            return
        cur = user_currency(u.id)
        items = [(KINDS.get(k, k), total) for k, total in by_kind]
        img = charts.spend_by_kind_chart(items, cur)
        await query.message.reply_photo(img, caption="💸 Куда ушли деньги (в одной валюте)")


async def expenses_close_kind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    kind = query.data.split(":", 1)[1]
    ok = db.close_consumable(u.id, kind)
    label = KINDS.get(kind, kind)
    if ok:
        await query.edit_message_text(f"✅ Отметил: {label} закончилась.")
    else:
        await query.edit_message_text(f"{label} и так не была открыта 🤷")
    await query.message.reply_html(_expenses_text(u.id), reply_markup=expenses_menu_kb())


# ── Открытие упаковки (диалог: тип → цена) ───────────────────────
async def expenses_new_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Что открываешь?", reply_markup=_kind_kb("exnew", list(KINDS.keys()))
    )
    return EX_PRICE  # ждём выбор типа (кнопка), потом цену


async def expenses_new_kind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    kind = query.data.split(":", 1)[1]
    context.user_data["ex_kind"] = kind
    cur = user_currency(u.id)
    await query.edit_message_text(
        f"{KINDS[kind]} — сколько стоит упаковка? Напиши число (в {cur}):"
    )
    await query.message.reply_text("…или нажми «Отмена».", reply_markup=CANCEL_KB)
    return EX_PRICE


async def expenses_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (update.message.text or "").strip().replace(",", ".")
    if text == BTN_CANCEL.replace(",", "."):
        return await cancel(update, context)
    kind = context.user_data.get("ex_kind")
    if not kind:
        await update.message.reply_text(
            "Сначала выбери тип кнопкой выше 👆 или нажми «Отмена».",
            reply_markup=CANCEL_KB,
        )
        return EX_PRICE
    try:
        price = float(text)
    except ValueError:
        await update.message.reply_text(
            "Это не число. Напиши цену упаковки, например 120.", reply_markup=CANCEL_KB
        )
        return EX_PRICE
    if price <= 0 or price > 1_000_000:
        await update.message.reply_text("Введи разумную цену.", reply_markup=CANCEL_KB)
        return EX_PRICE

    cur = user_currency(u.id)
    db.open_consumable(u.id, kind, price, cur)
    context.user_data.pop("ex_kind", None)
    await update.message.reply_html(
        f"✅ Открыл: {KINDS[kind]} за {fmt_money(price, cur)}.\n"
        "Кончится — загляни в «💸 Расходы» и нажми «Упаковка кончилась».",
        reply_markup=MAIN_KB,
    )
    await update.message.reply_html(_expenses_text(u.id), reply_markup=expenses_menu_kb())
    return ConversationHandler.END


# ── Настройки (имя + валюта) ─────────────────────────────────────
def settings_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🙍 Сменить имя", callback_data="se:name")],
            [InlineKeyboardButton("💱 Валюта", callback_data="se:cur")],
            [InlineKeyboardButton("✏️ Изменить/удалить записи", callback_data="se:edit")],
        ]
    )


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    name = db.get_display_name(u.id) or u.first_name
    cur = user_currency(u.id)
    await update.message.reply_html(
        f"⚙️ <b>Настройки</b>\nИмя: <b>{name}</b>\nВалюта: <b>{cur}</b>",
        reply_markup=settings_menu_kb(),
    )


async def settings_currency_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇪🇺 € евро", callback_data="secur:€")],
            [InlineKeyboardButton("🇺🇦 ₴ гривна", callback_data="secur:грн")],
            [InlineKeyboardButton("🇨🇿 Kč крона", callback_data="secur:Kč")],
        ]
    )
    r = rates.get_rates()
    note = (
        f"\n\n<i>Примерный курс: 1 € ≈ {r.get('UAH', 0):.1f} грн ≈ "
        f"{r.get('CZK', 0):.1f} Kč. Суммы из других валют пересчитаю автоматически.</i>"
    )
    await query.edit_message_text(
        "Выбери валюту:" + note, parse_mode="HTML", reply_markup=kb
    )


async def settings_currency_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    cur = query.data.split(":", 1)[1]
    db.set_currency(u.id, cur)
    await query.edit_message_text(f"✅ Валюта: {cur} — суммы расходов теперь показываю в ней.")
    await query.message.reply_text("Главное меню 👇", reply_markup=MAIN_KB)


# ── Рейтинг ──────────────────────────────────────────────────────
async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board = db.leaderboard_week(*week_bounds(0))
    if not board:
        await update.message.reply_text("Пока никто ничего не записал 🙂", reply_markup=MAIN_KB)
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


# ── Редактирование записей ───────────────────────────────────────
async def _show_edit_list(message, user_id: int):
    rows = db.recent_sets(user_id, limit=10)
    if not rows:
        await message.reply_text(
            "Пока нет записей. Сначала запиши перекур 🚬", reply_markup=MAIN_KB
        )
        return ConversationHandler.END

    buttons = []
    for set_id, ts, count in rows:
        when = ts.replace("T", " ")[5:16]  # MM-DD HH:MM
        label = f"№{set_id} · {when}" + (f" · {count} шт" if count != 1 else "")
        buttons.append([InlineKeyboardButton(label, callback_data=f"pick:{set_id}:{count}")])
    await message.reply_text(
        "Какую запись изменить? Выбери её:", reply_markup=InlineKeyboardMarkup(buttons)
    )
    await message.reply_text("…или нажми «Отмена».", reply_markup=CANCEL_KB)
    return EDIT_VALUE


async def edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _show_edit_list(update.message, update.effective_user.id)


async def edit_from_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await _show_edit_list(query.message, query.from_user.id)


async def edit_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        f"Запись №{set_id} (сейчас: {count} шт). Что сделать?", reply_markup=kb
    )
    return EDIT_VALUE


async def edit_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, set_id, count = query.data.split(":")
    context.user_data["edit_id"] = int(set_id)
    await query.edit_message_text(
        f"Запись №{set_id} (сейчас: {count} шт).\nНапиши новое число:"
    )
    return EDIT_VALUE


async def edit_delete_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_id = int(query.data.split(":")[1])
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"delok:{set_id}")],
            [InlineKeyboardButton("↩️ Нет, оставить", callback_data="delno")],
        ]
    )
    await query.edit_message_text(f"Точно удалить запись №{set_id}?", reply_markup=kb)
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
        f"Всего теперь: <b>{db.total_count(query.from_user.id)}</b>", reply_markup=MAIN_KB
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
    context.user_data.pop("ex_kind", None)
    await update.message.reply_text("Отменил. 👌", reply_markup=MAIN_KB)
    return ConversationHandler.END


async def conv_escape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажата кнопка главного меню посреди диалога — выходим из диалога
    и сразу выполняем то, что человек хотел (чтобы бот не «залипал»)."""
    context.user_data.pop("edit_id", None)
    context.user_data.pop("ex_kind", None)
    text = (update.message.text or "").strip()
    handler = {
        BTN_ADD: add_cmd,
        BTN_DELLAST: dellast_cmd,
        BTN_STATS: stats_menu,
        BTN_EXPENSES: expenses_menu,
        BTN_TOP: top_cmd,
        BTN_SETTINGS: settings_menu,
        BTN_HELP: help_cmd,
    }.get(text)
    if handler:
        await handler(update, context)
    return ConversationHandler.END


# ── Прочее ───────────────────────────────────────────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(HELP, reply_markup=MAIN_KB)


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_html(
        f"Сегодня ты выкурил <b>{db.today_count(u.id)}</b> раз 🚬", reply_markup=MAIN_KB
    )


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
    import re
    return filters.Regex(f"^{re.escape(label)}$")


def _main_buttons_filter() -> filters.BaseFilter:
    """Фильтр на любую кнопку главного меню — для аварийного выхода из диалогов."""
    import re
    pattern = "|".join(re.escape(b) for b in _MAIN_BUTTONS)
    return filters.Regex(f"^({pattern})$")


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Не задан BOT_TOKEN (см. .env.example)")

    db.init_db()
    os.makedirs(PHOTO_DIR, exist_ok=True)

    app = Application.builder().token(token).build()

    # Аварийный выход из любого диалога по кнопке главного меню
    escape_fb = MessageHandler(_main_buttons_filter(), conv_escape)
    common_fb = [
        CommandHandler("cancel", cancel),
        MessageHandler(_btn(BTN_CANCEL), cancel),
        escape_fb,
    ]
    # «Свободный» текст внутри диалога: всё, кроме кнопок меню и «Отмена»,
    # чтобы такие нажатия уходили в fallbacks (отмена / аварийный выход).
    free_text = (
        filters.TEXT & ~filters.COMMAND
        & ~_main_buttons_filter() & ~_btn(BTN_CANCEL)
    )

    # Регистрация / смена имени (в т.ч. из настроек)
    name_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("setname", setname_entry),
            CallbackQueryHandler(setname_from_cb, pattern=r"^se:name$"),
        ],
        states={NAME: [MessageHandler(free_text, name_received)]},
        fallbacks=common_fb,
        allow_reentry=True,
    )

    # Открытие упаковки расходника (тип → цена)
    expenses_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(expenses_new_entry, pattern=r"^ex:new$")],
        states={
            EX_PRICE: [
                CallbackQueryHandler(expenses_new_kind, pattern=r"^exnew:"),
                MessageHandler(free_text, expenses_new_price),
            ],
        },
        fallbacks=common_fb,
        per_message=False,
        allow_reentry=True,
    )

    # Редактирование (вход — из меню «⚙️ Настройки» или командой /edit)
    edit_conv = ConversationHandler(
        entry_points=[
            CommandHandler("edit", edit_entry),
            CallbackQueryHandler(edit_from_settings, pattern=r"^se:edit$"),
        ],
        states={
            EDIT_VALUE: [
                CallbackQueryHandler(edit_picked, pattern=r"^pick:"),
                CallbackQueryHandler(edit_change, pattern=r"^chg:"),
                CallbackQueryHandler(edit_delete_ask, pattern=r"^del:"),
                CallbackQueryHandler(edit_delete_ok, pattern=r"^delok:"),
                CallbackQueryHandler(edit_delete_no, pattern=r"^delno$"),
                MessageHandler(free_text, edit_value),
            ],
        },
        fallbacks=common_fb,
        allow_reentry=True,
    )

    app.add_handler(name_conv)
    app.add_handler(expenses_conv)
    app.add_handler(edit_conv)

    # Перекур + быстрое удаление последнего
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(MessageHandler(_btn(BTN_ADD), add_cmd))
    app.add_handler(CommandHandler("dellast", dellast_cmd))
    app.add_handler(MessageHandler(_btn(BTN_DELLAST), dellast_cmd))

    # Статистика
    app.add_handler(CommandHandler("stats", stats_menu))
    app.add_handler(MessageHandler(_btn(BTN_STATS), stats_menu))
    app.add_handler(CallbackQueryHandler(stats_action, pattern=r"^st:"))

    # Расходы
    app.add_handler(CommandHandler("expenses", expenses_menu))
    app.add_handler(MessageHandler(_btn(BTN_EXPENSES), expenses_menu))
    app.add_handler(CallbackQueryHandler(expenses_action, pattern=r"^ex:(close|chart)$"))
    app.add_handler(CallbackQueryHandler(expenses_close_kind, pattern=r"^exclose:"))

    # Настройки
    app.add_handler(CommandHandler("settings", settings_menu))
    app.add_handler(MessageHandler(_btn(BTN_SETTINGS), settings_menu))
    app.add_handler(CallbackQueryHandler(settings_currency_menu, pattern=r"^se:cur$"))
    app.add_handler(CallbackQueryHandler(settings_currency_set, pattern=r"^secur:"))

    # Рейтинг, помощь, прочее
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(MessageHandler(_btn(BTN_TOP), top_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(_btn(BTN_HELP), help_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    log.info("Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
