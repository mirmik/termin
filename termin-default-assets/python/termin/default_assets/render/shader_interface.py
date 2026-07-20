"""Canonical shader interface comparison helpers for hot reload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PropertySignature = tuple[str, str]
GraphInputSignature = tuple[PropertySignature, ...]


@dataclass(frozen=True)
class ShaderInterfaceChange:
    material_changed: bool
    graph_inputs_changed: bool


def _property_signature(prop: dict) -> PropertySignature:
    return (str(prop["name"]), str(prop["property_type"]))


def shader_material_interface_signature(program: Any | None) -> tuple[Any, ...]:
    """Snapshot the material-facing part of a canonical TcShaderProgram."""
    if program is None or not program.is_valid:
        return ()

    result: list[Any] = [
        (
            "properties",
            tuple(
                (
                    prop["name"],
                    prop["property_type"],
                    prop.get("default"),
                    prop["range_min"],
                    prop["range_max"],
                )
                for prop in program.properties
            ),
        )
    ]
    for phase in program.phases:
        shader = phase["shader"]
        state = phase["state"]
        result.append(
            (
                phase["phase_mark"],
                phase["priority"],
                tuple(sorted(state.items())),
                shader.material_ubo_block_size,
                shader.material_ubo_entry_count,
                repr(shader.contract),
            )
        )
    return tuple(result)


def shader_graph_input_signature(program: Any | None) -> GraphInputSignature:
    if program is None or not program.is_valid:
        return ()
    return tuple(
        _property_signature(prop)
        for prop in program.properties
        if prop["property_type"] in ("Texture", "Texture2D")
    )


def compare_shader_interface(old_program: Any | None, new_program: Any | None) -> ShaderInterfaceChange:
    old_material = shader_material_interface_signature(old_program)
    new_material = shader_material_interface_signature(new_program)
    old_graph_inputs = shader_graph_input_signature(old_program)
    new_graph_inputs = shader_graph_input_signature(new_program)
    return ShaderInterfaceChange(
        material_changed=old_material != new_material,
        graph_inputs_changed=old_graph_inputs != new_graph_inputs,
    )
