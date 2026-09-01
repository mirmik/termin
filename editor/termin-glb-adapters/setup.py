#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup
from termin_build.versioning import public_version


setup(
    name="termin-glb-adapters",
    version=public_version(),
    license="Apache-2.0",
    description="Termin asset, Entity and scene adapters for portable GLB data",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(
        where="python",
        include=["termin.glb_adapters", "termin.glb_adapters.*"],
    ),
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "termin-base",
        "termin-graphics-core",
        "termin-mesh",
        "termin-animation",
        "termin-assets",
        "termin-components-animation",
        "termin-components-render",
        "termin-components-skeleton",
        "termin-default-assets",
        "termin-glb",
        "termin-image",
        "termin-materials",
        "termin-scene",
        "termin-skeleton",
    ],
    entry_points={
        "termin.asset_import_plugins": [
            "glb = termin.glb_adapters.asset_plugin:create_import_plugin",
        ],
        "termin.asset_runtime_plugins": [
            "glb = termin.glb_adapters.asset_plugin:create_runtime_plugin",
        ],
    },
    zip_safe=False,
)
