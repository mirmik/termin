from termin.editor_tcgui.material_inspector import MaterialInspectorTcgui
from tgfx import TcTexture


class _Phase:
    def __init__(self) -> None:
        self.assigned: list[tuple[str, object]] = []
        self.textures = {"u_albedo_texture": None}

    def set_texture(self, uniform_name: str, texture) -> None:
        self.assigned.append((uniform_name, texture))


class _Material:
    def __init__(self) -> None:
        self.name = "TestMaterial"
        self.phases = [_Phase()]

    def set_texture(self, uniform_name: str, texture) -> int:
        applied = 0
        for phase in self.phases:
            if uniform_name in phase.textures:
                phase.set_texture(uniform_name, texture)
                applied += 1
        return applied


class _ResourceManager:
    def find_material_name(self, material) -> None:
        return None


def test_material_inspector_default_texture_assigns_tc_texture() -> None:
    inspector = MaterialInspectorTcgui.__new__(MaterialInspectorTcgui)
    inspector._material = _Material()
    inspector._rm = _ResourceManager()
    inspector.on_changed = None

    inspector._set_texture_all_phases("u_albedo_texture", "default", "", "white")

    assigned = inspector._material.phases[0].assigned
    assert len(assigned) == 1
    assert assigned[0][0] == "u_albedo_texture"
    assert isinstance(assigned[0][1], TcTexture)
    assert assigned[0][1].is_valid
