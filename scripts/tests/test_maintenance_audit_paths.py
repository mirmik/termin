import importlib.util
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_webgpu_audit():
    script_path = REPO_ROOT / "scripts" / "audit_webgpu_shaders.py"
    spec = importlib.util.spec_from_file_location(
        "audit_webgpu_shaders_under_test", script_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_webgpu_audit_default_catalog_uses_graphics_district() -> None:
    audit = _load_webgpu_audit()

    assert audit.DEFAULT_CATALOG == (
        REPO_ROOT
        / "graphics"
        / "termin-graphics"
        / "resources"
        / "builtin_shaders"
        / "engine-shader-catalog.json"
    )
    assert audit.DEFAULT_CATALOG.is_file()


def test_duplication_audit_defaults_cover_district_manifest() -> None:
    manifest = json.loads(
        (REPO_ROOT / "build-system" / "districts.json").read_text(encoding="utf-8")
    )
    expected = {
        str(Path(district["root"]) / package)
        for district in manifest["districts"]
        for package in district["packages"]
    }

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "maintenance" / "duplication-check.sh"),
            "--list-default-targets",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    actual = set(result.stdout.splitlines())

    assert expected <= actual
    assert "termin-csharp" in actual
    assert all((REPO_ROOT / target).is_dir() for target in actual)
