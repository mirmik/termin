"""
Entity and Component system with C++ backend.

Both C++ and Python components are supported:
- C++ components use REGISTER_COMPONENT macro
- Python components inherit from Component (auto-registered)
"""

from __future__ import annotations

from termin.entity._entity_native import (
    Entity as _NativeEntity,
    Component as _NativeComponent,
    ComponentRegistry,
    EntityRegistry,
    CXXRotatorComponent,
)


class Component(_NativeComponent):
    """
    Base class for Python components.

    Subclasses are automatically registered with ComponentRegistry.
    Override type_name(), start(), update(dt), on_destroy() as needed.
    """

    def __init_subclass__(cls, **kwargs):
        """Auto-register subclass with ComponentRegistry."""
        super().__init_subclass__(**kwargs)

        # Skip abstract classes (those with abstract methods)
        if getattr(cls, '__abstractmethods__', None):
            return

        # Register with C++ ComponentRegistry
        ComponentRegistry.instance().register_python(cls.__name__, cls)

    def type_name(self) -> str:
        """Return component type name for serialization."""
        return self.__class__.__name__


class Entity(_NativeEntity):
    """
    Entity wrapper with serialization support.

    Provides Python-side serialization that delegates to C++ for core functionality.
    """

    def __init__(self, pose=None, name: str = "entity", uuid: str = "",
                 priority: int = 0, pickable: bool = True, selectable: bool = True,
                 serializable: bool = True, layer: int = 0, flags: int = 0):
        super().__init__(pose, name, uuid)
        self.priority = priority
        self.pickable = pickable
        self.selectable = selectable
        self.serializable = serializable
        self.layer = max(0, min(63, layer))
        self.flags = flags & 0xFFFFFFFFFFFFFFFF

    # Serialization methods stay in Python for now
    def serialize(self) -> dict | None:
        """Serialize entity to dict."""
        if not self.serializable:
            return None

        from termin.geombase import GeneralPose3

        pose = self.transform.local_pose()
        data = {
            "uuid": self.uuid,
            "name": self.name,
            "priority": self.priority,
            "scale": list(pose.scale),
            "visible": self.visible,
            "active": self.active,
            "pickable": self.pickable,
            "selectable": self.selectable,
            "layer": self.layer,
            "flags": self.flags,
            "pose": {
                "position": list(pose.lin),
                "rotation": list(pose.ang),
            },
            "components": [],
            "children": [],
        }

        # Serialize components
        for comp in self.components:
            if hasattr(comp, 'serialize'):
                comp_data = comp.serialize()
                if comp_data is not None:
                    data["components"].append(comp_data)

        # Serialize children
        for child in self.children():
            if hasattr(child, 'serializable') and child.serializable:
                child_data = child.serialize()
                if child_data is not None:
                    data["children"].append(child_data)

        return data

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "Entity":
        """Deserialize entity from dict."""
        import numpy as np
        from termin.geombase import GeneralPose3

        ent = cls(
            pose=GeneralPose3(
                lin=np.array(data["pose"]["position"]),
                ang=np.array(data["pose"]["rotation"]),
                scale=np.array(data.get("scale", [1.0, 1.0, 1.0])),
            ),
            name=data["name"],
            priority=data.get("priority", 0),
            pickable=data.get("pickable", True),
            selectable=data.get("selectable", True),
            layer=data.get("layer", 0),
            flags=data.get("flags", 0),
            uuid=data.get("uuid", ""),
        )

        ent.visible = data.get("visible", True)
        ent.active = data.get("active", True)

        # Deserialize components
        for comp_data in data.get("components", []):
            comp_type = comp_data.get("type")
            if comp_type is None:
                continue

            # Try to create component from registry
            if ComponentRegistry.instance().has(comp_type):
                comp = ComponentRegistry.instance().create(comp_type)
                if hasattr(comp, 'deserialize_data'):
                    comp.deserialize_data(comp_data.get("data", {}), context)
                ent.add_component(comp)

        # Deserialize children
        for child_data in data.get("children", []):
            child_ent = cls.deserialize(child_data, context)
            child_ent.set_parent(ent)

        return ent


__all__ = [
    "Component",
    "Entity",
    "ComponentRegistry",
    "EntityRegistry",
    "RotatorComponent",
]
