from __future__ import annotations

from pathlib import Path

from termin_build.package_manifest import PackageEntry, local_dependency_order_errors


def package(path: str, distribution: str) -> PackageEntry:
    return PackageEntry(
        path=path,
        distribution=distribution,
        features=(),
        native_extensions=(),
    )


def test_local_dependencies_must_precede_their_consumers(tmp_path: Path) -> None:
    dependency = tmp_path / "dependency"
    consumer = tmp_path / "consumer"
    dependency.mkdir()
    consumer.mkdir()
    dependency.joinpath("setup.py").write_text(
        "from setuptools import setup\nsetup(name='termin-mcp')\n",
        encoding="utf-8",
    )
    consumer.joinpath("setup.py").write_text(
        "from setuptools import setup\n"
        "setup(name='graphics-adapter', install_requires=['termin_mcp>=1'])\n",
        encoding="utf-8",
    )
    dependency_entry = package("dependency", "termin-mcp")
    consumer_entry = package("consumer", "graphics-adapter")

    assert local_dependency_order_errors(
        tmp_path, [consumer_entry, dependency_entry]
    ) == [
        "consumer: local dependency 'termin-mcp' must appear earlier in "
        "build-system/packages.json"
    ]
    assert not local_dependency_order_errors(
        tmp_path, [dependency_entry, consumer_entry]
    )
