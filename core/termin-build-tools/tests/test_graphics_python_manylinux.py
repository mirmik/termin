from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build.graphics_python_manylinux import (
    DOCKERFILE_RELATIVE_PATH,
    LAVAPIPE_REQUIREMENTS_RELATIVE_PATH,
    LOCK_RELATIVE_PATH,
    SLANG_PATCH_RELATIVE_PATH,
    SLANG_VERSION_SCRIPT_RELATIVE_PATH,
    GraphicsPythonManylinuxError,
    ManylinuxLock,
    _is_auditwheel_alias,
    _verify_dockerfile,
    MANYLINUX_PRODUCT_SCHEMA,
)
from termin_build.graphics_python_product import PRODUCT_DISTRIBUTION, RESOURCE_DISTRIBUTION


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_public_manylinux_product_contract_is_monolithic_dual_abi() -> None:
    assert MANYLINUX_PRODUCT_SCHEMA == 4
    assert PRODUCT_DISTRIBUTION == "termin-graphics"
    assert RESOURCE_DISTRIBUTION == "termin-graphics-profile"


def test_repository_manylinux_lock_pins_image_tools_and_both_abis() -> None:
    lock = ManylinuxLock.load(REPO_ROOT / LOCK_RELATIVE_PATH)

    assert lock.policy == "manylinux_2_28_x86_64"
    assert lock.base_image.endswith(
        "@sha256:0bf9db09181f36be8cf0628332abb5d31855b7d0f372faa776f492ccd9d3100d"
    )
    assert lock.auditwheel_version == "6.8.1"
    assert lock.software_vulkan == {
        "implementation": "Mesa lavapipe",
        "version": "24.3.4",
        "source_url": "https://archive.mesa3d.org/mesa-24.3.4.tar.xz",
        "source_sha256": (
            "e641ae27191d387599219694560d221b7feaa91c900bcec46bf444218ed66025"
        ),
        "icd_manifest": (
            "/opt/termin-lavapipe/share/vulkan/icd.d/lvp_icd.x86_64.json"
        ),
    }
    assert set(lock.python_interpreters) == {"cp314", "cp314t"}
    assert lock.python_interpreters["cp314"][0] == Path(
        "/opt/python/cp314-cp314/bin/python"
    )
    assert lock.python_interpreters["cp314t"][0] == Path(
        "/opt/python/cp314-cp314t/bin/python"
    )
    dockerfile = _verify_dockerfile(REPO_ROOT, lock)
    assert dockerfile == REPO_ROOT / DOCKERFILE_RELATIVE_PATH
    assert (REPO_ROOT / SLANG_PATCH_RELATIVE_PATH).is_file()
    assert (REPO_ROOT / SLANG_VERSION_SCRIPT_RELATIVE_PATH).is_file()
    requirements = REPO_ROOT / LAVAPIPE_REQUIREMENTS_RELATIVE_PATH
    assert "--hash=sha256:" in requirements.read_text(encoding="utf-8")
    pinned_license_sources = {
        license_entry.name: license_entry
        for license_entry in lock.release_licenses
        if license_entry.source_url is not None
    }
    assert set(pinned_license_sources) == {"libglvnd", "libXau", "libxcb"}


@pytest.mark.parametrize(
    ("soname", "candidate", "expected"),
    [
        ("libtermin_base.so", "libtermin_base-deadbeef.so", True),
        ("libSDL2-2.0.so.0", "libSDL2-2.0-deadbeef.so.0", True),
        ("libtermin_base.so", "libtermin_base.so", True),
        ("libtermin_base.so", "libtermin_inspect-deadbeef.so", False),
        ("LICENSE", "LICENSE", True),
    ],
)
def test_auditwheel_alias_detection(
    soname: str, candidate: str, expected: bool
) -> None:
    assert _is_auditwheel_alias(soname, candidate) is expected


def test_manylinux_lock_rejects_mutable_image_tag(tmp_path: Path) -> None:
    value = json.loads((REPO_ROOT / LOCK_RELATIVE_PATH).read_text(encoding="utf-8"))
    value["base_image"] = "quay.io/pypa/manylinux_2_28_x86_64:latest"
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(GraphicsPythonManylinuxError, match="digest-pinned"):
        ManylinuxLock.load(path)
