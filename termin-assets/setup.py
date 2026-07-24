#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-assets",
    version="0.1.0",
    license="MIT",
    description="Shared asset-system contracts for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin_assets"],
    install_requires=["tcbase", "watchdog"],
    zip_safe=False,
)
