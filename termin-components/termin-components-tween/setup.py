#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-components-tween",
    version="0.1.0",
    license="MIT",
    description="Tween manager scene component for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=["termin.tween_components", "termin_tween_component_specs"],
    package_dir={
        "termin.tween_components": "python/termin/tween_components",
        "termin_tween_component_specs": "python/termin_tween_component_specs",
    },
    install_requires=[
        "numpy",
        "termin-scene",
        "termin-tween",
    ],
    zip_safe=False,
)
