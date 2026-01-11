"""Graph compiler - converts node graph to RenderPipeline.

Responsibilities:
- Generate unique resource names for connections
- Resolve input/output resource mappings
- Create FramePass instances with correct parameters
- Infer ResourceSpec from FBO nodes and pass types
- Assign viewport_name from ViewportFrames to contained passes
- Topological sort and pipeline assembly
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from termin.nodegraph.scene import NodeGraphScene
    from termin.nodegraph.node import GraphNode
    from termin.nodegraph.connection import NodeConnection
    from termin.nodegraph.socket import NodeSocket
    from termin.nodegraph.viewport_frame import ViewportFrame


class CompileError(Exception):
    """Error during graph compilation."""
    pass


def find_containing_frame(
    node: "GraphNode",
    viewport_frames: List["ViewportFrame"],
) -> Optional["ViewportFrame"]:
    """
    Find the ViewportFrame that contains a node.

    A node is considered "inside" a frame if its center is within the frame bounds.

    Returns:
        ViewportFrame containing the node, or None if outside all frames.
    """
    if not viewport_frames:
        return None

    node_rect = node.sceneBoundingRect()
    node_center = node_rect.center()

    for frame in viewport_frames:
        frame_rect = frame.sceneBoundingRect()
        if frame_rect.contains(node_center):
            return frame

    return None


def build_node_viewport_map(
    nodes: List["GraphNode"],
    viewport_frames: List["ViewportFrame"],
    debug: bool = False,
) -> Dict["GraphNode", str]:
    """
    Build a mapping from nodes to their viewport names.

    Returns:
        Dict mapping each node to its viewport_name (empty string if no frame).
    """
    result: Dict["GraphNode", str] = {}

    for node in nodes:
        frame = find_containing_frame(node, viewport_frames)
        if frame:
            result[node] = frame.viewport_name
        else:
            result[node] = ""

        if debug:
            node_rect = node.sceneBoundingRect()
            print(f"Node {node.title}: center=({node_rect.center().x():.0f}, {node_rect.center().y():.0f}) -> viewport={result[node] or '(none)'}")
            for vf in viewport_frames:
                vf_rect = vf.sceneBoundingRect()
                print(f"  Frame '{vf.viewport_name}': ({vf_rect.x():.0f}, {vf_rect.y():.0f}, {vf_rect.width():.0f}x{vf_rect.height():.0f})")

    return result


def generate_resource_name(node: "GraphNode", socket: "NodeSocket", node_index: int) -> str:
    """
    Generate unique resource name for a socket.

    For FBO resource nodes: use the configured name directly.
    For other nodes: "{node_name}_{socket_name}" or "{node_type}_{index}_{socket_name}".
    """
    # FBO resource nodes use their instance name (from header)
    if node.node_type == "resource" and node.data.get("resource_type") == "fbo":
        # Use node.name (instance name shown in header), not the "name" parameter
        name = node.name
        # If no instance name, fall back to indexed name
        if not name:
            return f"fbo_{node_index}"
        return name

    if node.name:
        base = node.name.replace(" ", "_")
    else:
        base = f"{node.title}_{node_index}"

    return f"{base}_{socket.name}"


def resolve_resource_names(
    nodes: List["GraphNode"],
    connections: List["NodeConnection"],
) -> Tuple[Dict["NodeSocket", str], Dict[str, str], Dict[str, str]]:
    """
    Assign resource names to all sockets based on connections.

    Rules:
    - Connected sockets share the same resource name (from output socket)
    - Unconnected output sockets get auto-generated names
    - Unconnected input sockets get "empty" or special defaults
    - Target sockets (X_target) create aliases between output and FBO

    Returns:
        Tuple of:
        - Dict mapping each socket to its resource name
        - Dict mapping resource name to socket type ("fbo", "shadow", etc.)
        - Dict mapping output_res name to FBO name (aliases from _target connections)
    """
    # Build node index map
    node_to_index = {node: i for i, node in enumerate(nodes)}

    # Result: socket -> resource_name
    socket_names: Dict["NodeSocket", str] = {}
    # Track resource types: resource_name -> socket_type
    resource_types: Dict[str, str] = {}
    # Track target aliases: output_res_name -> fbo_name
    target_aliases: Dict[str, str] = {}

    # First pass: assign names to all output sockets
    for node in nodes:
        idx = node_to_index[node]
        for socket in node.output_sockets:
            name = generate_resource_name(node, socket, idx)
            socket_names[socket] = name
            resource_types[name] = socket.socket_type

    # Second pass: initial propagation to get _target input names
    # (We need to know what FBO is connected to _target before we can override output)
    for conn in connections:
        if conn.start_socket is None or conn.end_socket is None:
            continue
        output_socket = conn.start_socket
        input_socket = conn.end_socket
        if output_socket in socket_names:
            socket_names[input_socket] = socket_names[output_socket]

    # Third pass: handle _target connections
    # When output_res_target is connected to an FBO, the output_res socket
    # should use the FBO's name instead of the auto-generated name.
    for node in nodes:
        # Build map of output sockets by name
        output_socket_map: Dict[str, "NodeSocket"] = {}
        for socket in node.output_sockets:
            output_socket_map[socket.name] = socket

        for socket in node.input_sockets:
            if not socket.name.endswith("_target"):
                continue

            # Check if this target is connected
            if socket not in socket_names:
                continue

            # Get the corresponding output socket name (remove _target suffix)
            output_name = socket.name[:-7]  # len("_target") == 7
            output_socket = output_socket_map.get(output_name)

            if output_socket is None:
                continue

            # Get FBO name from the target connection
            fbo_name = socket_names[socket]

            # Store the old output name for the alias
            old_output_name = socket_names.get(output_socket)
            if old_output_name and fbo_name:
                target_aliases[old_output_name] = fbo_name

            # Update output socket to use the FBO name
            # This makes the pass output to the connected FBO resource
            socket_names[output_socket] = fbo_name

    # Fourth pass: re-propagate names through connections
    # Now that _target overrides are applied, downstream sockets get the correct names
    for conn in connections:
        if conn.start_socket is None or conn.end_socket is None:
            continue
        output_socket = conn.start_socket
        input_socket = conn.end_socket
        if output_socket in socket_names:
            socket_names[input_socket] = socket_names[output_socket]

    # Fifth pass: assign default names to unconnected input sockets
    for node in nodes:
        idx = node_to_index[node]
        for socket in node.input_sockets:
            if socket not in socket_names:
                # Unconnected input - use "empty" prefix for auto-creation
                name = f"empty_{node.title}_{idx}_{socket.name}"
                socket_names[socket] = name
                resource_types[name] = socket.socket_type

    return socket_names, resource_types, target_aliases


def get_socket_resource_params(node: "GraphNode", socket_names: Dict["NodeSocket", str]) -> Dict[str, str]:
    """
    Get resource name parameters for a pass node.

    Maps socket names to constructor parameter names:
    - input_res, output_res, shadow_res, etc.
    """
    params = {}

    for socket in node.input_sockets:
        if socket in socket_names:
            # Socket name like "input_res" or "shadow_res" maps directly to param
            param_name = socket.name
            # Skip target sockets - they're just for UI visualization
            if param_name.endswith("_target"):
                continue
            params[param_name] = socket_names[socket]

    for socket in node.output_sockets:
        if socket in socket_names:
            params[socket.name] = socket_names[socket]

    return params


def infer_resource_spec(
    resource_name: str,
    fbo_nodes: Dict[str, "GraphNode"],
    connected_passes: List[str],
) -> Dict[str, Any] | None:
    """
    Infer ResourceSpec parameters for a resource.

    Priority:
    1. Explicit FBO node with settings
    2. Heuristics based on connected pass types
    3. Defaults

    Returns:
        Dict with ResourceSpec parameters, or None if defaults are OK.
    """
    # Check if there's an FBO node providing this resource
    if resource_name in fbo_nodes:
        node = fbo_nodes[resource_name]
        spec = {"resource": resource_name}

        # Get parameters from FBO node
        fmt = node.get_param("format")
        if fmt:
            spec["format"] = fmt

        samples = node.get_param("samples")
        if samples:
            try:
                spec["samples"] = int(samples)
            except ValueError:
                pass

        # Size mode: viewport or fixed
        size_mode = node.get_param("size_mode")
        if size_mode == "fixed":
            # Use explicit size
            width = node.get_param("width")
            height = node.get_param("height")
            if width and height:
                try:
                    spec["size"] = (int(width), int(height))
                except ValueError:
                    pass
        else:
            # Viewport mode - use scale
            scale = node.get_param("scale")
            if scale:
                try:
                    scale_value = float(scale)
                    if scale_value != 1.0:
                        spec["scale"] = scale_value
                except ValueError:
                    pass

        # Clear color
        if node.get_param("clear_color"):
            r = node.get_param("clear_color_r") or 0.0
            g = node.get_param("clear_color_g") or 0.0
            b = node.get_param("clear_color_b") or 0.0
            a = node.get_param("clear_color_a") or 1.0
            spec["clear_color"] = (float(r), float(g), float(b), float(a))

        # Clear depth
        if node.get_param("clear_depth"):
            depth_value = node.get_param("clear_depth_value")
            if depth_value is not None:
                spec["clear_depth"] = float(depth_value)
            else:
                spec["clear_depth"] = 1.0

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


def collect_fbo_nodes(
    nodes: List["GraphNode"],
    socket_names: Dict["NodeSocket", str],
) -> Dict[str, "GraphNode"]:
    """
    Collect FBO resource nodes and map by their socket names.

    Uses socket_names to get the actual resource name used in the pipeline,
    not the user-defined "name" parameter.
    """
    fbo_nodes = {}

    for node in nodes:
        if node.node_type != "resource":
            continue
        if node.data.get("resource_type") != "fbo":
            continue

        # Get resource name from output socket (same as used in pipeline)
        for socket in node.output_sockets:
            if socket in socket_names:
                fbo_nodes[socket_names[socket]] = node

    return fbo_nodes


def create_pass_instance(
    node: "GraphNode",
    resource_params: Dict[str, str],
    viewport_name: str = "",
) -> Any:
    """
    Create a FramePass instance from a graph node.

    Args:
        node: Graph node with pass_class in data
        resource_params: Dict of resource name parameters (input_res, output_res, etc.)
        viewport_name: Viewport name from containing ViewportFrame (empty = offscreen)

    Returns:
        FramePass instance
    """
    from termin.nodegraph.pass_registry import get_pass_class

    class_name = node.data.get("pass_class", node.title)
    pass_cls = get_pass_class(class_name)

    if pass_cls is None:
        raise CompileError(f"Unknown pass class: {class_name}")

    # Build constructor kwargs
    kwargs = {}

    # Pass name
    kwargs["pass_name"] = node.name if node.name else node.title

    # Resource parameters (filter out viewport_name if present)
    for key, value in resource_params.items():
        if key != "viewport_name":
            kwargs[key] = value

    # Viewport name - assign from containing frame (as separate param, not resource)
    if viewport_name:
        kwargs["viewport_name"] = viewport_name

    # UI parameters from node
    for param in node._params:
        value = node._param_values.get(param.name)
        if value is not None and param.name not in resource_params:
            kwargs[param.name] = value

    # Try to create instance, handling optional parameters
    try:
        return pass_cls(**kwargs)
    except TypeError as e:
        # Some parameters might not be accepted - try with just basics
        import inspect
        sig = inspect.signature(pass_cls.__init__)
        valid_params = set(sig.parameters.keys())

        # Check if class accepts **kwargs (VAR_KEYWORD)
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )

        basic_kwargs = {"pass_name": kwargs.get("pass_name", node.title)}

        for key, value in kwargs.items():
            # Include param if it's in signature OR class accepts **kwargs
            if key in valid_params or has_var_keyword:
                basic_kwargs[key] = value

        try:
            instance = pass_cls(**basic_kwargs)
            # Set remaining params as attributes if possible
            for key, value in kwargs.items():
                if key not in basic_kwargs:
                    # Always set viewport_name if not in constructor
                    if key == "viewport_name":
                        instance.viewport_name = value
            return instance
        except TypeError:
            raise CompileError(f"Failed to create {class_name}: {e}")


def build_canonical_resource_map(passes: List[Any]) -> Dict[str, str]:
    """
    Build a map from resource names to their canonical names.

    Inplace passes create aliases: input and output refer to the same FBO.
    We need to track these and use only canonical names for ResourceSpecs.

    Returns:
        Dict mapping each resource name to its canonical name.
    """
    canonical: Dict[str, str] = {}

    for p in passes:
        # Get inplace aliases from the pass
        inplace_aliases = p.get_inplace_aliases()

        for src, dst in inplace_aliases:
            # Find canonical name for source
            src_canon = canonical.get(src, src)
            # Assign same canonical to destination
            canonical[dst] = src_canon
            # Also ensure source points to canonical
            canonical[src] = src_canon

    return canonical


def compile_graph(scene: "NodeGraphScene", debug: bool = False) -> "RenderPipeline":
    """
    Compile a node graph into a RenderPipeline.

    Steps:
    1. Collect pass nodes, FBO nodes, and viewport frames
    2. Build node-to-viewport mapping
    3. Resolve resource names from connections
    4. Create pass instances with viewport_name
    5. Use FrameGraph for topological sort
    6. Build canonical resource map (for inplace aliases)
    7. Infer ResourceSpecs with viewport_name
    8. Assemble RenderPipeline

    Args:
        scene: NodeGraphScene to compile
        debug: Print debug info about viewport containment

    Returns:
        RenderPipeline ready for use
    """
    from termin.visualization.render.framegraph import RenderPipeline
    from termin.visualization.render.framegraph.resource_spec import ResourceSpec
    from termin.visualization.render.framegraph.core import FrameGraph

    nodes = scene.get_nodes()
    connections = scene.get_connections()
    viewport_frames = scene.get_viewport_frames()

    # Separate node types
    pass_nodes = [n for n in nodes if n.node_type in ("pass", "effect")]

    if not pass_nodes:
        return RenderPipeline(name="empty", passes=[], pipeline_specs=[])

    # Build node to viewport mapping
    node_viewport_map = build_node_viewport_map(nodes, viewport_frames, debug=debug)

    # Resolve resource names, types, and target aliases
    socket_names, resource_types, target_aliases = resolve_resource_names(nodes, connections)

    # Collect FBO nodes mapped by their socket names
    fbo_nodes_map = collect_fbo_nodes(nodes, socket_names)

    # Build resource to viewport mapping from FBO nodes positions
    # (viewport_name is determined by which ViewportFrame contains the FBO node)
    resource_to_viewport: Dict[str, str] = {}
    for node in nodes:
        if node.node_type == "resource":
            # Get the resource name from the FBO node's output socket
            for socket in node.output_sockets:
                if socket in socket_names:
                    res_name = socket_names[socket]
                    viewport_name = node_viewport_map.get(node, "")
                    resource_to_viewport[res_name] = viewport_name

    # Create pass instances
    passes = []
    resource_to_passes: Dict[str, List[str]] = {}  # For spec inference

    for node in pass_nodes:
        resource_params = get_socket_resource_params(node, socket_names)
        viewport_name = node_viewport_map.get(node, "")

        try:
            pass_instance = create_pass_instance(node, resource_params, viewport_name)
            passes.append(pass_instance)

            # Track which passes use which resources
            class_name = node.data.get("pass_class", node.title)
            for res_name in resource_params.values():
                resource_to_passes.setdefault(res_name, []).append(class_name)
        except CompileError as e:
            print(f"Warning: {e}")
            continue

    # Use FrameGraph for topological sort
    try:
        frame_graph = FrameGraph(passes)
        sorted_passes = frame_graph.build_schedule()

        # Get canonical resource names from FrameGraph
        canonical_map = frame_graph._canonical_resources
    except Exception as e:
        print(f"Warning: Topological sort failed: {e}, using original order")
        sorted_passes = passes
        # Build our own canonical map
        canonical_map = build_canonical_resource_map(passes)

    # Infer ResourceSpecs only for canonical FBO resources
    # Skip shadow maps and other non-FBO resource types
    pipeline_specs = []
    seen_canonical: Set[str] = set()

    for res_name, pass_classes in resource_to_passes.items():
        # Skip non-FBO resources (shadow maps, etc.)
        res_type = resource_types.get(res_name, "fbo")
        if res_type != "fbo":
            continue

        # Get canonical name
        canon_name = canonical_map.get(res_name, res_name)

        if canon_name in seen_canonical:
            continue
        seen_canonical.add(canon_name)

        # Check if this resource has a _target alias to an FBO
        # If so, use the FBO's name for ResourceSpec (input name of the resource)
        # The output_res name is the "output name" used by downstream passes
        fbo_name = target_aliases.get(res_name)
        if fbo_name:
            # Resource has FBO via _target - use FBO name for spec
            spec_params = infer_resource_spec(fbo_name, fbo_nodes_map, pass_classes)
        else:
            # No _target connection - use auto-generated name
            spec_params = infer_resource_spec(canon_name, fbo_nodes_map, pass_classes)

        if spec_params:
            # Add viewport_name to spec - check both the resource and its FBO alias
            viewport_name = resource_to_viewport.get(res_name, "")
            if not viewport_name and fbo_name and fbo_name in resource_to_viewport:
                viewport_name = resource_to_viewport[fbo_name]
            if viewport_name:
                spec_params["viewport_name"] = viewport_name

            try:
                spec = ResourceSpec(**spec_params)
                pipeline_specs.append(spec)
            except Exception:
                pass

    return RenderPipeline(
        name="compiled_graph",
        passes=sorted_passes,
        pipeline_specs=pipeline_specs,
    )


def compile_graph_to_dict(scene: "NodeGraphScene", debug: bool = False) -> dict:
    """
    Compile graph and return serialized pipeline dict.

    Convenient for debugging and display.
    """
    pipeline = compile_graph(scene, debug=debug)
    return pipeline.serialize()
