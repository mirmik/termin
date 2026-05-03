"""Agent tools for diffusion-editor — manipulate layers, canvas, etc."""

from __future__ import annotations

from nemor.core.tool_registry import ToolRegistry

from .commands import (
    AddLayerCommand,
    RemoveLayerCommand,
    SetLayerVisibilityCommand,
    SetLayerOpacityCommand,
)


def _get_layer_stack(config):
    return config["_layer_stack"]


def _get_document(config):
    return config["_document_service"]


def _find_layer(layer_stack, name: str):
    for layer in layer_stack._all_layers_flat():
        if layer.name == name:
            return layer
    return None


def _on_main(config, func):
    run = config.get("_run_on_main_thread")
    if run is None:
        return func()
    return run(func)


# ── Tool implementations ────────────────────────────────────────────────────


def _tool_list_layers(args, config):
    def op():
        layer_stack = _get_layer_stack(config)
        layers = layer_stack._all_layers_flat()
        if not layers:
            return "(no layers)"
        lines = []
        for i, layer in enumerate(layers):
            active = " [active]" if layer is layer_stack.active_layer else ""
            lines.append(
                f"  [{i}] {layer.name}: type={type(layer).__name__}, "
                f"visible={layer.visible}, opacity={layer.opacity:.0%}{active}"
            )
        w, h = layer_stack.width, layer_stack.height
        lines.append(f"Canvas: {w}x{h}, {len(layers)} layers total")
        return "\n".join(lines)

    return _on_main(config, op)


def _tool_add_layer(args, config):
    name = args["name"]

    def op():
        document = _get_document(config)
        document.execute(AddLayerCommand(name=name))
        return f"Layer '{name}' created."

    return _on_main(config, op)


def _tool_remove_layer(args, config):
    name = args["name"]

    def op():
        document = _get_document(config)
        layer_stack = _get_layer_stack(config)
        layer = _find_layer(layer_stack, name)
        if layer is None:
            return f"Layer '{name}' not found."
        document.execute(RemoveLayerCommand(layer=layer))
        return f"Layer '{name}' removed."

    return _on_main(config, op)


def _tool_set_layer_visibility(args, config):
    name = args["name"]
    visible = args["visible"]

    def op():
        document = _get_document(config)
        layer_stack = _get_layer_stack(config)
        layer = _find_layer(layer_stack, name)
        if layer is None:
            return f"Layer '{name}' not found."
        document.execute(SetLayerVisibilityCommand(layer=layer, visible=visible))
        return f"Layer '{name}' visibility set to {visible}."

    return _on_main(config, op)


def _tool_set_layer_opacity(args, config):
    name = args["name"]
    opacity = float(args["opacity"])
    opacity = max(0.0, min(1.0, opacity))

    def op():
        document = _get_document(config)
        layer_stack = _get_layer_stack(config)
        layer = _find_layer(layer_stack, name)
        if layer is None:
            return f"Layer '{name}' not found."
        document.execute(SetLayerOpacityCommand(layer=layer, opacity=opacity))
        return f"Layer '{name}' opacity set to {opacity:.0%}."

    return _on_main(config, op)


def _tool_get_canvas_info(args, config):
    def op():
        layer_stack = _get_layer_stack(config)
        w, h = layer_stack.width, layer_stack.height
        active = layer_stack.active_layer
        active_name = active.name if active else "(none)"
        layers = layer_stack._all_layers_flat()
        return (
            f"Canvas: {w}x{h}\n"
            f"Active layer: {active_name}\n"
            f"Layer count: {len(layers)}"
        )

    return _on_main(config, op)


def _tool_view_canvas(args, config):
    import hashlib
    import io
    import os

    def op():
        from PIL import Image

        layer_stack = _get_layer_stack(config)
        arr = layer_stack.composite()

        img = Image.fromarray(arr, "RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_data = buf.getvalue()

        try:
            from nemor.images import (
                IMAGE_EXT_BY_MIME,
                prepare_image_for_llm,
            )
            data, mime = prepare_image_for_llm(png_data, "image/png")
            ext = IMAGE_EXT_BY_MIME[mime]
        except Exception:
            data, mime = png_data, "image/png"
            ext = ".png"

        nemor_dir = config.get("nemor_dir") or os.path.expanduser("~/.nemor")
        media_dir = os.path.join(nemor_dir, "media")
        os.makedirs(media_dir, exist_ok=True)

        file_hash = hashlib.sha1(data).hexdigest()[:12]
        dest_name = f"canvas_{file_hash}{ext}"
        dest_path = os.path.join(media_dir, dest_name)
        with open(dest_path, "wb") as f:
            f.write(data)

        w, h = img.size
        size = len(data)
        size_str = f"{size / 1024:.0f}KB" if size >= 1024 else f"{size}B"
        layer_count = len(layer_stack._all_layers_flat())

        filename = f"canvas_{w}x{h}{ext}"
        text = f"Canvas: {w}x{h}, {layer_count} layers ({size_str})"
        return {
            "text": text,
            "images": [{
                "path": dest_path,
                "url": f"/media/{dest_name}",
                "filename": filename,
                "mime": mime,
                "size": size,
            }],
        }

    return _on_main(config, op)


# ── Registry factory ────────────────────────────────────────────────────────


def create_editor_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register("list_layers", _tool_list_layers, {
        "type": "function",
        "function": {
            "name": "list_layers",
            "description": "List all layers in the document with their names, types, visibility, opacity, and active status. Includes canvas dimensions.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    })

    registry.register("add_layer", _tool_add_layer, {
        "type": "function",
        "function": {
            "name": "add_layer",
            "description": "Add a new empty layer to the document. The layer appears at the top of the stack.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Layer name"},
                },
                "required": ["name"],
            },
        },
    })

    registry.register("remove_layer", _tool_remove_layer, {
        "type": "function",
        "function": {
            "name": "remove_layer",
            "description": "Remove a layer by name. This action is undoable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact layer name to remove"},
                },
                "required": ["name"],
            },
        },
    })

    registry.register("set_layer_visibility", _tool_set_layer_visibility, {
        "type": "function",
        "function": {
            "name": "set_layer_visibility",
            "description": "Show or hide a layer by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact layer name"},
                    "visible": {"type": "boolean", "description": "True = visible, False = hidden"},
                },
                "required": ["name", "visible"],
            },
        },
    })

    registry.register("set_layer_opacity", _tool_set_layer_opacity, {
        "type": "function",
        "function": {
            "name": "set_layer_opacity",
            "description": "Set layer opacity (0.0 = fully transparent, 1.0 = fully opaque).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact layer name"},
                    "opacity": {"type": "number", "description": "Opacity value from 0.0 to 1.0"},
                },
                "required": ["name", "opacity"],
            },
        },
    })

    registry.register("get_canvas_info", _tool_get_canvas_info, {
        "type": "function",
        "function": {
            "name": "get_canvas_info",
            "description": "Get canvas dimensions, active layer name, and total layer count.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    })

    registry.register("view_canvas", _tool_view_canvas, {
        "type": "function",
        "function": {
            "name": "view_canvas",
            "description": "Capture the current canvas as an image so you can see the composite result of all visible layers. Use this to inspect what the user sees, verify your changes, or decide what to do next.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    })

    return registry
