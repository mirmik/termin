from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from termin_build import artifact_manifest
from termin_build import graphics_python_product as product_module
from termin_build.graphics_python_product import (
    GraphicsPythonProductError,
    LINUX_BUNDLED_RUNTIME_LIBRARIES,
    SUPPORTED_PYTHON_ABIS,
    _merge_variant_wheels,
    _parse_product_build_args,
    build_product,
    build_resource_wheel,
    compose_product_wheel,
)
from termin_build.python_abi import PythonAbiIdentity
from termin_build.wheelhouse import inspect_wheel


def _write_manifest(sdk_prefix: Path, *, free_threaded: bool = True) -> None:
    abi = PythonAbiIdentity(
        version="3.14",
        soabi=(
            "cpython-314t-x86_64-linux-gnu"
            if free_threaded
            else "cpython-314-x86_64-linux-gnu"
        ),
        free_threaded=free_threaded,
        py_gil_disabled=free_threaded,
    )
    artifacts = [
        {
            "extension": "termin.graphics._fake",
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


def _write_shader_compiler(sdk_prefix: Path) -> None:
    shaderc = sdk_prefix / "bin" / "termin_shaderc"
    shaderc.parent.mkdir(parents=True, exist_ok=True)
    shaderc.write_bytes(b"shaderc")
    shaderc.chmod(0o755)


@pytest.mark.parametrize(
    ("free_threaded", "expected_abi"),
    [(False, "cp314"), (True, "cp314t")],
)
def test_resource_wheel_owns_precompiled_assets_and_shader_compiler(
    tmp_path: Path,
    free_threaded: bool,
    expected_abi: str,
) -> None:
    sdk_prefix = tmp_path / "native-prefix"
    _write_manifest(sdk_prefix, free_threaded=free_threaded)
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
    _write_shader_compiler(sdk_prefix)

    wheel = build_resource_wheel(
        sdk_prefix=sdk_prefix,
        wheel_dir=wheel_dir,
        requirements=[("numpy", "2.0"), ("PyYAML", "6.0")],
    )

    artifact = inspect_wheel(wheel)
    assert artifact.name == product_module.RESOURCE_DISTRIBUTION
    assert artifact.version == product_module.PRODUCT_VERSION
    assert artifact.abi_tags == frozenset({expected_abi})
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
        assert "termin_graphics_profile/bin/termin_shaderc" in names
        assert "termin_graphics_profile/bin/slangc" not in names
        assert not any("/libslang" in name for name in names)
        assert not any("libstdc++-slang-compat" in name for name in names)
        assert "termin_graphics_profile/share/termin/fonts/DroidSans.ttf" in names
        assert "termin_graphics_profile/share/termin/shaders/vulkan/example.vert.spv" in names
        assert "termin_graphics_profile/native-libraries.json" in names
        native_libraries = json.loads(
            archive.read("termin_graphics_profile/native-libraries.json")
        )
        assert not any(name.startswith("libslang") for name in native_libraries)
        assert "libstdc++-slang-compat.so.6" not in native_libraries
        assert "termin_graphics_profile/shader-toolchain.json" not in names
        assert any(name.endswith(".dist-info/licenses/SDL2/LICENSE.txt") for name in names)
        assert not any(name.endswith(".dist-info/licenses/Slang/LICENSE") for name in names)
        module = archive.read("termin_graphics_profile/__init__.py").decode("utf-8")
        assert "TERMIN_BUILTIN_SHADER_ROOT" in module
        assert "TERMIN_SHADER_ARTIFACT_ROOT" in module
        assert "def shader_compiler_path() -> Path:" in module
        assert "def slang_compiler_path() -> Path:" not in module
        assert 'TERMIN_SHADERC", str(shader_compiler_path())' in module
        assert "TERMIN_SLANGC" not in module
        assert 'TERMIN_SHADER_DEV_COMPILE", "0"' in module
        assert "Requires-Dist: numpy==2.0" in metadata
        assert "Requires-Dist: PyYAML==6.0" in metadata
        assert "License-File: licenses/SDL2/LICENSE.txt" in metadata
        assert "License-File: licenses/Slang/LICENSE" not in metadata


def _write_split_wheel(
    path: Path,
    distribution: str,
    payloads: dict[str, bytes],
    requires: tuple[str, ...] = ("numpy>=2",),
) -> None:
    stem = distribution.replace("-", "_")
    dist_info = f"{stem}-{product_module.PRODUCT_VERSION}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.4\n"
            f"Name: {distribution}\n"
            f"Version: {product_module.PRODUCT_VERSION}\n"
            "Requires-Python: >=3.14\n"
            + "".join(f"Requires-Dist: {requirement}\n" for requirement in requires)
            + "\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: false\n"
            "Tag: cp314-cp314-manylinux_2_28_x86_64\n",
        )
        for name, payload in payloads.items():
            archive.writestr(name, payload)


def test_compose_product_wheel_merges_payload_and_strips_internal_metadata(
    tmp_path: Path,
) -> None:
    first = tmp_path / "termin_base.whl"
    second = tmp_path / "termin_graphics_core.whl"
    _write_split_wheel(first, "termin-base", {"termin/base.py": b"base"})
    _write_split_wheel(
        second,
        "termin-graphics-core",
        {"termin/graphics.py": b"graphics"},
        requires=("PyYAML>=6",),
    )
    release_license = tmp_path / "LICENSE.txt"
    release_license.write_text("license text\n", encoding="utf-8")

    output = compose_product_wheel(
        [first, second],
        tmp_path / "out",
        abi="cp314",
        platform_tag="manylinux_2_28_x86_64",
        licenses=[("Termin", release_license)],
    )

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "termin/base.py" in names
        assert "termin/graphics.py" in names
        assert not any(
            name.endswith(".dist-info/METADATA") and not name.startswith("termin_graphics-")
            for name in names
        )
        metadata = archive.read(
            f"termin_graphics-{product_module.PRODUCT_VERSION}.dist-info/METADATA"
        ).decode()
        assert "Name: termin-graphics\n" in metadata
        assert "Requires-Dist: numpy>=2\n" in metadata
        assert "Requires-Dist: PyYAML>=6\n" in metadata
        assert "License-File: Termin/LICENSE.txt\n" in metadata
        assert (
            archive.read(
                f"termin_graphics-{product_module.PRODUCT_VERSION}.dist-info/"
                "licenses/Termin/LICENSE.txt"
            )
            == b"license text\n"
        )


def test_compose_product_wheel_rejects_conflicting_payload_collision(tmp_path: Path) -> None:
    first = tmp_path / "first.whl"
    second = tmp_path / "second.whl"
    _write_split_wheel(first, "termin-base", {"termin/shared.py": b"one"})
    _write_split_wheel(second, "termin-graphics-core", {"termin/shared.py": b"two"})

    with pytest.raises(GraphicsPythonProductError, match="payload collision"):
        compose_product_wheel(
            [first, second], tmp_path / "out", abi="cp314", platform_tag="manylinux_2_28_x86_64"
        )


def test_graphics_python_product_cannot_disable_window_support(tmp_path: Path) -> None:
    with pytest.raises(GraphicsPythonProductError, match="always includes window support"):
        build_product(tmp_path, ["--no-sdl"])


def test_graphics_python_product_defaults_to_dual_abi_matrix() -> None:
    variants, forwarded = _parse_product_build_args(["--debug", "--no-unity"])

    assert variants == SUPPORTED_PYTHON_ABIS == ("cp314", "cp314t")
    assert forwarded == ["--debug", "--no-unity"]


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--python-abi", "cp314", "--debug"], "cp314"),
        (["--python-abi=cp314t", "--no-unity"], "cp314t"),
    ],
)
def test_graphics_python_product_supports_focused_abi_build(
    arguments: list[str],
    expected: str,
) -> None:
    variants, forwarded = _parse_product_build_args(arguments)

    assert variants == (expected,)
    assert all(not argument.startswith("--python-abi") for argument in forwarded)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--python-abi"],
        ["--python-abi=cp313"],
        ["--python-abi=cp314", "--python-abi=cp314t"],
    ],
)
def test_graphics_python_product_rejects_invalid_abi_selection(
    arguments: list[str],
) -> None:
    with pytest.raises(GraphicsPythonProductError, match="python-abi|Python ABI"):
        _parse_product_build_args(arguments)


def test_merge_variant_wheels_deduplicates_identical_pure_wheel_bytes(
    tmp_path: Path,
) -> None:
    cp314 = tmp_path / "cp314"
    cp314t = tmp_path / "cp314t"
    cp314.mkdir()
    cp314t.mkdir()
    shared = "termin_math-0.1.0-py3-none-any.whl"
    (cp314 / shared).write_bytes(b"same pure wheel")
    (cp314t / shared).write_bytes(b"same pure wheel")
    (cp314 / "termin_graphics-0.1.0-cp314-cp314-linux_x86_64.whl").write_bytes(b"regular")
    (cp314t / "termin_graphics-0.1.0-cp314-cp314t-linux_x86_64.whl").write_bytes(
        b"free-threaded"
    )

    records = _merge_variant_wheels(
        [("cp314", cp314), ("cp314t", cp314t)],
        tmp_path / "aggregate",
    )

    assert len(records) == 3
    shared_record = next(record for record in records if record["filename"] == shared)
    assert shared_record["python_abis"] == ["cp314", "cp314t"]
    assert len(list((tmp_path / "aggregate").glob("*.whl"))) == 3


def test_merge_variant_wheels_rejects_same_filename_with_different_bytes(
    tmp_path: Path,
) -> None:
    cp314 = tmp_path / "cp314"
    cp314t = tmp_path / "cp314t"
    cp314.mkdir()
    cp314t.mkdir()
    wheel = "termin_math-0.1.0-py3-none-any.whl"
    (cp314 / wheel).write_bytes(b"regular-build")
    (cp314t / wheel).write_bytes(b"free-threaded-build")

    with pytest.raises(GraphicsPythonProductError, match="differs between"):
        _merge_variant_wheels(
            [("cp314", cp314), ("cp314t", cp314t)],
            tmp_path / "aggregate",
        )


def test_build_product_uses_isolated_abi_roots_and_verifies_merged_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Profiles:
        @staticmethod
        def profile(name: str) -> object:
            assert name == "graphics"
            return object()

    class NativeManifest:
        def __init__(self, variant: str):
            free_threaded = variant == "cp314t"
            self.python_abi = PythonAbiIdentity(
                version="3.14",
                soabi=(
                    "cpython-314t-x86_64-linux-gnu"
                    if free_threaded
                    else "cpython-314-x86_64-linux-gnu"
                ),
                free_threaded=free_threaded,
                py_gil_disabled=free_threaded,
            )
            self.native_build_id = f"native-{variant}"

        @staticmethod
        def has_extension(extension: str) -> bool:
            return extension in product_module.WINDOW_EXTENSIONS

    prepared: list[tuple[str, Path]] = []
    binding_envs: list[tuple[str, Path, Path]] = []
    verified: list[tuple[Path, Path, Path]] = []

    def prepare_python(
        repo_root: Path,
        *,
        variant: str | None = None,
        environment_root: Path | None = None,
    ) -> Path:
        assert repo_root == tmp_path
        assert variant is not None and environment_root is not None
        prepared.append((variant, environment_root))
        return environment_root / "bin" / "python"

    def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
        assert cwd == tmp_path
        assert env is not None
        variant = env["TERMIN_PYTHON_ABI"]
        binding_envs.append((variant, Path(env["BUILD_DIR"]), Path(env["SDK_PREFIX"])))
        return 0

    def build_wheels(**kwargs: object) -> int:
        wheel_dir = Path(str(kwargs["wheel_dir"]))
        wheel_dir.mkdir(parents=True, exist_ok=True)
        assert kwargs["package_version"] == product_module.PRODUCT_VERSION
        return 0

    def build_resource(**kwargs: object) -> Path:
        sdk_prefix = Path(str(kwargs["sdk_prefix"]))
        wheel_dir = Path(str(kwargs["wheel_dir"]))
        variant = sdk_prefix.parent.name
        wheel = wheel_dir / (
            f"termin_graphics_profile-{product_module.PRODUCT_VERSION}-cp314-"
            f"{variant}-linux_x86_64.whl"
        )
        _write_split_wheel(
            wheel,
            product_module.RESOURCE_DISTRIBUTION,
            {"termin/graphics/__init__.py": variant.encode("ascii")},
        )
        return wheel

    def load_native_manifest(path: Path) -> NativeManifest:
        return NativeManifest(path.parent.parent.name)

    def verify(
        repo_root: Path,
        wheel_dir: Path,
        build_python: Path,
        *,
        external_wheels: Path,
        distribution: str,
    ) -> None:
        assert repo_root == tmp_path
        assert distribution == product_module.PRODUCT_DISTRIBUTION
        assert {path.name for path in wheel_dir.glob("*.whl")} == {
                f"termin_graphics-{product_module.PRODUCT_VERSION}-cp314-cp314-linux_x86_64.whl",
                f"termin_graphics-{product_module.PRODUCT_VERSION}-cp314-cp314t-linux_x86_64.whl",
        }
        verified.append((wheel_dir, build_python, external_wheels))

    monkeypatch.setattr(product_module, "load_sdk_profiles", lambda _root: Profiles())
    monkeypatch.setattr(product_module, "load_manifest", lambda _root: object())
    monkeypatch.setattr(product_module, "select_python_packages", lambda *_a, **_kw: [])
    monkeypatch.setattr(product_module, "prepare_pinned_python_build_environment", prepare_python)
    monkeypatch.setattr(
        product_module,
        "prepare_locked_runtime_wheels",
        lambda _root, _python, *, wheel_dir: wheel_dir,
    )
    monkeypatch.setattr(
        product_module,
        "prepare_slang_toolchain",
        lambda *_a, **_kw: tmp_path / "slangc",
    )
    monkeypatch.setattr(product_module, "_run", run)
    monkeypatch.setattr(product_module, "_resolve_bindings_dir", lambda _r, build: build)
    monkeypatch.setattr(product_module, "build_local_wheel_artifact_set", build_wheels)
    monkeypatch.setattr(product_module, "build_resource_wheel", build_resource)
    monkeypatch.setattr(product_module, "write_local_wheel_manifest", lambda *_a, **_kw: None)
    monkeypatch.setattr(product_module, "validate_local_wheel_artifact_set", lambda *_a, **_kw: {})
    monkeypatch.setattr(
        product_module.ArtifactManifest,
        "load",
        staticmethod(load_native_manifest),
    )
    monkeypatch.setattr(product_module, "verify_product", verify)

    assert build_product(tmp_path, []) == 0

    assert [variant for variant, _root in prepared] == ["cp314", "cp314t"]
    assert [variant for variant, _build, _sdk in binding_envs] == ["cp314", "cp314t"]
    assert all(build.parent.name == variant for variant, build, _sdk in binding_envs)
    assert all(sdk.parent.name == variant for variant, _build, sdk in binding_envs)
    assert len(verified) == 2
    assert verified[0][0] == verified[1][0]
    assert verified[0][1].parents[2].name == "cp314"
    assert verified[1][1].parents[2].name == "cp314t"
    manifest = json.loads(
        (tmp_path / "dist" / "graphics-python" / product_module.PRODUCT_MANIFEST).read_text(
            encoding="utf-8"
        )
    )
    assert manifest["schema"] == 3
    assert manifest["version"] == product_module.PRODUCT_VERSION
    assert manifest["python_abi_variants"] == ["cp314", "cp314t"]
    assert [entry["id"] for entry in manifest["variants"]] == ["cp314", "cp314t"]
    assert {entry["native_build_id"] for entry in manifest["variants"]} == {
        "native-cp314",
        "native-cp314t",
    }
    assert [entry["wheel_count"] for entry in manifest["variants"]] == [1, 1]
    assert all("wheel" in entry and "resource_wheel" not in entry for entry in manifest["variants"])
    assert manifest["wheel_count"] == 2
