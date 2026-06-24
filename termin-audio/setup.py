#!/usr/bin/env python3

from setuptools import setup


setup(
    name="termin-audio",
    version="0.1.0",
    license="MIT",
    description="Audio runtime and asset integration for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=[
        "termin.audio",
        "termin.audio.components",
        "termin_audio_component_specs",
    ],
    package_dir={
        "termin.audio": "python/termin/audio",
        "termin.audio.components": "python/termin/audio/components",
        "termin_audio_component_specs": "python/termin_audio_component_specs",
    },
    install_requires=[
        "numpy",
        "tcbase",
    ],
    zip_safe=False,
)
