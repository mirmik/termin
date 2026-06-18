"""PropertyPath - utility for addressing prefab override properties."""

from __future__ import annotations

from typing import Any, Iterator, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.core.component import Component
    from termin.scene import Entity


class PropertyPath:
    """Utility for addressing properties within an Entity hierarchy."""

    ENTITY_PROPS = frozenset({
        "name", "visible", "enabled", "pickable", "selectable",
        "layer", "flags", "priority",
    })
    TRANSFORM_PROPS = frozenset({"position", "rotation", "scale"})

    @classmethod
    def get(cls, entity: "Entity", path: str) -> Any:
        """Get value at path."""
        parts = path.split("/")
        return cls._get_recursive(entity, parts)

    @classmethod
    def _get_recursive(cls, entity: "Entity", parts: list[str]) -> Any:
        if not parts:
            raise KeyError("Empty path")

        part = parts[0]
        remaining = parts[1:]

        if part in cls.ENTITY_PROPS:
            if remaining:
                raise KeyError(f"Entity property '{part}' has no sub-properties")
            return getattr(entity, part)
        if part == "transform":
            return cls._get_transform(entity, remaining)
        if part == "components":
            return cls._get_component(entity, remaining)
        if part == "children":
            return cls._get_child(entity, remaining)

        raise KeyError(f"Unknown path segment: '{part}'")

    @classmethod
    def _get_transform(cls, entity: "Entity", parts: list[str]) -> Any:
        if not parts:
            raise KeyError("Transform path requires sub-property")

        prop = parts[0]
        if parts[1:]:
            raise KeyError(f"Transform property '{prop}' has no sub-properties")

        pose = entity.transform.local_pose()
        if prop == "position":
            return pose.lin.copy()
        if prop == "rotation":
            return pose.ang.copy()
        if prop == "scale":
            return pose.scale.copy()
        raise KeyError(f"Unknown transform property: '{prop}'")

    @classmethod
    def _get_component(cls, entity: "Entity", parts: list[str]) -> Any:
        if not parts:
            raise KeyError("Component path requires component identifier")

        comp_id = parts[0]
        remaining = parts[1:]

        component = cls._find_component(entity, comp_id)
        if component is None:
            raise KeyError(f"Component not found: '{comp_id}'")

        if not remaining:
            return component

        prop_path = ".".join(remaining)
        return cls._get_component_property(component, prop_path)

    @classmethod
    def _find_component(cls, entity: "Entity", comp_id: str) -> "Component | None":
        try:
            idx = int(comp_id)
            if 0 <= idx < len(entity.components):
                return entity.components[idx]
            return None
        except ValueError:
            pass

        for comp in entity.components:
            if comp.__class__.__name__ == comp_id:
                return comp

        return None

    @classmethod
    def _get_component_property(cls, component: "Component", prop_path: str) -> Any:
        inspect_fields = {}
        for klass in reversed(type(component).__mro__):
            if hasattr(klass, "inspect_fields") and klass.inspect_fields:
                inspect_fields.update(klass.inspect_fields)

        if prop_path in inspect_fields:
            field = inspect_fields[prop_path]
            return field.get_value(component)

        parts = prop_path.split(".")
        obj = component
        for part in parts:
            obj = getattr(obj, part)
        return obj

    @classmethod
    def _get_child(cls, entity: "Entity", parts: list[str]) -> Any:
        if not parts:
            raise KeyError("Child path requires child identifier")

        child_id = parts[0]
        remaining = parts[1:]

        child = cls._find_child(entity, child_id)
        if child is None:
            raise KeyError(f"Child not found: '{child_id}'")

        if not remaining:
            return child

        return cls._get_recursive(child, remaining)

    @classmethod
    def _find_child(cls, entity: "Entity", child_id: str) -> "Entity | None":
        children = [t.entity for t in entity.transform.children if t.entity is not None]

        try:
            idx = int(child_id)
            if 0 <= idx < len(children):
                return children[idx]
            return None
        except ValueError:
            pass

        for child in children:
            if child.name == child_id:
                return child

        return None

    @classmethod
    def set(cls, entity: "Entity", path: str, value: Any) -> bool:
        """Set value at path."""
        try:
            parts = path.split("/")
            cls._set_recursive(entity, parts, value)
            return True
        except (KeyError, AttributeError):
            return False

    @classmethod
    def _set_recursive(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        if not parts:
            raise KeyError("Empty path")

        part = parts[0]
        remaining = parts[1:]

        if part in cls.ENTITY_PROPS:
            if remaining:
                raise KeyError(f"Entity property '{part}' has no sub-properties")
            setattr(entity, part, value)
            return
        if part == "transform":
            cls._set_transform(entity, remaining, value)
            return
        if part == "components":
            cls._set_component(entity, remaining, value)
            return
        if part == "children":
            cls._set_child(entity, remaining, value)
            return

        raise KeyError(f"Unknown path segment: '{part}'")

    @classmethod
    def _set_transform(cls, entity: "Entity", parts: list[str], value: Any) -> None:
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
        inspect_fields = {}
        for klass in reversed(type(component).__mro__):
            if hasattr(klass, "inspect_fields") and klass.inspect_fields:
                inspect_fields.update(klass.inspect_fields)

        if prop_path in inspect_fields:
            field = inspect_fields[prop_path]
            field.set_value(component, value)
            return

        parts = prop_path.split(".")
        obj = component
        for part in parts[:-1]:
            obj = getattr(obj, part)

        last = parts[-1]
        current = getattr(obj, last)
        if isinstance(current, np.ndarray):
            current[...] = value
        else:
            setattr(obj, last, value)

    @classmethod
    def _set_child(cls, entity: "Entity", parts: list[str], value: Any) -> None:
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
        """Iterate over all properties of entity."""
        for prop in cls.ENTITY_PROPS:
            path = f"{prefix}{prop}" if prefix else prop
            yield path, getattr(entity, prop)

        pose = entity.transform.local_pose()
        t_prefix = f"{prefix}transform/" if prefix else "transform/"
        yield f"{t_prefix}position", pose.lin.copy()
        yield f"{t_prefix}rotation", pose.ang.copy()
        yield f"{t_prefix}scale", pose.scale.copy()

        for comp in entity.components:
            comp_name = comp.__class__.__name__
            c_prefix = f"{prefix}components/{comp_name}/" if prefix else f"components/{comp_name}/"

            for prop_path, value in cls._iter_component_props(comp):
                yield f"{c_prefix}{prop_path}", value

        if include_children:
            for i, child_transform in enumerate(entity.transform.children):
                child = child_transform.entity
                if child is None:
                    continue

                child_id = child.name if child.name else str(i)
                ch_prefix = f"{prefix}children/{child_id}/" if prefix else f"children/{child_id}/"
                yield from cls.iter_all(child, include_children=True, prefix=ch_prefix)

    @classmethod
    def _iter_component_props(
        cls, component: "Component"
    ) -> Iterator[tuple[str, Any]]:
        inspect_fields = {}
        for klass in reversed(type(component).__mro__):
            if hasattr(klass, "inspect_fields") and klass.inspect_fields:
                inspect_fields.update(klass.inspect_fields)

        for name, field in inspect_fields.items():
            if not field.is_serializable:
                continue
            try:
                value = field.get_value(component)
                yield name, cls._copy_value(value)
            except Exception as e:
                from tcbase import log

                log.debug(
                    f"[PropertyPath] Failed to read property '{name}' "
                    f"of component '{type(component).__name__}': {e}"
                )

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
        """Iterate over all properties from serialized entity data."""
        for prop in cls.ENTITY_PROPS:
            if prop in data:
                path = f"{prefix}{prop}" if prefix else prop
                yield path, data[prop]

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

        for comp_data in data.get("components", []):
            comp_type = comp_data.get("type")
            if not comp_type:
                continue
            comp_fields = comp_data.get("data", {})
            c_prefix = f"{prefix}components/{comp_type}/" if prefix else f"components/{comp_type}/"

            for field_name, value in comp_fields.items():
                yield f"{c_prefix}{field_name}", value

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
        """Find differences between two entities."""
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
        if type(a) is not type(b):
            return False
        if isinstance(a, np.ndarray):
            return np.allclose(a, b)
        if isinstance(a, (list, tuple)):
            if len(a) != len(b):
                return False
            return all(cls._values_equal(x, y) for x, y in zip(a, b, strict=True))
        if isinstance(a, dict):
            if set(a.keys()) != set(b.keys()):
                return False
            return all(cls._values_equal(a[k], b[k]) for k in a)
        return a == b
