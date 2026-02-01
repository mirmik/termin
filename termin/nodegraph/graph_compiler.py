"""Graph compiler - compiles GraphData to RenderPipeline.

Works with pure data structures (no Qt dependencies).
Can be moved to C++ later.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from termin.nodegraph.graph_data import (
    GraphData,
    NodeData,
    ConnectionData,
    ViewportFrameData,
)


class CompileError(Exception):
    """Error during graph compilation."""
    pass


def _create_pass_instance(pass_cls, pass_class_name: str, kwargs: dict, viewport_name: str = ""):
    """
    Create a pass instance.

    For C++ passes, some kwargs are constructor params, others are properties.
    We try to create with all kwargs, then progressively remove invalid ones
    and set them as properties after construction.
    """
    # Remove viewport_name from kwargs - it's set as property after construction
    constructor_kwargs = {k: v for k, v in kwargs.items() if k != "viewport_name"}

    instance = None
    used_kwargs = set()

    # Try with all kwargs first
    try:
        instance = pass_cls(**constructor_kwargs)
        used_kwargs = set(constructor_kwargs.keys())
    except TypeError:
        # Try to find which kwargs the constructor accepts by testing
        # Start with empty, add one by one
        working_kwargs = {}
        for key, value in constructor_kwargs.items():
            try:
                pass_cls(**working_kwargs, **{key: value})
                working_kwargs[key] = value
            except TypeError:
                pass  # This kwarg is not accepted by constructor

        try:
            instance = pass_cls(**working_kwargs)
            used_kwargs = set(working_kwargs.keys())
        except TypeError:
            # Last resort: no args
            instance = pass_cls()

    # Set remaining kwargs as properties
    for key, value in constructor_kwargs.items():
        if key not in used_kwargs:
            if hasattr(instance, key):
                try:
                    setattr(instance, key, value)
                except (AttributeError, TypeError):
                    pass  # Property is read-only or wrong type

    # Set viewport_name as property if supported
    if viewport_name and hasattr(instance, "set_viewport_name"):
        instance.set_viewport_name(viewport_name)
    elif viewport_name and hasattr(instance, "viewport_name"):
        instance.viewport_name = viewport_name

    return instance


def find_containing_frame(
    node: NodeData,
    viewport_frames: List[ViewportFrameData],
) -> Optional[ViewportFrameData]:
    """Find the ViewportFrame that contains a node by position."""
    if not viewport_frames:
        return None

    node_cx = node.x + 100  # Approximate node center
    node_cy = node.y + 50

    for frame in viewport_frames:
        if (frame.x <= node_cx <= frame.x + frame.width and
            frame.y <= node_cy <= frame.y + frame.height):
            return frame

    return None


def build_node_viewport_map(
    nodes: List[NodeData],
    viewport_frames: List[ViewportFrameData],
) -> Dict[str, str]:
    """Build mapping: node_id -> viewport_name."""
    result: Dict[str, str] = {}

    for node in nodes:
        frame = find_containing_frame(node, viewport_frames)
        result[node.id] = frame.viewport_name if frame else ""

    return result


def topological_sort(graph: GraphData) -> List[NodeData]:
    """Topologically sort nodes based on connections."""
    # Build adjacency: node_id -> list of dependent node_ids
    dependents: Dict[str, List[str]] = {n.id: [] for n in graph.nodes}
    in_degree: Dict[str, int] = {n.id: 0 for n in graph.nodes}

    for conn in graph.connections:
        if conn.from_node_id in dependents and conn.to_node_id in in_degree:
            dependents[conn.from_node_id].append(conn.to_node_id)
            in_degree[conn.to_node_id] += 1

    # Kahn's algorithm
    queue = [n.id for n in graph.nodes if in_degree[n.id] == 0]
    sorted_ids: List[str] = []

    while queue:
        node_id = queue.pop(0)
        sorted_ids.append(node_id)
        for dep_id in dependents[node_id]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                queue.append(dep_id)

    if len(sorted_ids) != len(graph.nodes):
        raise CompileError("Graph has cycles")

    # Return nodes in sorted order
    node_map = {n.id: n for n in graph.nodes}
    return [node_map[nid] for nid in sorted_ids]


def assign_resource_names(
    graph: GraphData,
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, List[str]]]:
    """
    Assign resource names to all sockets.

    Returns:
        - socket_names: node_id -> {socket_name -> resource_name}
        - resource_types: resource_name -> socket_type
        - target_aliases: resource_name -> [alias_names]
    """
    socket_names: Dict[str, Dict[str, str]] = {n.id: {} for n in graph.nodes}
    resource_types: Dict[str, str] = {}
    target_aliases: Dict[str, List[str]] = {}

    node_index: Dict[str, int] = {n.id: i for i, n in enumerate(graph.nodes)}

    # Pass 1: Assign names to FBO resource nodes
    for node in graph.nodes:
        if node.node_type == "resource":
            resource_type = node.params.get("resource_type", "fbo")
            if resource_type == "fbo":
                name = node.name or f"fbo_{node_index[node.id]}"
                for output in node.outputs:
                    socket_names[node.id][output.name] = name
                    resource_types[name] = output.socket_type

    # Pass 2: Assign names to output sockets of pass nodes
    for node in graph.nodes:
        if node.node_type == "pass":
            idx = node_index[node.id]
            for output in node.outputs:
                if output.name not in socket_names[node.id]:
                    name = f"{node.pass_class}_{idx}_{output.name}"
                    socket_names[node.id][output.name] = name
                    resource_types[name] = output.socket_type

    # Pass 3: Propagate through connections
    for conn in graph.connections:
        from_name = socket_names.get(conn.from_node_id, {}).get(conn.from_socket)
        if from_name:
            socket_names[conn.to_node_id][conn.to_socket] = from_name

    # Pass 4: Handle target sockets (aliases)
    for node in graph.nodes:
        for inp in node.inputs:
            if inp.name.endswith("_target"):
                base_name = inp.name[:-7]  # Remove "_target"
                if base_name in socket_names[node.id] and inp.name in socket_names[node.id]:
                    base_res = socket_names[node.id][base_name]
                    target_res = socket_names[node.id][inp.name]
                    if base_res != target_res:
                        if base_res not in target_aliases:
                            target_aliases[base_res] = []
                        if target_res not in target_aliases[base_res]:
                            target_aliases[base_res].append(target_res)

    # Pass 5: Default names for unconnected inputs
    for node in graph.nodes:
        idx = node_index[node.id]
        for inp in node.inputs:
            if inp.name not in socket_names[node.id]:
                name = f"empty_{node.name or node.pass_class}_{idx}_{inp.name}"
                socket_names[node.id][inp.name] = name
                resource_types[name] = inp.socket_type

    return socket_names, resource_types, target_aliases


def collect_fbo_nodes(graph: GraphData) -> Dict[str, NodeData]:
    """Collect FBO resource nodes by their output resource name."""
    result: Dict[str, NodeData] = {}

    for node in graph.nodes:
        if node.node_type == "resource" and node.params.get("resource_type") == "fbo":
            name = node.name or node.id
            result[name] = node

    return result


def infer_resource_spec(
    resource_name: str,
    fbo_nodes: Dict[str, NodeData],
    connected_passes: List[str],
) -> Dict[str, Any] | None:
    """Infer ResourceSpec parameters for a resource."""
    if resource_name in fbo_nodes:
        node = fbo_nodes[resource_name]
        spec: Dict[str, Any] = {"resource": resource_name}

        fmt = node.params.get("format")
        if fmt:
            spec["format"] = fmt

        samples = node.params.get("samples")
        if samples:
            try:
                spec["samples"] = int(samples)
            except ValueError:
                pass

        filter_mode = node.params.get("filter")
        if filter_mode:
            from termin._native.render import TextureFilter
            spec["filter"] = TextureFilter.NEAREST if filter_mode == "nearest" else TextureFilter.LINEAR

        size_mode = node.params.get("size_mode")
        if size_mode == "fixed":
            width = node.params.get("width")
            height = node.params.get("height")
            if width and height:
                try:
                    spec["size"] = (int(width), int(height))
                except ValueError:
                    pass
        else:
            scale = node.params.get("scale")
            if scale:
                try:
                    scale_value = float(scale)
                    if scale_value != 1.0:
                        spec["scale"] = scale_value
                except ValueError:
                    pass

        if node.params.get("clear_color"):
            r = node.params.get("clear_color_r", 0.0)
            g = node.params.get("clear_color_g", 0.0)
            b = node.params.get("clear_color_b", 0.0)
            a = node.params.get("clear_color_a", 1.0)
            spec["clear_color"] = (float(r), float(g), float(b), float(a))

        if node.params.get("clear_depth"):
            depth_value = node.params.get("clear_depth_value", 1.0)
            spec["clear_depth"] = float(depth_value)

        return spec

    # Heuristics based on pass types
    hdr_passes = {"PostProcessPass", "BloomPass", "TonemapPass", "ColorPass"}
    msaa_passes = {"ColorPass", "DepthPass", "SkyBoxPass"}

    needs_hdr = any(p in hdr_passes for p in connected_passes)
    needs_msaa = any(p in msaa_passes for p in connected_passes)

    if needs_hdr or needs_msaa:
        spec = {"resource": resource_name}
        if needs_hdr:
            spec["format"] = "rgba16f"
        if needs_msaa:
            spec["samples"] = 4
        return spec

    return None


def compile_graph_data(graph: GraphData) -> "RenderPipeline":
    """
    Compile GraphData to RenderPipeline.

    Args:
        graph: Pure data graph representation.

    Returns:
        Compiled RenderPipeline ready for rendering.

    Raises:
        CompileError: If compilation fails.
    """
    from termin.visualization.render.framegraph.pipeline import RenderPipeline
    from termin.nodegraph.pass_registry import get_pass_class

    # Sort nodes topologically
    sorted_nodes = topological_sort(graph)

    # Assign resource names
    socket_names, resource_types, target_aliases = assign_resource_names(graph)

    # Build viewport map
    node_viewport_map = build_node_viewport_map(graph.nodes, graph.viewport_frames)

    # Collect FBO nodes for ResourceSpec inference
    fbo_nodes = collect_fbo_nodes(graph)

    # Track which passes use each resource
    resource_users: Dict[str, List[str]] = {}
    for node in sorted_nodes:
        if node.node_type != "pass":
            continue
        for inp in node.inputs:
            res_name = socket_names[node.id].get(inp.name)
            if res_name:
                if res_name not in resource_users:
                    resource_users[res_name] = []
                resource_users[res_name].append(node.pass_class)

    # Create pipeline
    pipeline = RenderPipeline()

    # Add passes
    for node in sorted_nodes:
        if node.node_type != "pass":
            continue

        pass_cls = get_pass_class(node.pass_class)
        if pass_cls is None:
            raise CompileError(f"Unknown pass class: {node.pass_class}")

        # Build constructor arguments
        kwargs = dict(node.params)

        # Add resource names from sockets
        for inp in node.inputs:
            if inp.name in socket_names[node.id]:
                if not inp.name.endswith("_target"):
                    kwargs[inp.name] = socket_names[node.id][inp.name]
        for out in node.outputs:
            if out.name in socket_names[node.id]:
                kwargs[out.name] = socket_names[node.id][out.name]

        # Get viewport_name for this node
        viewport_name = node_viewport_map.get(node.id, "")

        # Create pass instance
        pass_instance = _create_pass_instance(pass_cls, node.pass_class, kwargs, viewport_name)

        pipeline.add_pass(pass_instance)

    # Add ResourceSpecs (only for FBO resources, not shadow maps etc.)
    from termin._native.render import ResourceSpec

    seen_resources: Set[str] = set()
    for node in sorted_nodes:
        if node.node_type != "pass":
            continue
        for inp in node.inputs:
            res_name = socket_names[node.id].get(inp.name)
            if res_name and res_name not in seen_resources:
                seen_resources.add(res_name)

                # Skip non-FBO resources (shadow maps are managed by ShadowPass)
                res_type = resource_types.get(res_name, "fbo")
                if res_type != "fbo":
                    continue

                spec_data = infer_resource_spec(
                    res_name,
                    fbo_nodes,
                    resource_users.get(res_name, []),
                )

                if spec_data:
                    spec = ResourceSpec(**spec_data)
                    pipeline.add_spec(spec)

    return pipeline
