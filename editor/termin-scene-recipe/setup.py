#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup
from termin_build.versioning import public_version


setup(
    name="termin-scene-recipe",
    version=public_version(),
    license="Apache-2.0",
    description="Scene recipe synchronization and generation tools for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(
        where="python",
        include=["termin.scene_recipe", "termin.scene_recipe.*"],
    ),
    package_dir={"": "python"},
    install_requires=["termin-mcp"],
    entry_points={
        "console_scripts": [
            "termin-scene-recipe=termin.scene_recipe.cli:main",
        ],
    },
    zip_safe=False,
)
