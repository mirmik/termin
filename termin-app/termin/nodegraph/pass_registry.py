"""Pass registry for the node graph editor.

Provides access to registered FramePass classes and their inspect_fields,
enabling dynamic creation of node parameters from pass definitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Any, Type

from termin.nodegraph.node import NodeParam

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.core import FramePass


def get_pass_class(class_name: str) -> Type["FramePass"] | None:
    """
    Get a FramePass class by name from ResourceManager.

    Args:
        class_name: Name of the pass class (e.g., "ColorPass", "BloomPass").

    Returns:
        The class or None if not found.
    """
    try:
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        return rm.get_frame_pass(class_name)
    except Exception as e:
        from tcbase import log
        log.warn(f"[pass_registry] get_pass_class('{class_name}') failed: {e}")
        return None


def get_all_pass_names() -> List[str]:
    """Get list of all registered FramePass class names."""
    try:
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        return list(rm.frame_passes.keys())
    except Exception as e:
        from tcbase import log
        log.warn(f"[pass_registry] get_all_pass_names() failed: {e}")
        return []


def inspect_field_info_to_node_param(info) -> NodeParam | None:
    """
    Convert an InspectFieldInfo (from InspectRegistry) to a NodeParam.

    Args:
        info: InspectFieldInfo from InspectRegistry.all_fields().

    Returns:
        NodeParam or None if the field type is not supported.
    """
    kind = info.kind
    name = info.path
    label = info.label or name

    if kind == "float":
        return NodeParam(
            name=name,
            label=label,
            param_type="float",
            default=0.0,
            min_val=info.min if info.min is not None else 0.0,
            max_val=info.max if info.max is not None else 100.0,
        )

    elif kind == "int":
        return NodeParam(
            name=name,
            label=label,
            param_type="int",
            default=0,
            min_val=info.min if info.min is not None else 0,
            max_val=info.max if info.max is not None else 100,
        )

    elif kind == "bool":
        return NodeParam(
            name=name,
            label=label,
            param_type="bool",
            default=False,
        )

    elif kind == "string":
        # Check if string field has choices (INSPECT_FIELD_CHOICES)
        if info.choices:
            # Use values as choices (they get passed directly to pass constructor)
            choice_values = [c.value for c in info.choices]
            default = choice_values[0] if choice_values else ""
            return NodeParam(
                name=name,
                label=label,
                param_type="choice",
                default=default,
                choices=choice_values,
            )
        return NodeParam(
            name=name,
            label=label,
            param_type="text",
            default="",
        )

    elif kind == "enum" and info.choices:
        # Choices are list of EnumChoice with value and label
        choice_labels = [c.label for c in info.choices]
        default = choice_labels[0] if choice_labels else ""
        return NodeParam(
            name=name,
            label=label,
            param_type="choice",
            default=default,
            choices=choice_labels,
        )

    elif kind == "tc_material":
        # Get material names from ResourceManager
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        material_names = rm.list_material_names()
        choices = ["(None)"] + material_names
        return NodeParam(
            name=name,
            label=label,
            param_type="choice",
            default="(None)",
            choices=choices,
        )

    # Unsupported types (vec3, color, etc.) - skip for now
    return None


# Fields that are represented as graph connections, not UI parameters
SOCKET_FIELDS = {
    "input_res",
    "output_res",
    "shadow_res",
    "depth_res",
    "id_res",
    "normal_res",
}


def create_params_from_pass(class_name: str) -> List[NodeParam]:
    """
    Create NodeParam list from a pass class's inspect fields.

    Uses InspectRegistry to get fields (works for both C++ and Python classes).
    Also reads Python-only inspect_fields from the class.
    Filters out fields that are represented as graph connections (sockets).

    Args:
        class_name: Name of the pass class.

    Returns:
        List of NodeParam for the node editor.
    """
    params = []
    seen_names = set()

    # Get visibility conditions from class
    cls = get_pass_class(class_name)
    visibility_conditions = {}
    if cls is not None:
        visibility_conditions = getattr(cls, "node_param_visibility", {})

    # 1. Get fields from C++ InspectRegistry
    try:
        from termin._native.inspect import InspectRegistry
        registry = InspectRegistry.instance()
        all_fields = registry.all_fields(class_name)

        for info in all_fields:
            if not info.is_inspectable:
                continue
            if info.path in SOCKET_FIELDS:
                continue

            param = inspect_field_info_to_node_param(info)
            if param is not None:
                # Apply visibility conditions
                if param.name in visibility_conditions:
                    param.visible_when = visibility_conditions[param.name]
                params.append(param)
                seen_names.add(param.name)
    except Exception as e:
        from tcbase import log
        log.warn(f"[pass_registry] create_params_from_pass('{class_name}') C++ fields failed: {e}")

    # 2. Get Python-only inspect_fields from class
    if cls is not None:
        py_fields = getattr(cls, "inspect_fields", {})
        for name, field in py_fields.items():
            if name in seen_names:
                continue
            if name in SOCKET_FIELDS:
                continue
            if not field.is_inspectable:
                continue

            param = _python_field_to_node_param(name, field)
            if param is not None:
                # Apply visibility conditions
                if name in visibility_conditions:
                    param.visible_when = visibility_conditions[name]
                params.append(param)

    return params


def _python_field_to_node_param(name: str, field) -> NodeParam | None:
    """Convert a Python InspectField to NodeParam."""
    kind = field.kind
    label = field.label or name

    if kind == "float":
        return NodeParam(
            name=name,
            label=label,
            param_type="float",
            default=0.0,
            min_val=field.min if field.min is not None else 0.0,
            max_val=field.max if field.max is not None else 100.0,
        )
    elif kind == "int":
        return NodeParam(
            name=name,
            label=label,
            param_type="int",
            default=0,
            min_val=field.min if field.min is not None else 0,
            max_val=field.max if field.max is not None else 100,
        )
    elif kind == "bool":
        return NodeParam(
            name=name,
            label=label,
            param_type="bool",
            default=False,
        )
    elif kind == "string":
        if field.choices:
            choice_values = [c[0] for c in field.choices]
            default = choice_values[0] if choice_values else ""
            return NodeParam(
                name=name,
                label=label,
                param_type="choice",
                default=default,
                choices=choice_values,
            )
        return NodeParam(
            name=name,
            label=label,
            param_type="text",
            default="",
        )
    elif kind == "enum" and field.choices:
        choice_labels = [c[1] for c in field.choices]
        default = choice_labels[0] if choice_labels else ""
        return NodeParam(
            name=name,
            label=label,
            param_type="choice",
            default=default,
            choices=choice_labels,
        )
    elif kind == "tc_material":
        # Get material names from ResourceManager
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        material_names = rm.list_material_names()
        choices = ["(None)"] + material_names
        return NodeParam(
            name=name,
            label=label,
            param_type="choice",
            default="(None)",
            choices=choices,
        )

    return None


def get_pass_sockets(class_name: str) -> tuple[list, list]:
    """
    Get node_inputs and node_outputs from a pass class.

    Args:
        class_name: Name of the pass class.

    Returns:
        Tuple of (node_inputs, node_outputs).
        Each is a list of (param_name, socket_type) tuples.
    """
    cls = get_pass_class(class_name)
    if cls is None:
        return [], []

    # Collect from MRO (base classes first, subclasses override)
    inputs = []
    outputs = []

    for klass in reversed(cls.__mro__):
        if hasattr(klass, 'node_inputs'):
            class_inputs = getattr(klass, 'node_inputs', None)
            if class_inputs is not None:
                inputs = list(class_inputs)
        if hasattr(klass, 'node_outputs'):
            class_outputs = getattr(klass, 'node_outputs', None)
            if class_outputs is not None:
                outputs = list(class_outputs)

    return inputs, outputs


def get_pass_inplace_pairs(class_name: str) -> list:
    """
    Get node_inplace_pairs from a pass class.

    Args:
        class_name: Name of the pass class.

    Returns:
        List of (input_name, output_name) tuples for inplace pairs.
    """
    cls = get_pass_class(class_name)
    if cls is None:
        return []

    # Collect from MRO (base classes first, subclasses override)
    pairs = []

    for klass in reversed(cls.__mro__):
        class_pairs = getattr(klass, 'node_inplace_pairs', None)
        if class_pairs is not None:
            pairs = list(class_pairs)

    return pairs


def get_pass_categories() -> Dict[str, List[str]]:
    """
    Get pass classes organized by category.

    Reads the `category` class attribute from each registered pass class.

    Returns:
        Dict of category -> list of class names.
    """
    all_pass_names = get_all_pass_names()
    result: Dict[str, List[str]] = {}

    for class_name in all_pass_names:
        cls = get_pass_class(class_name)
        if cls is None:
            continue

        # Get category from class attribute
        category = getattr(cls, "category", "Other")

        if category not in result:
            result[category] = []
        result[category].append(class_name)

    # Sort class names within each category
    for category in result:
        result[category].sort()

    return result
