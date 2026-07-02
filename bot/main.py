"""Телеграм-бот «Счётчик сигарет» — интерактивный, с кнопками.

Логика простая: одна сигарета = один перекур. Нажал «Перекур +1» — записал.
Статистика спрятана под одной кнопкой, внутри — разные срезы (по часам суток,
по дням недели, динамика, интервалы, тренд). Деньги считаются не «по пачке»,
а по реальным расходникам: табак / бумага / фильтры / пачка сигарет — открыл
упаковку (записал цену), кончилась — отметил. Данные в SQLite.

Интерфейс локализован (английский по умолчанию, плюс русский и чешский) —
все строки живут в bot/i18n.py, язык хранится у пользователя в БД.
"""

from __future__ import annotations

import logging
import os
import re
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

from . import charts, db, i18n, rates

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO
)
log = logging.getLogger("cigarette-bot")

PHOTO_DIR = os.environ.get("PHOTO_DIR", "/data/photos")
MIN_PER_CIG = 5  # средняя длительность одной сигареты, минут (для оценки времени)

# ── Типы расходников (ключи; подписи берутся из i18n по языку) ────
KINDS = ["tobacco", "paper", "filters", "cigs"]

# ── Состояния диалогов ───────────────────────────────────────────
NAME, EDIT_VALUE, EX_PRICE = range(3)


# ── Клавиатуры (строятся под язык пользователя) ──────────────────
def main_kb(lang: str) -> ReplyKeyboardMarkup:
    T = lambda k: i18n.t(lang, k)
    return ReplyKeyboardMarkup(
        [
            [T("btn_add")],
            [T("btn_dellast")],
            [T("btn_stats"), T("btn_expenses")],
            [T("btn_top"), T("btn_settings")],
            [T("btn_help")],
        ],
        resize_keyboard=True,
    )


def cancel_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[i18n.t(lang, "btn_cancel")]], resize_keyboard=True)


def skip_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[i18n.t(lang, "btn_skip")]], resize_keyboard=True)


def stats_menu_kb(lang: str) -> InlineKeyboardMarkup:
    T = lambda k: i18n.t(lang, k)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(T("st_summary"), callback_data="st:summary")],
            [InlineKeyboardButton(T("st_hours"), callback_data="st:hours"),
             InlineKeyboardButton(T("st_weekday"), callback_data="st:weekday")],
            [InlineKeyboardButton(T("st_days"), callback_data="st:days"),
             InlineKeyboardButton(T("st_cumul"), callback_data="st:cumul")],
            [InlineKeyboardButton(T("st_intervals"), callback_data="st:intervals"),
             InlineKeyboardButton(T("st_trend"), callback_data="st:trend")],
        ]
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


def fmt_duration(td: timedelta, lang: str) -> str:
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    d, rem = divmod(total, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    dd, hh, mm = i18n.t(lang, "dur_d"), i18n.t(lang, "dur_h"), i18n.t(lang, "dur_m")
    if d:
        return f"{d} {dd} {h} {hh} {m} {mm}"
    if h:
        return f"{h} {hh} {m} {mm}"
    return f"{m} {mm}"


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
    lang = db.get_language(u.id)
    if is_new:
        await update.message.reply_html(
            i18n.t(lang, "start_new"), reply_markup=skip_kb(lang)
        )
        return NAME
    name = db.get_display_name(u.id) or u.first_name
    await update.message.reply_html(
        i18n.t(lang, "start_back", name=name) + "\n\n" + i18n.t(lang, "help"),
        reply_markup=main_kb(lang),
    )
    return ConversationHandler.END


async def setname_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    lang = db.get_language(u.id)
    current = db.get_display_name(u.id) or u.first_name
    await update.message.reply_html(
        i18n.t(lang, "setname_current", name=current), reply_markup=skip_kb(lang)
    )
    return NAME


async def setname_from_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    db.upsert_user(u.id, u.username, u.first_name)
    lang = db.get_language(u.id)
    current = db.get_display_name(u.id) or u.first_name
    await query.message.reply_html(
        i18n.t(lang, "setname_current", name=current), reply_markup=skip_kb(lang)
    )
    return NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    lang = db.get_language(u.id)
    text = (update.message.text or "").strip()
    if i18n.is_skip(text):
        name = db.get_display_name(u.id) or u.first_name
        await update.message.reply_html(
            i18n.t(lang, "name_kept", name=name), reply_markup=main_kb(lang)
        )
        return ConversationHandler.END
    if not text or len(text) > 32:
        await update.message.reply_text(
            i18n.t(lang, "name_bad"), reply_markup=skip_kb(lang)
        )
        return NAME
    db.set_display_name(u.id, text)
    await update.message.reply_html(
        i18n.t(lang, "name_done", name=text), reply_markup=main_kb(lang)
    )
    return ConversationHandler.END


# ── Перекур: просто +1 ────────────────────────────────────────────
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    lang = db.get_language(u.id)
    db.add_set(u.id, 1)
    total = db.total_count(u.id)
    today = db.today_count(u.id)
    now = datetime.now().strftime("%H:%M")
    await update.message.reply_html(
        i18n.t(lang, "add_logged", now=now, today=today, total=total),
        reply_markup=main_kb(lang),
    )


# ── Быстрое удаление последнего перекура ─────────────────────────
async def dellast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    lang = db.get_language(u.id)
    rows = db.recent_sets(u.id, limit=1)
    if not rows:
        await update.message.reply_text(
            i18n.t(lang, "dellast_none"), reply_markup=main_kb(lang)
        )
        return
    set_id, ts, _ = rows[0]
    when = ts.replace("T", " ")[5:16]  # MM-DD HH:MM
    db.delete_set(set_id)
    await update.message.reply_html(
        i18n.t(lang, "dellast_done", id=set_id, when=when,
               today=db.today_count(u.id), total=db.total_count(u.id)),
        reply_markup=main_kb(lang),
    )


# ── Статистика (одна кнопка → меню) ──────────────────────────────
async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = db.get_language(update.effective_user.id)
    await update.message.reply_html(
        i18n.t(lang, "stats_title"), reply_markup=stats_menu_kb(lang)
    )


async def stats_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    lang = db.get_language(u.id)
    what = query.data.split(":", 1)[1]
    msg = query.message

    total = db.total_count(u.id)
    if total == 0:
        await msg.reply_text(i18n.t(lang, "stats_nodata"), reply_markup=main_kb(lang))
        return

    if what == "summary":
        await _send_summary(msg, u.id)
    elif what == "hours":
        img = charts.hours_chart(db.by_hour(u.id), lang)
        await msg.reply_photo(img, caption=i18n.t(lang, "cap_hours"))
    elif what == "weekday":
        img = charts.weekday_chart(db.by_weekday(u.id), lang)
        await msg.reply_photo(img, caption=i18n.t(lang, "cap_weekday"))
    elif what == "days":
        img = charts.days_bar_chart(db.per_day(u.id), i18n.t(lang, "chart_days_title"), lang)
        await msg.reply_photo(img, caption=i18n.t(lang, "cap_days"))
    elif what == "cumul":
        img = charts.cumulative_chart(db.sessions(u.id), total, lang)
        await msg.reply_photo(img, caption=i18n.t(lang, "cap_cumul", total=total))
    elif what == "intervals":
        await _send_intervals(msg, u.id)
    elif what == "trend":
        await _send_trend(msg, u.id)


async def _send_summary(msg, user_id: int):
    lang = db.get_language(user_id)
    total = db.total_count(user_id)
    n = db.sets_count(user_id)
    days = db.per_day(user_id)
    per_day_avg = round(total / len(days), 1) if days else 0
    best = max((v for _, v in days), default=0)
    hrs = db.by_hour(user_id)
    peak_h = max(range(24), key=lambda i: hrs[i]) if any(hrs) else None

    lines = [
        i18n.t(lang, "sum_title"),
        i18n.t(lang, "sum_total", total=total),
        i18n.t(lang, "sum_breaks", n=n),
        i18n.t(lang, "sum_days", days=len(days)),
        i18n.t(lang, "sum_avg", avg=per_day_avg),
        i18n.t(lang, "sum_best", best=best),
    ]
    if peak_h is not None:
        lines.append(i18n.t(lang, "sum_peak", h=f"{peak_h:02d}"))

    spent = total_spent_converted(user_id)
    cur = user_currency(user_id)
    if spent > 0:
        lines.append(i18n.t(lang, "sum_spent", money=fmt_money(spent, cur)))
    lines.append(
        i18n.t(lang, "sum_time",
               dur=fmt_duration(timedelta(minutes=total * MIN_PER_CIG), lang))
    )
    await msg.reply_html("\n".join(lines), reply_markup=main_kb(lang))


async def _send_intervals(msg, user_id: int):
    lang = db.get_language(user_id)
    sess = db.sessions(user_id)
    times = [datetime.fromisoformat(ts) for ts, _ in sess]
    now = datetime.now()
    since_last = now - times[-1]
    lines = [
        i18n.t(lang, "int_title"),
        i18n.t(lang, "int_since", dur=fmt_duration(since_last, lang)),
    ]
    if len(times) >= 2:
        diffs = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        longest = max(diffs)
        avg = sum(diffs, timedelta()) / len(diffs)
        lines.append(i18n.t(lang, "int_longest", dur=fmt_duration(longest, lang)))
        lines.append(i18n.t(lang, "int_avg", dur=fmt_duration(avg, lang)))
    else:
        lines.append(i18n.t(lang, "int_more"))
    await msg.reply_html("\n".join(lines), reply_markup=main_kb(lang))


async def _send_trend(msg, user_id: int):
    lang = db.get_language(user_id)
    this = db.range_total(user_id, *week_bounds(0))
    last = db.range_total(user_id, *week_bounds(1))
    if this == 0 and last == 0:
        await msg.reply_text(i18n.t(lang, "trend_none"), reply_markup=main_kb(lang))
        return
    if last == 0:
        verdict = i18n.t(lang, "trend_nolast")
    else:
        diff = this - last
        pct = diff / last * 100
        if diff < 0:
            verdict = i18n.t(lang, "trend_less", pct=f"{-pct:.0f}", diff=diff)
        elif diff > 0:
            verdict = i18n.t(lang, "trend_more", pct=f"{pct:.0f}", diff=diff)
        else:
            verdict = i18n.t(lang, "trend_same")
    await msg.reply_html(
        i18n.t(lang, "trend_body", this=this, last=last, verdict=verdict),
        reply_markup=main_kb(lang),
    )


# ── Расходы (расходники) ─────────────────────────────────────────
def expenses_menu_kb(lang: str) -> InlineKeyboardMarkup:
    T = lambda k: i18n.t(lang, k)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(T("ex_new"), callback_data="ex:new")],
            [InlineKeyboardButton(T("ex_close"), callback_data="ex:close")],
            [InlineKeyboardButton(T("ex_chart"), callback_data="ex:chart")],
        ]
    )


def _expenses_text(user_id: int) -> str:
    lang = db.get_language(user_id)
    cur = user_currency(user_id)
    spent = total_spent_converted(user_id)
    total_cigs = db.total_count(user_id)
    lines = [i18n.t(lang, "exp_title")]
    open_items = db.open_consumables(user_id)
    if open_items:
        lines.append(i18n.t(lang, "exp_open_now"))
        for kind, price, c, _ in open_items:
            shown = fmt_money(rates.convert(price, c or cur, cur), cur)
            # если покупал в другой валюте — подскажем исходную цену
            if c and c != cur:
                shown += f" <i>({fmt_money(price, c)})</i>"
            lines.append(f"• {i18n.kind_label(lang, kind)} — {shown}")
    else:
        lines.append(i18n.t(lang, "exp_none_open"))
    if spent > 0:
        lines.append(i18n.t(lang, "exp_total", money=fmt_money(spent, cur)))
        if total_cigs:
            lines.append(i18n.t(lang, "exp_per_cig", money=fmt_money(spent / total_cigs, cur)))
    else:
        lines.append(i18n.t(lang, "exp_hint"))
    return "\n".join(lines)


async def expenses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    lang = db.get_language(u.id)
    await update.message.reply_html(
        _expenses_text(u.id), reply_markup=expenses_menu_kb(lang)
    )


def _kind_kb(prefix: str, kinds: list[str], lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(i18n.kind_label(lang, k), callback_data=f"{prefix}:{k}")]
        for k in kinds
    ]
    return InlineKeyboardMarkup(rows)


async def expenses_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопки меню расходов, КРОМЕ «открыть» (та — отдельный диалог)."""
    query = update.callback_query
    await query.answer()
    u = query.from_user
    lang = db.get_language(u.id)
    action = query.data.split(":", 1)[1]

    if action == "close":
        open_items = db.open_consumables(u.id)
        if not open_items:
            await query.edit_message_text(i18n.t(lang, "exp_no_open"))
            await query.message.reply_text(i18n.t(lang, "main_menu"), reply_markup=main_kb(lang))
            return
        kinds = [k for k, *_ in open_items]
        await query.edit_message_text(
            i18n.t(lang, "exp_which_closed"), reply_markup=_kind_kb("exclose", kinds, lang)
        )
    elif action == "chart":
        by_kind = spent_by_kind_converted(u.id)
        if not by_kind:
            await query.message.reply_text(
                i18n.t(lang, "exp_no_spend"), reply_markup=main_kb(lang)
            )
            return
        cur = user_currency(u.id)
        items = [(i18n.kind_label(lang, k), total) for k, total in by_kind]
        img = charts.spend_by_kind_chart(items, cur, lang)
        await query.message.reply_photo(img, caption=i18n.t(lang, "cap_spend"))


async def expenses_close_kind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    lang = db.get_language(u.id)
    kind = query.data.split(":", 1)[1]
    ok = db.close_consumable(u.id, kind)
    label = i18n.kind_label(lang, kind)
    if ok:
        await query.edit_message_text(i18n.t(lang, "exp_closed_ok", label=label))
    else:
        await query.edit_message_text(i18n.t(lang, "exp_closed_already", label=label))
    await query.message.reply_html(_expenses_text(u.id), reply_markup=expenses_menu_kb(lang))


# ── Открытие упаковки (диалог: тип → цена) ───────────────────────
async def expenses_new_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_language(query.from_user.id)
    await query.edit_message_text(
        i18n.t(lang, "exp_what_open"), reply_markup=_kind_kb("exnew", KINDS, lang)
    )
    return EX_PRICE  # ждём выбор типа (кнопка), потом цену


async def expenses_new_kind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    lang = db.get_language(u.id)
    kind = query.data.split(":", 1)[1]
    context.user_data["ex_kind"] = kind
    cur = user_currency(u.id)
    await query.edit_message_text(
        i18n.t(lang, "exp_price_q", label=i18n.kind_label(lang, kind), cur=cur)
    )
    await query.message.reply_text(i18n.t(lang, "cancel_hint"), reply_markup=cancel_kb(lang))
    return EX_PRICE


async def expenses_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    lang = db.get_language(u.id)
    raw = (update.message.text or "").strip()
    if i18n.is_cancel(raw):
        return await cancel(update, context)
    text = raw.replace(",", ".")
    kind = context.user_data.get("ex_kind")
    if not kind:
        await update.message.reply_text(
            i18n.t(lang, "exp_pick_first"), reply_markup=cancel_kb(lang)
        )
        return EX_PRICE
    try:
        price = float(text)
    except ValueError:
        await update.message.reply_text(
            i18n.t(lang, "exp_not_number"), reply_markup=cancel_kb(lang)
        )
        return EX_PRICE
    if price <= 0 or price > 1_000_000:
        await update.message.reply_text(
            i18n.t(lang, "exp_bad_price"), reply_markup=cancel_kb(lang)
        )
        return EX_PRICE

    cur = user_currency(u.id)
    db.open_consumable(u.id, kind, price, cur)
    context.user_data.pop("ex_kind", None)
    await update.message.reply_html(
        i18n.t(lang, "exp_opened", label=i18n.kind_label(lang, kind), money=fmt_money(price, cur)),
        reply_markup=main_kb(lang),
    )
    await update.message.reply_html(_expenses_text(u.id), reply_markup=expenses_menu_kb(lang))
    return ConversationHandler.END


# ── Настройки (имя + валюта + язык) ──────────────────────────────
def settings_menu_kb(lang: str) -> InlineKeyboardMarkup:
    T = lambda k: i18n.t(lang, k)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(T("se_name"), callback_data="se:name")],
            [InlineKeyboardButton(T("se_cur"), callback_data="se:cur")],
            [InlineKeyboardButton(T("se_lang"), callback_data="se:lang")],
            [InlineKeyboardButton(T("se_edit"), callback_data="se:edit")],
        ]
    )


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    lang = db.get_language(u.id)
    name = db.get_display_name(u.id) or u.first_name
    cur = user_currency(u.id)
    await update.message.reply_html(
        i18n.t(lang, "se_title", name=name, cur=cur, lang_name=i18n.lang_name(lang)),
        reply_markup=settings_menu_kb(lang),
    )


async def settings_currency_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_language(query.from_user.id)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(lang, "cur_eur"), callback_data="secur:€")],
            [InlineKeyboardButton(i18n.t(lang, "cur_uah"), callback_data="secur:грн")],
            [InlineKeyboardButton(i18n.t(lang, "cur_czk"), callback_data="secur:Kč")],
        ]
    )
    r = rates.get_rates()
    note = i18n.t(lang, "cur_note", uah=f"{r.get('UAH', 0):.1f}", czk=f"{r.get('CZK', 0):.1f}")
    await query.edit_message_text(
        i18n.t(lang, "cur_choose") + note, parse_mode="HTML", reply_markup=kb
    )


async def settings_currency_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    lang = db.get_language(u.id)
    cur = query.data.split(":", 1)[1]
    db.set_currency(u.id, cur)
    await query.edit_message_text(i18n.t(lang, "cur_set", cur=cur))
    await query.message.reply_text(i18n.t(lang, "main_menu"), reply_markup=main_kb(lang))


async def settings_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_language(query.from_user.id)
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.lang_name(code), callback_data=f"selang:{code}")]
         for code in i18n.LANGS]
    )
    await query.edit_message_text(i18n.t(lang, "lang_choose"), reply_markup=kb)


async def settings_language_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user
    code = query.data.split(":", 1)[1]
    if code not in i18n.LANGS:
        code = i18n.DEFAULT_LANG
    db.set_language(u.id, code)
    await query.edit_message_text(i18n.t(code, "lang_set", lang_name=i18n.lang_name(code)))
    await query.message.reply_text(i18n.t(code, "main_menu"), reply_markup=main_kb(code))


# ── Рейтинг ──────────────────────────────────────────────────────
async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = db.get_language(update.effective_user.id)
    board = db.leaderboard_week(*week_bounds(0))
    if not board:
        await update.message.reply_text(i18n.t(lang, "top_empty"), reply_markup=main_kb(lang))
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [i18n.t(lang, "top_title"), i18n.t(lang, "top_sub"), ""]
    for i, (name, week) in enumerate(board):
        mark = medals[i] if i < 3 else f"{i + 1}."
        lines.append(i18n.t(lang, "top_line", mark=mark, name=name, week=week))
    await update.message.reply_html("\n".join(lines), reply_markup=main_kb(lang))


# ── Редактирование записей ───────────────────────────────────────
async def _show_edit_list(message, user_id: int):
    lang = db.get_language(user_id)
    rows = db.recent_sets(user_id, limit=10)
    if not rows:
        await message.reply_text(i18n.t(lang, "edit_none"), reply_markup=main_kb(lang))
        return ConversationHandler.END

    buttons = []
    for set_id, ts, count in rows:
        when = ts.replace("T", " ")[5:16]  # MM-DD HH:MM
        label = f"#{set_id} · {when}" + (f" · {count}×" if count != 1 else "")
        buttons.append([InlineKeyboardButton(label, callback_data=f"pick:{set_id}:{count}")])
    await message.reply_text(
        i18n.t(lang, "edit_pick"), reply_markup=InlineKeyboardMarkup(buttons)
    )
    await message.reply_text(i18n.t(lang, "cancel_hint"), reply_markup=cancel_kb(lang))
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
    lang = db.get_language(query.from_user.id)
    _, set_id, count = query.data.split(":")
    set_id = int(set_id)
    if db.set_owner(set_id) != query.from_user.id:
        await query.edit_message_text(i18n.t(lang, "edit_notyours"))
        return ConversationHandler.END
    context.user_data["edit_id"] = set_id
    context.user_data.pop("edit_mode", None)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(lang, "edit_chg"), callback_data=f"chg:{set_id}:{count}")],
            [InlineKeyboardButton(i18n.t(lang, "edit_time"), callback_data=f"time:{set_id}")],
            [InlineKeyboardButton(i18n.t(lang, "edit_del"), callback_data=f"del:{set_id}")],
        ]
    )
    await query.edit_message_text(
        i18n.t(lang, "edit_what", id=set_id, count=count), reply_markup=kb
    )
    return EDIT_VALUE


async def edit_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_language(query.from_user.id)
    _, set_id, count = query.data.split(":")
    context.user_data["edit_id"] = int(set_id)
    context.user_data["edit_mode"] = "count"
    await query.edit_message_text(
        i18n.t(lang, "edit_change_prompt", id=set_id, count=count)
    )
    return EDIT_VALUE


async def edit_time_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_language(query.from_user.id)
    set_id = int(query.data.split(":")[1])
    if db.set_owner(set_id) != query.from_user.id:
        await query.edit_message_text(i18n.t(lang, "edit_notyours"))
        return ConversationHandler.END
    context.user_data["edit_id"] = set_id
    context.user_data["edit_mode"] = "time"
    cur_iso = db.set_created_at(set_id)
    now = cur_iso.replace("T", " ")[:16] if cur_iso else ""
    await query.edit_message_text(
        i18n.t(lang, "edit_time_prompt", id=set_id, now=now), parse_mode="HTML"
    )
    return EDIT_VALUE


async def edit_delete_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_language(query.from_user.id)
    set_id = int(query.data.split(":")[1])
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(lang, "del_yes"), callback_data=f"delok:{set_id}")],
            [InlineKeyboardButton(i18n.t(lang, "del_no"), callback_data="delno")],
        ]
    )
    await query.edit_message_text(i18n.t(lang, "edit_del_confirm", id=set_id), reply_markup=kb)
    return EDIT_VALUE


async def edit_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_language(query.from_user.id)
    set_id = int(query.data.split(":")[1])
    if db.set_owner(set_id) != query.from_user.id:
        await query.edit_message_text(i18n.t(lang, "edit_notyours"))
        return ConversationHandler.END
    db.delete_set(set_id)
    context.user_data.pop("edit_id", None)
    context.user_data.pop("edit_mode", None)
    await query.edit_message_text(i18n.t(lang, "edit_deleted", id=set_id))
    await query.message.reply_html(
        i18n.t(lang, "total_now", total=db.total_count(query.from_user.id)),
        reply_markup=main_kb(lang),
    )
    return ConversationHandler.END


async def edit_delete_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_language(query.from_user.id)
    context.user_data.pop("edit_id", None)
    context.user_data.pop("edit_mode", None)
    await query.edit_message_text(i18n.t(lang, "edit_del_no"))
    await query.message.reply_text(i18n.t(lang, "main_menu"), reply_markup=main_kb(lang))
    return ConversationHandler.END


def _parse_new_time(text: str, current_iso: str) -> str | None:
    """Разбирает введённое пользователем время в ISO-строку.
    Недостающие части (год/дату) берёт из текущего времени записи."""
    text = text.strip().replace("T", " ")
    try:
        cur = datetime.fromisoformat(current_iso)
    except (ValueError, TypeError):
        cur = datetime.now()
    fmts = [
        ("%Y-%m-%d %H:%M:%S", None),
        ("%Y-%m-%d %H:%M", None),
        ("%d.%m.%Y %H:%M", None),
        ("%d.%m %H:%M", "year"),
        ("%d.%m.%Y", None),
        ("%d.%m", "year"),
        ("%H:%M:%S", "date"),
        ("%H:%M", "date"),
    ]
    for fmt, fill in fmts:
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fill == "year":
            dt = dt.replace(year=cur.year)
        elif fill == "date":
            dt = dt.replace(year=cur.year, month=cur.month, day=cur.day)
        return dt.replace(second=0, microsecond=0).isoformat(timespec="seconds")
    return None


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    lang = db.get_language(u.id)
    raw = (update.message.text or "").strip()
    if i18n.is_cancel(raw):
        return await cancel(update, context)
    set_id = context.user_data.get("edit_id")
    if set_id is None:
        await update.message.reply_text(
            i18n.t(lang, "edit_pick_first"), reply_markup=cancel_kb(lang)
        )
        return EDIT_VALUE
    if db.set_owner(set_id) != u.id:
        await update.message.reply_text(i18n.t(lang, "edit_notyours"), reply_markup=main_kb(lang))
        context.user_data.pop("edit_id", None)
        context.user_data.pop("edit_mode", None)
        return ConversationHandler.END
    if context.user_data.get("edit_mode") == "time":
        new_iso = _parse_new_time(raw, db.set_created_at(set_id))
        if new_iso is None:
            await update.message.reply_text(
                i18n.t(lang, "edit_time_bad"), reply_markup=cancel_kb(lang)
            )
            return EDIT_VALUE
        db.edit_set_time(set_id, new_iso)
        context.user_data.pop("edit_id", None)
        context.user_data.pop("edit_mode", None)
        await update.message.reply_html(
            i18n.t(lang, "edit_time_done", id=set_id, when=new_iso.replace("T", " ")[:16]),
            reply_markup=main_kb(lang),
        )
        return ConversationHandler.END
    if i18n.is_delete_word(raw):
        db.delete_set(set_id)
        context.user_data.pop("edit_id", None)
        context.user_data.pop("edit_mode", None)
        await update.message.reply_html(
            i18n.t(lang, "edit_del_bytext", id=set_id, total=db.total_count(u.id)),
            reply_markup=main_kb(lang),
        )
        return ConversationHandler.END
    try:
        count = int(raw)
    except ValueError:
        await update.message.reply_text(
            i18n.t(lang, "edit_bad_number"), reply_markup=cancel_kb(lang)
        )
        return EDIT_VALUE
    if count <= 0 or count > 10000:
        await update.message.reply_text(
            i18n.t(lang, "edit_range"), reply_markup=cancel_kb(lang)
        )
        return EDIT_VALUE
    db.edit_set(set_id, count)
    context.user_data.pop("edit_id", None)
    context.user_data.pop("edit_mode", None)
    await update.message.reply_html(
        i18n.t(lang, "edit_changed", id=set_id, count=count, total=db.total_count(u.id)),
        reply_markup=main_kb(lang),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = db.get_language(update.effective_user.id)
    context.user_data.pop("edit_id", None)
    context.user_data.pop("edit_mode", None)
    context.user_data.pop("ex_kind", None)
    await update.message.reply_text(i18n.t(lang, "cancelled"), reply_markup=main_kb(lang))
    return ConversationHandler.END


async def conv_escape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажата кнопка главного меню посреди диалога — выходим из диалога
    и сразу выполняем то, что человек хотел (чтобы бот не «залипал»)."""
    context.user_data.pop("edit_id", None)
    context.user_data.pop("edit_mode", None)
    context.user_data.pop("ex_kind", None)
    text = (update.message.text or "").strip()
    handlers = {
        "btn_add": add_cmd,
        "btn_dellast": dellast_cmd,
        "btn_stats": stats_menu,
        "btn_expenses": expenses_menu,
        "btn_top": top_cmd,
        "btn_settings": settings_menu,
        "btn_help": help_cmd,
    }
    for key, handler in handlers.items():
        if text in i18n.variants(key):
            await handler(update, context)
            break
    return ConversationHandler.END


# ── Прочее ───────────────────────────────────────────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = db.get_language(update.effective_user.id)
    await update.message.reply_html(i18n.t(lang, "help"), reply_markup=main_kb(lang))


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    lang = db.get_language(u.id)
    await update.message.reply_html(
        i18n.t(lang, "today_cmd", n=db.today_count(u.id)), reply_markup=main_kb(lang)
    )


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    lang = db.get_language(u.id)
    set_id = db.last_set_id(u.id)
    if set_id is None:
        await update.message.reply_text(
            i18n.t(lang, "photo_no_break"), reply_markup=main_kb(lang)
        )
        return
    user_dir = os.path.join(PHOTO_DIR, str(u.id))
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"set_{set_id}.jpg")
    tg_file = await update.message.photo[-1].get_file()
    await tg_file.download_to_drive(path)
    db.attach_photo(set_id, path)
    await update.message.reply_text(i18n.t(lang, "photo_saved"), reply_markup=main_kb(lang))


# ── Фильтры по кнопкам (совпадение на любом из языков) ───────────
def _variants_filter(keys: list[str]) -> filters.BaseFilter:
    strings: list[str] = []
    for key in keys:
        strings += i18n.variants(key)
    pattern = "|".join(re.escape(s) for s in strings)
    return filters.Regex(f"^({pattern})$")


def _btn(key: str) -> filters.BaseFilter:
    return _variants_filter([key])


def _main_buttons_filter() -> filters.BaseFilter:
    """Фильтр на любую кнопку главного меню (все языки) — для аварийного выхода."""
    return _variants_filter(i18n.MAIN_BTN_KEYS)


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
        MessageHandler(_btn("btn_cancel"), cancel),
        escape_fb,
    ]
    # «Свободный» текст внутри диалога: всё, кроме кнопок меню и «Отмена»,
    # чтобы такие нажатия уходили в fallbacks (отмена / аварийный выход).
    free_text = (
        filters.TEXT & ~filters.COMMAND
        & ~_main_buttons_filter() & ~_btn("btn_cancel")
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
                CallbackQueryHandler(edit_time_ask, pattern=r"^time:"),
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
    app.add_handler(MessageHandler(_btn("btn_add"), add_cmd))
    app.add_handler(CommandHandler("dellast", dellast_cmd))
    app.add_handler(MessageHandler(_btn("btn_dellast"), dellast_cmd))

    # Статистика
    app.add_handler(CommandHandler("stats", stats_menu))
    app.add_handler(MessageHandler(_btn("btn_stats"), stats_menu))
    app.add_handler(CallbackQueryHandler(stats_action, pattern=r"^st:"))

    # Расходы
    app.add_handler(CommandHandler("expenses", expenses_menu))
    app.add_handler(MessageHandler(_btn("btn_expenses"), expenses_menu))
    app.add_handler(CallbackQueryHandler(expenses_action, pattern=r"^ex:(close|chart)$"))
    app.add_handler(CallbackQueryHandler(expenses_close_kind, pattern=r"^exclose:"))

    # Настройки
    app.add_handler(CommandHandler("settings", settings_menu))
    app.add_handler(MessageHandler(_btn("btn_settings"), settings_menu))
    app.add_handler(CallbackQueryHandler(settings_currency_menu, pattern=r"^se:cur$"))
    app.add_handler(CallbackQueryHandler(settings_currency_set, pattern=r"^secur:"))
    app.add_handler(CallbackQueryHandler(settings_language_menu, pattern=r"^se:lang$"))
    app.add_handler(CallbackQueryHandler(settings_language_set, pattern=r"^selang:"))

    # Рейтинг, помощь, прочее
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(MessageHandler(_btn("btn_top"), top_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(_btn("btn_help"), help_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    log.info("Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
