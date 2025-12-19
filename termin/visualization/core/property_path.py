"""
PropertyPath — utility for addressing properties within Entity hierarchy.

Used by prefab override system to track which properties are overridden.
"""

from __future__ import annotations

from typing import Any, Iterator, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.component import Component


class PropertyPath:
    """
    Utility for addressing properties within Entity hierarchy.

    Path formats:
        "name"                                  # Entity.name
        "visible"                               # Entity.visible
        "transform.position"                    # Transform position (lin)
        "transform.rotation"                    # Transform rotation (ang)
        "transform.scale"                       # Transform scale
        "components/MeshRenderer/material"      # Component by type
        "components/MeshRenderer/cast_shadow"   # Component field
        "components/0/enabled"                  # Component by index
        "children/0/name"                       # Child entity by index
        "children/ChildName/transform.position" # Child entity by name
    """

    # Entity properties that can be overridden
    ENTITY_PROPS = frozenset({
        "name", "visible", "active", "pickable", "selectable",
        "layer", "flags", "priority",
    })

    # Transform properties
    TRANSFORM_PROPS = frozenset({"position", "rotation", "scale"})

    @classmethod
    def get(cls, entity: "Entity", path: str) -> Any:
        """
        Get value at path.

        Args:
            entity: Root entity
            path: Property path

        Returns:
            Value at path

        Raises:
            KeyError: If path doesn't exist
        """
        parts = path.split("/")
        return cls._get_recursive(entity, parts)

    @classmethod
    def _get_recursive(cls, entity: "Entity", parts: list[str]) -> Any:
        """Recursive get implementation."""
        if not parts:
            raise KeyError("Empty path")

        part = parts[0]
        remaining = parts[1:]

        # Entity properties
        if part in cls.ENTITY_PROPS:
            if remaining:
                raise KeyError(f"Entity property '{part}' has no sub-properties")
            return getattr(entity, part)

        # Transform properties
        if part == "transform":
            return cls._get_transform(entity, remaining)

        # Components
        if part == "components":
            return cls._get_component(entity, remaining)

        # Children
        if part == "children":
            return cls._get_child(entity, remaining)

        raise KeyError(f"Unknown path segment: '{part}'")

    @classmethod
    def _get_transform(cls, entity: "Entity", parts: list[str]) -> Any:
        """Get transform property."""
        if not parts:
            raise KeyError("Transform path requires sub-property")

        prop = parts[0]
        if parts[1:]:
            raise KeyError(f"Transform property '{prop}' has no sub-properties")

        pose = entity.transform.local_pose()

        if prop == "position":
            return pose.lin.copy()
        elif prop == "rotation":
            return pose.ang.copy()
        elif prop == "scale":
            return pose.scale.copy()
        else:
            raise KeyError(f"Unknown transform property: '{prop}'")

    @classmethod
    def _get_component(cls, entity: "Entity", parts: list[str]) -> Any:
        """Get component or component property."""
        if not parts:
            raise KeyError("Component path requires component identifier")

        comp_id = parts[0]
        remaining = parts[1:]

        # Find component by type name or index
        component = cls._find_component(entity, comp_id)
        if component is None:
            raise KeyError(f"Component not found: '{comp_id}'")

        if not remaining:
            return component

        # Get component property
        prop_path = ".".join(remaining)
        return cls._get_component_property(component, prop_path)

    @classmethod
    def _find_component(cls, entity: "Entity", comp_id: str) -> "Component | None":
        """Find component by type name or index."""
        # Try as index
        try:
            idx = int(comp_id)
            if 0 <= idx < len(entity.components):
                return entity.components[idx]
            return None
        except ValueError:
            pass

        # Try as type name
        for comp in entity.components:
            if comp.__class__.__name__ == comp_id:
                return comp

        return None

    @classmethod
    def _get_component_property(cls, component: "Component", prop_path: str) -> Any:
        """Get property from component using inspect_fields or direct access."""
        # Collect inspect_fields from class hierarchy
        inspect_fields = {}
        for klass in reversed(type(component).__mro__):
            if hasattr(klass, "inspect_fields") and klass.inspect_fields:
                inspect_fields.update(klass.inspect_fields)

        # Check if it's an inspect_field
        if prop_path in inspect_fields:
            field = inspect_fields[prop_path]
            return field.get_value(component)

        # Try direct attribute access for dotted paths
        parts = prop_path.split(".")
        obj = component
        for part in parts:
            obj = getattr(obj, part)
        return obj

    @classmethod
    def _get_child(cls, entity: "Entity", parts: list[str]) -> Any:
        """Get child entity or child property."""
        if not parts:
            raise KeyError("Child path requires child identifier")

        child_id = parts[0]
        remaining = parts[1:]

        child = cls._find_child(entity, child_id)
        if child is None:
            raise KeyError(f"Child not found: '{child_id}'")

        if not remaining:
            return child

        # Recurse into child
        return cls._get_recursive(child, remaining)

    @classmethod
    def _find_child(cls, entity: "Entity", child_id: str) -> "Entity | None":
        """Find child entity by name or index."""
        children = [t.entity for t in entity.transform.children if t.entity is not None]

        # Try as index
        try:
            idx = int(child_id)
            if 0 <= idx < len(children):
                return children[idx]
            return None
        except ValueError:
            pass

        # Try as name
        for child in children:
            if child.name == child_id:
                return child

        return None

    @classmethod
    def set(cls, entity: "Entity", path: str, value: Any) -> bool:
        """
        Set value at path.

        Args:
            entity: Root entity
            path: Property path
            value: Value to set

        Returns:
            True if successful, False if path doesn't exist
        """
        try:
            parts = path.split("/")
            cls._set_recursive(entity, parts, value)
            return True
        except (KeyError, AttributeError):
            return False

    @classmethod
    def _set_recursive(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        """Recursive set implementation."""
        if not parts:
            raise KeyError("Empty path")

        part = parts[0]
        remaining = parts[1:]

        # Entity properties
        if part in cls.ENTITY_PROPS:
            if remaining:
                raise KeyError(f"Entity property '{part}' has no sub-properties")
            setattr(entity, part, value)
            return

        # Transform properties
        if part == "transform":
            cls._set_transform(entity, remaining, value)
            return

        # Components
        if part == "components":
            cls._set_component(entity, remaining, value)
            return

        # Children
        if part == "children":
            cls._set_child(entity, remaining, value)
            return

        raise KeyError(f"Unknown path segment: '{part}'")

    @classmethod
    def _set_transform(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        """Set transform property."""
        if not parts:
            raise KeyError("Transform path requires sub-property")

        prop = parts[0]
        if parts[1:]:
            raise KeyError(f"Transform property '{prop}' has no sub-properties")

        pose = entity.transform.local_pose()
        value_array = np.asarray(value, dtype=np.float32)

        if prop == "position":
            pose.lin[...] = value_array
        elif prop == "rotation":
            pose.ang[...] = value_array
        elif prop == "scale":
            pose.scale[...] = value_array
        else:
            raise KeyError(f"Unknown transform property: '{prop}'")

        entity.transform.set_local_pose(pose)

    @classmethod
    def _set_component(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        """Set component property."""
        if not parts:
            raise KeyError("Component path requires component identifier")

        comp_id = parts[0]
        remaining = parts[1:]

        component = cls._find_component(entity, comp_id)
        if component is None:
            raise KeyError(f"Component not found: '{comp_id}'")

        if not remaining:
            raise KeyError("Cannot replace entire component via PropertyPath")

        prop_path = ".".join(remaining)
        cls._set_component_property(component, prop_path, value)

    @classmethod
    def _set_component_property(
        cls, component: "Component", prop_path: str, value: Any
    ) -> None:
        """Set property on component using inspect_fields or direct access."""
        # Collect inspect_fields from class hierarchy
        inspect_fields = {}
        for klass in reversed(type(component).__mro__):
            if hasattr(klass, "inspect_fields") and klass.inspect_fields:
                inspect_fields.update(klass.inspect_fields)

        # Check if it's an inspect_field
        if prop_path in inspect_fields:
            field = inspect_fields[prop_path]
            field.set_value(component, value)
            return

        # Try direct attribute access for dotted paths
        parts = prop_path.split(".")
        obj = component
        for part in parts[:-1]:
            obj = getattr(obj, part)

        last = parts[-1]

        # Handle numpy arrays
        current = getattr(obj, last)
        if isinstance(current, np.ndarray):
            current[...] = value
        else:
            setattr(obj, last, value)

    @classmethod
    def _set_child(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        """Set child entity property."""
        if not parts:
            raise KeyError("Child path requires child identifier")

        child_id = parts[0]
        remaining = parts[1:]

        child = cls._find_child(entity, child_id)
        if child is None:
            raise KeyError(f"Child not found: '{child_id}'")

        if not remaining:
            raise KeyError("Cannot replace entire child via PropertyPath")

        cls._set_recursive(child, remaining, value)

    @classmethod
    def exists(cls, entity: "Entity", path: str) -> bool:
        """Check if path exists."""
        try:
            cls.get(entity, path)
            return True
        except (KeyError, AttributeError):
            return False

    @classmethod
    def iter_all(
        cls,
        entity: "Entity",
        include_children: bool = True,
        prefix: str = "",
    ) -> Iterator[tuple[str, Any]]:
        """
        Iterate over all properties of entity.

        Args:
            entity: Entity to iterate
            include_children: Include children recursively
            prefix: Path prefix for recursion

        Yields:
            (path, value) tuples
        """
        # Entity properties
        for prop in cls.ENTITY_PROPS:
            path = f"{prefix}{prop}" if prefix else prop
            yield path, getattr(entity, prop)

        # Transform properties
        pose = entity.transform.local_pose()
        t_prefix = f"{prefix}transform/" if prefix else "transform/"
        yield f"{t_prefix}position", pose.lin.copy()
        yield f"{t_prefix}rotation", pose.ang.copy()
        yield f"{t_prefix}scale", pose.scale.copy()

        # Components
        for comp in entity.components:
            comp_name = comp.__class__.__name__
            c_prefix = f"{prefix}components/{comp_name}/" if prefix else f"components/{comp_name}/"

            for prop_path, value in cls._iter_component_props(comp):
                yield f"{c_prefix}{prop_path}", value

        # Children
        if include_children:
            for i, child_transform in enumerate(entity.transform.children):
                child = child_transform.entity
                if child is None:
                    continue

                # Use name if unique, otherwise index
                child_id = child.name if child.name else str(i)
                ch_prefix = f"{prefix}children/{child_id}/" if prefix else f"children/{child_id}/"

                yield from cls.iter_all(child, include_children=True, prefix=ch_prefix)

    @classmethod
    def _iter_component_props(
        cls, component: "Component"
    ) -> Iterator[tuple[str, Any]]:
        """Iterate over component properties via inspect_fields."""
        # Collect inspect_fields from class hierarchy
        inspect_fields = {}
        for klass in reversed(type(component).__mro__):
            if hasattr(klass, "inspect_fields") and klass.inspect_fields:
                inspect_fields.update(klass.inspect_fields)

        for name, field in inspect_fields.items():
            if field.non_serializable:
                continue
            try:
                value = field.get_value(component)
                yield name, cls._copy_value(value)
            except Exception:
                pass

    @classmethod
    def _copy_value(cls, value: Any) -> Any:
        """Create a copy of value for safe storage."""
        if isinstance(value, np.ndarray):
            return value.copy()
        if isinstance(value, (list, tuple)):
            return type(value)(cls._copy_value(v) for v in value)
        if isinstance(value, dict):
            return {k: cls._copy_value(v) for k, v in value.items()}
        return value

    @classmethod
    def iter_from_data(
        cls,
        data: dict,
        prefix: str = "",
    ) -> Iterator[tuple[str, Any]]:
        """
        Iterate over all properties from serialized entity data.

        Args:
            data: Serialized entity dict
            prefix: Path prefix for recursion

        Yields:
            (path, value) tuples
        """
        # Entity properties
        for prop in cls.ENTITY_PROPS:
            if prop in data:
                path = f"{prefix}{prop}" if prefix else prop
                yield path, data[prop]

        # Transform (pose + scale)
        if "pose" in data:
            pose = data["pose"]
            t_prefix = f"{prefix}transform/" if prefix else "transform/"
            if "position" in pose:
                yield f"{t_prefix}position", pose["position"]
            if "rotation" in pose:
                yield f"{t_prefix}rotation", pose["rotation"]
        if "scale" in data:
            t_prefix = f"{prefix}transform/" if prefix else "transform/"
            yield f"{t_prefix}scale", data["scale"]

        # Components
        for comp_data in data.get("components", []):
            comp_type = comp_data.get("type")
            if not comp_type:
                continue
            comp_fields = comp_data.get("data", {})
            c_prefix = f"{prefix}components/{comp_type}/" if prefix else f"components/{comp_type}/"

            for field_name, value in comp_fields.items():
                yield f"{c_prefix}{field_name}", value

        # Children
        for i, child_data in enumerate(data.get("children", [])):
            child_name = child_data.get("name", str(i))
            ch_prefix = f"{prefix}children/{child_name}/" if prefix else f"children/{child_name}/"
            yield from cls.iter_from_data(child_data, prefix=ch_prefix)

    @classmethod
    def diff(
        cls,
        entity_a: "Entity",
        entity_b: "Entity",
    ) -> dict[str, tuple[Any, Any]]:
        """
        Find differences between two entities.

        Args:
            entity_a: First entity
            entity_b: Second entity

        Returns:
            Dict {path: (value_a, value_b)} for differing properties
        """
        props_a = dict(cls.iter_all(entity_a))
        props_b = dict(cls.iter_all(entity_b))

        result = {}

        all_paths = set(props_a.keys()) | set(props_b.keys())
        for path in all_paths:
            val_a = props_a.get(path)
            val_b = props_b.get(path)

            if not cls._values_equal(val_a, val_b):
                result[path] = (val_a, val_b)

        return result

    @classmethod
    def _values_equal(cls, a: Any, b: Any) -> bool:
        """Compare two values for equality."""
        if type(a) != type(b):
            return False

        if isinstance(a, np.ndarray):
            return np.allclose(a, b)

        if isinstance(a, (list, tuple)):
            if len(a) != len(b):
                return False
            return all(cls._values_equal(x, y) for x, y in zip(a, b))

        if isinstance(a, dict):
            if set(a.keys()) != set(b.keys()):
                return False
            return all(cls._values_equal(a[k], b[k]) for k in a)

        return a == b
