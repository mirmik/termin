"""UI-neutral shader runtime configuration for editor and launcher hosts."""

from __future__ import annotations

import os
from pathlib import Path

from tcbase import log

from termin.editor_core.settings import EditorSettings
from termin.shader_tools import existing_executable, resolve_path_tool, resolve_sdk_tool


def _configured_tool(env_name: str, label: str) -> Path | None:
    configured = os.environ.get(env_name)
    if configured:
        path = Path(configured)
        resolved = existing_executable(path)
        if resolved is not None:
            return resolved
        log.error(f"[ShaderRuntime] {env_name} points to missing {label}: {configured}")
        return None
    return None


def resolve_termin_shaderc() -> Path | None:
    configured = _configured_tool("TERMIN_SHADERC", "file")
    if configured is not None:
        return configured

    sdk_tool = resolve_sdk_tool("termin_shaderc", Path(__file__))
    if sdk_tool is not None:
        return sdk_tool

    return resolve_path_tool("termin_shaderc")


def resolve_slangc() -> Path | None:
    settings_path = EditorSettings.instance().get_slang_compiler()
    if settings_path:
        path = Path(settings_path)
        resolved = existing_executable(path)
        if resolved is not None:
            return resolved
        log.error(f"[ShaderRuntime] configured Slang compiler is missing: {settings_path}")
        return None

    configured = _configured_tool("TERMIN_SLANGC", "slangc")
    if configured is not None:
        return configured

    sdk_tool = resolve_sdk_tool("slangc", Path(__file__))
    if sdk_tool is not None:
        return sdk_tool

    return resolve_path_tool("slangc")


def _sdk_shader_cache_root() -> Path:
    configured = os.environ.get("TERMIN_SDK_SHADER_CACHE_ROOT")
    if configured:
        return Path(configured)

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "Termin" / "Cache" / "sdk-shaders"

    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"
    return base / "termin" / "sdk-shaders"


def configure_sdk_shader_runtime(label: str, *, render_engine=None) -> None:
    root = _sdk_shader_cache_root()
    configure_shader_runtime(
        artifact_root=root / "artifacts",
        cache_root=root / "cache",
        label=label,
        render_engine=render_engine,
    )


def configure_shader_runtime(
    *,
    artifact_root: Path,
    cache_root: Path,
    label: str,
    render_engine=None,
) -> None:
    compiler = resolve_termin_shaderc()
    if compiler is None:
        log.error(f"[ShaderRuntime] termin_shaderc not found; {label} Slang shaders cannot compile")
        return

    slangc = resolve_slangc()
    if slangc is None:
        log.error(f"[ShaderRuntime] slangc not found; {label} Slang shaders cannot compile")
        return

    try:
        artifact_root.mkdir(parents=True, exist_ok=True)
        cache_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.error(
            f"[ShaderRuntime] {label} failed to create shader cache directories: {exc}"
        )
        return
    os.environ["TERMIN_SLANGC"] = str(slangc)

    try:
        if render_engine is None:
            # Non-engine tools such as the launcher still own one standalone
            # graphics runtime and use the compatibility resolver.
            import tgfx

            tgfx.configure_shader_runtime(
                artifact_root=str(artifact_root),
                cache_root=str(cache_root),
                shader_compiler=str(compiler),
                dev_compile=True,
            )
        else:
            render_engine.configure_shader_artifacts(
                artifact_root=str(artifact_root),
                cache_root=str(cache_root),
                compiler_path=str(compiler),
                dev_compile_enabled=True,
            )
        log.info(
            f"[ShaderRuntime] {label} configured: "
            f"artifact_root='{artifact_root}' cache_root='{cache_root}' "
            f"compiler='{compiler}' slangc='{slangc}' dev_compile=True"
        )
    except Exception as exc:
        log.error(f"[ShaderRuntime] {label} shader runtime configuration failed: {exc}")
