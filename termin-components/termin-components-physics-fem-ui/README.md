# Native FEM physics UI adapter

This optional adapter keeps presentation out of the FEM physics scene binding.
`FEMPhysicsWorldComponent` publishes a UI-neutral telemetry snapshot, while
`FEMPhysicsHudComponent` formats that snapshot into a native `UIComponent`
document. The HUD expects the named labels `energy_value`, `energy_change`,
`simulation_value`, and `topology_value` on its own entity's UI document.
