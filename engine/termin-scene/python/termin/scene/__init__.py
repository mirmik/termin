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
    TransformKind,
    UnknownComponentStats,
    degrade_components_to_unknown,
    upgrade_unknown_components,
)
from termin.scene.python_component import (
    FIXED_UPDATE_PRIORITY_CONTROL,
    FIXED_UPDATE_PRIORITY_PHYSICS,
    FIXED_UPDATE_PRIORITY_POST_PHYSICS,
    LIFECYCLE_PRIORITY_DEFAULT,
    LIFECYCLE_PRIORITY_EARLY,
    LIFECYCLE_PRIORITY_LATE,
    PythonComponent,
    publish_python_component,
    publish_python_component_owner,
    publish_python_components,
    shutdown_python_components,
)

__all__ = [
    "Entity",
    "TcScene",
    "TcComponentRef",
    "GeneralTransform3",
    "TransformKind",
    "Component",
    "ComponentRegistry",
    "TcComponent",
    "UnknownComponentStats",
    "degrade_components_to_unknown",
    "upgrade_unknown_components",
    "PythonComponent",
    "FIXED_UPDATE_PRIORITY_CONTROL",
    "FIXED_UPDATE_PRIORITY_PHYSICS",
    "FIXED_UPDATE_PRIORITY_POST_PHYSICS",
    "LIFECYCLE_PRIORITY_EARLY",
    "LIFECYCLE_PRIORITY_DEFAULT",
    "LIFECYCLE_PRIORITY_LATE",
    "publish_python_component",
    "publish_python_component_owner",
    "publish_python_components",
    "shutdown_python_components",
]
