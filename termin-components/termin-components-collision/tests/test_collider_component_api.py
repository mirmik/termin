from termin.colliders.collider_component import ColliderComponent


def test_capsule_component_box_size_maps_to_capsule_dimensions():
    component = ColliderComponent()
    component.collider_type = "Capsule"
    component.box_size = (0.2, 0.4, 1.0)

    collider = component.collider

    assert collider.half_height == 0.5
    assert collider.radius == 0.1


def test_collider_component_exposes_offset_fields_to_python():
    component = ColliderComponent()

    component.collider_offset_enabled = True
    component.collider_offset_position = (1.0, 2.0, 3.0)
    component.collider_offset_euler = (10.0, 20.0, 30.0)

    assert component.collider_offset_enabled is True
    assert component.collider_offset_position == (1.0, 2.0, 3.0)
    assert component.collider_offset_euler == (10.0, 20.0, 30.0)
