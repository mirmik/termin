"""Filesystem helpers for runtime package export."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from termin.project_build.runtime_package.models import RuntimePackageExportDiagnostic


def project_relative_path(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()


def write_clean_package_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def resource_sort_key(resource: dict[str, str]) -> tuple[int, str]:
    type_order = {
        "shader": 0,
        "shader_program": 1,
        "pipeline": 2,
        "mesh": 3,
        "material": 4,
    }
    resource_type = resource["type"]
    return (type_order.get(resource_type, 100), resource["path"])


def append_project_file_diagnostic(
    diagnostics: list[RuntimePackageExportDiagnostic],
    project_root: Path,
    path: Path,
    message: str,
    level: str = "warning",
) -> None:
    diagnostics.append(
        RuntimePackageExportDiagnostic(
            level=level,
            path=project_relative_path(project_root, path),
            message=message,
        )
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
