#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-prefab",
    version="0.1.0",
    license="MIT",
    description="Prefab runtime and asset integration for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=find_namespace_packages(where="python", include=["termin.prefab", "termin.prefab.*"]),
    package_dir={"": "python"},
    install_requires=[
        "termin-assets",
        "termin-inspect",
        "termin-scene",
        "tcbase",
        "numpy",
    ],
    entry_points={
        "termin.asset_import_plugins": [
            "prefab = termin.prefab.asset_plugin:create_import_plugin",
        ],
        "termin.asset_runtime_plugins": [
            "prefab = termin.prefab.asset_plugin:create_runtime_plugin",
        ],
    },
    zip_safe=False,
)
