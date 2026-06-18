#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup


setup(
    name="termin-default-assets",
    version="0.1.0",
    license="MIT",
    description="Default Termin asset adapters and import plugins",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=find_namespace_packages(where="python", include=["termin.default_assets", "termin.default_assets.*"]),
    package_dir={"": "python"},
    install_requires=[
        "termin-assets",
        "termin-audio",
        "termin-navmesh",
        "termin-render",
        "termin-voxels",
        "tcgui",
        "tmesh",
        "numpy",
    ],
    entry_points={
        "termin.asset_import_plugins": [
            "audio_clip = termin.default_assets.audio.asset_plugin:create_import_plugin",
            "glsl = termin.default_assets.render.glsl_plugin:create_import_plugin",
            "material = termin.default_assets.render.material_plugin:create_import_plugin",
            "mesh = termin.default_assets.mesh.asset_plugin:create_import_plugin",
            "navmesh = termin.default_assets.navmesh.asset_plugin:create_import_plugin",
            "pipeline = termin.default_assets.render.pipeline_plugin:create_import_plugin",
            "prefab = termin.default_assets.prefab.asset_plugin:create_import_plugin",
            "scene_pipeline = termin.default_assets.render.scene_pipeline_plugin:create_import_plugin",
            "shader = termin.default_assets.render.shader_plugin:create_import_plugin",
            "texture = termin.default_assets.render.texture_plugin:create_import_plugin",
            "ui = termin.default_assets.ui.asset_plugin:create_import_plugin",
            "voxel_grid = termin.default_assets.voxels.asset_plugin:create_import_plugin",
        ],
        "termin.asset_runtime_plugins": [
            "audio_clip = termin.default_assets.audio.asset_plugin:create_runtime_plugin",
            "glsl = termin.default_assets.render.glsl_plugin:create_runtime_plugin",
            "material = termin.default_assets.render.material_plugin:create_runtime_plugin",
            "mesh = termin.default_assets.mesh.asset_plugin:create_runtime_plugin",
            "navmesh = termin.default_assets.navmesh.asset_plugin:create_runtime_plugin",
            "pipeline = termin.default_assets.render.pipeline_plugin:create_runtime_plugin",
            "prefab = termin.default_assets.prefab.asset_plugin:create_runtime_plugin",
            "scene_pipeline = termin.default_assets.render.scene_pipeline_plugin:create_runtime_plugin",
            "shader = termin.default_assets.render.shader_plugin:create_runtime_plugin",
            "texture = termin.default_assets.render.texture_plugin:create_runtime_plugin",
            "ui = termin.default_assets.ui.asset_plugin:create_runtime_plugin",
            "voxel_grid = termin.default_assets.voxels.asset_plugin:create_runtime_plugin",
        ],
    },
    zip_safe=False,
)
