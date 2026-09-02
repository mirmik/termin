#!/usr/bin/env python3
"""Render the public Task interface as a grouped, searchable command menu."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence


CATEGORY_ORDER = (
    "maintenance",
    "build",
    "distribution",
    "quality",
    "docs",
    "environment",
    "runtime",
    "ci",
)

CATEGORY_TITLES = {
    "maintenance": "Maintenance",
    "build": "Build",
    "distribution": "Packaging and publishing",
    "quality": "Tests and quality checks",
    "docs": "Documentation",
    "environment": "Toolchains and installation",
    "runtime": "Run and diagnostics",
    "ci": "Continuous integration",
}

CATEGORY_RANK = {name: rank for rank, name in enumerate(CATEGORY_ORDER)}


class TaskMenuError(RuntimeError):
    """An actionable failure while loading the Task command catalog."""


def load_tasks() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["task", "--list", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise TaskMenuError(f"failed to start Task: {error}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise TaskMenuError(f"Task command discovery failed: {detail}")

    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise TaskMenuError(f"Task returned invalid JSON: {error}") from error

    if not isinstance(document, dict):
        raise TaskMenuError("Task JSON root is not an object")

    tasks = document.get("tasks")
    if not isinstance(tasks, list):
        raise TaskMenuError("Task JSON does not contain a task list")

    if not all(isinstance(task, dict) for task in tasks):
        raise TaskMenuError("Task JSON contains a malformed task entry")

    return tasks


def task_category(task: dict[str, Any]) -> str:
    location = task.get("location")
    if not isinstance(location, dict):
        return "other"

    taskfile = location.get("taskfile")
    if not isinstance(taskfile, str):
        return "other"

    stem = Path(taskfile).stem.casefold()
    if stem == "taskfile":
        return "other"
    return stem


def category_title(category: str) -> str:
    return CATEGORY_TITLES.get(category, category.replace("-", " ").title())


def task_matches(task: dict[str, Any], category: str, terms: Sequence[str]) -> bool:
    if not terms:
        return True

    name = task.get("name")
    description = task.get("desc")
    haystack = " ".join(
        (
            name if isinstance(name, str) else "",
            description if isinstance(description, str) else "",
            category,
            category_title(category),
        )
    ).casefold()
    return all(term.casefold() in haystack for term in terms)


def grouped_tasks(
    tasks: Sequence[dict[str, Any]], terms: Sequence[str]
) -> list[tuple[str, list[dict[str, Any]]]]:
    visible_tasks = [
        task
        for task in tasks
        if task.get("name") != "default" and isinstance(task.get("name"), str)
    ]
    categories = {task_category(task) for task in visible_tasks}
    category_query = " ".join(terms).casefold()
    selected_category = next(
        (
            category
            for category in categories
            if category_query
            in (category.casefold(), category_title(category).casefold())
        ),
        None,
    )

    groups: dict[str, list[dict[str, Any]]] = {}
    for task in visible_tasks:
        category = task_category(task)
        if selected_category == category or (
            selected_category is None and task_matches(task, category, terms)
        ):
            groups.setdefault(category, []).append(task)

    ordered_categories = sorted(
        groups,
        key=lambda category: (CATEGORY_RANK.get(category, len(CATEGORY_RANK)), category),
    )
    return [
        (category, sorted(groups[category], key=lambda task: task["name"]))
        for category in ordered_categories
    ]


def render_menu(tasks: Sequence[dict[str, Any]], terms: Sequence[str]) -> str:
    groups = grouped_tasks(tasks, terms)
    if not groups:
        query = " ".join(terms)
        return f"No Termin tasks match: {query}"

    lines = ["Termin task catalog", ""]
    for group_index, (category, category_tasks) in enumerate(groups):
        if group_index:
            lines.append("")
        lines.append(category_title(category))

        commands = [f"task {task['name']}" for task in category_tasks]
        command_width = max(len(command) for command in commands)
        for command, task in zip(commands, category_tasks, strict=True):
            description = task.get("desc")
            description_text = description if isinstance(description, str) else ""
            lines.append(f"  {command:<{command_width}}  {description_text}".rstrip())

    lines.extend(
        (
            "",
            "Filter:  task help -- <text>",
            "Details: task --summary <task>",
            "Raw:     task --list",
        )
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    terms = list(sys.argv[1:] if argv is None else argv)
    try:
        tasks = load_tasks()
    except TaskMenuError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(render_menu(tasks, terms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
