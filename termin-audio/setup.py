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
    ],
    package_dir={
        "termin.audio": "python/termin/audio",
        "termin.audio.components": "python/termin/audio/components",
    },
    install_requires=[
        "numpy",
        "tcbase",
        "termin-assets",
    ],
    entry_points={
        "termin.asset_import_plugins": [
            "audio_clip = termin.audio.asset_plugin:create_import_plugin",
        ],
        "termin.asset_runtime_plugins": [
            "audio_clip = termin.audio.asset_plugin:create_runtime_plugin",
        ],
    },
    zip_safe=False,
)
