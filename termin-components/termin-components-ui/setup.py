#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-components-ui",
    version="0.1.0",
    license="MIT",
    description="Widget UI scene components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=["termin.ui_components", "termin_ui_component_specs"],
    package_dir={
        "termin.ui_components": "python/termin/ui_components",
        "termin_ui_component_specs": "python/termin_ui_component_specs",
    },
    install_requires=[
        "tcbase",
        "tcgui",
        "tgfx",
        "termin-input",
        "termin-inspect",
    ],
    zip_safe=False,
)
