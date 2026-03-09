# termin.scene - core scene types
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
from termin.scene.python_component import PythonComponent, InputComponent

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
    "InputComponent",
]
