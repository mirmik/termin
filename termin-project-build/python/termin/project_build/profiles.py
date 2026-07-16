"""Toolkit-neutral storage for Termin project build profiles."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


BUILD_PROFILE_SCHEMA_VERSION = 1


class ProfileBuildError(RuntimeError):
    """A profile document cannot be loaded, validated, or persisted."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class BuildProfile:
    name: str
    project_root: Path
    target: str
    entry_scene: Path
    output_dir: Path
    data: Mapping[str, Any]


class BuildProfileStore:
    """Loaded schema-v1 profile document with deterministic persistence."""

    def __init__(
        self,
        project_root: Path,
        path: Path,
        document: Mapping[str, Any],
    ) -> None:
        self.project_root = project_root.resolve()
        self.path = path.resolve()
        self._document = copy.deepcopy(dict(document))

    @classmethod
    def load(cls, project_root: Path, path: Path) -> BuildProfileStore:
        resolved_path = path.resolve()
        document = _read_json_object(resolved_path)
        _validate_schema_version(document, context=str(resolved_path))
        _required_object(document, "profiles", context=str(resolved_path))
        return cls(project_root=project_root, path=resolved_path, document=document)

    @classmethod
    def create(cls, project_root: Path, path: Path) -> BuildProfileStore:
        return cls(
            project_root=project_root,
            path=path,
            document={"version": BUILD_PROFILE_SCHEMA_VERSION, "profiles": {}},
        )

    def profile_names(self) -> tuple[str, ...]:
        profiles = _required_object(self._document, "profiles", context=str(self.path))
        return tuple(sorted(profiles))

    def get_profile(self, profile_name: str) -> BuildProfile:
        profiles = _required_object(self._document, "profiles", context=str(self.path))
        raw_profile = _required_object(profiles, profile_name, context="profiles")
        return _build_profile(self.project_root, profile_name, raw_profile)

    def update_profile(
        self,
        profile_name: str,
        data: Mapping[str, Any],
    ) -> BuildProfile:
        if profile_name == "":
            raise ProfileBuildError("build profile name must be a non-empty string")
        raw_profile = copy.deepcopy(dict(data))
        profile = _build_profile(self.project_root, profile_name, raw_profile)
        profiles = _required_object(self._document, "profiles", context=str(self.path))
        profiles[profile_name] = raw_profile
        return profile

    def save(self, path: Path | None = None) -> Path:
        destination = (path if path is not None else self.path).resolve()
        serialized = json.dumps(
            self._document,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n"

        temporary_path: Path | None = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(serialized)
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, destination)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ProfileBuildError(
                f"failed to write build profiles file {destination}: {exc}"
            ) from exc

        self.path = destination
        return destination


def load_build_profile(
    project_root: Path,
    profiles_path: Path,
    profile_name: str,
) -> BuildProfile:
    return BuildProfileStore.load(project_root, profiles_path).get_profile(profile_name)


def resolve_project_path(project_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def _build_profile(
    project_root: Path,
    profile_name: str,
    raw_profile: Mapping[str, Any],
) -> BuildProfile:
    context = f"profile '{profile_name}'"
    target = _required_string(raw_profile, "target", context=context)
    entry_scene = resolve_project_path(
        project_root,
        _required_string(raw_profile, "entry_scene", context=context),
    )
    output_dir = resolve_project_path(
        project_root,
        _required_string(raw_profile, "output_dir", context=context),
    )
    return BuildProfile(
        name=profile_name,
        project_root=project_root.resolve(),
        target=target,
        entry_scene=entry_scene,
        output_dir=output_dir,
        data=copy.deepcopy(dict(raw_profile)),
    )


def _read_json_object(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except OSError as exc:
        raise ProfileBuildError(f"failed to read build profiles file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileBuildError(f"failed to parse build profiles file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileBuildError(f"build profiles root must be a JSON object: {path}")
    return data


def _validate_schema_version(data: Mapping[str, Any], context: str) -> None:
    value = data.get("version")
    if value is None:
        raise ProfileBuildError(
            f"{context} must contain integer field 'version' with value "
            f"{BUILD_PROFILE_SCHEMA_VERSION}"
        )
    if not isinstance(value, int):
        raise ProfileBuildError(f"{context} field 'version' must be an integer")
    if value != BUILD_PROFILE_SCHEMA_VERSION:
        raise ProfileBuildError(
            f"{context} has unsupported build profile schema version {value}; "
            f"supported version is {BUILD_PROFILE_SCHEMA_VERSION}"
        )


def _required_object(
    data: Mapping[str, Any],
    key: str,
    context: str,
) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ProfileBuildError(f"{context} must contain object field '{key}'")
    return value


def _required_string(data: Mapping[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or value == "":
        raise ProfileBuildError(f"{context} must contain non-empty string field '{key}'")
    return value
