"""PropertyPath - utility for addressing prefab override properties."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Iterator, TYPE_CHECKING

import numpy as np
from tcbase import log

if TYPE_CHECKING:
    from termin.scene import Component, Entity


class PropertyPathError(KeyError):
    """Raised when a prefab override path cannot be resolved or applied."""


def _entity_name(entity: "Entity") -> Any:
    return entity.name


def _set_entity_name(entity: "Entity", value: Any) -> None:
    entity.name = value


def _entity_visible(entity: "Entity") -> Any:
    return entity.visible


def _set_entity_visible(entity: "Entity", value: Any) -> None:
    entity.visible = value


def _entity_enabled(entity: "Entity") -> Any:
    return entity.enabled


def _set_entity_enabled(entity: "Entity", value: Any) -> None:
    entity.enabled = value


def _entity_pickable(entity: "Entity") -> Any:
    return entity.pickable


def _set_entity_pickable(entity: "Entity", value: Any) -> None:
    entity.pickable = value


def _entity_selectable(entity: "Entity") -> Any:
    return entity.selectable


def _set_entity_selectable(entity: "Entity", value: Any) -> None:
    entity.selectable = value


def _entity_layer(entity: "Entity") -> Any:
    return entity.layer


def _set_entity_layer(entity: "Entity", value: Any) -> None:
    entity.layer = value


def _entity_flags(entity: "Entity") -> Any:
    return entity.flags


def _set_entity_flags(entity: "Entity", value: Any) -> None:
    entity.flags = value


def _entity_priority(entity: "Entity") -> Any:
    return entity.priority


def _set_entity_priority(entity: "Entity", value: Any) -> None:
    entity.priority = value


_EntityGetter = Callable[["Entity"], Any]
_EntitySetter = Callable[["Entity", Any], None]

_ENTITY_ACCESSORS: dict[str, tuple[_EntityGetter, _EntitySetter]] = {
    "name": (_entity_name, _set_entity_name),
    "visible": (_entity_visible, _set_entity_visible),
    "enabled": (_entity_enabled, _set_entity_enabled),
    "pickable": (_entity_pickable, _set_entity_pickable),
    "selectable": (_entity_selectable, _set_entity_selectable),
    "layer": (_entity_layer, _set_entity_layer),
    "flags": (_entity_flags, _set_entity_flags),
    "priority": (_entity_priority, _set_entity_priority),
}


class PropertyPath:
    """Utility for addressing properties within an Entity hierarchy."""

    ENTITY_PROPS = frozenset(_ENTITY_ACCESSORS)
    TRANSFORM_PROPS = frozenset({"position", "rotation", "scale"})

    @classmethod
    def get(cls, entity: "Entity", path: str) -> Any:
        """Get value at path."""
        parts = path.split("/")
        return cls._get_recursive(entity, parts)

    @classmethod
    def _get_recursive(cls, entity: "Entity", parts: list[str]) -> Any:
        if not parts:
            raise PropertyPathError("Empty path")

        part = parts[0]
        remaining = parts[1:]

        if part in cls.ENTITY_PROPS:
            if remaining:
                raise PropertyPathError(f"Entity property '{part}' has no sub-properties")
            getter, _ = _ENTITY_ACCESSORS[part]
            return getter(entity)
        if part == "transform":
            return cls._get_transform(entity, remaining)
        if part == "components":
            return cls._get_component(entity, remaining)
        if part == "children":
            return cls._get_child(entity, remaining)

        raise PropertyPathError(f"Unknown path segment: '{part}'")

    @classmethod
    def _get_transform(cls, entity: "Entity", parts: list[str]) -> Any:
        if not parts:
            raise PropertyPathError("Transform path requires sub-property")

        prop = parts[0]
        if parts[1:]:
            raise PropertyPathError(f"Transform property '{prop}' has no sub-properties")

        pose = entity.transform.local_pose()
        if prop == "position":
            return pose.lin.copy()
        if prop == "rotation":
            return pose.ang.copy()
        if prop == "scale":
            return pose.scale.copy()
        raise PropertyPathError(f"Unknown transform property: '{prop}'")

    @classmethod
    def _get_component(cls, entity: "Entity", parts: list[str]) -> Any:
        if not parts:
            raise PropertyPathError("Component path requires component identifier")

        comp_id = parts[0]
        remaining = parts[1:]

        component = cls._find_component(entity, comp_id)
        if component is None:
            raise PropertyPathError(f"Component not found: '{comp_id}'")

        if not remaining:
            return component

        prop_path = ".".join(remaining)
        return cls._get_component_property(component, prop_path)

    @classmethod
    def _find_component(cls, entity: "Entity", comp_id: str) -> "Component | None":
        components = list(entity.components)
        try:
            idx = int(comp_id)
            if 0 <= idx < len(components):
                return components[idx]
            return None
        except ValueError:
            pass

        for comp in components:
            if cls._component_type_name(comp) == comp_id:
                return comp

        return None

    @classmethod
    def _component_type_name(cls, component: "Component") -> str:
        from termin.scene import Component, PythonComponent, TcComponentRef

        if isinstance(component, PythonComponent):
            return component.type_name()
        if isinstance(component, Component):
            return component.type_name()
        if isinstance(component, TcComponentRef):
            return component.type_name
        raise PropertyPathError(
            f"Component object does not expose a Termin component type: {type(component).__name__}"
        )

    @classmethod
    def _inspect_fields(cls, component: "Component") -> dict[str, Any]:
        inspect_fields: dict[str, Any] = {}
        for klass in reversed(type(component).__mro__):
            fields = klass.__dict__.get("inspect_fields")
            if fields:
                inspect_fields.update(fields)
        inspect_fields.update(cls._registry_inspect_fields(component, inspect_fields))
        return inspect_fields

    @classmethod
    def _registry_inspect_fields(
        cls,
        component: "Component",
        existing_fields: dict[str, Any],
    ) -> dict[str, Any]:
        from termin.inspect import InspectField, InspectRegistry
        from termin.scene import TcComponentRef

        component_type = cls._component_type_name(component)
        registry_fields: dict[str, InspectField] = {}
        try:
            registry = InspectRegistry.instance()
            field_infos = registry.all_fields(component_type)
        except Exception as exc:
            log.debug(
                f"[PropertyPath] Failed to query inspect fields for "
                f"component '{component_type}': {exc}"
            )
            return registry_fields

        for info in field_infos:
            if info.path in existing_fields:
                continue

            def make_getter(path: str) -> Callable[[Any], Any]:
                def getter(target: Any) -> Any:
                    if isinstance(target, TcComponentRef):
                        return target.get_field(path)
                    return registry.get(target, path)

                return getter

            def make_setter(path: str) -> Callable[[Any, Any], None]:
                def setter(target: Any, value: Any) -> None:
                    if isinstance(target, TcComponentRef):
                        entity = target.entity
                        if entity is not None and entity.valid():
                            target.set_field(path, value, entity.scene)
                        else:
                            target.set_field(path, value)
                        return
                    registry.set(target, path, value)

                return setter

            choices = (
                [(choice.value, choice.label) for choice in info.choices]
                if info.choices
                else None
            )
            registry_fields[info.path] = InspectField(
                path=info.path,
                label=info.label,
                kind=info.kind,
                min=info.min,
                max=info.max,
                step=info.step,
                choices=choices,
                getter=make_getter(info.path),
                setter=make_setter(info.path),
                is_serializable=info.is_serializable,
                is_inspectable=info.is_inspectable,
            )

        return registry_fields

    @classmethod
    def _require_component_field(cls, component: "Component", prop_path: str) -> Any:
        inspect_fields = cls._inspect_fields(component)
        field = inspect_fields.get(prop_path)
        if field is not None:
            return field

        available = ", ".join(sorted(inspect_fields)) or "<none>"
        raise PropertyPathError(
            f"Component '{cls._component_type_name(component)}' has no inspect field "
            f"'{prop_path}'. Available fields: {available}"
        )

    @classmethod
    def _get_component_property(cls, component: "Component", prop_path: str) -> Any:
        field = cls._require_component_field(component, prop_path)
        try:
            return field.get_value(component)
        except Exception as exc:
            raise PropertyPathError(
                f"Failed to read inspect field '{prop_path}' "
                f"from component '{cls._component_type_name(component)}': {exc}"
            ) from exc

    @classmethod
    def _get_child(cls, entity: "Entity", parts: list[str]) -> Any:
        if not parts:
            raise PropertyPathError("Child path requires child identifier")

        child_id = parts[0]
        remaining = parts[1:]

        child = cls._find_child(entity, child_id)
        if child is None:
            raise PropertyPathError(f"Child not found: '{child_id}'")

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
            cls.set_or_raise(entity, path, value)
            return True
        except PropertyPathError:
            log.warning(
                f"[PropertyPath] Failed to set '{path}' on entity "
                f"'{cls._entity_name_for_log(entity)}'",
                exc_info=True,
            )
            return False

    @classmethod
    def set_or_raise(cls, entity: "Entity", path: str, value: Any) -> None:
        """Set value at path and raise PropertyPathError on failure."""
        parts = path.split("/")
        try:
            cls._set_recursive(entity, parts, value)
        except PropertyPathError:
            raise
        except Exception as exc:
            raise PropertyPathError(
                f"Failed to set property path '{path}' on entity "
                f"'{cls._entity_name_for_log(entity)}': {exc}"
            ) from exc

    @classmethod
    def _entity_name_for_log(cls, entity: "Entity") -> str:
        try:
            return str(entity.name)
        except Exception:
            return "<unnamed>"

    @classmethod
    def _set_recursive(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        if not parts:
            raise PropertyPathError("Empty path")

        part = parts[0]
        remaining = parts[1:]

        if part in cls.ENTITY_PROPS:
            if remaining:
                raise PropertyPathError(f"Entity property '{part}' has no sub-properties")
            _, setter = _ENTITY_ACCESSORS[part]
            setter(entity, value)
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

        raise PropertyPathError(f"Unknown path segment: '{part}'")

    @classmethod
    def _set_transform(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        if not parts:
            raise PropertyPathError("Transform path requires sub-property")

        prop = parts[0]
        if parts[1:]:
            raise PropertyPathError(f"Transform property '{prop}' has no sub-properties")

        pose = entity.transform.local_pose()
        value_array = np.asarray(value, dtype=np.float32)

        if prop == "position":
            pose.lin[...] = value_array
        elif prop == "rotation":
            pose.ang[...] = value_array
        elif prop == "scale":
            pose.scale[...] = value_array
        else:
            raise PropertyPathError(f"Unknown transform property: '{prop}'")

        entity.transform.set_local_pose(pose)

    @classmethod
    def _set_component(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        if not parts:
            raise PropertyPathError("Component path requires component identifier")

        comp_id = parts[0]
        remaining = parts[1:]

        component = cls._find_component(entity, comp_id)
        if component is None:
            raise PropertyPathError(f"Component not found: '{comp_id}'")

        if not remaining:
            raise PropertyPathError("Cannot replace entire component via PropertyPath")

        prop_path = ".".join(remaining)
        cls._set_component_property(component, prop_path, value)

    @classmethod
    def _set_component_property(
        cls, component: "Component", prop_path: str, value: Any
    ) -> None:
        field = cls._require_component_field(component, prop_path)
        try:
            field.set_value(component, value)
        except Exception as exc:
            raise PropertyPathError(
                f"Failed to write inspect field '{prop_path}' "
                f"on component '{cls._component_type_name(component)}': {exc}"
            ) from exc

    @classmethod
    def _set_child(cls, entity: "Entity", parts: list[str], value: Any) -> None:
        if not parts:
            raise PropertyPathError("Child path requires child identifier")

        child_id = parts[0]
        remaining = parts[1:]

        child = cls._find_child(entity, child_id)
        if child is None:
            raise PropertyPathError(f"Child not found: '{child_id}'")

        if not remaining:
            raise PropertyPathError("Cannot replace entire child via PropertyPath")

        cls._set_recursive(child, remaining, value)

    @classmethod
    def exists(cls, entity: "Entity", path: str) -> bool:
        """Check if path exists."""
        try:
            cls.get(entity, path)
            return True
        except PropertyPathError:
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
            getter, _ = _ENTITY_ACCESSORS[prop]
            yield path, getter(entity)

        pose = entity.transform.local_pose()
        t_prefix = f"{prefix}transform/" if prefix else "transform/"
        yield f"{t_prefix}position", pose.lin.copy()
        yield f"{t_prefix}rotation", pose.ang.copy()
        yield f"{t_prefix}scale", pose.scale.copy()

        for comp in entity.components:
            comp_name = cls._component_type_name(comp)
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
        component_type = cls._component_type_name(component)
        for name, field in cls._inspect_fields(component).items():
            if not field.is_serializable:
                continue
            try:
                value = field.get_value(component)
                yield name, cls._copy_value(value)
            except Exception as e:
                log.debug(
                    f"[PropertyPath] Failed to read property '{name}' "
                    f"of component '{component_type}': {e}"
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
