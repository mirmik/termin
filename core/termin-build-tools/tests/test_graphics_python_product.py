from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from termin_build import artifact_manifest
from termin_build.graphics_python_product import (
    GraphicsPythonProductError,
    LINUX_BUNDLED_RUNTIME_LIBRARIES,
    build_product,
    build_resource_wheel,
)
from termin_build.python_abi import PythonAbiIdentity
from termin_build.wheelhouse import inspect_wheel


def _write_manifest(sdk_prefix: Path) -> None:
    abi = PythonAbiIdentity(
        version="3.14",
        soabi="cpython-314t-x86_64-linux-gnu",
        free_threaded=True,
        py_gil_disabled=True,
    )
    artifacts = [
        {
            "extension": "tgfx._fake",
            "sha256": "0" * 64,
            "runtime_dependencies": [
                {
                    "name": "libtermin_graphics.so.0",
                    "path": "lib/libtermin_graphics.so.0",
                    "sha256": "1" * 64,
                }
            ],
        }
    ]
    payload = {
        "schema": artifact_manifest.SCHEMA_VERSION,
        "manifest_kind": artifact_manifest.SDK_MANIFEST_KIND,
        "python_abi": abi.to_dict(),
        "native_build_id": artifact_manifest.compute_native_build_id(artifacts, abi),
        "artifacts": artifacts,
    }
    sdk_prefix.mkdir(parents=True)
    (sdk_prefix / artifact_manifest.SDK_MANIFEST_NAME).write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_resource_wheel_owns_precompiled_assets_without_shader_toolchain(
    tmp_path: Path,
) -> None:
    sdk_prefix = tmp_path / "native-prefix"
    _write_manifest(sdk_prefix)
    for relative, payload in (
        ("lib/libtermin_graphics.so.0", b"graphics"),
        (f"lib/{LINUX_BUNDLED_RUNTIME_LIBRARIES[0]}", b"sdl"),
        ("share/termin/fonts/DroidSans.ttf", b"font"),
        ("share/termin/builtin_shaders/catalog.json", b"{}"),
        ("share/termin/shaders/vulkan/example.vert.spv", b"spirv"),
        ("share/licenses/SDL2/LICENSE.txt", b"SDL license"),
    ):
        path = sdk_prefix / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()

    wheel = build_resource_wheel(
        sdk_prefix=sdk_prefix,
        wheel_dir=wheel_dir,
        requirements=[("tgfx", "0.1.0"), ("tcplot", "0.2.0")],
    )

    artifact = inspect_wheel(wheel)
    assert artifact.name == "termin-graphics-profile"
    assert artifact.abi_tags == frozenset({"cp314t"})
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata = archive.read(
            next(name for name in names if name.endswith(".dist-info/METADATA"))
        ).decode("utf-8")
        assert "termin_graphics_profile/lib/libtermin_graphics.so.0" in names
        assert (
            f"termin_graphics_profile/lib/{LINUX_BUNDLED_RUNTIME_LIBRARIES[0]}"
            in names
        )
        assert not any(name.startswith("termin_graphics_profile/bin/") for name in names)
        assert not any("/libslang" in name for name in names)
        assert "termin_graphics_profile/share/termin/fonts/DroidSans.ttf" in names
        assert "termin_graphics_profile/share/termin/shaders/vulkan/example.vert.spv" in names
        assert "termin_graphics_profile/native-libraries.json" in names
        assert any(name.endswith(".dist-info/licenses/SDL2/LICENSE.txt") for name in names)
        module = archive.read("termin_graphics_profile/__init__.py").decode("utf-8")
        assert "TERMIN_BUILTIN_SHADER_ROOT" in module
        assert "TERMIN_SHADER_ARTIFACT_ROOT" in module
        assert 'TERMIN_SHADER_DEV_COMPILE", "0"' in module
        assert "Requires-Dist: tcplot==0.2.0" in metadata
        assert "Requires-Dist: tgfx==0.1.0" in metadata
        assert "License-File: licenses/SDL2/LICENSE.txt" in metadata


def test_graphics_python_product_cannot_disable_window_support(tmp_path: Path) -> None:
    with pytest.raises(GraphicsPythonProductError, match="always includes window support"):
        build_product(tmp_path, ["--no-sdl"])
