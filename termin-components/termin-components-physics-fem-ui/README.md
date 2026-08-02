# Native FEM physics UI adapter

This optional adapter keeps presentation out of the FEM physics scene binding.
`FEMPhysicsWorldComponent` publishes a UI-neutral telemetry snapshot, while
`FEMPhysicsHudComponent` formats that snapshot into a native `UIComponent`
document. The HUD expects the named labels `energy_value`, `energy_change`,
`simulation_value`, and `topology_value` on its own entity's UI document.
Optional `body_value`, `motor_value`, `contact_value`, and `friction_value`
labels expose tracked-body pose/speed and aggregate actuation/contact telemetry
without coupling the physics module to a particular presentation.
For acceptance scenes, `servo_group_root_entity_name` may bind a named
`Checkbox` to all descendant servo components; the HUD polls the current
generation of the document instead of retaining widget pointers across UI
rebuilds.
