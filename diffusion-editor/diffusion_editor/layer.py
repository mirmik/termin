import io
import json
import logging
import zipfile

import numpy as np
from PIL import Image

from .tiles import DenseTileGrid
from .tool import (
    Tool, DiffusionTool, LamaTool, InstructTool, tool_from_dict,
    _save_array_to_zip, _load_array_from_zip,
)

logger = logging.getLogger(__name__)


class Layer:
    def __init__(self, name: str, width: int, height: int,
                 image: np.ndarray = None, tile_size: int = 256):
        self.name = name
        self.visible = True
        self.opacity = 1.0
        self.children: list['Layer'] = []
        self.parent: 'Layer | None' = None
        if image is not None:
            arr = np.ascontiguousarray(image.astype(np.uint8))
        else:
            arr = np.zeros((height, width, 4), dtype=np.uint8)
        self.content = DenseTileGrid.from_array(arr, tile_size=tile_size)
        self.image = self.content.array
        self.tool: Tool | None = None

    def add_child(self, child: 'Layer', index: int | None = None):
        if child.parent is not None:
            child.parent.remove_child(child)
        child.parent = self
        if index is not None:
            self.children.insert(index, child)
        else:
            self.children.append(child)

    def remove_child(self, child: 'Layer'):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def all_descendants(self) -> list['Layer']:
        result = []
        for child in self.children:
            result.append(child)
            result.extend(child.all_descendants())
        return result

    @property
    def width(self):
        return self.content.width

    @property
    def height(self):
        return self.content.height

    def to_dict(self, path: str) -> dict:
        file_key = path.replace("/", "_")
        d = {
            "path": path,
            "type": "layer",
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity,
            "image_file": f"layers/{file_key}_image.npy",
            "children": [],
        }
        if self.tool is not None:
            d["tool"] = self.tool.to_dict(path, file_key)
        for i, child in enumerate(self.children):
            d["children"].append(child.to_dict(f"{path}/{i}"))
        return d

    def save_images_to_zip(self, zf: zipfile.ZipFile, path: str):
        file_key = path.replace("/", "_")
        _save_array_to_zip(zf, f"layers/{file_key}_image.npy", self.image)
        if self.tool is not None:
            self.tool.save_assets_to_zip(zf, file_key)
        for i, child in enumerate(self.children):
            child.save_images_to_zip(zf, f"{path}/{i}")

    @classmethod
    def from_dict(cls, d: dict, zf: zipfile.ZipFile, tile_size: int = 256) -> "Layer":
        arr = _load_array_from_zip(zf, d["image_file"], mode="RGBA")
        layer = cls.__new__(cls)
        layer.name = d["name"]
        layer.visible = d["visible"]
        layer.opacity = d["opacity"]
        layer.content = DenseTileGrid.from_array(arr, tile_size=tile_size)
        layer.image = layer.content.array
        layer.children = []
        layer.parent = None
        layer.tool = None
        if "tool" in d:
            layer.tool = tool_from_dict(d["tool"], zf)
        for child_dict in d.get("children", []):
            child = _layer_from_dict(child_dict, zf, tile_size=tile_size)
            child.parent = layer
            layer.children.append(child)
        return layer


def _layer_from_dict(d: dict, zf: zipfile.ZipFile, tile_size: int = 256) -> Layer:
    """Dispatch layer deserialization by type.

    Supports both the new unified format (type=layer + optional tool sub-dict)
    and the legacy format (type=diffusion/lama/instruct with tool data inline).
    """
    layer_type = d.get("type", "layer")

    if layer_type in ("diffusion", "lama", "instruct"):
        # Legacy format: tool data is inline in the layer dict.
        # Load as a plain Layer, then attach the tool from the same dict.
        layer = Layer.from_dict(d, zf, tile_size=tile_size)
        layer.tool = tool_from_dict(d, zf)
        return layer

    return Layer.from_dict(d, zf, tile_size=tile_size)
