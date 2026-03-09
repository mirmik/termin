#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="tcgui",
    version="0.1.0",
    license="MIT",
    description="Widget-based UI framework for termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=find_packages(where="python"),
    package_dir={"": "python"},
    install_requires=[
        "tcbase",
        "tgfx",
        "numpy",
        "Pillow",
        "PyYAML",
    ],
    zip_safe=False,
)
