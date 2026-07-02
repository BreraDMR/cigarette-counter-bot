"""Локализация интерфейса бота: русский, английский, чешский.

Все видимые пользователю строки живут здесь. Каждый ключ — словарь
{lang: шаблон}. Плейсхолдеры подставляются через str.format(**kwargs).

Язык по умолчанию для новых пользователей — английский (см. db.get_language).
"""

from __future__ import annotations

LANGS = ["en", "ru", "cs"]
DEFAULT_LANG = "en"

# Человекочитаемые названия языков (для меню и настроек)
LANG_NAMES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "cs": "🇨🇿 Čeština",
}

# Логические кнопки главного меню (для фильтров и аварийного выхода)
MAIN_BTN_KEYS = [
    "btn_add", "btn_dellast", "btn_stats",
    "btn_expenses", "btn_top", "btn_settings", "btn_help",
]

# Дни недели для графиков
WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    "cs": ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"],
}

# Названия типов расходников
KIND_LABELS = {
    "tobacco": {"en": "🌿 Tobacco", "ru": "🌿 Табак", "cs": "🌿 Tabák"},
    "paper":   {"en": "📄 Paper", "ru": "📄 Бумага", "cs": "📄 Papírky"},
    "filters": {"en": "⚪️ Filters", "ru": "⚪️ Фильтры", "cs": "⚪️ Filtry"},
    "cigs":    {"en": "🚬 Pack of cigarettes", "ru": "🚬 Пачка сигарет", "cs": "🚬 Krabička cigaret"},
}

# Слова-команды удаления записи текстом (все языки)
DELETE_WORDS = {"удалить", "удали", "delete", "del", "smazat", "smaž", "smaz"}

STRINGS: dict[str, dict[str, str]] = {
    # ── Кнопки главного меню ──────────────────────────────────────
    "btn_add":      {"en": "🚬 Smoke +1", "ru": "🚬 Перекур +1", "cs": "🚬 Cigareta +1"},
    "btn_dellast":  {"en": "🗑 Delete last", "ru": "🗑 Удалить последний", "cs": "🗑 Smazat poslední"},
    "btn_stats":    {"en": "📊 Statistics", "ru": "📊 Статистика", "cs": "📊 Statistiky"},
    "btn_expenses": {"en": "💸 Expenses", "ru": "💸 Расходы", "cs": "💸 Výdaje"},
    "btn_top":      {"en": "🏆 Leaderboard", "ru": "🏆 Рейтинг", "cs": "🏆 Žebříček"},
    "btn_settings": {"en": "⚙️ Settings", "ru": "⚙️ Настройки", "cs": "⚙️ Nastavení"},
    "btn_help":     {"en": "ℹ️ Help", "ru": "ℹ️ Помощь", "cs": "ℹ️ Nápověda"},
    "btn_cancel":   {"en": "❌ Cancel", "ru": "❌ Отмена", "cs": "❌ Zrušit"},
    "btn_skip":     {"en": "⏭ Skip", "ru": "⏭ Пропустить", "cs": "⏭ Přeskočit"},

    # ── Длительность (единицы) ────────────────────────────────────
    "dur_d": {"en": "d", "ru": "дн", "cs": "d"},
    "dur_h": {"en": "h", "ru": "ч", "cs": "h"},
    "dur_m": {"en": "m", "ru": "мин", "cs": "min"},

    # ── Помощь ────────────────────────────────────────────────────
    "help": {
        "en": (
            "🚬 <b>Cigarette counter</b>\n\n"
            "Use the buttons below 👇\n\n"
            "• <b>🚬 Smoke +1</b> — logs one cigarette. One smoke break = one cigarette.\n"
            "• <b>🗑 Delete last</b> — quickly remove the last break (if you tapped by mistake).\n"
            "• <b>📊 Statistics</b> — all in one menu: summary, by hour of day "
            "(when cravings hit), by weekday, dynamics, intervals, trend.\n"
            "• <b>💸 Expenses</b> — track supplies: tobacco, paper, filters or a pack. "
            "Opened a pack — log its price; ran out — mark it. The bot counts how much "
            "money went up in smoke and where exactly.\n"
            "• <b>🏆 Leaderboard</b> — who's calmer this week (fewer = higher).\n"
            "• <b>⚙️ Settings</b> — change name, currency, language and edit/delete entries.\n\n"
            "📷 After a break you can send a photo — it'll be linked to the last entry."
        ),
        "ru": (
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
            "• <b>⚙️ Настройки</b> — сменить имя, валюту, язык и поправить/удалить записи.\n\n"
            "📷 После перекура можешь прислать фото — оно привяжется к последней записи."
        ),
        "cs": (
            "🚬 <b>Počítadlo cigaret</b>\n\n"
            "Používej tlačítka dole 👇\n\n"
            "• <b>🚬 Cigareta +1</b> — zapíše jednu cigaretu. Jedna pauza = jedna cigareta.\n"
            "• <b>🗑 Smazat poslední</b> — rychle odebere poslední pauzu (když klikneš omylem).\n"
            "• <b>📊 Statistiky</b> — vše v jednom menu: přehled, podle hodin dne "
            "(kdy to táhne nejvíc), podle dní v týdnu, vývoj, intervaly, trend.\n"
            "• <b>💸 Výdaje</b> — evidence spotřebáku: tabák, papírky, filtry nebo krabička. "
            "Otevřel jsi balení — zapiš cenu; došlo — označ. Bot spočítá, kolik peněz "
            "šlo „do kouře“ a kam přesně.\n"
            "• <b>🏆 Žebříček</b> — kdo je za týden klidnější (méně = výš).\n"
            "• <b>⚙️ Nastavení</b> — změnit jméno, měnu, jazyk a upravit/smazat záznamy.\n\n"
            "📷 Po pauze můžeš poslat fotku — připojí se k poslednímu záznamu."
        ),
    },

    # ── Регистрация / имя ─────────────────────────────────────────
    "start_new": {
        "en": ("Hi! 👋 I count your cigarettes. One smoke break = one cigarette.\n\n"
               "How should I show you on the leaderboard? Type a name "
               "or tap “Skip” to keep your Telegram name."),
        "ru": ("Привет! 👋 Я считаю твои сигареты. Один перекур — одна сигарета.\n\n"
               "Как тебя записать в рейтинге? Напиши имя "
               "или нажми «Пропустить», чтобы оставить имя из Telegram."),
        "cs": ("Ahoj! 👋 Počítám tvoje cigarety. Jedna pauza = jedna cigareta.\n\n"
               "Jak tě mám zobrazit v žebříčku? Napiš jméno "
               "nebo klikni na „Přeskočit“, aby zůstalo jméno z Telegramu."),
    },
    "start_back": {
        "en": "Welcome back, <b>{name}</b>! 🚬",
        "ru": "С возвращением, <b>{name}</b>! 🚬",
        "cs": "Vítej zpět, <b>{name}</b>! 🚬",
    },
    "setname_current": {
        "en": "You're currently shown as <b>{name}</b>.\nType a new name or tap “Skip”.",
        "ru": "Сейчас ты записан как <b>{name}</b>.\nНапиши новое имя или нажми «Пропустить».",
        "cs": "Teď jsi zobrazen jako <b>{name}</b>.\nNapiš nové jméno nebo klikni na „Přeskočit“.",
    },
    "name_kept": {
        "en": "OK, kept the name <b>{name}</b>. 👍",
        "ru": "Ок, оставил имя <b>{name}</b>. 👍",
        "cs": "OK, ponechal jsem jméno <b>{name}</b>. 👍",
    },
    "name_bad": {
        "en": "The name must be 1–32 characters. Try again.",
        "ru": "Имя должно быть от 1 до 32 символов. Попробуй ещё раз.",
        "cs": "Jméno musí mít 1–32 znaků. Zkus to znovu.",
    },
    "name_done": {
        "en": "Done! You're now <b>{name}</b>. 🎉",
        "ru": "Готово! Теперь ты — <b>{name}</b>. 🎉",
        "cs": "Hotovo! Teď jsi <b>{name}</b>. 🎉",
    },

    # ── Перекур / удаление последнего ─────────────────────────────
    "add_logged": {
        "en": ("✅ Smoke break logged at {now} 🚬\n"
               "Today: <b>{today}</b>  ·  Total: <b>{total}</b>\n"
               "📷 You can send a photo for this break."),
        "ru": ("✅ Перекур записан в {now} 🚬\n"
               "Сегодня: <b>{today}</b>  ·  Всего: <b>{total}</b>\n"
               "📷 Можешь прислать фото к этому перекуру."),
        "cs": ("✅ Pauza zapsána v {now} 🚬\n"
               "Dnes: <b>{today}</b>  ·  Celkem: <b>{total}</b>\n"
               "📷 Můžeš k této pauze poslat fotku."),
    },
    "dellast_none": {
        "en": "No entries — nothing to delete 🤷",
        "ru": "Нет записей — удалять нечего 🤷",
        "cs": "Žádné záznamy — není co mazat 🤷",
    },
    "dellast_done": {
        "en": ("🗑 Deleted the last break (#{id} · {when}).\n"
               "Today: <b>{today}</b>  ·  Total: <b>{total}</b>"),
        "ru": ("🗑 Удалил последний перекур (№{id} · {when}).\n"
               "Сегодня: <b>{today}</b>  ·  Всего: <b>{total}</b>"),
        "cs": ("🗑 Smazal jsem poslední pauzu (č. {id} · {when}).\n"
               "Dnes: <b>{today}</b>  ·  Celkem: <b>{total}</b>"),
    },

    # ── Статистика ────────────────────────────────────────────────
    "stats_title": {
        "en": "📊 <b>Statistics</b>\nWhat to show?",
        "ru": "📊 <b>Статистика</b>\nЧто показать?",
        "cs": "📊 <b>Statistiky</b>\nCo zobrazit?",
    },
    "stats_nodata": {
        "en": "No data yet. Tap “🚬 Smoke +1” 🚬",
        "ru": "Пока нет данных. Нажми «🚬 Перекур +1» 🚬",
        "cs": "Zatím žádná data. Klikni na „🚬 Cigareta +1“ 🚬",
    },
    "st_summary":  {"en": "📋 Summary", "ru": "📋 Сводка", "cs": "📋 Přehled"},
    "st_hours":    {"en": "🕐 By hour of day", "ru": "🕐 По часам суток", "cs": "🕐 Podle hodin dne"},
    "st_weekday":  {"en": "📅 By weekday", "ru": "📅 По дням недели", "cs": "📅 Podle dní v týdnu"},
    "st_days":     {"en": "📈 Daily dynamics", "ru": "📈 Динамика по дням", "cs": "📈 Vývoj po dnech"},
    "st_cumul":    {"en": "🔥 Cumulative", "ru": "🔥 Накопительно", "cs": "🔥 Kumulativně"},
    "st_intervals": {"en": "⏱ Intervals", "ru": "⏱ Интервалы", "cs": "⏱ Intervaly"},
    "st_trend":    {"en": "📉 Weekly trend", "ru": "📉 Тренд по неделям", "cs": "📉 Týdenní trend"},

    "cap_hours":   {"en": "🕐 When cravings hit most", "ru": "🕐 В какое время суток тянет чаще", "cs": "🕐 Kdy tě to táhne nejčastěji"},
    "cap_weekday": {"en": "📅 By weekday", "ru": "📅 По дням недели", "cs": "📅 Podle dní v týdnu"},
    "cap_days":    {"en": "📈 How many each day", "ru": "📈 Сколько в какой день", "cs": "📈 Kolik který den"},
    "cap_cumul":   {"en": "🔥 Total cigarettes: {total}", "ru": "🔥 Всего сигарет: {total}", "cs": "🔥 Cigaret celkem: {total}"},

    "sum_title":  {"en": "📋 <b>Summary</b>", "ru": "📋 <b>Сводка</b>", "cs": "📋 <b>Přehled</b>"},
    "sum_total":  {"en": "Total cigarettes: <b>{total}</b>", "ru": "Всего сигарет: <b>{total}</b>", "cs": "Cigaret celkem: <b>{total}</b>"},
    "sum_breaks": {"en": "Smoke breaks: <b>{n}</b>", "ru": "Перекуров: <b>{n}</b>", "cs": "Pauz: <b>{n}</b>"},
    "sum_days":   {"en": "Days smoked: <b>{days}</b>", "ru": "Дней с курением: <b>{days}</b>", "cs": "Dní s kouřením: <b>{days}</b>"},
    "sum_avg":    {"en": "Average per day: <b>{avg}</b>", "ru": "В среднем за день: <b>{avg}</b>", "cs": "Průměrně za den: <b>{avg}</b>"},
    "sum_best":   {"en": "Most in a day: <b>{best}</b>", "ru": "Больше всего за день: <b>{best}</b>", "cs": "Nejvíc za den: <b>{best}</b>"},
    "sum_peak":   {"en": "You smoke most around <b>{h}:00</b>", "ru": "Чаще всего куришь около <b>{h}:00</b>", "cs": "Nejčastěji kouříš kolem <b>{h}:00</b>"},
    "sum_spent":  {"en": "💸 Spent on supplies: <b>{money}</b>", "ru": "💸 Потрачено на расходники: <b>{money}</b>", "cs": "💸 Utraceno za spotřebák: <b>{money}</b>"},
    "sum_time":   {"en": "⏱ Time gone up in smoke: <b>{dur}</b>", "ru": "⏱ Времени «в дым»: <b>{dur}</b>", "cs": "⏱ Času „v kouři“: <b>{dur}</b>"},

    "int_title":    {"en": "⏱ <b>Intervals</b>", "ru": "⏱ <b>Интервалы</b>", "cs": "⏱ <b>Intervaly</b>"},
    "int_since":    {"en": "Smoke-free for: <b>{dur}</b>", "ru": "Не куришь уже: <b>{dur}</b>", "cs": "Bez cigarety už: <b>{dur}</b>"},
    "int_longest":  {"en": "Longest break: <b>{dur}</b>", "ru": "Самый длинный перерыв: <b>{dur}</b>", "cs": "Nejdelší pauza: <b>{dur}</b>"},
    "int_avg":      {"en": "Average between breaks: <b>{dur}</b>", "ru": "В среднем между перекурами: <b>{dur}</b>", "cs": "Průměr mezi pauzami: <b>{dur}</b>"},
    "int_more":     {"en": "<i>Log a couple more — I'll show breaks and the average interval.</i>",
                     "ru": "<i>Сделай ещё пару записей — покажу перерывы и средний интервал.</i>",
                     "cs": "<i>Zapiš ještě pár — ukážu pauzy a průměrný interval.</i>"},

    "trend_none":   {"en": "No data for the last two weeks 🙂", "ru": "Пока нет данных за последние две недели 🙂", "cs": "Zatím žádná data za poslední dva týdny 🙂"},
    "trend_nolast": {"en": "📈 No entries last week — nothing to compare.", "ru": "📈 На прошлой неделе записей не было — не с чем сравнить.", "cs": "📈 Minulý týden žádné záznamy — není s čím srovnat."},
    "trend_less":   {"en": "📉 Down <b>{pct}%</b> ({diff}). Keep it up! 👏", "ru": "📉 Меньше на <b>{pct}%</b> ({diff} шт). Так держать! 👏", "cs": "📉 Méně o <b>{pct}%</b> ({diff} ks). Jen tak dál! 👏"},
    "trend_more":   {"en": "📈 Up <b>{pct}%</b> (+{diff}).", "ru": "📈 Больше на <b>{pct}%</b> (+{diff} шт).", "cs": "📈 Více o <b>{pct}%</b> (+{diff} ks)."},
    "trend_same":   {"en": "➖ Same as last week.", "ru": "➖ Столько же, что и на прошлой неделе.", "cs": "➖ Stejně jako minulý týden."},
    "trend_body": {
        "en": ("📉 <b>Weekly trend</b>\nThis week: <b>{this}</b> cigarettes\n"
               "Last week: <b>{last}</b> cigarettes\n\n{verdict}"),
        "ru": ("📉 <b>Тренд по неделям</b>\nЭта неделя: <b>{this}</b> сигарет\n"
               "Прошлая неделя: <b>{last}</b> сигарет\n\n{verdict}"),
        "cs": ("📉 <b>Týdenní trend</b>\nTento týden: <b>{this}</b> cigaret\n"
               "Minulý týden: <b>{last}</b> cigaret\n\n{verdict}"),
    },

    # ── Расходы ───────────────────────────────────────────────────
    "ex_new":   {"en": "🆕 Open a pack", "ru": "🆕 Открыть упаковку", "cs": "🆕 Otevřít balení"},
    "ex_close": {"en": "✅ Pack finished", "ru": "✅ Упаковка кончилась", "cs": "✅ Balení došlo"},
    "ex_chart": {"en": "📊 Where money went", "ru": "📊 Куда ушли деньги", "cs": "📊 Kam šly peníze"},

    "exp_title":     {"en": "💸 <b>Expenses</b>", "ru": "💸 <b>Расходы</b>", "cs": "💸 <b>Výdaje</b>"},
    "exp_open_now":  {"en": "\nCurrently open:", "ru": "\nСейчас открыто:", "cs": "\nAktuálně otevřeno:"},
    "exp_none_open": {"en": "\n<i>No open packs.</i>", "ru": "\n<i>Открытых упаковок нет.</i>", "cs": "\n<i>Žádná otevřená balení.</i>"},
    "exp_total":     {"en": "\nTotal spent: <b>{money}</b>", "ru": "\nВсего потрачено: <b>{money}</b>", "cs": "\nCelkem utraceno: <b>{money}</b>"},
    "exp_per_cig":   {"en": "Cost per cigarette ≈ <b>{money}</b>", "ru": "Цена одной сигареты ≈ <b>{money}</b>", "cs": "Cena jedné cigarety ≈ <b>{money}</b>"},
    "exp_hint":      {"en": "\n<i>Open your first pack and log its price — I'll start counting money.</i>",
                      "ru": "\n<i>Открой первую упаковку и запиши её цену — начну считать деньги.</i>",
                      "cs": "\n<i>Otevři první balení a zapiš cenu — začnu počítat peníze.</i>"},
    "exp_no_open":   {"en": "No open packs right now 🤷", "ru": "Сейчас нет открытых упаковок 🤷", "cs": "Teď nejsou žádná otevřená balení 🤷"},
    "main_menu":     {"en": "Main menu 👇", "ru": "Главное меню 👇", "cs": "Hlavní menu 👇"},
    "exp_which_closed": {"en": "Which pack is finished?", "ru": "Какая упаковка закончилась?", "cs": "Které balení došlo?"},
    "exp_no_spend":  {"en": "No spending yet. Open a pack and log a price 💸", "ru": "Пока нет трат. Открой упаковку и запиши цену 💸", "cs": "Zatím žádné výdaje. Otevři balení a zapiš cenu 💸"},
    "cap_spend":     {"en": "💸 Where the money went (single currency)", "ru": "💸 Куда ушли деньги (в одной валюте)", "cs": "💸 Kam šly peníze (v jedné měně)"},
    "exp_closed_ok": {"en": "✅ Marked: {label} finished.", "ru": "✅ Отметил: {label} закончилась.", "cs": "✅ Označeno: {label} došlo."},
    "exp_closed_already": {"en": "{label} wasn't open anyway 🤷", "ru": "{label} и так не была открыта 🤷", "cs": "{label} stejně nebylo otevřené 🤷"},
    "exp_what_open": {"en": "What are you opening?", "ru": "Что открываешь?", "cs": "Co otevíráš?"},
    "exp_price_q":   {"en": "{label} — how much is the pack? Type a number (in {cur}):",
                      "ru": "{label} — сколько стоит упаковка? Напиши число (в {cur}):",
                      "cs": "{label} — kolik stojí balení? Napiš číslo (v {cur}):"},
    "cancel_hint":   {"en": "…or tap “Cancel”.", "ru": "…или нажми «Отмена».", "cs": "…nebo klikni na „Zrušit“."},
    "exp_pick_first": {"en": "First pick a type with the button above 👆 or tap “Cancel”.",
                       "ru": "Сначала выбери тип кнопкой выше 👆 или нажми «Отмена».",
                       "cs": "Nejdřív vyber typ tlačítkem výše 👆 nebo klikni na „Zrušit“."},
    "exp_not_number": {"en": "That's not a number. Type the pack price, e.g. 120.",
                       "ru": "Это не число. Напиши цену упаковки, например 120.",
                       "cs": "To není číslo. Napiš cenu balení, např. 120."},
    "exp_bad_price": {"en": "Enter a reasonable price.", "ru": "Введи разумную цену.", "cs": "Zadej rozumnou cenu."},
    "exp_opened":    {"en": ("✅ Opened: {label} for {money}.\n"
                             "When it's gone — open “💸 Expenses” and tap “Pack finished”."),
                      "ru": ("✅ Открыл: {label} за {money}.\n"
                             "Кончится — загляни в «💸 Расходы» и нажми «Упаковка кончилась»."),
                      "cs": ("✅ Otevřeno: {label} za {money}.\n"
                             "Až dojde — otevři „💸 Výdaje“ a klikni na „Balení došlo“.")},

    # ── Настройки ─────────────────────────────────────────────────
    "se_name": {"en": "🙍 Change name", "ru": "🙍 Сменить имя", "cs": "🙍 Změnit jméno"},
    "se_cur":  {"en": "💱 Currency", "ru": "💱 Валюта", "cs": "💱 Měna"},
    "se_lang": {"en": "🌐 Language", "ru": "🌐 Язык", "cs": "🌐 Jazyk"},
    "se_edit": {"en": "✏️ Edit/delete entries", "ru": "✏️ Изменить/удалить записи", "cs": "✏️ Upravit/smazat záznamy"},
    "se_title": {
        "en": "⚙️ <b>Settings</b>\nName: <b>{name}</b>\nCurrency: <b>{cur}</b>\nLanguage: <b>{lang_name}</b>",
        "ru": "⚙️ <b>Настройки</b>\nИмя: <b>{name}</b>\nВалюта: <b>{cur}</b>\nЯзык: <b>{lang_name}</b>",
        "cs": "⚙️ <b>Nastavení</b>\nJméno: <b>{name}</b>\nMěna: <b>{cur}</b>\nJazyk: <b>{lang_name}</b>",
    },
    "cur_eur": {"en": "🇪🇺 € euro", "ru": "🇪🇺 € евро", "cs": "🇪🇺 € euro"},
    "cur_uah": {"en": "🇺🇦 ₴ hryvnia", "ru": "🇺🇦 ₴ гривна", "cs": "🇺🇦 ₴ hřivna"},
    "cur_czk": {"en": "🇨🇿 Kč koruna", "ru": "🇨🇿 Kč крона", "cs": "🇨🇿 Kč koruna"},
    "cur_note": {
        "en": ("\n\n<i>Approx. rate: 1 € ≈ {uah} UAH ≈ {czk} CZK. "
               "Amounts in other currencies are converted automatically.</i>"),
        "ru": ("\n\n<i>Примерный курс: 1 € ≈ {uah} грн ≈ {czk} Kč. "
               "Суммы из других валют пересчитаю автоматически.</i>"),
        "cs": ("\n\n<i>Přibližný kurz: 1 € ≈ {uah} UAH ≈ {czk} Kč. "
               "Částky v jiných měnách přepočítám automaticky.</i>"),
    },
    "cur_choose": {"en": "Choose a currency:", "ru": "Выбери валюту:", "cs": "Vyber měnu:"},
    "cur_set": {"en": "✅ Currency: {cur} — expenses are now shown in it.",
                "ru": "✅ Валюта: {cur} — суммы расходов теперь показываю в ней.",
                "cs": "✅ Měna: {cur} — výdaje teď ukazuji v ní."},
    "lang_choose": {"en": "Choose a language:", "ru": "Выбери язык:", "cs": "Vyber jazyk:"},
    "lang_set": {"en": "✅ Language: {lang_name}.", "ru": "✅ Язык: {lang_name}.", "cs": "✅ Jazyk: {lang_name}."},

    # ── Рейтинг ───────────────────────────────────────────────────
    "top_empty": {"en": "Nobody has logged anything yet 🙂", "ru": "Пока никто ничего не записал 🙂", "cs": "Zatím nikdo nic nezapsal 🙂"},
    "top_title": {"en": "🏆 <b>This week's leaderboard</b>", "ru": "🏆 <b>Рейтинг за эту неделю</b>", "cs": "🏆 <b>Žebříček za tento týden</b>"},
    "top_sub":   {"en": "<i>who's calmer (fewer = higher)</i>", "ru": "<i>у кого спокойнее (меньше — выше)</i>", "cs": "<i>kdo je klidnější (méně = výš)</i>"},
    "top_line":  {"en": "{mark} <b>{name}</b> — {week} this week", "ru": "{mark} <b>{name}</b> — {week} за неделю", "cs": "{mark} <b>{name}</b> — {week} za týden"},

    # ── Редактирование записей ────────────────────────────────────
    "edit_none":  {"en": "No entries yet. Log a smoke break first 🚬", "ru": "Пока нет записей. Сначала запиши перекур 🚬", "cs": "Zatím žádné záznamy. Nejdřív zapiš pauzu 🚬"},
    "edit_pick":  {"en": "Which entry to change? Pick one:", "ru": "Какую запись изменить? Выбери её:", "cs": "Který záznam upravit? Vyber ho:"},
    "edit_notyours": {"en": "That's not your entry 🙅", "ru": "Это не твоя запись 🙅", "cs": "To není tvůj záznam 🙅"},
    "edit_chg":   {"en": "✏️ Change count", "ru": "✏️ Изменить число", "cs": "✏️ Změnit počet"},
    "edit_time":  {"en": "🕐 Change time", "ru": "🕐 Изменить время", "cs": "🕐 Změnit čas"},
    "edit_del":   {"en": "🗑 Delete entry", "ru": "🗑 Удалить запись", "cs": "🗑 Smazat záznam"},
    "edit_what":  {"en": "Entry #{id} (now: {count} pcs). What to do?", "ru": "Запись №{id} (сейчас: {count} шт). Что сделать?", "cs": "Záznam č. {id} (teď: {count} ks). Co provést?"},
    "edit_change_prompt": {"en": "Entry #{id} (now: {count} pcs).\nType a new number:",
                           "ru": "Запись №{id} (сейчас: {count} шт).\nНапиши новое число:",
                           "cs": "Záznam č. {id} (teď: {count} ks).\nNapiš nové číslo:"},
    "edit_time_prompt": {
        "en": ("Entry #{id} (now: {now}).\nType a new time. Formats:\n"
               "• <code>14:30</code> — time only (date stays)\n"
               "• <code>01.07 14:30</code> — day and time\n"
               "• <code>2026-07-01 14:30</code> — full"),
        "ru": ("Запись №{id} (сейчас: {now}).\nНапиши новое время. Можно так:\n"
               "• <code>14:30</code> — только время (дата останется прежней)\n"
               "• <code>01.07 14:30</code> — день и время\n"
               "• <code>2026-07-01 14:30</code> — полностью"),
        "cs": ("Záznam č. {id} (teď: {now}).\nNapiš nový čas. Můžeš takto:\n"
               "• <code>14:30</code> — jen čas (datum zůstane)\n"
               "• <code>01.07 14:30</code> — den a čas\n"
               "• <code>2026-07-01 14:30</code> — celé"),
    },
    "edit_time_bad": {"en": "Didn't get the time 🤔 Type e.g. “14:30” or “01.07 14:30”.",
                      "ru": "Не понял время 🤔 Напиши, например, «14:30» или «01.07 14:30».",
                      "cs": "Nerozumím času 🤔 Napiš např. „14:30“ nebo „01.07 14:30“."},
    "edit_time_done": {"en": "🕐 Time of entry #{id} changed to <b>{when}</b>.",
                       "ru": "🕐 Время записи №{id} изменено на <b>{when}</b>.",
                       "cs": "🕐 Čas záznamu č. {id} změněn na <b>{when}</b>."},
    "edit_del_confirm": {"en": "Delete entry #{id}?", "ru": "Точно удалить запись №{id}?", "cs": "Opravdu smazat záznam č. {id}?"},
    "del_yes": {"en": "✅ Yes, delete", "ru": "✅ Да, удалить", "cs": "✅ Ano, smazat"},
    "del_no":  {"en": "↩️ No, keep", "ru": "↩️ Нет, оставить", "cs": "↩️ Ne, ponechat"},
    "edit_deleted": {"en": "🗑 Entry #{id} deleted.", "ru": "🗑 Запись №{id} удалена.", "cs": "🗑 Záznam č. {id} smazán."},
    "total_now": {"en": "Total now: <b>{total}</b>", "ru": "Всего теперь: <b>{total}</b>", "cs": "Celkem teď: <b>{total}</b>"},
    "edit_del_no": {"en": "OK, deleted nothing. 👌", "ru": "Ок, ничего не удалял. 👌", "cs": "OK, nic jsem nesmazal. 👌"},
    "edit_pick_first": {"en": "First pick an entry with the button above 👆 or tap “Cancel”.",
                        "ru": "Сначала выбери запись кнопкой выше 👆 или нажми «Отмена».",
                        "cs": "Nejdřív vyber záznam tlačítkem výše 👆 nebo klikni na „Zrušit“."},
    "edit_del_bytext": {"en": "🗑 Entry #{id} deleted. Total now: <b>{total}</b>",
                        "ru": "🗑 Запись №{id} удалена. Всего теперь: <b>{total}</b>",
                        "cs": "🗑 Záznam č. {id} smazán. Celkem teď: <b>{total}</b>"},
    "edit_bad_number": {"en": "Type a new number or the word “delete”.",
                        "ru": "Напиши новое число или слово «удалить».",
                        "cs": "Napiš nové číslo nebo slovo „smazat“."},
    "edit_range": {"en": "Enter a reasonable number from 1 to 10000.",
                   "ru": "Введи разумное число от 1 до 10000.",
                   "cs": "Zadej rozumné číslo od 1 do 10000."},
    "edit_changed": {"en": "✏️ Entry #{id} changed to <b>{count}</b>. Total now: <b>{total}</b>",
                     "ru": "✏️ Запись №{id} изменена на <b>{count}</b>. Всего теперь: <b>{total}</b>",
                     "cs": "✏️ Záznam č. {id} změněn na <b>{count}</b>. Celkem teď: <b>{total}</b>"},

    # ── Прочее ────────────────────────────────────────────────────
    "cancelled": {"en": "Cancelled. 👌", "ru": "Отменил. 👌", "cs": "Zrušeno. 👌"},
    "today_cmd": {"en": "Today you've smoked <b>{n}</b> times 🚬", "ru": "Сегодня ты выкурил <b>{n}</b> раз 🚬", "cs": "Dnes jsi kouřil <b>{n}</b>× 🚬"},
    "photo_no_break": {"en": "Log a smoke break first, then send a photo 🚬", "ru": "Сначала запиши перекур, потом пришли фото 🚬", "cs": "Nejdřív zapiš pauzu, pak pošli fotku 🚬"},
    "photo_saved": {"en": "📷 Photo saved and linked to the break!", "ru": "📷 Фото сохранено и привязано к перекуру!", "cs": "📷 Fotka uložena a připojena k pauze!"},

    # ── Подписи графиков ──────────────────────────────────────────
    "chart_line_ylabel":  {"en": "Cigarettes per break", "ru": "Сигарет за перекур", "cs": "Cigaret za pauzu"},
    "chart_cumul_title":  {"en": "Total cigarettes: {total}", "ru": "Всего сигарет: {total}", "cs": "Cigaret celkem: {total}"},
    "chart_cumul_ylabel": {"en": "Cumulative", "ru": "Накопительно", "cs": "Kumulativně"},
    "chart_days_title":   {"en": "Cigarettes by day", "ru": "Сигареты по дням", "cs": "Cigarety po dnech"},
    "chart_days_ylabel":  {"en": "Cigarettes per day", "ru": "Сигарет за день", "cs": "Cigaret za den"},
    "chart_hours_title":  {"en": "When you smoke most", "ru": "Когда ты куришь чаще всего", "cs": "Kdy kouříš nejčastěji"},
    "chart_cigs":         {"en": "Cigarettes", "ru": "Сигарет", "cs": "Cigaret"},
    "chart_hours_xlabel": {"en": "Hour of day", "ru": "Час суток", "cs": "Hodina dne"},
    "chart_hours_peak":   {"en": "peak at {h}:00", "ru": "пик в {h}:00", "cs": "vrchol v {h}:00"},
    "chart_weekday_title": {"en": "Cigarettes by weekday", "ru": "Сигареты по дням недели", "cs": "Cigarety podle dní v týdnu"},
    "chart_spend_title":  {"en": "Where the money went — {total} {cur} total", "ru": "Куда ушли деньги — всего {total} {cur}", "cs": "Kam šly peníze — celkem {total} {cur}"},
    "chart_money_ylabel": {"en": "Spent, {cur}", "ru": "Потрачено, {cur}", "cs": "Utraceno, {cur}"},
}


def t(lang: str, key: str, **kw) -> str:
    """Строка на языке lang с подстановкой плейсхолдеров."""
    entry = STRINGS.get(key, {})
    template = entry.get(lang) or entry.get(DEFAULT_LANG) or entry.get("ru") or key
    return template.format(**kw) if kw else template


def variants(key: str) -> list[str]:
    """Все переводы строки (для сопоставления кнопок независимо от языка)."""
    entry = STRINGS.get(key, {})
    out: list[str] = []
    for lang in LANGS:
        v = entry.get(lang)
        if v and v not in out:
            out.append(v)
    return out


def lang_name(lang: str) -> str:
    return LANG_NAMES.get(lang, LANG_NAMES[DEFAULT_LANG])


def kind_label(lang: str, kind: str) -> str:
    d = KIND_LABELS.get(kind)
    if not d:
        return kind
    return d.get(lang) or d.get(DEFAULT_LANG) or kind


def weekday_labels(lang: str) -> list[str]:
    return WEEKDAYS.get(lang, WEEKDAYS[DEFAULT_LANG])


def is_cancel(text: str) -> bool:
    return text in variants("btn_cancel")


def is_skip(text: str) -> bool:
    return text in variants("btn_skip")


def is_delete_word(text: str) -> bool:
    return text.strip().lower() in DELETE_WORDS
