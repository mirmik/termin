"""Node factory and predefined node types."""

from __future__ import annotations

from typing import List

from termin.nodegraph.node import GraphNode, NodeParam
from termin.nodegraph.socket import NodeSocket
from termin.nodegraph.pass_registry import (
    create_params_from_pass,
    get_pass_categories,
    get_pass_sockets,
    get_pass_inplace_pairs,
)


# Maps node title to pass class name (when they differ)
TITLE_TO_PASS_CLASS = {
    "SkyboxPass": "SkyBoxPass",
    "PostProcess": "PostProcessPass",
    "Present": "PresentToScreenPass",
}


def _get_pass_class_name(title: str) -> str:
    """Get pass class name from node title."""
    return TITLE_TO_PASS_CLASS.get(title, title)


def _get_dynamic_params(pass_class_name: str) -> List[NodeParam]:
    """
    Try to get parameters dynamically from the pass class's inspect_fields.
    Returns empty list if class not found or no inspect_fields.
    """
    return create_params_from_pass(pass_class_name)


def create_node(node_type: str, title: str) -> GraphNode:
    """Factory function to create nodes by type."""
    if node_type == "resource":
        return create_resource_node(title)
    elif node_type == "pass":
        return create_pass_node(title)
    elif node_type == "effect":
        return create_effect_node(title)
    elif node_type == "viewport":
        return create_viewport_node(title)
    else:
        return GraphNode(title, node_type)


def create_resource_node(title: str) -> GraphNode:
    """Create a resource node (FBO or Shadow Maps)."""
    if title == "Shadow Maps":
        return _create_shadow_maps_node()
    else:
        return _create_fbo_node(title)


def _create_shadow_maps_node() -> GraphNode:
    """Create a Shadow Maps resource node."""
    node = GraphNode("Shadow Maps", "resource")
    node.add_output(NodeSocket("shadow", "shadow"))
    node.data["resource_type"] = "shadow_map_array"
    node.data["resource_name"] = "shadow_maps"
    return node


def _create_fbo_node(title: str = "FBO") -> GraphNode:
    """Create an FBO resource node with configurable parameters."""
    node = GraphNode(title, "resource")

    # Single FBO output
    node.add_output(NodeSocket("fbo", "fbo"))

    node.data["resource_type"] = "fbo"

    # Format parameter
    node.add_param(NodeParam(
        name="format",
        label="Format",
        param_type="choice",
        default="rgba8",
        choices=["rgba8", "rgba16f", "rgba32f", "r16f", "r32f"],
    ))

    # MSAA samples
    node.add_param(NodeParam(
        name="samples",
        label="MSAA",
        param_type="choice",
        default="1",
        choices=["1", "2", "4", "8"],
    ))

    # Texture filter mode
    node.add_param(NodeParam(
        name="filter",
        label="Filter",
        param_type="choice",
        default="linear",
        choices=["linear", "nearest"],
    ))

    # Size mode: viewport (use viewport size * scale) or fixed
    node.add_param(NodeParam(
        name="size_mode",
        label="Size",
        param_type="choice",
        default="viewport",
        choices=["viewport", "fixed"],
    ))

    # Scale for viewport mode (0.25, 0.5, 1.0, 2.0)
    node.add_param(NodeParam(
        name="scale",
        label="Scale",
        param_type="choice",
        default="1.0",
        choices=["0.25", "0.5", "1.0", "2.0"],
        visible_when={"size_mode": "viewport"},
    ))

    # Fixed width (for fixed mode)
    node.add_param(NodeParam(
        name="width",
        label="Width",
        param_type="int",
        default=1024,
        min_val=1,
        max_val=65536,
        visible_when={"size_mode": "fixed"},
    ))

    # Fixed height (for fixed mode)
    node.add_param(NodeParam(
        name="height",
        label="Height",
        param_type="int",
        default=1024,
        min_val=1,
        max_val=65536,
        visible_when={"size_mode": "fixed"},
    ))

    # Color buffer
    node.add_param(NodeParam(
        name="has_color",
        label="Color",
        param_type="bool",
        default=True,
    ))

    # Depth buffer
    node.add_param(NodeParam(
        name="has_depth",
        label="Depth",
        param_type="bool",
        default=True,
    ))

    # Clear color flag
    node.add_param(NodeParam(
        name="clear_color",
        label="Clear Color",
        param_type="bool",
        default=False,
    ))

    # Clear color RGBA values
    node.add_param(NodeParam(
        name="clear_color_r",
        label="R",
        param_type="float",
        default=0.0,
        min_val=0.0,
        max_val=1.0,
        visible_when={"clear_color": True},
    ))
    node.add_param(NodeParam(
        name="clear_color_g",
        label="G",
        param_type="float",
        default=0.0,
        min_val=0.0,
        max_val=1.0,
        visible_when={"clear_color": True},
    ))
    node.add_param(NodeParam(
        name="clear_color_b",
        label="B",
        param_type="float",
        default=0.0,
        min_val=0.0,
        max_val=1.0,
        visible_when={"clear_color": True},
    ))
    node.add_param(NodeParam(
        name="clear_color_a",
        label="A",
        param_type="float",
        default=1.0,
        min_val=0.0,
        max_val=1.0,
        visible_when={"clear_color": True},
    ))

    # Clear depth flag
    node.add_param(NodeParam(
        name="clear_depth",
        label="Clear Depth",
        param_type="bool",
        default=False,
    ))

    # Clear depth value
    node.add_param(NodeParam(
        name="clear_depth_value",
        label="Depth",
        param_type="float",
        default=1.0,
        min_val=0.0,
        max_val=1.0,
        visible_when={"clear_depth": True},
    ))

    return node


def create_pass_node(title: str) -> GraphNode:
    """Create a render pass node."""
    node = GraphNode(title, "pass")
    pass_class_name = _get_pass_class_name(title)
    node.data["pass_class"] = pass_class_name

    # Get sockets and inplace pairs from pass class
    inputs, outputs = get_pass_sockets(pass_class_name)
    inplace_pairs = get_pass_inplace_pairs(pass_class_name)

    # Build set of inplace output names for quick lookup
    inplace_outputs = {out_name for _, out_name in inplace_pairs}

    # Add regular input sockets
    for param_name, socket_type in inputs:
        node.add_input(NodeSocket(param_name, socket_type))

    # Add output sockets and target inputs for non-inplace outputs
    for param_name, socket_type in outputs:
        node.add_output(NodeSocket(param_name, socket_type))

        # If this output is NOT inplace, add a target input socket
        # (if nothing connected - auto-create FBO)
        if param_name not in inplace_outputs:
            target_socket = NodeSocket(f"{param_name}_target", socket_type)
            node.add_input(target_socket)

    # Store inplace pairs in node data for visualization
    node.data["inplace_pairs"] = inplace_pairs

    # Get parameters dynamically from pass class inspect_fields
    dynamic_params = _get_dynamic_params(pass_class_name)
    for param in dynamic_params:
        node.add_param(param)

    return node


def create_effect_node(title: str) -> GraphNode:
    """Create a post-effect pass node."""
    node = GraphNode(title, "effect")
    pass_class_name = _get_pass_class_name(title)
    node.data["pass_class"] = pass_class_name

    # Get sockets and inplace pairs from pass class
    inputs, outputs = get_pass_sockets(pass_class_name)
    inplace_pairs = get_pass_inplace_pairs(pass_class_name)

    # Build set of inplace output names for quick lookup
    inplace_outputs = {out_name for _, out_name in inplace_pairs}

    # Add regular input sockets
    for param_name, socket_type in inputs:
        node.add_input(NodeSocket(param_name, socket_type))

    # Add output sockets and target inputs for non-inplace outputs
    for param_name, socket_type in outputs:
        node.add_output(NodeSocket(param_name, socket_type))

        # If this output is NOT inplace, add a target input socket
        # (if nothing connected - auto-create FBO)
        if param_name not in inplace_outputs:
            target_socket = NodeSocket(f"{param_name}_target", socket_type)
            node.add_input(target_socket)

    # Store inplace pairs in node data for visualization
    node.data["inplace_pairs"] = inplace_pairs

    # Get parameters dynamically from pass class inspect_fields
    dynamic_params = _get_dynamic_params(pass_class_name)
    for param in dynamic_params:
        node.add_param(param)

    return node


def create_viewport_node(title: str) -> GraphNode:
    """Create a viewport output node."""
    node = GraphNode(title, "viewport")

    # Viewport is a sink - it receives the final image
    node.add_input(NodeSocket("color", "fbo"))
    node.add_input(NodeSocket("id", "texture"))  # For picking
    node.add_input(NodeSocket("depth", "texture"))  # Optional

    node.data["viewport_name"] = "default"

    # Viewport doesn't need params - use ViewportFrame for that

    return node


def get_available_passes_by_category() -> dict[str, list[str]]:
    """
    Get available passes organized by category for context menus.

    Returns dict of category -> list of pass class names.
    Falls back to hardcoded list if registry is unavailable.
    """
    categories = get_pass_categories()
    return categories


def create_pass_node_by_class(class_name: str) -> GraphNode:
    """
    Create a pass node from the registered class name.

    Uses the pass class to determine node type and parameters.
    """
    # Determine if this is an effect pass or regular pass
    effect_passes = {"BloomPass", "GrayscalePass", "MaterialPass"}

    if class_name in effect_passes:
        return create_effect_node(class_name)
    else:
        return create_pass_node(class_name)
