"""Entity and Component system (thin pip facade over SDK-built _entity_native)."""

from termin_nanobind.runtime import preload_sdk_libs

# _entity_native links against entity_lib which transitively pulls many libs.
# Preloading entity_lib forces the whole chain to resolve via SDK RPATH.
preload_sdk_libs("entity_lib")

from termin.entity._entity_native import (
    Entity,
    Component,
    ComponentRegistry,
    EntityRegistry,
    TcComponentRef,
    TcScene,
)

# Alias kept for backward compatibility with earlier termin releases.
TcSceneRef = TcScene

__all__ = [
    "Component",
    "Entity",
    "ComponentRegistry",
    "EntityRegistry",
    "TcComponentRef",
    "TcScene",
    "TcSceneRef",
]
