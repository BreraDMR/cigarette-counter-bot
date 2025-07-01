"""Построение красивых графиков (стиль «как в Excel») через matplotlib.

Каждая функция возвращает PNG в виде BytesIO, готовый к отправке в Telegram.
"""

from __future__ import annotations

import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # без GUI, рендер в файл
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from . import i18n

# Палитра в духе Excel
ACCENT = "#2E75B6"   # синий
ACCENT2 = "#ED7D31"  # оранжевый
GRID = "#D9D9D9"
TEXT = "#404040"

plt.rcParams.update(
    {
        "font.size": 11,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT,
        "text.color": TEXT,
        "xtick.color": TEXT,
        "ytick.color": TEXT,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def _finish(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def line_chart(sessions: list[tuple[str, int]], title: str, lang: str = "ru") -> io.BytesIO:
    """Линейный график сигарет по перекурам (с заливкой области)."""
    x = [datetime.fromisoformat(ts) for ts, _ in sessions]
    y = [c for _, c in sessions]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, y, color=ACCENT, linewidth=2.2, marker="o", markersize=5,
            markerfacecolor="white", markeredgecolor=ACCENT, markeredgewidth=1.6)
    ax.fill_between(x, y, color=ACCENT, alpha=0.12)

    for xi, yi in zip(x, y):
        ax.annotate(str(yi), (xi, yi), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=9, color=ACCENT)

    ax.set_title(title, fontsize=15, fontweight="bold", pad=14)
    ax.set_ylabel(i18n.t(lang, "chart_line_ylabel"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.autofmt_xdate(rotation=30)
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(y=0.18)
    return _finish(fig)


def cumulative_chart(sessions: list[tuple[str, int]], total: int, lang: str = "ru") -> io.BytesIO:
    """Накопительный график: сколько всего выкурил к каждому моменту."""
    x = [datetime.fromisoformat(ts) for ts, _ in sessions]
    cum, running = [], 0
    for _, c in sessions:
        running += c
        cum.append(running)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, cum, color=ACCENT2, linewidth=2.6)
    ax.fill_between(x, cum, color=ACCENT2, alpha=0.18)

    ax.set_title(i18n.t(lang, "chart_cumul_title", total=total), fontsize=16, fontweight="bold", pad=14)
    ax.set_ylabel(i18n.t(lang, "chart_cumul_ylabel"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.autofmt_xdate(rotation=30)
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(y=0.12)
    return _finish(fig)


def days_bar_chart(days: list[tuple[str, int]], title: str, lang: str = "ru") -> io.BytesIO:
    """Гистограмма (столбики) по дням: сколько сигарет в какой день."""
    labels = [datetime.fromisoformat(d).strftime("%d.%m") for d, _ in days]
    values = [v for _, v in days]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, values, color=ACCENT, width=0.62, edgecolor="white")

    # выделяем больше всего за день
    if values:
        best = max(range(len(values)), key=lambda i: values[i])
        bars[best].set_color(ACCENT2)

    for rect, v in zip(bars, values):
        ax.annotate(str(v), (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    textcoords="offset points", xytext=(0, 5), ha="center",
                    fontsize=9, fontweight="bold")

    ax.set_title(title, fontsize=15, fontweight="bold", pad=14)
    ax.set_ylabel(i18n.t(lang, "chart_days_ylabel"))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    ax.margins(y=0.18)
    fig.autofmt_xdate(rotation=30)
    return _finish(fig)


def hours_chart(by_hour: list[int], lang: str = "ru") -> io.BytesIO:
    """Гистограмма «в какое время суток чаще куришь» (24 столбика, по часам)."""
    hours = list(range(24))
    values = list(by_hour)

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(hours, values, color=ACCENT, width=0.82, edgecolor="white")

    if any(values):
        peak = max(range(24), key=lambda i: values[i])
        bars[peak].set_color(ACCENT2)
        ax.annotate(i18n.t(lang, "chart_hours_peak", h=f"{peak:02d}"),
                    (peak, values[peak]), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=10,
                    fontweight="bold", color=ACCENT2)

    ax.set_title(i18n.t(lang, "chart_hours_title"), fontsize=15, fontweight="bold", pad=14)
    ax.set_ylabel(i18n.t(lang, "chart_cigs"))
    ax.set_xlabel(i18n.t(lang, "chart_hours_xlabel"))
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    ax.margins(y=0.18)
    return _finish(fig)


def weekday_chart(by_weekday: list[int], lang: str = "ru") -> io.BytesIO:
    """Гистограмма по дням недели (Пн…Вс)."""
    labels = i18n.weekday_labels(lang)
    values = list(by_weekday)

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [ACCENT] * 7
    # выходные — другим цветом
    colors[5] = colors[6] = "#7B61FF"
    bars = ax.bar(labels, values, color=colors, width=0.66, edgecolor="white")

    if any(values):
        peak = max(range(7), key=lambda i: values[i])
        bars[peak].set_color(ACCENT2)

    for rect, v in zip(bars, values):
        if v:
            ax.annotate(str(v), (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                        textcoords="offset points", xytext=(0, 5), ha="center",
                        fontsize=9, fontweight="bold")

    ax.set_title(i18n.t(lang, "chart_weekday_title"), fontsize=15, fontweight="bold", pad=14)
    ax.set_ylabel(i18n.t(lang, "chart_cigs"))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    ax.margins(y=0.18)
    return _finish(fig)


def spend_by_kind_chart(items: list[tuple[str, float]], currency: str, lang: str = "ru") -> io.BytesIO:
    """Круговая диаграмма: на что ушли деньги (табак/бумага/фильтры/…)."""
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    palette = [ACCENT, ACCENT2, "#7B61FF", "#27AE60", "#C0392B", "#F1C40F"]
    colors = [palette[i % len(palette)] for i in range(len(values))]

    fig, ax = plt.subplots(figsize=(8, 6))
    total = sum(values) or 1

    def autopct(pct):
        return f"{pct:.0f}%\n{pct / 100 * total:.0f} {currency}"

    wedges, _texts, autotexts = ax.pie(
        values, colors=colors, autopct=autopct, startangle=90,
        wedgeprops=dict(width=0.42, edgecolor="white"), pctdistance=0.78,
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_fontweight("bold")
        t.set_color(TEXT)

    ax.legend(wedges, labels, loc="center", frameon=False, fontsize=11)
    ax.set_title(i18n.t(lang, "chart_spend_title", total=f"{total:.0f}", cur=currency),
                 fontsize=15, fontweight="bold", pad=14)
    ax.set(aspect="equal")
    return _finish(fig)


def money_bar_chart(days: list[tuple[str, float]], currency: str, title: str, lang: str = "ru") -> io.BytesIO:
    """Гистограмма потраченных денег по дням."""
    labels = [datetime.fromisoformat(d).strftime("%d.%m") for d, _ in days]
    values = [v for _, v in days]

    def fmt(v: float) -> str:
        return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, values, color=ACCENT2, width=0.62, edgecolor="white")
    if values:
        worst = max(range(len(values)), key=lambda i: values[i])
        bars[worst].set_color("#C0392B")

    for rect, v in zip(bars, values):
        ax.annotate(fmt(v), (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    textcoords="offset points", xytext=(0, 5), ha="center",
                    fontsize=9, fontweight="bold")

    ax.set_title(title, fontsize=15, fontweight="bold", pad=14)
    ax.set_ylabel(i18n.t(lang, "chart_money_ylabel", cur=currency))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    ax.margins(y=0.18)
    fig.autofmt_xdate(rotation=30)
    return _finish(fig)
