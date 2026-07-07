from __future__ import annotations

import struct
from typing import Any, Callable, Set

from termin.inspect import InspectField
from termin.render_framework.python_pass import PythonFramePass
from tgfx import TcShader
from tgfx._tgfx_native import CULL_NONE, Tgfx2ShaderHandle, tc_shader_ensure_tgfx2

from termin.render_passes._render_passes_native import tc_picking_id_to_rgb


_HIGHLIGHT_SHADER_UUID = "termin-engine-highlight"


def _pick_id_to_rgb_float(pick_id: int) -> tuple[float, float, float]:
    r, g, b = tc_picking_id_to_rgb(pick_id)
    return float(r) / 255.0, float(g) / 255.0, float(b) / 255.0


def _pack_uniform_fields(layout: dict[str, Any], values: dict[str, Any]) -> bytes:
    """Pack values into a byte buffer using the shader's field layout."""
    total_size = layout.get("size", 0)
    buf = bytearray(total_size)
    for field in layout.get("fields", []):
        name = field["name"]
        offset = field["offset"]
        field_size = field["size"]
        if name not in values:
            continue
        val = values[name]
        if isinstance(val, (int, float)):
            if field_size == 4:
                struct.pack_into("=f", buf, offset, float(val))
            elif field_size == 8:
                struct.pack_into("=f", buf, offset, 0.0)
            elif field_size == 12:
                struct.pack_into("=f", buf, offset, float(val))
        elif isinstance(val, (tuple, list)):
            if field_size == 8:
                struct.pack_into("=2f", buf, offset, *val)
            elif field_size == 12:
                struct.pack_into("=3f", buf, offset, *val)
    return bytes(buf)


class HighlightPass(PythonFramePass):
    category = "Effects"

    node_inputs = [("input_res", "fbo"), ("id_res", "fbo")]
    node_outputs = [("output_res", "fbo")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "id_res": InspectField(path="id_res", label="ID Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "color": InspectField(path="color", label="Outline Color", kind="color"),
    }

    _shader: TcShader | None = None
    _params_layout: dict[str, Any] | None = None

    def __init__(
        self,
        selected_id_getter: Callable[[], int | None] | None = None,
        color=(0.0, 0.0, 0.0, 1.0),
        input_res: str = "color",
        id_res: str = "id",
        output_res: str = "color_highlight",
        pass_name: str = "Highlight",
    ) -> None:
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.id_res = id_res
        self.output_res = output_res
        self.color = color
        self._get_id = selected_id_getter

    def compute_reads(self) -> Set[str]:
        return {self.input_res, self.id_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    @classmethod
    def _ensure_params_layout(cls) -> dict[str, Any] | None:
        """Extract the u_params buffer field layout from the compiled shader."""
        if cls._params_layout is not None:
            return cls._params_layout
        if cls._shader is None or not cls._shader.is_valid:
            return None
        binding = cls._shader.find_resource_binding("u_params")
        if binding is None:
            return None
        cls._params_layout = {
            "size": binding.get("size", 48),
            "fields": binding.get("fields", []),
        }
        return cls._params_layout

    @classmethod
    def _ensure_fragment_shader(cls, ctx2) -> Tgfx2ShaderHandle:
        if cls._shader is None:
            cls._shader = TcShader.from_builtin_catalog(_HIGHLIGHT_SHADER_UUID)
        if not cls._shader.is_valid:
            return Tgfx2ShaderHandle()
        shader_result = tc_shader_ensure_tgfx2(ctx2, cls._shader)
        cls._ensure_params_layout()
        return shader_result.fs

    def _selected_id(self) -> int:
        if self._get_id is None:
            return 0
        selected_id = self._get_id()
        return int(selected_id) if selected_id is not None else 0

    def execute(self, ctx) -> None:
        from tcbase import log

        if ctx.ctx2 is None:
            log.error("[HighlightPass] ctx.ctx2 is None; pass is tgfx2-only")
            return

        color_tex2 = ctx.tex2_reads.get(self.input_res)
        target_tex2 = ctx.tex2_writes.get(self.output_res)
        if not color_tex2 or not target_tex2:
            log.warn(
                f"[HighlightPass] Missing tex2: input={bool(color_tex2)}, output={bool(target_tex2)}, "
                f"input_res='{self.input_res}', output_res='{self.output_res}'"
            )
            return

        ctx2 = ctx.ctx2
        fs = self._ensure_fragment_shader(ctx2)
        if not fs:
            log.error("[HighlightPass] fragment shader was not created")
            return

        tex_id2 = ctx.tex2_reads.get(self.id_res)
        selected_id = self._selected_id()
        enabled = tex_id2 is not None and selected_id > 0

        if enabled:
            sel_r, sel_g, sel_b = _pick_id_to_rgb_float(selected_id)
        else:
            sel_r = sel_g = sel_b = 0.0

        _, _, w, h = ctx.render_rect
        texel_x = 1.0 / max(1, int(w))
        texel_y = 1.0 / max(1, int(h))
        outline = self.color

        layout = self._ensure_params_layout()
        if layout and layout.get("fields"):
            params_bytes = _pack_uniform_fields(
                layout,
                {
                    "selected_color": (sel_r, sel_g, sel_b),
                    "enabled": 1.0 if enabled else 0.0,
                    "outline_color": (float(outline[0]), float(outline[1]), float(outline[2])),
                    "texel_size": (texel_x, texel_y),
                },
            )
        else:
            log.error("[HighlightPass] no u_params layout metadata from shader")
            return
        ctx2.begin_pass(target_tex2)
        ctx2.set_viewport(0, 0, int(w), int(h))
        ctx2.set_depth_test(False)
        ctx2.set_depth_write(False)
        ctx2.set_blend(False)
        ctx2.set_cull(CULL_NONE)
        try:
            ctx2.bind_shader(Tgfx2ShaderHandle(), fs)
            ctx2.use_shader_resource_layout(self._shader)
            ctx2.bind_texture_by_name("u_color", color_tex2)
            id_bind = tex_id2 if tex_id2 is not None else color_tex2
            ctx2.bind_texture_by_name("u_id", id_bind)
            ctx2.bind_uniform_by_name("u_params", params_bytes)
            ctx2.draw_fullscreen_quad()
        finally:
            ctx2.end_pass()

    def clear_callbacks(self) -> None:
        self._get_id = None


__all__ = ["HighlightPass"]
