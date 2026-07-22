"""Shared mechanics for Android-family APK builds."""

from __future__ import annotations

from collections.abc import Sequence
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from termin.project_build.target_build_common import read_log_tail


ANDROID_RELEASE_SIGNING_ENV = (
    "TERMIN_ANDROID_SIGNING_KEYSTORE",
    "TERMIN_ANDROID_SIGNING_KEY_ALIAS",
    "TERMIN_ANDROID_SIGNING_STORE_PASSWORD",
    "TERMIN_ANDROID_SIGNING_KEY_PASSWORD",
)


@dataclass(frozen=True)
class AndroidApkProduct:
    display_name: str
    gradle_build_dir: str
    artifact_qualifier: str
    log_filename: str


@dataclass(frozen=True)
class AndroidGradleVariant:
    configuration: str
    name: str
    task: str


@dataclass(frozen=True)
class AndroidApkPipelineResult:
    apk_path: Path
    log_path: Path
    variant: AndroidGradleVariant


def prepare_android_apk_output(dist_dir: Path, logs_dir: Path) -> None:
    (dist_dir / "apk").mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)


def resolve_android_gradle_variant(configuration: str) -> AndroidGradleVariant:
    normalized = configuration.strip().lower()
    if normalized in {"dev", "debug"}:
        return AndroidGradleVariant(
            configuration=normalized,
            name="debug",
            task="assembleDebug",
        )
    if normalized == "release":
        return AndroidGradleVariant(
            configuration=normalized,
            name="release",
            task="assembleRelease",
        )
    raise ValueError(
        f"Unsupported Android build configuration {configuration!r}; "
        "expected dev, debug, or release"
    )


def build_android_apk(
    *,
    product: AndroidApkProduct,
    configuration: str,
    project_name: str,
    application_id: str,
    termin_root: Path,
    build_script: Path,
    package_dir: Path,
    dist_dir: Path,
    logs_dir: Path,
    gradle: Path | None,
    android_sdk_root: Path,
    abi: str,
    platform: str,
    product_arguments: Sequence[str] = (),
    log_callback: Callable[[str], None] | None = None,
) -> AndroidApkPipelineResult:
    variant = resolve_android_gradle_variant(configuration)
    if variant.name == "release":
        _validate_release_signing_environment()

    log_path = logs_dir / product.log_filename
    cmd = [
        str(build_script),
        "--assets-dir",
        str(package_dir),
        "--sdk-root",
        str(android_sdk_root),
        "--abi",
        abi,
        "--platform",
        platform,
        "--variant",
        variant.name,
        *product_arguments,
    ]
    if gradle is not None:
        cmd.extend(["--gradle", str(gradle)])

    metadata_path = _gradle_output_dir(termin_root, product, variant) / "output-metadata.json"
    metadata_path.unlink(missing_ok=True)
    _run_logged_process(
        cmd=cmd,
        log_path=log_path,
        log_callback=log_callback,
        display_name=product.display_name,
    )

    source_apk = discover_gradle_apk(
        termin_root=termin_root,
        product=product,
        variant=variant,
        expected_application_id=application_id,
    )
    qualifier = f"-{product.artifact_qualifier}" if product.artifact_qualifier else ""
    apk_path = dist_dir / "apk" / f"{project_name}{qualifier}-{variant.name}.apk"
    shutil.copy2(source_apk, apk_path)
    return AndroidApkPipelineResult(
        apk_path=apk_path,
        log_path=log_path,
        variant=variant,
    )


def discover_gradle_apk(
    *,
    termin_root: Path,
    product: AndroidApkProduct,
    variant: AndroidGradleVariant,
    expected_application_id: str,
) -> Path:
    output_dir = _gradle_output_dir(termin_root, product, variant)
    metadata_path = output_dir / "output-metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"{product.display_name} build did not produce Gradle artifact metadata: "
            f"{metadata_path}"
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read Gradle artifact metadata {metadata_path}: {exc}") from exc

    if not isinstance(metadata, dict):
        raise RuntimeError(f"Gradle artifact metadata must be an object: {metadata_path}")
    metadata_application_id = metadata.get("applicationId")
    if metadata_application_id != expected_application_id:
        raise RuntimeError(
            f"Gradle artifact applicationId mismatch in {metadata_path}: "
            f"expected {expected_application_id!r}, got {metadata_application_id!r}"
        )
    elements = metadata.get("elements")
    if not isinstance(elements, list) or len(elements) != 1:
        count = len(elements) if isinstance(elements, list) else 0
        raise RuntimeError(
            f"Expected exactly one APK in Gradle artifact metadata {metadata_path}, found {count}"
        )
    element = elements[0]
    output_file = element.get("outputFile") if isinstance(element, dict) else None
    if not isinstance(output_file, str) or not output_file.endswith(".apk"):
        raise RuntimeError(f"Invalid APK outputFile in Gradle artifact metadata {metadata_path}")

    apk_path = (output_dir / output_file).resolve()
    resolved_output_dir = output_dir.resolve()
    if not apk_path.is_relative_to(resolved_output_dir):
        raise RuntimeError(
            f"Gradle artifact path escapes its output directory in {metadata_path}: {output_file}"
        )
    if not apk_path.is_file():
        raise FileNotFoundError(
            f"Gradle artifact metadata points to a missing APK: {apk_path}"
        )
    return apk_path


def _gradle_output_dir(
    termin_root: Path,
    product: AndroidApkProduct,
    variant: AndroidGradleVariant,
) -> Path:
    return (
        termin_root
        / "build"
        / product.gradle_build_dir
        / "app"
        / "outputs"
        / "apk"
        / variant.name
    )


def _validate_release_signing_environment() -> None:
    missing = [name for name in ANDROID_RELEASE_SIGNING_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Android release builds require signing configuration. Missing environment "
            f"variables: {', '.join(missing)}"
        )
    keystore = Path(os.environ["TERMIN_ANDROID_SIGNING_KEYSTORE"]).expanduser()
    if not keystore.is_file():
        raise FileNotFoundError(f"Android release signing keystore does not exist: {keystore}")


def _run_logged_process(
    *,
    cmd: list[str],
    log_path: Path,
    log_callback: Callable[[str], None] | None,
    display_name: str,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as log_file:
        command_line = "$ " + " ".join(cmd)
        log_file.write(command_line + "\n")
        log_file.flush()
        if log_callback is not None:
            log_callback(command_line)

        process = subprocess.Popen(
            cmd,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if process.stdout is not None:
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
                if log_callback is not None:
                    log_callback(line.rstrip("\n"))
        returncode = process.wait()

    if returncode != 0:
        log_tail = read_log_tail(log_path)
        raise RuntimeError(
            f"{display_name} build failed with exit code {returncode}; "
            f"see {log_path}\n{log_tail}"
        )
