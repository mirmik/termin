#!/usr/bin/env python3

from setuptools import setup
from termin_build.versioning import public_version


setup(
    name="termin-assets",
    version=public_version(),
    license="Apache-2.0",
    description="Shared asset-system contracts for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin_assets"],
    install_requires=["termin-base", "watchdog"],
    zip_safe=False,
)
