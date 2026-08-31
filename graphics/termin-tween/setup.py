#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-tween",
    version="0.1.0",
    license="Apache-2.0",
    description="Tweening primitives and manager for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.tween"],
    package_dir={"termin.tween": "python/termin/tween"},
    install_requires=["tcbase"],
    zip_safe=False,
)
