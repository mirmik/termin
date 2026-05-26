"""Foliage component package."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_components_foliage")

from termin.foliage._foliage_native import (
    FoliageInstance,
    FoliageLayerComponent,
    TcFoliageData,
)

from termin.foliage.asset_plugin import (
    FoliageDataImportPlugin,
    build_foliage_meta,
    register_foliage_data_import_plugin,
)

__all__ = [
    "FoliageDataImportPlugin",
    "FoliageInstance",
    "FoliageLayerComponent",
    "TcFoliageData",
    "build_foliage_meta",
    "register_foliage_data_import_plugin",
]
