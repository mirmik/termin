"""Android project build wrapper."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from termin.project_build.runtime_package_exporter import (
    RuntimePackageExportDiagnostic,
    RuntimePackageExportResult,
    export_runtime_package,
)


@dataclass
class AndroidBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    apk_path: Path
    log_path: Path
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


def build_android_project(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path | None = None,
    termin_root: str | Path | None = None,
    build_script: str | Path | None = None,
    gradle: str | Path | None = None,
    shader_compiler: str | Path | None = None,
    abi: str = "arm64-v8a",
    platform: str = "android-26",
) -> AndroidBuildResult:
    project_root_path = Path(project_root).resolve()
    project_name = _read_project_name(project_root_path)
    dist_dir = _resolve_dist_dir(project_root_path, project_name, output_dir)
    package_dir = dist_dir / "package"
    apk_dir = dist_dir / "apk"
    logs_dir = dist_dir / "logs"
    apk_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    package_result = export_runtime_package(
        project_root=project_root_path,
        entry_scene=entry_scene,
        output_dir=package_dir,
        shader_compiler=shader_compiler,
    )

    termin_root_path = _resolve_termin_root(termin_root)
    build_script_path = _resolve_build_script(termin_root_path, build_script)
    log_path = logs_dir / "android-build.log"
    _run_android_build_script(
        build_script=build_script_path,
        package_dir=package_result.package_dir,
        log_path=log_path,
        gradle=Path(gradle) if gradle is not None else None,
        abi=abi,
        platform=platform,
    )

    source_apk = termin_root_path / "build" / "android-gradle" / "app" / "outputs" / "apk" / "debug" / "app-debug.apk"
    if not source_apk.exists():
        raise FileNotFoundError(f"Android build did not produce APK: {source_apk}")

    apk_path = apk_dir / f"{project_name}-debug.apk"
    shutil.copy2(source_apk, apk_path)

    return AndroidBuildResult(
        dist_dir=dist_dir,
        package_result=package_result,
        apk_path=apk_path,
        log_path=log_path,
        diagnostics=list(package_result.diagnostics),
    )


def _resolve_dist_dir(project_root: Path, project_name: str, output_dir: str | Path | None) -> Path:
    if output_dir is not None:
        return Path(output_dir).resolve()
    return (project_root / "dist" / "android" / project_name).resolve()


def _resolve_termin_root(termin_root: str | Path | None) -> Path:
    if termin_root is not None:
        root = Path(termin_root).resolve()
    else:
        root = Path(__file__).resolve().parents[3]
    if not (root / "build-android-apk.sh").exists():
        raise FileNotFoundError(f"Termin root has no build-android-apk.sh: {root}")
    return root


def _resolve_build_script(termin_root: Path, build_script: str | Path | None) -> Path:
    if build_script is not None:
        script = Path(build_script).resolve()
    else:
        script = termin_root / "build-android-apk.sh"
    if not script.exists():
        raise FileNotFoundError(f"Android build script does not exist: {script}")
    return script


def _run_android_build_script(
    build_script: Path,
    package_dir: Path,
    log_path: Path,
    gradle: Path | None,
    abi: str,
    platform: str,
) -> None:
    cmd = [
        str(build_script),
        "--assets-dir",
        str(package_dir),
        "--abi",
        abi,
        "--platform",
        platform,
    ]
    if gradle is not None:
        cmd.extend(["--gradle", str(gradle)])

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        result.stdout + result.stderr,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Android build failed with exit code {result.returncode}; see {log_path}"
        )


def _read_project_name(project_root: Path) -> str:
    project_files = sorted(project_root.glob("*.terminproj"))
    if not project_files:
        return project_root.name

    project_file = project_files[0]
    try:
        with open(project_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return project_file.stem

    if not isinstance(data, dict):
        return project_file.stem

    name = data.get("name")
    if isinstance(name, str) and name != "":
        return name
    return project_file.stem
