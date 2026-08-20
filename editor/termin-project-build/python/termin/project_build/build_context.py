"""Normalized project build context construction."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from termin.project.settings import load_project_settings
from termin.project.world_controller_selection import ProjectWorldControllerSelection
from termin.project_build.common import read_project_name


@dataclass
class BuildContext:
    project_root: Path
    project_name: str
    target: str
    configuration: str
    resource_policy: str
    entry_scene: Path
    scenes: tuple[Path, ...]
    generated_output_root: Path
    dist_dir: Path
    package_dir: Path
    logs_dir: Path
    world_controller: ProjectWorldControllerSelection | None
    target_options: dict[str, object] = field(default_factory=dict)


def create_build_context(
    project_root: str | Path,
    entry_scene: str | Path,
    target: str,
    scenes: Iterable[str | Path] | None = None,
    output_dir: str | Path | None = None,
    project_name: str | None = None,
    configuration: str = "dev",
    resource_policy: str = "strict",
    target_options: Mapping[str, object] | None = None,
) -> BuildContext:
    project_root_path = Path(project_root).resolve()
    resolved_project_name = project_name
    if resolved_project_name is None:
        resolved_project_name = read_project_name(project_root_path)

    settings = load_project_settings(project_root_path)
    generated_output_root = (project_root_path / settings.build_output_dir).resolve()
    dist_dir = resolve_build_dist_dir(
        project_root=project_root_path,
        project_name=resolved_project_name,
        target=target,
        output_dir=output_dir,
        generated_output_root=generated_output_root,
    )
    entry_scene_path = _resolve_entry_scene(project_root_path, entry_scene)
    scene_paths = tuple(
        _resolve_entry_scene(project_root_path, scene)
        for scene in (scenes if scenes is not None else (entry_scene_path,))
    )

    return BuildContext(
        project_root=project_root_path,
        project_name=resolved_project_name,
        target=target,
        configuration=configuration,
        resource_policy=resource_policy,
        entry_scene=entry_scene_path,
        scenes=scene_paths,
        generated_output_root=generated_output_root,
        dist_dir=dist_dir,
        package_dir=dist_dir / "package",
        logs_dir=dist_dir / "logs",
        world_controller=settings.world_controller,
        target_options=dict(target_options or {}),
    )


def _resolve_entry_scene(project_root: Path, entry_scene: str | Path) -> Path:
    entry_path = Path(entry_scene)
    if entry_path.is_absolute():
        return entry_path.resolve()
    return (project_root / entry_path).resolve()


def resolve_build_dist_dir(
    project_root: Path,
    project_name: str,
    target: str,
    output_dir: str | Path | None,
    generated_output_root: Path | None = None,
) -> Path:
    if output_dir is not None:
        return Path(output_dir).resolve()

    output_root = generated_output_root or (project_root / "dist").resolve()
    if target == "desktop":
        return (output_root / "desktop" / project_name).resolve()
    if target == "android":
        return (output_root / "android" / project_name).resolve()
    if target == "quest_openxr":
        return (output_root / "quest_openxr" / project_name).resolve()

    raise ValueError(f"Unsupported build target: {target}")
