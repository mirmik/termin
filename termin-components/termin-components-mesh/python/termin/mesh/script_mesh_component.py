"""ScriptMeshComponent - generate MeshComponent geometry from termin-csg code."""

from __future__ import annotations

import math

from tcbase import log
from termin.inspect import InspectField
from termin.mesh.mesh_component import MeshComponent
from termin.scene.python_component import PythonComponent
from termin.csg import Solid, to_tc_mesh
from tmesh import TcMesh
from termin.csg.cad import (
    Contour,
    box,
    circle,
    cone,
    contour,
    cylinder,
    extrude,
    polygon,
    rect,
    rotate,
    scale,
    sphere,
    translate,
)


def _generate_action(component) -> None:
    component.generate()


def _request_render_update() -> None:
    from termin.engine import RenderingManager

    manager = RenderingManager.instance_or_none()
    if manager is None:
        return

    try:
        manager.request_render_update()
    except Exception as e:
        log.error(f"[ScriptMeshComponent] Failed to request render update: {e}")


class ScriptMeshComponent(PythonComponent):
    """Builds a TcMesh from a small termin-csg script and writes MeshComponent."""

    required_components = ("MeshComponent",)

    inspect_fields = {
        "script": InspectField(
            path="script",
            label="Script",
            kind="string",
        ),
        "mesh_name": InspectField(
            path="mesh_name",
            label="Mesh Name",
            kind="string",
        ),
        "auto_generate": InspectField(
            path="auto_generate",
            label="Auto Generate",
            kind="bool",
        ),
        "contour_height": InspectField(
            path="contour_height",
            label="Contour Height",
            kind="float",
            min=0.001,
            max=1000.0,
            step=0.1,
        ),
        "flat_shading": InspectField(
            path="flat_shading",
            label="Flat Shading",
            kind="bool",
        ),
        "generate_btn": InspectField(
            path=None,
            label="Generate Mesh",
            kind="button",
            action=_generate_action,
            is_serializable=False,
        ),
    }

    def __init__(
        self,
        script: str = "box(2, 2, 2, center=True)",
        mesh_name: str = "script_mesh",
        auto_generate: bool = True,
        contour_height: float = 1.0,
        flat_shading: bool = True,
    ):
        super().__init__(enabled=True)
        self.script = script
        self.mesh_name = mesh_name
        self.auto_generate = auto_generate
        self.contour_height = contour_height
        self.flat_shading = flat_shading
        self._last_build_key = None

    def on_added(self) -> None:
        if self.auto_generate:
            self._generate_if_needed()

    def on_editor_start(self) -> None:
        if self.auto_generate:
            self._generate_if_needed()

    def start(self) -> None:
        if self.auto_generate:
            self._generate_if_needed()

    def _build_key(self) -> tuple[str, str, float, bool]:
        return (self.script, self.mesh_name, float(self.contour_height), bool(self.flat_shading))

    def _generate_if_needed(self) -> None:
        key = self._build_key()
        if self._last_build_key == key:
            return
        self.generate()

    def _script_env(self) -> dict:
        return {
            "Contour": Contour,
            "Solid": Solid,
            "TcMesh": TcMesh,
            "box": box,
            "circle": circle,
            "cone": cone,
            "contour": contour,
            "cylinder": cylinder,
            "extrude": extrude,
            "math": math,
            "polygon": polygon,
            "rect": rect,
            "rotate": rotate,
            "scale": scale,
            "sphere": sphere,
            "translate": translate,
            "__builtins__": {
                "abs": abs,
                "float": float,
                "int": int,
                "len": len,
                "max": max,
                "min": min,
                "range": range,
                "round": round,
                "sum": sum,
            },
        }

    def _evaluate_script(self):
        source = self.script.strip()
        if not source:
            raise ValueError("script is empty")

        env = self._script_env()
        local_env = {}
        try:
            code = compile(source, "<ScriptMeshComponent>", "eval")
            return eval(code, env, local_env)
        except SyntaxError:
            code = compile(source, "<ScriptMeshComponent>", "exec")
            exec(code, env, local_env)
            if "result" in local_env:
                return local_env["result"]
            if "mesh" in local_env:
                return local_env["mesh"]
            raise ValueError("script must be an expression or assign result/mesh") from None

    def _to_tc_mesh(self, value) -> TcMesh:
        value_type = type(value)
        if value_type is TcMesh:
            return value
        if value_type is Solid:
            return to_tc_mesh(value, self.mesh_name, flat_shading=bool(self.flat_shading))
        if value_type is Contour:
            solid = value.extrude(self.contour_height)
            return to_tc_mesh(solid, self.mesh_name, flat_shading=bool(self.flat_shading))
        raise TypeError(f"script returned unsupported value: {value_type.__name__}")

    def _mesh_component(self):
        ent = self.entity
        if ent is None:
            log.error("[ScriptMeshComponent] Generate failed: component has no entity")
            return None

        comp = ent.get_component(MeshComponent)
        if comp is not None:
            return comp

        try:
            ent.add_component_by_name("MeshComponent")
            comp = ent.get_component(MeshComponent)
        except Exception as e:
            log.error(f"[ScriptMeshComponent] Failed to add MeshComponent: {e}")
            return None

        if comp is None:
            log.error("[ScriptMeshComponent] Failed to resolve MeshComponent after add")
            return None
        return comp

    def generate(self) -> None:
        try:
            value = self._evaluate_script()
            tc_mesh = self._to_tc_mesh(value)
        except Exception as e:
            log.error(f"[ScriptMeshComponent] Generate failed: {e}")
            return

        mesh_component = self._mesh_component()
        if mesh_component is None:
            return

        mesh_component.set_mesh(tc_mesh)
        _request_render_update()
        self._last_build_key = self._build_key()
        log.info(
            f"[ScriptMeshComponent] Generated mesh '{self.mesh_name}' "
            f"verts={tc_mesh.vertex_count} tris={tc_mesh.triangle_count}"
        )


__all__ = ["ScriptMeshComponent"]
