# termin.scene - core scene types
from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_scene")

from termin.scene._scene_native import (
    Entity,
    TcScene,
    TcComponentRef,
    Component,
    ComponentRegistry,
    TcComponent,
    GeneralTransform3,
    UnknownComponentStats,
    degrade_components_to_unknown,
    upgrade_unknown_components,
)
from termin.scene.python_component import PythonComponent

__all__ = [
    "Entity",
    "TcScene",
    "TcComponentRef",
    "GeneralTransform3",
    "Component",
    "ComponentRegistry",
    "TcComponent",
    "UnknownComponentStats",
    "degrade_components_to_unknown",
    "upgrade_unknown_components",
    "PythonComponent",
]
