"""Build the light and dark README charts from the current summary cards."""

import argparse
from datetime import date, datetime
from html import escape
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from read_summary_cards import Snapshot, read_snapshot


ACTIVITY = {
    "base": "#191e1b",
    "ink": "#f7f4eb",
    "muted": "#c9d0c7",
    "line": "#485149",
    "accent": "#ff8a6a",
    "bars": "#c76952",
    "partial": "#a67665",
    "hours": "#8eab92",
}
LANGUAGE = {
    "light": {
        "base": "#fafbf9", "ink": "#202320", "muted": "#515851",
        "line": "#d9ddd7", "track": "#e6eae4", "bar": "#677866", "accent": "#b93822",
    },
    "dark": {
        "base": "#202620", "ink": "#eef2ec", "muted": "#bec9c0",
        "line": "#465147", "track": "#343e35", "bar": "#91a690", "accent": "#ff8a6a",
    },
}


class Chart:
    def __init__(self) -> None:
        self.items: list[str] = []

    def text(self, x, y, value, color, size, *, weight=400, align="start", numeric=False):
        css = ' class="numeric"' if numeric else ""
        self.items.append(
            f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{align}"{css}>{escape(str(value))}</text>'
        )

    def rect(self, x, y, width, height, color, *, tooltip=None):
        props = f'x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" fill="{color}"'
        if tooltip is None:
            self.items.append(f"<rect {props}/>")
        else:
            self.items.append(f"<rect {props}><title>{escape(tooltip)}</title></rect>")

    def rule(self, x1, y1, x2, y2, color, *, dashed=False):
        dash = ' stroke-dasharray="3 3"' if dashed else ""
        self.items.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{color}"{dash}/>'
        )


def format_tick(value: int) -> str:
    return f"{value / 1000:g}k" if value >= 1000 else str(value)


def histogram(chart, x, y, width, values, limit, name, note, ticks, tooltips, colors):
    palette = ACTIVITY
    chart.text(x, y, name, palette["ink"], 14, weight=650)
    chart.text(x + width, y, note, palette["muted"], 11, align="end")

    left, top, height = x + 32, y + 14, 80
    plot_width = width - 32
    for index in range(3):
        line_y = top + height * index / 2
        chart.rule(left, line_y, x + width, line_y, palette["line"], dashed=index == 1)
        chart.text(
            left - 6, line_y + 3, format_tick(round(limit * (2 - index) / 2)),
            palette["muted"], 10, align="end", numeric=True,
        )

    step = plot_width / len(values)
    gap = 4 if len(values) <= 13 else 3
    for index, value in enumerate(values):
        if value:
            bar_height = max(1, height * value / limit)
            chart.rect(
                left + step * index, top + height - bar_height, step - gap, bar_height,
                colors[index], tooltip=tooltips[index],
            )

    for index, label in ticks:
        position = left + step * (index + 0.5)
        anchor = "middle"
        if index == 0:
            position, anchor = left, "start"
        elif index == len(values) - 1:
            position, anchor = x + width, "end"
        chart.text(position, top + height + 15, label, palette["muted"], 10, align=anchor, numeric=True)


def language_chart(chart, x, y, width, name, rows, palette):
    chart.text(x, y, name, palette["ink"], 15, weight=650)
    track_x = x + 94
    track_width = width - 144
    for index, (language, fraction) in enumerate(rows):
        line_y = y + 27 + index * 25
        chart.text(x, line_y, language, palette["ink"], 14, weight=650 if index == 0 else 400)
        chart.rect(track_x, line_y - 9, track_width, 8, palette["track"])
        chart.rect(track_x, line_y - 9, track_width * fraction, 8, palette["accent"] if index == 0 else palette["bar"])
        chart.text(x + width, line_y, f"{fraction:.1%}", palette["muted"], 11, align="end", numeric=True)


def render(snapshot: Snapshot, as_of: date, theme: str, compact: bool) -> str:
    width, height = (408, 902) if compact else (900, 601)
    panel_height = 463 if compact else 320
    inset = 20 if compact else 34
    inner = width - 2 * inset
    chart = Chart()
    language = LANGUAGE[theme]
    activity = ACTIVITY
    chart.rect(0, 0, width, height, language["base"])
    chart.rect(0, 0, width, panel_height, activity["base"])

    chart.text(inset, 42 if compact else 47, "GitHub activity", activity["ink"], 27 if compact else 31, weight=750)
    updated = f"Snapshot · {as_of:%d %b %Y}"
    chart.text(
        inset if compact else width - inset, 64 if compact else 45, updated,
        activity["muted"], 12, align="start" if compact else "end",
    )

    for index, (value, name) in enumerate(zip(snapshot.totals, ("Commits", "Pull requests", "Contributions"), strict=True)):
        left = inset + index * inner / 3
        if index:
            chart.rule(left, 85 if compact else 73, left, 134 if compact else 135, activity["line"])
            left += 11 if compact else 23
        chart.text(left, 110 if compact else 112, value, activity["accent"], 31 if compact else 48, weight=800)
        chart.text(left, 133 if compact else 138, name, activity["muted"], 13 if compact else 14)

    chart.rule(inset, 153, width - inset, 153, activity["line"])
    months, counts = zip(*snapshot.monthly, strict=True)
    peak = max(counts)
    month_limit = max(100, math.ceil(peak / 100) * 100)
    month_indexes = [round((len(months) - 1) * part / 4) for part in range(5)]
    tick_labels = [
        (i, month.strftime("%b ’%y" if i in (0, len(months) - 1) else "%b"))
        for i in month_indexes
        for month in [months[i]]
    ]
    month_colors = [
        activity["partial"] if i in (0, len(months) - 1)
        else activity["accent"] if value == peak else activity["bars"]
        for i, value in enumerate(counts)
    ]
    monthly_width = inner if compact else math.floor((inner - 34) * 0.60)
    histogram(
        chart, inset, 181 if compact else 184, monthly_width, counts, month_limit,
        "Monthly contributions", "Edge months partial", tick_labels,
        [f"{month:%b %Y} · {value:,} contributions" for month, value in snapshot.monthly],
        month_colors,
    )

    hour_limit = max(10, math.ceil(max(snapshot.hourly) / 10) * 10)
    histogram(
        chart, inset if compact else inset + monthly_width + 34, 328 if compact else 184,
        inner if compact else inner - monthly_width - 34, snapshot.hourly, hour_limit,
        "Commit hours", "Sample · UTC+8",
        [(i, f"{i:02d}") for i in (0, 6, 12, 18, 23)],
        [f"{hour:02d}:00 UTC+8 · {count} sampled commits" for hour, count in enumerate(snapshot.hourly)],
        [activity["hours"]] * 24,
    )

    chart.text(inset, panel_height + 49, "Languages", language["ink"], 29, weight=750)
    language_width = inner if compact else (inner - 34) / 2
    language_chart(chart, inset, panel_height + 79, language_width, "By repository count", snapshot.by_repo, language)
    language_chart(
        chart, inset if compact else inset + language_width + 34,
        panel_height + (255 if compact else 79), language_width,
        "By commit count", snapshot.by_commit, language,
    )

    note1 = "Both views use each repository’s primary language."
    note2 = "Percentages are shares of the languages shown."
    if compact:
        chart.text(inset, 869, note1, language["muted"], 12)
        chart.text(inset, 887, note2, language["muted"], 12)
    else:
        chart.text(inset, 579, f"{note1} {note2}", language["muted"], 12)

    commit, prs, contributions = snapshot.totals
    description = (
        f"{commit} commits, {prs} pull requests and {contributions} GitHub contributions. "
        "Monthly activity, sampled commit hours in UTC+8 and language shares by repository and commit count."
    )
    shapes = "\n".join(chart.items)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
<title id="title">Dogtiti’s GitHub activity and languages</title>
<desc id="description">{escape(description)}</desc>
<style>
text {{ font-family: system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }}
.numeric {{ font-family: SFMono-Regular, Consolas, "Liberation Mono", monospace; }}
</style>
<defs><clipPath id="canvas"><rect width="{width}" height="{height}" rx="8"/></clipPath></defs>
<g clip-path="url(#canvas)">
{shapes}
</g>
<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="8" fill="none" stroke="{language["line"]}"/>
</svg>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("profile-summary-card-output/github"))
    parser.add_argument("--output", type=Path, default=Path("assets"))
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(ZoneInfo("Asia/Shanghai")).date())
    args = parser.parse_args()

    snapshot = read_snapshot(args.source)
    images = {
        f"profile-dashboard-{'compact-' if compact else ''}{theme}.svg": render(snapshot, args.as_of, theme, compact)
        for compact in (False, True)
        for theme in LANGUAGE
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for name, svg in images.items():
        (args.output / name).write_text(svg, encoding="utf-8")
    print(f"Rendered {len(images)} dashboard variants from the five upstream cards.")


if __name__ == "__main__":
    main()
