#!/usr/bin/env python3
"""Generate a git activity report with a small SVG infographic."""

from __future__ import annotations

import argparse
import csv
import html
import math
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class CommitStats:
    source: str
    sha: str
    day: date
    author: str
    subject: str
    additions: int
    deletions: int
    files: int
    binary_files: int

    @property
    def churn(self) -> int:
        return self.additions + self.deletions


def run_git(args: list[str], cwd: Path) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
    )
    return process.stdout


def parse_commits(repo: Path, source: str, excluded_shas: set[str]) -> list[CommitStats]:
    output = run_git(
        [
            "log",
            "--date=short",
            "--pretty=format:--COMMIT--%x09%H%x09%ad%x09%an%x09%s",
            "--numstat",
        ],
        repo,
    )

    commits: list[CommitStats] = []
    current: dict[str, object] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        commits.append(
            CommitStats(
                source=str(current["source"]),
                sha=str(current["sha"]),
                day=datetime.strptime(str(current["day"]), "%Y-%m-%d").date(),
                author=str(current["author"]),
                subject=str(current["subject"]),
                additions=int(current["additions"]),
                deletions=int(current["deletions"]),
                files=int(current["files"]),
                binary_files=int(current["binary_files"]),
            )
        )
        current = None

    for line in output.splitlines():
        if line.startswith("--COMMIT--\t"):
            flush()
            _, sha, day, author, subject = line.split("\t", 4)
            if sha in excluded_shas:
                current = None
                continue
            current = {
                "source": source,
                "sha": sha,
                "day": day,
                "author": author,
                "subject": subject,
                "additions": 0,
                "deletions": 0,
                "files": 0,
                "binary_files": 0,
            }
            continue
        if current is None or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added, deleted = parts[0], parts[1]
        current["files"] = int(current["files"]) + 1
        if added == "-" or deleted == "-":
            current["binary_files"] = int(current["binary_files"]) + 1
            continue
        current["additions"] = int(current["additions"]) + int(added)
        current["deletions"] = int(current["deletions"]) + int(deleted)

    flush()
    return commits


def grouped_by_day(commits: list[CommitStats]) -> list[dict[str, object]]:
    by_day: dict[date, dict[str, object]] = defaultdict(
        lambda: {
            "commits": 0,
            "additions": 0,
            "deletions": 0,
            "files": 0,
            "binary_files": 0,
            "authors": Counter(),
            "sources": Counter(),
        }
    )
    for commit in commits:
        row = by_day[commit.day]
        row["commits"] = int(row["commits"]) + 1
        row["additions"] = int(row["additions"]) + commit.additions
        row["deletions"] = int(row["deletions"]) + commit.deletions
        row["files"] = int(row["files"]) + commit.files
        row["binary_files"] = int(row["binary_files"]) + commit.binary_files
        authors = row["authors"]
        assert isinstance(authors, Counter)
        authors[commit.author] += 1
        sources = row["sources"]
        assert isinstance(sources, Counter)
        sources[commit.source] += 1

    rows: list[dict[str, object]] = []
    for day, row in by_day.items():
        additions = int(row["additions"])
        deletions = int(row["deletions"])
        row["day"] = day
        row["churn"] = additions + deletions
        rows.append(row)
    return sorted(rows, key=lambda item: item["day"])


def grouped_by_month(commits: list[CommitStats]) -> list[dict[str, object]]:
    by_month: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "commits": 0,
            "additions": 0,
            "deletions": 0,
            "files": 0,
            "binary_files": 0,
            "authors": Counter(),
            "sources": Counter(),
        }
    )
    for commit in commits:
        month = commit.day.strftime("%Y-%m")
        row = by_month[month]
        row["commits"] = int(row["commits"]) + 1
        row["additions"] = int(row["additions"]) + commit.additions
        row["deletions"] = int(row["deletions"]) + commit.deletions
        row["files"] = int(row["files"]) + commit.files
        row["binary_files"] = int(row["binary_files"]) + commit.binary_files
        authors = row["authors"]
        assert isinstance(authors, Counter)
        authors[commit.author] += 1
        sources = row["sources"]
        assert isinstance(sources, Counter)
        sources[commit.source] += 1

    rows: list[dict[str, object]] = []
    for month, row in by_month.items():
        additions = int(row["additions"])
        deletions = int(row["deletions"])
        row["month"] = month
        row["churn"] = additions + deletions
        rows.append(row)
    return sorted(rows, key=lambda item: str(item["month"]))


def quarter_label(day: date) -> str:
    return f"{day.year} Q{((day.month - 1) // 3) + 1}"


def grouped_by_quarter(commits: list[CommitStats]) -> list[dict[str, object]]:
    by_quarter: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "commits": 0,
            "additions": 0,
            "deletions": 0,
            "files": 0,
            "binary_files": 0,
            "authors": Counter(),
            "sources": Counter(),
        }
    )
    for commit in commits:
        quarter = quarter_label(commit.day)
        row = by_quarter[quarter]
        row["commits"] = int(row["commits"]) + 1
        row["additions"] = int(row["additions"]) + commit.additions
        row["deletions"] = int(row["deletions"]) + commit.deletions
        row["files"] = int(row["files"]) + commit.files
        row["binary_files"] = int(row["binary_files"]) + commit.binary_files
        authors = row["authors"]
        assert isinstance(authors, Counter)
        authors[commit.author] += 1
        sources = row["sources"]
        assert isinstance(sources, Counter)
        sources[commit.source] += 1

    rows: list[dict[str, object]] = []
    for quarter, row in by_quarter.items():
        additions = int(row["additions"])
        deletions = int(row["deletions"])
        row["quarter"] = quarter
        row["churn"] = additions + deletions
        rows.append(row)
    return sorted(rows, key=lambda item: str(item["quarter"]))


def fmt(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def author_list(counter: Counter[str]) -> str:
    return ", ".join(f"{name} ({count})" for name, count in counter.most_common(3))


def make_svg(top_days: list[dict[str, object]], totals: dict[str, int]) -> str:
    width = 1120
    height = 660
    left = 210
    right = 290
    top = 110
    bar_height = 42
    gap = 24
    scale_width = width - left - right
    max_churn = max(int(day["churn"]) for day in top_days) if top_days else 1

    rows: list[str] = []
    for index, day in enumerate(top_days):
        y = top + index * (bar_height + gap)
        churn = int(day["churn"])
        additions = int(day["additions"])
        commits = int(day["commits"])
        files = int(day["files"])
        total_width = round(scale_width * math.sqrt(churn / max_churn), 2)
        add_width = round(total_width * additions / churn, 2) if churn else 0
        del_width = round(total_width - add_width, 2)
        label = html.escape(str(day["day"]))
        rows.append(
            f'<text x="32" y="{y + 28}" class="day">{label}</text>'
            f'<rect x="{left}" y="{y}" width="{max(total_width, 2)}" height="{bar_height}" rx="6" class="bar-bg"/>'
            f'<rect x="{left}" y="{y}" width="{add_width}" height="{bar_height}" rx="6" class="add"/>'
            f'<rect x="{left + add_width}" y="{y}" width="{del_width}" height="{bar_height}" class="del"/>'
            f'<text x="{left + scale_width + 20}" y="{y + 27}" class="value">'
            f'{fmt(churn)} lines, {commits} commits, {files} files</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Семь дней максимальной напряженности разработки Termin</title>
  <desc id="desc">Горизонтальные составные столбцы показывают добавления и удаления по дням.</desc>
  <style>
    .bg {{ fill: #f7f4ee; }}
    .ink {{ fill: #202124; font-family: Segoe UI, Arial, sans-serif; }}
    .muted {{ fill: #67645f; font-family: Segoe UI, Arial, sans-serif; }}
    .day {{ fill: #202124; font: 700 21px Segoe UI, Arial, sans-serif; }}
    .value {{ fill: #202124; font: 600 15px Segoe UI, Arial, sans-serif; }}
    .bar-bg {{ fill: #ddd7cb; }}
    .add {{ fill: #287a5b; }}
    .del {{ fill: #b84a45; }}
    .card {{ fill: #fffdf8; stroke: #ded8cb; }}
  </style>
  <rect width="100%" height="100%" class="bg"/>
  <text x="32" y="48" class="ink" font-size="30" font-weight="800">Termin: семь дней максимальной напряженности</text>
  <text x="32" y="78" class="muted" font-size="17">Метрика: additions + deletions по git numstat. Шкала столбцов корневая, чтобы первичный импорт не съел график.</text>
  <rect x="30" y="560" width="326" height="64" rx="8" class="card"/>
  <text x="50" y="586" class="muted" font-size="15">Всего коммитов</text>
  <text x="50" y="613" class="ink" font-size="24" font-weight="800">{fmt(totals["commits"])}</text>
  <rect x="385" y="560" width="326" height="64" rx="8" class="card"/>
  <text x="405" y="586" class="muted" font-size="15">Учтено строковых изменений</text>
  <text x="405" y="613" class="ink" font-size="24" font-weight="800">{fmt(totals["churn"])}</text>
  <rect x="740" y="560" width="326" height="64" rx="8" class="card"/>
  <text x="760" y="586" class="muted" font-size="15">Дней с коммитами</text>
  <text x="760" y="613" class="ink" font-size="24" font-weight="800">{fmt(totals["days"])}</text>
  {''.join(rows)}
</svg>
"""


def make_monthly_svg(months: list[dict[str, object]], totals: dict[str, int]) -> str:
    width = 1280
    height = 720
    left = 76
    right = 34
    top = 88
    bottom = 128
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_churn = max(int(month["churn"]) for month in months) if months else 1
    bar_gap = 5
    bar_width = max(10, (plot_width - bar_gap * max(len(months) - 1, 0)) / max(len(months), 1))

    bars: list[str] = []
    for index, month in enumerate(months):
        churn = int(month["churn"])
        additions = int(month["additions"])
        commits = int(month["commits"])
        x = left + index * (bar_width + bar_gap)
        total_height = round(plot_height * math.sqrt(churn / max_churn), 2) if churn else 0
        add_height = round(total_height * additions / churn, 2) if churn else 0
        del_height = round(total_height - add_height, 2)
        y = top + plot_height - total_height
        label = html.escape(str(month["month"]))
        bars.append(
            f'<g><title>{label}: {fmt(churn)} строк churn, {commits} коммитов</title>'
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{total_height:.2f}" rx="3" class="bar-bg"/>'
            f'<rect x="{x:.2f}" y="{(y + del_height):.2f}" width="{bar_width:.2f}" height="{add_height:.2f}" rx="3" class="add"/>'
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{del_height:.2f}" rx="3" class="del"/>'
            f'<text x="{(x + bar_width / 2):.2f}" y="{height - 72}" class="month" transform="rotate(-55 {(x + bar_width / 2):.2f} {height - 72})">{label}</text>'
            f'</g>'
        )

    top_months = sorted(months, key=lambda item: int(item["churn"]), reverse=True)[:3]
    callouts = []
    for index, month in enumerate(top_months, 1):
        callouts.append(
            f'<text x="{left + 18}" y="{height - 70 + index * 18}" class="small">'
            f'{index}. {month["month"]}: {fmt(int(month["churn"]))} строк, {fmt(int(month["commits"]))} коммитов</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Месячная гистограмма напряженности разработки Termin</title>
  <desc id="desc">Столбцы показывают месячный churn строк по объединенной истории текущего и архивного репозиториев.</desc>
  <style>
    .bg {{ fill: #f6f7f2; }}
    .ink {{ fill: #202124; font-family: Segoe UI, Arial, sans-serif; }}
    .muted {{ fill: #62665f; font-family: Segoe UI, Arial, sans-serif; }}
    .small {{ fill: #202124; font: 600 14px Segoe UI, Arial, sans-serif; }}
    .month {{ fill: #202124; font: 600 12px Segoe UI, Arial, sans-serif; text-anchor: end; }}
    .bar-bg {{ fill: #d7d9d0; }}
    .add {{ fill: #2e765e; }}
    .del {{ fill: #b24a43; }}
    .axis {{ stroke: #85887f; stroke-width: 1; }}
  </style>
  <rect width="100%" height="100%" class="bg"/>
  <text x="32" y="46" class="ink" font-size="30" font-weight="800">Termin: месячная гистограмма напряженности</text>
  <text x="32" y="76" class="muted" font-size="16">Объединены текущий репозиторий и termin-archieve; init-коммит монорепы исключен. Шкала корневая.</text>
  <line x1="{left}" y1="{top + plot_height}" x2="{width - right}" y2="{top + plot_height}" class="axis"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" class="axis"/>
  {''.join(bars)}
  <text x="{left}" y="{height - 20}" class="muted" font-size="13">Топ месяцев: {fmt(totals["months"])} месяцев в истории, {fmt(totals["commits"])} коммитов</text>
  {''.join(callouts)}
</svg>
"""


def make_markdown(
    commits: list[CommitStats],
    days: list[dict[str, object]],
    months: list[dict[str, object]],
    quarters: list[dict[str, object]],
    top_days: list[dict[str, object]],
    top_commit_days: list[dict[str, object]],
    top_commits: list[CommitStats],
    svg_name: str,
    monthly_svg_name: str,
    csv_name: str,
    excluded_shas: set[str],
) -> str:
    totals = {
        "commits": len(commits),
        "additions": sum(commit.additions for commit in commits),
        "deletions": sum(commit.deletions for commit in commits),
        "files": sum(commit.files for commit in commits),
        "binary_files": sum(commit.binary_files for commit in commits),
        "days": len(days),
    }
    totals["churn"] = totals["additions"] + totals["deletions"]
    first_day = min(commit.day for commit in commits)
    last_day = max(commit.day for commit in commits)
    authors = Counter(commit.author for commit in commits)
    hottest_months = sorted(months, key=lambda item: int(item["churn"]), reverse=True)[:3]
    hottest_quarter = max(quarters, key=lambda item: int(item["churn"]))
    hottest_months_churn = sum(int(month["churn"]) for month in hottest_months)

    lines = [
        "# Отчет по напряженности разработки",
        "",
        f"Сгенерировано из локальной git-истории {datetime.now().date().isoformat()}.",
        "",
        "![Семь дней максимальной напряженности разработки](./" + svg_name + ")",
        "",
        "![Месячная гистограмма напряженности разработки](./" + monthly_svg_name + ")",
        "",
        f"Полная дневная выгрузка: [`{csv_name}`](./{csv_name}).",
        "",
        "## Сводка",
        "",
        f"- Окно истории: {first_day.isoformat()} .. {last_day.isoformat()}",
        f"- Источников истории: {author_list(Counter(commit.source for commit in commits))}",
        f"- Коммитов: {fmt(totals['commits'])}",
        f"- Дней с коммитами: {fmt(totals['days'])}",
        f"- Месяцев с коммитами: {fmt(len(months))}",
        f"- Добавлено строк: {fmt(totals['additions'])}",
        f"- Удалено строк: {fmt(totals['deletions'])}",
        f"- Суммарный churn строк: {fmt(totals['churn'])}",
        f"- Файловых записей в numstat: {fmt(totals['files'])}",
        f"- Бинарных файловых записей: {fmt(totals['binary_files'])}",
        f"- Авторы по числу коммитов: {author_list(authors)}",
        f"- Исключены коммиты: {', '.join(sorted(sha[:10] for sha in excluded_shas))}",
        "",
        "## Главный вывод",
        "",
        f"Самый напряженный сезон по строковому churn - **{hottest_quarter['quarter']}**: "
        f"{fmt(int(hottest_quarter['churn']))} строковых изменений. "
        f"Если смотреть календарными месяцами, основной вал пришелся на "
        f"{', '.join(str(month['month']) for month in hottest_months)}: "
        f"{fmt(hottest_months_churn)} строковых изменений суммарно.",
        "",
        "## Семь самых горячих дней",
        "",
        "| Место | Дата | Churn | Добавлено | Удалено | Коммиты | Файлы | Бинарные | Авторы |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]

    for rank, day in enumerate(top_days, 1):
        authors_for_day = day["authors"]
        assert isinstance(authors_for_day, Counter)
        lines.append(
            f"| {rank} | {day['day']} | {fmt(int(day['churn']))} | "
            f"{fmt(int(day['additions']))} | {fmt(int(day['deletions']))} | "
            f"{fmt(int(day['commits']))} | {fmt(int(day['files']))} | "
            f"{fmt(int(day['binary_files']))} | {author_list(authors_for_day)} |"
        )

    lines.extend(
        [
            "",
            "## Дни с максимумом коммитов",
            "",
            "| Место | Дата | Коммиты | Churn | Добавлено | Удалено | Файлы | Авторы |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )

    for rank, day in enumerate(top_commit_days, 1):
        authors_for_day = day["authors"]
        assert isinstance(authors_for_day, Counter)
        lines.append(
            f"| {rank} | {day['day']} | {fmt(int(day['commits']))} | "
            f"{fmt(int(day['churn']))} | {fmt(int(day['additions']))} | "
            f"{fmt(int(day['deletions']))} | {fmt(int(day['files']))} | "
            f"{author_list(authors_for_day)} |"
        )

    lines.extend(
        [
            "",
            "## Самые напряженные месяцы",
            "",
            "| Место | Месяц | Churn | Добавлено | Удалено | Коммиты | Файлы | Источники |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )

    for rank, month in enumerate(sorted(months, key=lambda item: int(item["churn"]), reverse=True)[:10], 1):
        sources = month["sources"]
        assert isinstance(sources, Counter)
        lines.append(
            f"| {rank} | {month['month']} | {fmt(int(month['churn']))} | "
            f"{fmt(int(month['additions']))} | {fmt(int(month['deletions']))} | "
            f"{fmt(int(month['commits']))} | {fmt(int(month['files']))} | "
            f"{author_list(sources)} |"
        )

    lines.extend(
        [
            "",
            "## Самые напряженные кварталы",
            "",
            "| Место | Квартал | Churn | Добавлено | Удалено | Коммиты | Файлы | Источники |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )

    for rank, quarter in enumerate(sorted(quarters, key=lambda item: int(item["churn"]), reverse=True)[:8], 1):
        sources = quarter["sources"]
        assert isinstance(sources, Counter)
        lines.append(
            f"| {rank} | {quarter['quarter']} | {fmt(int(quarter['churn']))} | "
            f"{fmt(int(quarter['additions']))} | {fmt(int(quarter['deletions']))} | "
            f"{fmt(int(quarter['commits']))} | {fmt(int(quarter['files']))} | "
            f"{author_list(sources)} |"
        )

    lines.extend(
        [
            "",
            "## Крупнейшие коммиты",
            "",
            "| Место | Дата | Источник | Коммит | Churn | Добавлено | Удалено | Файлы | Автор | Тема |",
            "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )

    for rank, commit in enumerate(top_commits, 1):
        subject = commit.subject.replace("|", "\\|")
        lines.append(
            f"| {rank} | {commit.day} | {commit.source} | `{commit.sha[:10]}` | {fmt(commit.churn)} | "
            f"{fmt(commit.additions)} | {fmt(commit.deletions)} | {fmt(commit.files)} | "
            f"{commit.author} | {subject} |"
        )

    lines.extend(
        [
            "",
            "## Как читать",
            "",
            "- Churn здесь равен `additions + deletions` из `git log --numstat`; это прокси напряженности и объема, а не оценка продуктивности.",
            "- Бинарные файлы считаются как файловые записи, но не входят в строки, потому что git отдает для них `-`/`-`.",
            "- Крупные импорты, vendored-код, генерация и массовые переносы могут доминировать. Топ-дни стоит читать как кандидатов на разбор, не как повод для обвинений.",
            "- Коммит первичного импорта монорепы `newinit` исключен из статистики, иначе весь последующий график превращается в сноску.",
            "- День с большим числом удалений часто означает чистку или завершение миграции, а не потерянную работу.",
            "",
        ]
    )
    return "\n".join(lines)


def write_daily_csv(path: Path, days: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "date",
                "commits",
                "additions",
                "deletions",
                "churn",
                "files",
                "binary_files",
                "authors",
                "sources",
            ]
        )
        for day in days:
            authors = day["authors"]
            assert isinstance(authors, Counter)
            sources = day["sources"]
            assert isinstance(sources, Counter)
            writer.writerow(
                [
                    day["day"],
                    day["commits"],
                    day["additions"],
                    day["deletions"],
                    day["churn"],
                    day["files"],
                    day["binary_files"],
                    author_list(authors),
                    author_list(sources),
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--archive", type=Path, default=Path(r"C:\Users\sorok\project\termin-archieve"))
    parser.add_argument("--out-dir", type=Path, default=Path("docs"))
    parser.add_argument(
        "--exclude",
        action="append",
        default=["66e14f13cd30930928c0530e3bb97fe66fa06655"],
        help="Full commit SHA to exclude from statistics. May be passed multiple times.",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    archive = args.archive.resolve()
    excluded_shas = set(args.exclude)
    out_dir = (repo / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    commits = parse_commits(repo, "monorepo", excluded_shas)
    if archive.exists():
        commits.extend(parse_commits(archive, "archive", excluded_shas))
    commits = sorted(commits, key=lambda commit: (commit.day, commit.sha))
    days = grouped_by_day(commits)
    months = grouped_by_month(commits)
    quarters = grouped_by_quarter(commits)
    top_days = sorted(days, key=lambda item: int(item["churn"]), reverse=True)[:7]
    top_commit_days = sorted(days, key=lambda item: int(item["commits"]), reverse=True)[:7]
    top_commits = sorted(commits, key=lambda item: item.churn, reverse=True)[:12]
    totals = {
        "commits": len(commits),
        "churn": sum(commit.churn for commit in commits),
        "days": len(days),
        "months": len(months),
    }

    svg_name = "development-tension-report.svg"
    monthly_svg_name = "development-tension-monthly.svg"
    md_name = "development-tension-report.md"
    csv_name = "development-tension-daily.csv"
    (out_dir / svg_name).write_text(make_svg(top_days, totals), encoding="utf-8")
    (out_dir / monthly_svg_name).write_text(make_monthly_svg(months, totals), encoding="utf-8")
    write_daily_csv(out_dir / csv_name, days)
    (out_dir / md_name).write_text(
        make_markdown(
            commits,
            days,
            months,
            quarters,
            top_days,
            top_commit_days,
            top_commits,
            svg_name,
            monthly_svg_name,
            csv_name,
            excluded_shas,
        ),
        encoding="utf-8",
    )
    print(out_dir / md_name)
    print(out_dir / svg_name)
    print(out_dir / monthly_svg_name)
    print(out_dir / csv_name)


if __name__ == "__main__":
    main()
