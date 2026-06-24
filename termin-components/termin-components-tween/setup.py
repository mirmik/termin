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
    py_modules=["termin.tween.component"],
    packages=["termin_tween_component_specs"],
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "termin-scene",
        "termin-tween",
    ],
    zip_safe=False,
)
