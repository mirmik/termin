"""Shared shader runtime configuration helpers for editor-side UI."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

from tcbase import log

from termin.editor_core.settings import EditorSettings


def resolve_termin_shaderc() -> Path | None:
    configured = os.environ.get("TERMIN_SHADERC")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        log.error(f"[ShaderRuntime] TERMIN_SHADERC points to missing file: {configured}")
        return None

    sdk = os.environ.get("TERMIN_SDK")
    if sdk:
        candidate = Path(sdk) / "bin" / "termin_shaderc"
        if candidate.is_file():
            return candidate

    local_sdk = Path(__file__).resolve().parents[3] / "sdk" / "bin" / "termin_shaderc"
    if local_sdk.is_file():
        return local_sdk

    found = shutil.which("termin_shaderc")
    if found:
        return Path(found)
    return None


def resolve_slangc() -> Path | None:
    settings_path = EditorSettings.instance().get_slang_compiler()
    if settings_path:
        path = Path(settings_path)
        if path.is_file():
            return path
        log.error(f"[ShaderRuntime] configured Slang compiler is missing: {settings_path}")
        return None

    configured = os.environ.get("TERMIN_SLANGC")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        log.error(f"[ShaderRuntime] TERMIN_SLANGC points to missing file: {configured}")
        return None

    found = shutil.which("slangc")
    if found:
        return Path(found)

    sdk = os.environ.get("TERMIN_SDK")
    if sdk:
        candidate = Path(sdk) / "bin" / "slangc"
        if candidate.is_file():
            return candidate

    return None


def _sdk_shader_cache_root() -> Path:
    configured = os.environ.get("TERMIN_SDK_SHADER_CACHE_ROOT")
    if configured:
        return Path(configured)

    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"
    return base / "termin" / "sdk-shaders"


def configure_sdk_shader_runtime(label: str) -> None:
    root = _sdk_shader_cache_root()
    configure_shader_runtime(
        artifact_root=root / "artifacts",
        cache_root=root / "cache",
        label=label,
    )


def configure_shader_runtime(
    *,
    artifact_root: Path,
    cache_root: Path,
    label: str,
) -> None:
    compiler = resolve_termin_shaderc()
    if compiler is None:
        log.error(f"[ShaderRuntime] termin_shaderc not found; {label} Slang shaders cannot compile")
        return

    slangc = resolve_slangc()
    if slangc is None:
        log.error(f"[ShaderRuntime] slangc not found; {label} Slang shaders cannot compile")
        return

    artifact_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ["TERMIN_SLANGC"] = str(slangc)

    try:
        import tgfx

        tgfx.configure_shader_runtime(
            artifact_root=str(artifact_root),
            cache_root=str(cache_root),
            shader_compiler=str(compiler),
            dev_compile=True,
        )
        log.info(
            f"[ShaderRuntime] {label} configured: "
            f"artifact_root='{artifact_root}' cache_root='{cache_root}' "
            f"compiler='{compiler}' slangc='{slangc}' dev_compile=True"
        )
    except Exception as exc:
        log.error(f"[ShaderRuntime] {label} configure_shader_runtime failed: {exc}")
