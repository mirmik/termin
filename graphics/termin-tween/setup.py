#!/usr/bin/env python3

from setuptools import setup
from termin_build.versioning import public_version


setup(
    name="termin-tween",
    version=public_version(),
    license="Apache-2.0",
    description="Tweening primitives and manager for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.tween"],
    package_dir={"termin.tween": "python/termin/tween"},
    install_requires=["termin-base"],
    zip_safe=False,
)
