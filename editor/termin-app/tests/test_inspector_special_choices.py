from __future__ import annotations

from dataclasses import dataclass

from termin.editor_core.inspector_special_choices import InspectorSpecialChoices


@dataclass
class _Clip:
    value: str

    def name(self) -> str:
        return self.value


class _Settings:
    def get_agent_type_names(self):
        return ["Human", "Vehicle"]


class _Navigation:
    settings = _Settings()

    def navmesh_area_label(self, index: int) -> str:
        return "Walkable" if index == 0 else f"Area {index}"


def test_special_inspector_choices_cover_navigation_and_component_clips():
    provider = InspectorSpecialChoices(
        navigation_settings=_Navigation,
        target_clips=lambda _targets: (
            {"name": "Walk"},
            _Clip("Run"),
            _Clip("Walk"),
            {"name": ""},
        ),
    )

    assert provider.choices("agent_type", ()) == (
        ("Human", "Human"),
        ("Vehicle", "Vehicle"),
    )
    areas = provider.choices("navmesh_area", ())
    assert len(areas) == 64
    assert areas[0] == (0, "0: Walkable")
    assert areas[63] == (63, "63: Area 63")
    assert provider.choices("clip_selector", (object(),)) == (
        ("", "(none)"),
        ("Run", "Run"),
        ("Walk", "Walk"),
    )
    assert provider.choices("unknown", ()) is None
