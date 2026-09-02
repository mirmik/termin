from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import task_menu


def make_task(name: str, description: str, taskfile: str) -> dict[str, object]:
    return {
        "name": name,
        "desc": description,
        "location": {"taskfile": taskfile},
    }


def test_render_menu_groups_tasks_by_included_taskfile() -> None:
    tasks = [
        make_task("test:python", "Run Python tests", "/repo/taskfiles/quality.yml"),
        make_task("default", "Show menu", "/repo/Taskfile.yml"),
        make_task("build", "Build SDK", "/repo/taskfiles/build.yml"),
    ]

    menu = task_menu.render_menu(tasks, [])

    assert menu.index("Build") < menu.index("Tests and quality checks")
    assert "task build  Build SDK" in menu
    assert "task test:python  Run Python tests" in menu
    assert "task default" not in menu


def test_render_menu_filters_by_category_and_description() -> None:
    tasks = [
        make_task("build", "Build complete SDK", "/repo/taskfiles/build.yml"),
        make_task("clean", "Remove build artifacts", "/repo/taskfiles/maintenance.yml"),
        make_task("lint:python", "Run Python lint", "/repo/taskfiles/quality.yml"),
    ]

    quality_menu = task_menu.render_menu(tasks, ["quality"])
    build_menu = task_menu.render_menu(tasks, ["build"])
    description_menu = task_menu.render_menu(tasks, ["complete", "sdk"])

    assert "task lint:python" in quality_menu
    assert "task build" not in quality_menu
    assert "task build" in build_menu
    assert "task clean" not in build_menu
    assert "task build" in description_menu
    assert "task lint:python" not in description_menu


def test_render_menu_reports_an_empty_search() -> None:
    tasks = [make_task("build", "Build SDK", "/repo/taskfiles/build.yml")]

    assert task_menu.render_menu(tasks, ["missing"]) == "No Termin tasks match: missing"


def test_load_tasks_rejects_invalid_json() -> None:
    result = subprocess.CompletedProcess(
        args=["task", "--list", "--json"],
        returncode=0,
        stdout="not-json",
        stderr="",
    )
    with patch.object(task_menu.subprocess, "run", return_value=result):
        with pytest.raises(task_menu.TaskMenuError, match="invalid JSON"):
            task_menu.load_tasks()


def test_load_tasks_reports_task_discovery_failure() -> None:
    result = subprocess.CompletedProcess(
        args=["task", "--list", "--json"],
        returncode=1,
        stdout="",
        stderr="Taskfile is invalid",
    )

    with patch.object(task_menu.subprocess, "run", return_value=result):
        with pytest.raises(task_menu.TaskMenuError, match="Taskfile is invalid"):
            task_menu.load_tasks()


def test_load_tasks_rejects_non_object_json() -> None:
    result = subprocess.CompletedProcess(
        args=["task", "--list", "--json"],
        returncode=0,
        stdout="[]",
        stderr="",
    )

    with patch.object(task_menu.subprocess, "run", return_value=result):
        with pytest.raises(task_menu.TaskMenuError, match="root is not an object"):
            task_menu.load_tasks()


def test_load_tasks_returns_discovered_tasks() -> None:
    tasks = [make_task("build", "Build SDK", "/repo/taskfiles/build.yml")]
    result = subprocess.CompletedProcess(
        args=["task", "--list", "--json"],
        returncode=0,
        stdout=json.dumps({"tasks": tasks}),
        stderr="",
    )
    with patch.object(task_menu.subprocess, "run", return_value=result):
        assert task_menu.load_tasks() == tasks
