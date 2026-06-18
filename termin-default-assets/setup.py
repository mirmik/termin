#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-default-assets",
    version="0.1.0",
    license="MIT",
    description="Default Termin asset adapters and import plugins",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=find_namespace_packages(where="python", include=["termin.default_assets", "termin.default_assets.*"]),
    package_dir={"": "python"},
    install_requires=[
        "termin-assets",
        "tmesh",
        "numpy",
    ],
    entry_points={
        "termin.asset_import_plugins": [
            "mesh = termin.default_assets.mesh.asset_plugin:create_import_plugin",
        ],
        "termin.asset_runtime_plugins": [
            "mesh = termin.default_assets.mesh.asset_plugin:create_runtime_plugin",
        ],
    },
    zip_safe=False,
)
