"""Tool — attached auto-drawer with persistent settings for a Layer.

Tools hold AI-generation config (prompt, steps, seed, etc.).
Mask is owned by Layer, not by Tool — tools access it via the layer reference.
"""

from __future__ import annotations

import io
import zipfile
from abc import ABC, abstractmethod

import numpy as np
from PIL import Image


def _save_array_to_zip(zf: zipfile.ZipFile, path: str, arr: np.ndarray):
    buf = io.BytesIO()
    np.save(buf, arr)
    zf.writestr(path, buf.getvalue())


def _load_array_from_zip(zf: zipfile.ZipFile, path: str,
                          mode: str | None = None) -> np.ndarray:
    data = zf.read(path)
    if path.endswith('.npy'):
        return np.load(io.BytesIO(data))
    img = Image.open(io.BytesIO(data))
    if mode:
        img = img.convert(mode)
    return np.array(img, dtype=np.uint8)


def _load_pil_from_zip(zf: zipfile.ZipFile, path: str,
                        mode: str = "RGB") -> Image.Image:
    data = zf.read(path)
    if path.endswith('.npy'):
        arr = np.load(io.BytesIO(data))
        return Image.fromarray(arr).convert(mode)
    return Image.open(io.BytesIO(data)).convert(mode)


class Tool(ABC):
    """Abstract auto-drawer attached to a Layer."""

    tool_type: str = ""

    @abstractmethod
    def to_dict(self, path: str, file_key: str) -> dict:
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, d: dict, zf: zipfile.ZipFile) -> "Tool":
        ...

    @abstractmethod
    def save_assets_to_zip(self, zf: zipfile.ZipFile, file_key: str):
        ...


class DiffusionTool(Tool):
    tool_type = "diffusion"

    def __init__(self,
                 source_patch: Image.Image | None,
                 patch_x: int, patch_y: int, patch_w: int, patch_h: int,
                 prompt: str, negative_prompt: str,
                 strength: float, guidance_scale: float, steps: int,
                 seed: int,
                 model_path: str = "", prediction_type: str = "",
                 mode: str = "inpaint"):
        self.mode = mode
        self.source_patch = source_patch
        self.patch_x = patch_x
        self.patch_y = patch_y
        self.patch_w = patch_w
        self.patch_h = patch_h
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.strength = strength
        self.guidance_scale = guidance_scale
        self.steps = steps
        self.seed = seed
        self.model_path = model_path
        self.prediction_type = prediction_type
        self.ip_adapter_rect: tuple[int, int, int, int] | None = None
        self.ip_adapter_scale: float = 0.6
        self.masked_content: str = "original"
        self.manual_patch_rect: tuple[int, int, int, int] | None = None
        self.resize_to_model_resolution: bool = False

    def to_dict(self, path: str, file_key: str) -> dict:
        return {
            "tool_type": self.tool_type,
            "mode": self.mode,
            "source_file": f"layers/{file_key}_source.npy" if self.source_patch is not None else None,
            "patch_x": self.patch_x,
            "patch_y": self.patch_y,
            "patch_w": self.patch_w,
            "patch_h": self.patch_h,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "strength": self.strength,
            "guidance_scale": self.guidance_scale,
            "steps": self.steps,
            "seed": self.seed,
            "model_path": self.model_path,
            "prediction_type": self.prediction_type,
            "ip_adapter_rect": list(self.ip_adapter_rect) if self.ip_adapter_rect else None,
            "ip_adapter_scale": self.ip_adapter_scale,
            "masked_content": self.masked_content,
            "manual_patch_rect": list(self.manual_patch_rect) if self.manual_patch_rect else None,
            "resize_to_model_resolution": self.resize_to_model_resolution,
        }

    def save_assets_to_zip(self, zf: zipfile.ZipFile, file_key: str):
        if self.source_patch is not None:
            _save_array_to_zip(zf, f"layers/{file_key}_source.npy",
                               np.array(self.source_patch))

    @classmethod
    def from_dict(cls, d: dict, zf: zipfile.ZipFile) -> "DiffusionTool":
        source_patch = None
        if d.get("source_file") and d["source_file"] in zf.namelist():
            source_patch = _load_pil_from_zip(zf, d["source_file"], mode="RGB")

        tool = cls.__new__(cls)
        tool.source_patch = source_patch
        tool.patch_x = d["patch_x"]
        tool.patch_y = d["patch_y"]
        tool.patch_w = d["patch_w"]
        tool.patch_h = d["patch_h"]
        tool.prompt = d["prompt"]
        tool.negative_prompt = d["negative_prompt"]
        tool.strength = d["strength"]
        tool.guidance_scale = d["guidance_scale"]
        tool.steps = d["steps"]
        tool.seed = d["seed"]
        tool.model_path = d.get("model_path", "")
        tool.prediction_type = d.get("prediction_type", "")
        tool.mode = d.get("mode", "inpaint")
        rect = d.get("ip_adapter_rect")
        tool.ip_adapter_rect = tuple(rect) if rect else None
        tool.ip_adapter_scale = d.get("ip_adapter_scale", 0.6)
        tool.masked_content = d.get("masked_content", "original")
        mpr = d.get("manual_patch_rect")
        tool.manual_patch_rect = tuple(mpr) if mpr else None
        tool.resize_to_model_resolution = d.get("resize_to_model_resolution", False)
        return tool


class LamaTool(Tool):
    tool_type = "lama"

    def __init__(self,
                 source_patch: Image.Image | None,
                 patch_x: int, patch_y: int, patch_w: int, patch_h: int):
        self.source_patch = source_patch
        self.patch_x = patch_x
        self.patch_y = patch_y
        self.patch_w = patch_w
        self.patch_h = patch_h

    def to_dict(self, path: str, file_key: str) -> dict:
        return {
            "tool_type": self.tool_type,
            "source_file": f"layers/{file_key}_source.npy" if self.source_patch is not None else None,
            "patch_x": self.patch_x,
            "patch_y": self.patch_y,
            "patch_w": self.patch_w,
            "patch_h": self.patch_h,
        }

    def save_assets_to_zip(self, zf: zipfile.ZipFile, file_key: str):
        if self.source_patch is not None:
            _save_array_to_zip(zf, f"layers/{file_key}_source.npy",
                               np.array(self.source_patch))

    @classmethod
    def from_dict(cls, d: dict, zf: zipfile.ZipFile) -> "LamaTool":
        source_patch = None
        if d.get("source_file") and d["source_file"] in zf.namelist():
            source_patch = _load_pil_from_zip(zf, d["source_file"], mode="RGB")

        tool = cls.__new__(cls)
        tool.source_patch = source_patch
        tool.patch_x = d["patch_x"]
        tool.patch_y = d["patch_y"]
        tool.patch_w = d["patch_w"]
        tool.patch_h = d["patch_h"]
        return tool


class InstructTool(Tool):
    tool_type = "instruct"

    def __init__(self,
                 source_patch: Image.Image | None,
                 patch_x: int, patch_y: int, patch_w: int, patch_h: int,
                 instruction: str = "",
                 image_guidance_scale: float = 1.5,
                 guidance_scale: float = 7.0,
                 steps: int = 20,
                 seed: int = -1):
        self.source_patch = source_patch
        self.patch_x = patch_x
        self.patch_y = patch_y
        self.patch_w = patch_w
        self.patch_h = patch_h
        self.instruction = instruction
        self.image_guidance_scale = image_guidance_scale
        self.guidance_scale = guidance_scale
        self.steps = steps
        self.seed = seed
        self.manual_patch_rect: tuple[int, int, int, int] | None = None

    def to_dict(self, path: str, file_key: str) -> dict:
        return {
            "tool_type": self.tool_type,
            "source_file": f"layers/{file_key}_source.npy" if self.source_patch is not None else None,
            "patch_x": self.patch_x,
            "patch_y": self.patch_y,
            "patch_w": self.patch_w,
            "patch_h": self.patch_h,
            "instruction": self.instruction,
            "image_guidance_scale": self.image_guidance_scale,
            "guidance_scale": self.guidance_scale,
            "steps": self.steps,
            "seed": self.seed,
            "manual_patch_rect": list(self.manual_patch_rect) if self.manual_patch_rect else None,
        }

    def save_assets_to_zip(self, zf: zipfile.ZipFile, file_key: str):
        if self.source_patch is not None:
            _save_array_to_zip(zf, f"layers/{file_key}_source.npy",
                               np.array(self.source_patch))

    @classmethod
    def from_dict(cls, d: dict, zf: zipfile.ZipFile) -> "InstructTool":
        source_patch = None
        if d.get("source_file") and d["source_file"] in zf.namelist():
            source_patch = _load_pil_from_zip(zf, d["source_file"], mode="RGB")

        tool = cls.__new__(cls)
        tool.source_patch = source_patch
        tool.patch_x = d["patch_x"]
        tool.patch_y = d["patch_y"]
        tool.patch_w = d["patch_w"]
        tool.patch_h = d["patch_h"]
        tool.instruction = d.get("instruction", "")
        tool.image_guidance_scale = d.get("image_guidance_scale", 1.5)
        tool.guidance_scale = d.get("guidance_scale", 7.0)
        tool.steps = d.get("steps", 20)
        tool.seed = d.get("seed", -1)
        mpr = d.get("manual_patch_rect")
        tool.manual_patch_rect = tuple(mpr) if mpr else None
        return tool


# Registry for deserialization dispatch
_TOOL_REGISTRY: dict[str, type[Tool]] = {
    "diffusion": DiffusionTool,
    "lama": LamaTool,
    "instruct": InstructTool,
}


def tool_from_dict(d: dict, zf: zipfile.ZipFile) -> Tool | None:
    """Deserialize a tool from its dict representation.

    Supports both new format (tool_type field) and legacy format
    (type field = diffusion/lama/instruct).
    """
    tool_type = d.get("tool_type") or d.get("type")
    if not tool_type or tool_type not in _TOOL_REGISTRY:
        return None
    if tool_type == "layer":
        return None
    return _TOOL_REGISTRY[tool_type].from_dict(d, zf)
