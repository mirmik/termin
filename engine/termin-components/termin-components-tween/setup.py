#!/usr/bin/env python3

from setuptools import setup
from termin_build.versioning import public_version


setup(
    name="termin-components-tween",
    version=public_version(),
    license="Apache-2.0",
    description="Tween manager scene component for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.tween_components", "termin_tween_component_specs"],
    package_dir={
        "termin.tween_components": "python/termin/tween_components",
        "termin_tween_component_specs": "python/termin_tween_component_specs",
    },
    install_requires=[
        "termin-scene",
        "termin-tween",
    ],
    zip_safe=False,
)
