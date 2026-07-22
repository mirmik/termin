"""Project creation helpers and default scene template."""

from __future__ import annotations

import ctypes
import errno
import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path, PureWindowsPath

from termin.project.application_identity import default_project_application_identity


_LOGGER = logging.getLogger(__name__)


class ProjectCreationError(RuntimeError):
    """Raised when a new project cannot be created safely."""


class InvalidProjectNameError(ProjectCreationError):
    """Raised when a project name is not a portable path leaf."""


class InvalidProjectLocationError(ProjectCreationError):
    """Raised when a selected project root cannot be used safely."""


class ProjectAlreadyExistsError(ProjectCreationError):
    """Raised when project creation would replace an existing path."""


_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def validate_project_name(name: str) -> str:
    """Return a portable, single-directory-component project name.

    Both the launcher and the editor use this policy.  Project names are
    deliberately leaves rather than relative paths: a UI-selected directory
    is the sole authority for the destination root.
    """
    if not isinstance(name, str):
        raise InvalidProjectNameError("Project name must be text.")

    if name != name.strip():
        raise InvalidProjectNameError("Project name must not start or end with whitespace.")
    clean = name
    if not clean or clean in {".", ".."}:
        raise InvalidProjectNameError("Project name must not be empty or a dot path.")
    if any(ord(char) < 32 for char in clean) or any(char in clean for char in '<>:"/\\|?*'):
        raise InvalidProjectNameError("Project name must not contain path separators or reserved characters.")
    if PureWindowsPath(clean).drive or PureWindowsPath(clean).root:
        raise InvalidProjectNameError("Project name must be a single path component.")
    if clean.endswith((".", " ")):
        raise InvalidProjectNameError("Project name must not end with a dot or space.")

    windows_stem = clean.split(".", 1)[0].upper()
    if windows_stem in _WINDOWS_RESERVED_NAMES:
        raise InvalidProjectNameError("Project name is reserved on Windows.")
    return clean


def _resolve_creation_root(location: str | os.PathLike[str]) -> Path:
    """Resolve an existing destination root without creating parent paths."""
    try:
        root = Path(location).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InvalidProjectLocationError(f"Project location cannot be resolved: {location}") from exc
    if not root.is_dir():
        raise InvalidProjectLocationError(f"Project location is not a directory: {root}")
    return root


def _project_target(root: Path, name: str) -> Path:
    """Build a checked child target from a trusted resolved root and leaf."""
    target = root / name
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise InvalidProjectNameError("Project target escapes the selected location.") from exc
    return target


def _write_json(path: Path, contents: dict) -> None:
    path.write_text(json.dumps(contents, indent=2), encoding="utf-8")


def make_default_scene() -> dict:
    """Create a default scene with a Cube, Light, and Ground plane."""
    return {
        "version": "1.0",
        "scene": {
            "uuid": str(uuid.uuid4()),
            "entities": [
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Cube",
                    "priority": 0,
                    "visible": True,
                    "enabled": True,
                    "pickable": True,
                    "selectable": True,
                    "layer": 0,
                    "flags": 0,
                    "pose": {
                        "position": [0.0, 0.0, 0.5],
                        "rotation": [0.0, 0.0, 0.0, 1.0],
                    },
                    "scale": [1.0, 1.0, 1.0],
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "enabled": True,
                                "mesh": {
                                    "uuid": "00000000-0000-0000-0003-000000000001",
                                    "name": "Cube",
                                },
                                "material": {
                                    "uuid": "00000000-0001-0000-0001-000000000003",
                                    "name": "NormalizedPBR",
                                    "type": "uuid",
                                },
                                "cast_shadow": True,
                                "_override_material": True,
                                "_overridden_material_data": {
                                    "phases_uniforms": [
                                        {
                                            "u_diffuse_mul": 3.14,
                                            "u_color": [0.084, 0.671, 0.636, 1.0],
                                        },
                                        {
                                            "u_color": [0.084, 0.671, 0.636, 1.0],
                                            "u_metallic": 0.0,
                                            "u_roughness": 0.5,
                                            "u_subsurface": 0.0,
                                            "u_diffuse_mul": 3.14,
                                            "u_emission_color": [0.0, 0.0, 0.0, 1.0],
                                            "u_emission_intensity": 0.0,
                                            "u_normal_strength": 1.0,
                                        },
                                    ],
                                    "phases_textures": [
                                        {},
                                        {
                                            "u_albedo_texture": {
                                                "uuid": "__white_1x1__",
                                                "name": "__white_1x1__",
                                                "type": "path",
                                                "path": "__white_1x1__",
                                            },
                                            "u_normal_texture": {
                                                "uuid": "__normal_1x1__",
                                                "name": "__normal_1x1__",
                                                "type": "path",
                                                "path": "__normal_1x1__",
                                            },
                                        },
                                    ],
                                },
                            },
                        }
                    ],
                },
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Light",
                    "priority": 0,
                    "visible": True,
                    "enabled": True,
                    "pickable": True,
                    "selectable": True,
                    "layer": 0,
                    "flags": 0,
                    "pose": {
                        "position": [0.83, 4.48, 4.57],
                        "rotation": [-0.1098, -0.4342, 0.8540, 0.2647],
                    },
                    "scale": [1.0, 1.0, 1.0],
                    "components": [
                        {
                            "type": "LightComponent",
                            "data": {
                                "light_type": "directional",
                                "color": [1.0, 1.0, 1.0],
                                "intensity": 1.0,
                                "shadows_enabled": True,
                                "shadows_map_resolution": 2048,
                                "cascade_count": 3,
                                "max_distance": 100.0,
                                "split_lambda": 0.5,
                                "cascade_blend": True,
                            },
                        }
                    ],
                },
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Ground",
                    "priority": 0,
                    "visible": True,
                    "enabled": True,
                    "pickable": True,
                    "selectable": True,
                    "layer": 0,
                    "flags": 0,
                    "pose": {
                        "position": [0.0, 0.0, 0.0],
                        "rotation": [0.0, 0.0, 0.0, 1.0],
                    },
                    "scale": [5.0, 5.0, 1.0],
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "enabled": True,
                                "mesh": {
                                    "uuid": "00000000-0000-0000-0003-000000000003",
                                    "name": "Plane",
                                },
                                "material": {
                                    "uuid": "00000000-0001-0000-0001-000000000003",
                                    "name": "NormalizedPBR",
                                    "type": "uuid",
                                },
                                "cast_shadow": True,
                                "_override_material": True,
                                "_overridden_material_data": {
                                    "phases_uniforms": [
                                        {
                                            "u_diffuse_mul": 3.14,
                                            "u_color": [0.416, 0.232, 0.030, 1.0],
                                        },
                                        {
                                            "u_color": [0.416, 0.232, 0.030, 1.0],
                                            "u_metallic": 0.0,
                                            "u_roughness": 0.5,
                                            "u_subsurface": 0.0,
                                            "u_diffuse_mul": 3.14,
                                            "u_emission_color": [0.0, 0.0, 0.0, 1.0],
                                            "u_emission_intensity": 0.0,
                                            "u_normal_strength": 1.0,
                                        },
                                    ],
                                    "phases_textures": [
                                        {},
                                        {
                                            "u_albedo_texture": {
                                                "uuid": "__white_1x1__",
                                                "name": "__white_1x1__",
                                                "type": "path",
                                                "path": "__white_1x1__",
                                            },
                                            "u_normal_texture": {
                                                "uuid": "__normal_1x1__",
                                                "name": "__normal_1x1__",
                                                "type": "path",
                                                "path": "__normal_1x1__",
                                            },
                                        },
                                    ],
                                },
                            },
                        }
                    ],
                },
            ],
            "layer_names": {},
            "flag_names": {},
            "extensions": {
                "render_mount": {
                    "viewport_configs": [],
                    "pipeline_templates": [],
                },
                "render_state": {
                    "background_color": [0.05, 0.05, 0.08, 1.0],
                    "lighting": {
                        "ambient_color": [1.0, 1.0, 1.0],
                        "ambient_intensity": 0.15,
                        "shadow_settings": {
                            "method": 1,
                            "softness": 1.0,
                            "bias": 0.0,
                        },
                    },
                    "skybox": {
                        "type": 1,
                        "color": [0.5, 0.7, 0.9],
                        "top_color": [0.4, 0.6, 0.9],
                        "bottom_color": [0.6, 0.5, 0.4],
                    },
                },
            },
        },
        "editor": {
            "camera": {
                "position": [-3.46, 6.50, 5.13],
                "rotation": [0.0735, -0.2864, 0.9253, -0.2376],
                "radius": 7.0,
            },
        },
    }


def write_default_scene(path: str) -> None:
    """Write a default scene to the given file path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(make_default_scene(), f, indent=2)


def _project_manifest(name: str) -> dict:
    return {"version": 1, "name": name}


def _write_project_contents(project_dir: Path, name: str, final_scene_file: Path) -> None:
    """Write a complete starter project into an unpublished directory."""
    _write_json(project_dir / f"{name}.terminproj", _project_manifest(name))

    settings_dir = project_dir / "project_settings"
    settings_dir.mkdir()
    _write_json(
        settings_dir / "project.json",
        {
            "render_sync_mode": "none",
            "application": default_project_application_identity(name).to_dict(),
        },
    )

    navmesh_area_names = [""] * 64
    navmesh_area_names[0] = "Walkable"
    _write_json(
        settings_dir / "navigation.json",
        {
            "agent_types": [
                {
                    "name": "Human",
                    "radius": 0.5,
                    "height": 2.0,
                    "max_slope": 45.0,
                    "step_height": 0.4,
                }
            ],
            "navmesh_area_names": navmesh_area_names,
        },
    )
    _write_json(settings_dir / ".editor_state.json", {"last_scene": str(final_scene_file)})
    write_default_scene(str(project_dir / "scene.scene"))


def _remove_staging_directory(staging_dir: Path) -> None:
    if not staging_dir.exists():
        return
    try:
        shutil.rmtree(staging_dir)
    except OSError:
        _LOGGER.exception("Failed to remove incomplete project staging directory %s", staging_dir)


def _publish_staged_path(staging_path: Path, target_path: Path) -> None:
    """Atomically publish a staged file or directory without replacement.

    Linux has ``renameat2(..., RENAME_NOREPLACE)`` for this exact operation.
    Windows ``MoveFileEx`` semantics exposed by :func:`os.rename` likewise
    reject an existing destination.  We intentionally fail on other systems
    rather than weaken the non-destructive contract with a check-then-rename
    race or a visible partial directory.
    """
    if os.name == "nt":
        try:
            os.rename(staging_path, target_path)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise ProjectAlreadyExistsError(f"Project path already exists: {target_path}") from exc
            raise
        return

    if os.name != "posix":
        raise ProjectCreationError(
            "This platform does not support atomic no-replace project publication."
        )

    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exc:
        raise ProjectCreationError(
            "This platform does not support atomic no-replace project publication."
        ) from exc
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,  # AT_FDCWD
        os.fsencode(staging_path),
        -100,  # AT_FDCWD
        os.fsencode(target_path),
        1,  # RENAME_NOREPLACE
    )
    if result == 0:
        return

    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise ProjectAlreadyExistsError(f"Project path already exists: {target_path}")
    if error_number in {errno.ENOSYS, errno.EINVAL}:
        raise ProjectCreationError(
            "This filesystem does not support atomic no-replace project publication."
        )
    raise OSError(error_number, os.strerror(error_number), target_path)


def create_project(name: str, location: str | os.PathLike[str]) -> str:
    """Create a complete new project under *location* without overwriting data.

    The project is first assembled in a hidden sibling directory.  The final
    target is claimed exclusively only after that work succeeds, which also
    leaves no project directory behind when template generation fails.
    """
    project_name = validate_project_name(name)
    root = _resolve_creation_root(location)
    project_dir = _project_target(root, project_name)
    project_file = project_dir / f"{project_name}.terminproj"
    staging_dir = Path(tempfile.mkdtemp(prefix=".termin-project-", dir=root))

    try:
        _write_project_contents(staging_dir, project_name, project_file.parent / "scene.scene")
        _publish_staged_path(staging_dir, project_dir)
    except ProjectCreationError:
        _remove_staging_directory(staging_dir)
        raise
    except OSError as exc:
        _remove_staging_directory(staging_dir)
        raise ProjectCreationError(f"Failed to create project at {project_dir}: {exc}") from exc
    except Exception:
        _remove_staging_directory(staging_dir)
        raise

    return str(project_file)


def create_project_file(name: str, location: str | os.PathLike[str]) -> str:
    """Create one empty project descriptor without replacing an existing file.

    This supports the editor's file-save workflow while sharing the same name
    validation and destination confinement as full starter-project creation.
    The same atomic no-replace publication primitive used for full project
    directories publishes the completed sibling staging file.
    """
    project_name = validate_project_name(name)
    root = _resolve_creation_root(location)
    project_file = _project_target(root, f"{project_name}.terminproj")
    descriptor_fd, descriptor_path = tempfile.mkstemp(
        prefix=".termin-project-",
        suffix=".terminproj",
        dir=root,
    )
    staging_file = Path(descriptor_path)
    try:
        with os.fdopen(descriptor_fd, "w", encoding="utf-8") as descriptor:
            json.dump(_project_manifest(project_name), descriptor, indent=2)
            descriptor.flush()
            os.fsync(descriptor.fileno())
        _publish_staged_path(staging_file, project_file)
    except ProjectCreationError:
        raise
    except OSError as exc:
        raise ProjectCreationError(f"Failed to create project file {project_file}: {exc}") from exc
    finally:
        try:
            staging_file.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            _LOGGER.exception("Failed to remove project descriptor staging file %s", staging_file)

    return str(project_file)
