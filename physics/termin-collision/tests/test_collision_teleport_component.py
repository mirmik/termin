from __future__ import annotations

from types import SimpleNamespace

from termin.base import Action, MouseButton
from termin.colliders import teleport_component
from termin.colliders.teleport_component import TeleportComponent
from termin.geombase import Vec3


class _FakeTransform:
    def __init__(self) -> None:
        self.global_position = None

    def set_global_position(self, position: Vec3) -> None:
        self.global_position = position


def test_teleport_component_uses_collision_world_from_scene(monkeypatch) -> None:
    scene = object()
    ray = object()
    target_entity = SimpleNamespace(transform=_FakeTransform())
    hit = SimpleNamespace(
        valid=True,
        entity=object(),
        collider_point=Vec3(1.0, 2.0, 3.0),
    )
    calls = []

    class FakeCollisionWorld:
        def raycast_closest(self, actual_ray):
            calls.append(("raycast_closest", actual_ray))
            return hit

    def from_scene(actual_scene):
        calls.append(("from_scene", actual_scene))
        return FakeCollisionWorld()

    monkeypatch.setattr(
        teleport_component,
        "CollisionWorld",
        SimpleNamespace(from_scene=from_scene),
    )

    event = SimpleNamespace(
        button=MouseButton.LEFT,
        action=Action.PRESS,
        x=42,
        y=77,
        viewport=SimpleNamespace(
            scene=scene,
            screen_point_to_ray=lambda x, y: ray,
        ),
    )

    TeleportComponent.on_mouse_button(SimpleNamespace(entity=target_entity), event)

    assert calls == [("from_scene", scene), ("raycast_closest", ray)]
    assert target_entity.transform.global_position == hit.collider_point
