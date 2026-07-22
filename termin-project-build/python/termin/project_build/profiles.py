"""Typed, toolkit-neutral storage for Termin product build profiles."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, TypeAlias


BUILD_PROFILE_SCHEMA_VERSION = 2

SUPPORTED_CONFIGURATIONS = ("dev", "debug", "release")
SUPPORTED_RESOURCE_POLICIES = ("dev_smoke", "strict")
SUPPORTED_DESKTOP_OSES = ("linux", "windows")
SUPPORTED_DESKTOP_ARCHITECTURES = ("x86_64",)
SUPPORTED_DESKTOP_BACKENDS = ("vulkan", "opengl", "d3d11")
SUPPORTED_ANDROID_ABIS = ("arm64-v8a", "x86_64")
SUPPORTED_DESKTOP_PYTHON_POLICIES = ("minimal_strict", "sdk_broad_copy")


@dataclass(frozen=True)
class ProfileDiagnostic:
    """One stable, path-specific build-profile diagnostic."""

    code: str
    path: str
    message: str

    def format(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


class ProfileBuildError(RuntimeError):
    """A profile document cannot be loaded, validated, or persisted."""

    def __init__(
        self,
        message: str | None = None,
        exit_code: int = 2,
        diagnostics: tuple[ProfileDiagnostic, ...] = (),
    ) -> None:
        if not diagnostics:
            diagnostics = (
                ProfileDiagnostic(
                    code="profile.invalid",
                    path="",
                    message=message or "invalid build profile",
                ),
            )
        self.exit_code = exit_code
        self.diagnostics = diagnostics
        super().__init__("; ".join(diagnostic.format() for diagnostic in diagnostics))


@dataclass(frozen=True)
class DesktopTarget:
    os: str
    arch: str
    backends: tuple[str, ...]
    python_package_policy: str = "minimal_strict"

    @property
    def kind(self) -> str:
        return "desktop"


@dataclass(frozen=True)
class AndroidTarget:
    abi: str
    ndk_api: int

    @property
    def kind(self) -> str:
        return "android"


@dataclass(frozen=True)
class QuestOpenXRTarget:
    abi: str
    ndk_api: int

    @property
    def kind(self) -> str:
        return "quest_openxr"


BuildTarget: TypeAlias = DesktopTarget | AndroidTarget | QuestOpenXRTarget


@dataclass(frozen=True)
class ProfileContent:
    entry_scene: Path
    scenes: tuple[Path, ...]
    modules: tuple[str, ...]
    python_requirements: tuple[str, ...]
    resource_policy: str
    resource_includes: tuple[str, ...]


@dataclass(frozen=True)
class BuildProfile:
    name: str
    project_root: Path
    target: BuildTarget
    configuration: str
    content: ProfileContent
    output_dir: Path | None = None

    @property
    def target_kind(self) -> str:
        return self.target.kind


class BuildProfileStore:
    """Loaded schema-v2 profile document with deterministic persistence."""

    def __init__(
        self,
        project_root: Path,
        path: Path,
        profiles: Mapping[str, BuildProfile],
    ) -> None:
        self.project_root = project_root.resolve()
        self.path = path.resolve()
        self._profiles = dict(profiles)

    @classmethod
    def load(cls, project_root: Path, path: Path) -> BuildProfileStore:
        resolved_project_root = project_root.resolve()
        resolved_path = path.resolve()
        document = _read_json_object(resolved_path)
        context = str(resolved_path)
        _validate_schema_version(document, context=context)
        _reject_unknown_keys(document, {"version", "profiles"}, context)
        raw_profiles = _required_object(document, "profiles", context=context)
        profiles: dict[str, BuildProfile] = {}
        for profile_name, raw_profile in raw_profiles.items():
            profile_path = f"profiles.{profile_name}"
            if not isinstance(profile_name, str) or profile_name == "":
                _fail("profile.name", profile_path, "profile name must be a non-empty string")
            if not isinstance(raw_profile, dict):
                _fail("profile.type", profile_path, "profile must be an object")
            profiles[profile_name] = _parse_profile(
                resolved_project_root,
                profile_name,
                raw_profile,
                profile_path,
            )
        return cls(project_root=resolved_project_root, path=resolved_path, profiles=profiles)

    @classmethod
    def create(cls, project_root: Path, path: Path) -> BuildProfileStore:
        return cls(project_root=project_root, path=path, profiles={})

    def profile_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._profiles))

    def get_profile(self, profile_name: str) -> BuildProfile:
        profile = self._profiles.get(profile_name)
        if profile is None:
            available = ", ".join(self.profile_names()) or "<none>"
            _fail(
                "profile.missing",
                f"profiles.{profile_name}",
                f"build profile was not found; available profiles: {available}",
            )
        return profile

    def update_profile(self, profile_name: str, profile: BuildProfile) -> BuildProfile:
        if profile_name == "":
            _fail("profile.name", "profiles", "build profile name must be a non-empty string")
        normalized = replace(
            profile,
            name=profile_name,
            project_root=self.project_root,
        )
        _validate_typed_profile(normalized)
        self._profiles[profile_name] = normalized
        return normalized

    def delete_profile(self, profile_name: str) -> None:
        if profile_name not in self._profiles:
            _fail(
                "profile.missing",
                f"profiles.{profile_name}",
                "build profile was not found",
            )
        del self._profiles[profile_name]

    def duplicate_profile(self, source_name: str, destination_name: str) -> BuildProfile:
        if destination_name in self._profiles:
            _fail(
                "profile.duplicate",
                f"profiles.{destination_name}",
                "build profile already exists",
            )
        return self.update_profile(destination_name, self.get_profile(source_name))

    def save(self, path: Path | None = None) -> Path:
        destination = (path if path is not None else self.path).resolve()
        document = {
            "version": BUILD_PROFILE_SCHEMA_VERSION,
            "profiles": {
                name: _serialize_profile(self._profiles[name])
                for name in sorted(self._profiles)
            },
        }
        serialized = json.dumps(
            document,
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
                diagnostics=(
                    ProfileDiagnostic(
                        code="profile.write_failed",
                        path=str(destination),
                        message=f"failed to write build profiles file: {exc}",
                    ),
                )
            ) from exc

        self.path = destination
        return destination


def validate_build_profile(profile: BuildProfile) -> tuple[ProfileDiagnostic, ...]:
    """Return typed schema diagnostics without mutating or normalizing ``profile``."""
    try:
        _validate_typed_profile(profile)
    except ProfileBuildError as exc:
        return exc.diagnostics
    return ()


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


def _parse_profile(
    project_root: Path,
    profile_name: str,
    raw_profile: Mapping[str, Any],
    context: str,
) -> BuildProfile:
    _reject_unknown_keys(
        raw_profile,
        {"target", "configuration", "content", "output_dir", "runtime"},
        context,
    )
    configuration = _required_choice(
        raw_profile,
        "configuration",
        SUPPORTED_CONFIGURATIONS,
        context,
    )
    content = _parse_content(
        _required_object(raw_profile, "content", context),
        f"{context}.content",
    )
    target_data = _required_object(raw_profile, "target", context)
    target_kind = _required_string(target_data, "kind", f"{context}.target")
    runtime_data = raw_profile.get("runtime")
    if target_kind == "desktop":
        if not isinstance(runtime_data, dict):
            _fail(
                "profile.required",
                f"{context}.runtime",
                "desktop profile must contain object field 'runtime'",
            )
        target: BuildTarget = _parse_desktop_target(
            target_data,
            runtime_data,
            context,
        )
    elif target_kind == "android":
        if runtime_data is not None:
            _fail(
                "profile.target_field",
                f"{context}.runtime",
                "android target does not expose configurable runtime fields",
            )
        target = _parse_android_target(target_data, f"{context}.target")
    elif target_kind == "quest_openxr":
        if runtime_data is not None:
            _fail(
                "profile.target_field",
                f"{context}.runtime",
                "quest_openxr target does not expose configurable runtime fields",
            )
        target = _parse_quest_target(target_data, f"{context}.target")
    else:
        supported = "desktop, android, quest_openxr"
        _fail(
            "profile.target",
            f"{context}.target.kind",
            f"unsupported build target '{target_kind}'; supported targets: {supported}",
            exit_code=3,
        )

    output_dir: Path | None = None
    if "output_dir" in raw_profile:
        output_dir = _project_relative_path(raw_profile["output_dir"], f"{context}.output_dir")

    profile = BuildProfile(
        name=profile_name,
        project_root=project_root,
        target=target,
        configuration=configuration,
        content=content,
        output_dir=output_dir,
    )
    _validate_typed_profile(profile)
    return profile


def _parse_content(data: Mapping[str, Any], context: str) -> ProfileContent:
    _reject_unknown_keys(data, {"entry_scene", "scenes", "modules", "python", "resources"}, context)
    entry_scene = _project_relative_path(
        _required_value(data, "entry_scene", context),
        f"{context}.entry_scene",
    )
    scenes = _unique_path_list(
        _required_value(data, "scenes", context),
        f"{context}.scenes",
    )
    if entry_scene not in scenes:
        _fail(
            "profile.entry_scene",
            f"{context}.entry_scene",
            "entry scene must also occur in content.scenes",
        )
    modules = _unique_string_list(
        data.get("modules", []),
        f"{context}.modules",
    )

    python_data = data.get("python", {})
    if not isinstance(python_data, dict):
        _fail("profile.type", f"{context}.python", "field must be an object")
    _reject_unknown_keys(python_data, {"requirements"}, f"{context}.python")
    python_requirements = _unique_string_list(
        python_data.get("requirements", []),
        f"{context}.python.requirements",
    )

    resources_data = data.get("resources", {})
    if not isinstance(resources_data, dict):
        _fail("profile.type", f"{context}.resources", "field must be an object")
    _reject_unknown_keys(resources_data, {"policy", "include"}, f"{context}.resources")
    resource_policy = _choice_value(
        resources_data.get("policy", "strict"),
        SUPPORTED_RESOURCE_POLICIES,
        f"{context}.resources.policy",
    )
    resource_includes = _unique_string_list(
        resources_data.get("include", []),
        f"{context}.resources.include",
    )
    return ProfileContent(
        entry_scene=entry_scene,
        scenes=scenes,
        modules=modules,
        python_requirements=python_requirements,
        resource_policy=resource_policy,
        resource_includes=resource_includes,
    )


def _parse_desktop_target(
    target_data: Mapping[str, Any],
    runtime_data: Mapping[str, Any],
    context: str,
) -> DesktopTarget:
    target_context = f"{context}.target"
    runtime_context = f"{context}.runtime"
    _reject_unknown_keys(target_data, {"kind", "os", "arch"}, target_context)
    _reject_unknown_keys(runtime_data, {"backends", "python_package_policy"}, runtime_context)
    target_os = _required_choice(target_data, "os", SUPPORTED_DESKTOP_OSES, target_context)
    arch = _required_choice(
        target_data,
        "arch",
        SUPPORTED_DESKTOP_ARCHITECTURES,
        target_context,
    )
    backends = _unique_choice_list(
        _required_value(runtime_data, "backends", runtime_context),
        SUPPORTED_DESKTOP_BACKENDS,
        f"{runtime_context}.backends",
        allow_empty=False,
    )
    if target_os == "linux" and "d3d11" in backends:
        _fail(
            "profile.backend_platform",
            f"{runtime_context}.backends",
            "Linux desktop target cannot run the d3d11 backend",
        )
    python_package_policy = _choice_value(
        runtime_data.get("python_package_policy", "minimal_strict"),
        SUPPORTED_DESKTOP_PYTHON_POLICIES,
        f"{runtime_context}.python_package_policy",
    )
    return DesktopTarget(
        os=target_os,
        arch=arch,
        backends=backends,
        python_package_policy=python_package_policy,
    )


def _parse_android_target(data: Mapping[str, Any], context: str) -> AndroidTarget:
    _reject_unknown_keys(data, {"kind", "abi", "ndk_api"}, context)
    return AndroidTarget(
        abi=_required_choice(data, "abi", SUPPORTED_ANDROID_ABIS, context),
        ndk_api=_required_ndk_api(data, context),
    )


def _parse_quest_target(data: Mapping[str, Any], context: str) -> QuestOpenXRTarget:
    _reject_unknown_keys(data, {"kind", "abi", "ndk_api"}, context)
    abi = _required_choice(data, "abi", SUPPORTED_ANDROID_ABIS, context)
    if abi != "arm64-v8a":
        _fail(
            "profile.quest_abi",
            f"{context}.abi",
            "quest_openxr target currently supports only arm64-v8a",
        )
    return QuestOpenXRTarget(abi=abi, ndk_api=_required_ndk_api(data, context))


def _validate_typed_profile(profile: BuildProfile) -> None:
    if profile.name == "":
        _fail("profile.name", "profile.name", "profile name must be a non-empty string")
    _choice_value(profile.configuration, SUPPORTED_CONFIGURATIONS, "profile.configuration")
    _project_relative_path(profile.content.entry_scene.as_posix(), "profile.content.entry_scene")
    for index, scene in enumerate(profile.content.scenes):
        _project_relative_path(scene.as_posix(), f"profile.content.scenes[{index}]")
    if profile.output_dir is not None:
        _project_relative_path(profile.output_dir.as_posix(), "profile.output_dir")
    _choice_value(
        profile.content.resource_policy,
        SUPPORTED_RESOURCE_POLICIES,
        "profile.content.resources.policy",
    )
    if profile.content.entry_scene not in profile.content.scenes:
        _fail(
            "profile.entry_scene",
            "profile.content.entry_scene",
            "entry scene must also occur in content.scenes",
        )
    if len(set(profile.content.scenes)) != len(profile.content.scenes):
        _fail("profile.duplicate", "profile.content.scenes", "scene roots must be unique")
    _validate_typed_string_roots(profile.content.modules, "profile.content.modules")
    _validate_typed_string_roots(
        profile.content.python_requirements,
        "profile.content.python.requirements",
    )
    _validate_typed_string_roots(
        profile.content.resource_includes,
        "profile.content.resources.include",
    )
    if isinstance(profile.target, DesktopTarget):
        _choice_value(profile.target.os, SUPPORTED_DESKTOP_OSES, "profile.target.os")
        _choice_value(
            profile.target.arch,
            SUPPORTED_DESKTOP_ARCHITECTURES,
            "profile.target.arch",
        )
        _choice_value(
            profile.target.python_package_policy,
            SUPPORTED_DESKTOP_PYTHON_POLICIES,
            "profile.runtime.python_package_policy",
        )
        if not profile.target.backends:
            _fail("profile.empty", "profile.runtime.backends", "backend list must not be empty")
        if len(set(profile.target.backends)) != len(profile.target.backends):
            _fail("profile.duplicate", "profile.runtime.backends", "backends must be unique")
        for index, backend in enumerate(profile.target.backends):
            _choice_value(
                backend,
                SUPPORTED_DESKTOP_BACKENDS,
                f"profile.runtime.backends[{index}]",
            )
        if profile.target.os == "linux" and "d3d11" in profile.target.backends:
            _fail(
                "profile.backend_platform",
                "profile.runtime.backends",
                "Linux desktop target cannot run the d3d11 backend",
            )
    elif isinstance(profile.target, AndroidTarget):
        _choice_value(profile.target.abi, SUPPORTED_ANDROID_ABIS, "profile.target.abi")
        _validate_typed_ndk_api(profile.target.ndk_api)
    elif isinstance(profile.target, QuestOpenXRTarget):
        if profile.target.abi != "arm64-v8a":
            _fail(
                "profile.quest_abi",
                "profile.target.abi",
                "quest_openxr target currently supports only arm64-v8a",
            )
        _validate_typed_ndk_api(profile.target.ndk_api)
    else:
        _fail("profile.target", "profile.target", "unsupported typed target variant")


def _validate_typed_string_roots(values: tuple[str, ...], path: str) -> None:
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str) or value == "":
            _fail("profile.type", f"{path}[{index}]", "value must be a non-empty string")
        if value in seen:
            _fail("profile.duplicate", f"{path}[{index}]", f"duplicate value '{value}'")
        seen.add(value)


def _validate_typed_ndk_api(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 26:
        _fail(
            "profile.ndk_api",
            "profile.target.ndk_api",
            "NDK API must be an integer greater than or equal to 26",
        )


def _serialize_profile(profile: BuildProfile) -> dict[str, Any]:
    content: dict[str, Any] = {
        "entry_scene": profile.content.entry_scene.as_posix(),
        "modules": list(profile.content.modules),
        "python": {"requirements": list(profile.content.python_requirements)},
        "resources": {
            "include": list(profile.content.resource_includes),
            "policy": profile.content.resource_policy,
        },
        "scenes": [path.as_posix() for path in profile.content.scenes],
    }
    result: dict[str, Any] = {
        "configuration": profile.configuration,
        "content": content,
    }
    if profile.output_dir is not None:
        result["output_dir"] = profile.output_dir.as_posix()
    if isinstance(profile.target, DesktopTarget):
        result["target"] = {
            "arch": profile.target.arch,
            "kind": profile.target.kind,
            "os": profile.target.os,
        }
        result["runtime"] = {
            "backends": list(profile.target.backends),
            "python_package_policy": profile.target.python_package_policy,
        }
    elif isinstance(profile.target, AndroidTarget):
        result["target"] = {
            "abi": profile.target.abi,
            "kind": profile.target.kind,
            "ndk_api": profile.target.ndk_api,
        }
    else:
        result["target"] = {
            "abi": profile.target.abi,
            "kind": profile.target.kind,
            "ndk_api": profile.target.ndk_api,
        }
    return result


def _read_json_object(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except OSError as exc:
        raise ProfileBuildError(
            diagnostics=(
                ProfileDiagnostic(
                    code="profile.read_failed",
                    path=str(path),
                    message=f"failed to read build profiles file: {exc}",
                ),
            )
        ) from exc
    except json.JSONDecodeError as exc:
        raise ProfileBuildError(
            diagnostics=(
                ProfileDiagnostic(
                    code="profile.json",
                    path=str(path),
                    message=f"failed to parse build profiles file: {exc}",
                ),
            )
        ) from exc
    if not isinstance(data, dict):
        _fail("profile.root", str(path), "build profiles root must be a JSON object")
    return data


def _validate_schema_version(data: Mapping[str, Any], context: str) -> None:
    value = data.get("version")
    if value is None:
        _fail(
            "profile.version_missing",
            f"{context}.version",
            f"missing integer build profile schema version {BUILD_PROFILE_SCHEMA_VERSION}",
        )
    if not isinstance(value, int):
        _fail("profile.version_type", f"{context}.version", "schema version must be an integer")
    if value != BUILD_PROFILE_SCHEMA_VERSION:
        _fail(
            "profile.version_unsupported",
            f"{context}.version",
            f"unsupported build profile schema version {value}; supported version is "
            f"{BUILD_PROFILE_SCHEMA_VERSION}; schema v1 is not migrated automatically",
        )


def _reject_unknown_keys(data: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        key = unknown[0]
        _fail("profile.unknown_field", f"{context}.{key}", "unknown field")


def _required_value(data: Mapping[str, Any], key: str, context: str) -> Any:
    if key not in data:
        _fail("profile.required", f"{context}.{key}", "required field is missing")
    return data[key]


def _required_object(data: Mapping[str, Any], key: str, context: str) -> dict[str, Any]:
    value = _required_value(data, key, context)
    if not isinstance(value, dict):
        _fail("profile.type", f"{context}.{key}", "field must be an object")
    return value


def _required_string(data: Mapping[str, Any], key: str, context: str) -> str:
    value = _required_value(data, key, context)
    if not isinstance(value, str) or value == "":
        _fail("profile.type", f"{context}.{key}", "field must be a non-empty string")
    return value


def _required_choice(
    data: Mapping[str, Any],
    key: str,
    supported: tuple[str, ...],
    context: str,
) -> str:
    return _choice_value(_required_value(data, key, context), supported, f"{context}.{key}")


def _choice_value(value: Any, supported: tuple[str, ...], path: str) -> str:
    if not isinstance(value, str) or value == "":
        _fail("profile.type", path, "field must be a non-empty string")
    if value not in supported:
        _fail(
            "profile.choice",
            path,
            f"unsupported value '{value}'; supported values: {', '.join(supported)}",
        )
    return value


def _required_ndk_api(data: Mapping[str, Any], context: str) -> int:
    value = _required_value(data, "ndk_api", context)
    if not isinstance(value, int) or isinstance(value, bool) or value < 26:
        _fail(
            "profile.ndk_api",
            f"{context}.ndk_api",
            "field must be an integer greater than or equal to 26",
        )
    return value


def _project_relative_path(value: Any, path: str) -> Path:
    if not isinstance(value, str) or value == "":
        _fail("profile.path", path, "field must be a non-empty project-relative path")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        _fail("profile.path", path, "path must stay relative to the project root")
    normalized = Path(*[part for part in candidate.parts if part not in ("", ".")])
    if not normalized.parts:
        _fail("profile.path", path, "path must not resolve to the project root")
    return normalized


def _unique_path_list(value: Any, path: str) -> tuple[Path, ...]:
    if not isinstance(value, list):
        _fail("profile.type", path, "field must be a list")
    result: list[Path] = []
    seen: set[Path] = set()
    for index, item in enumerate(value):
        parsed = _project_relative_path(item, f"{path}[{index}]")
        if parsed in seen:
            _fail("profile.duplicate", f"{path}[{index}]", f"duplicate value '{parsed.as_posix()}'")
        seen.add(parsed)
        result.append(parsed)
    if not result:
        _fail("profile.empty", path, "scene root list must not be empty")
    return tuple(result)


def _unique_string_list(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail("profile.type", path, "field must be a list")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or item == "":
            _fail("profile.type", f"{path}[{index}]", "value must be a non-empty string")
        if item in seen:
            _fail("profile.duplicate", f"{path}[{index}]", f"duplicate value '{item}'")
        seen.add(item)
        result.append(item)
    return tuple(result)


def _unique_choice_list(
    value: Any,
    supported: tuple[str, ...],
    path: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    result = _unique_string_list(value, path)
    if not allow_empty and not result:
        _fail("profile.empty", path, "list must not be empty")
    for index, item in enumerate(result):
        if item not in supported:
            _fail(
                "profile.choice",
                f"{path}[{index}]",
                f"unsupported value '{item}'; supported values: {', '.join(supported)}",
            )
    return result


def _fail(code: str, path: str, message: str, exit_code: int = 2) -> None:
    raise ProfileBuildError(
        exit_code=exit_code,
        diagnostics=(ProfileDiagnostic(code=code, path=path, message=message),),
    )
