# Foliage placement and motion

`FoliageLayerComponent` draws one indexed prototype mesh with instances from a
`TcFoliageData` asset. Instance positions use the full entity transform; prototype
offsets use entity rotation and each instance's uniform `scale`, yaw and surface
normal. Entity scale changes placement spacing, not prototype size.

The GPU instance ABI is 48 bytes: position/yaw, normal/seed, scale/three reserved
floats. The foliage draw constant buffer is 176 bytes. These layouts are shared
by the render-core provider contract and the Slang transform.

## Motion API

All controls are Python-accessible and serialized by the native inspect registry.
Motion is disabled by default (`wind_strength = interaction_strength = 0`).

* `motion_time`: explicit seconds, including negative values. No render clock is
  sampled; the owner sets time from its simulation or editor preview controller.
* `prototype_height`: local positive Z height; roots must be at Z=0. The bend
  envelope is the square of the clamped height fraction.
* `wind_strength`: maximum displacement in world metres at full height.
* `wind_speed`: angular frequency in radians/second.
* `wind_wavelength`: world metres per coherent wind wave.
* `wind_direction_degrees`: direction in world XY.
* `interaction_x/y/z`: one sphere's world center.
* `interaction_radius`: sphere radius in world metres; zero disables it.
* `interaction_strength`: maximum displacement away from the sphere center.

Sphere falloff is evaluated at each instance root, so the whole tuft shares one
response. Both wind and interaction are projected onto the root tangent plane.
The deformation is an instantaneous shear, with an inverse-transpose normal
correction. There is no accumulated trample history or spring simulation.
Color, depth, normal, ID and shadow passes use the same transform implementation.

`compute_world_bounds()` returns `[minX,minY,minZ,maxX,maxY,maxZ]`, or `None` for
missing/empty geometry. It encloses each rotated/scaled prototype with a sphere
and adds maximum wind/interaction displacement. It is intentionally independent
of time. The current render collector does **not** consume these bounds yet.

`TcFoliageData.set_instances(instances)` validates and replaces the complete
instance list transactionally, computes placement bounds and increments the data
version once. It can initialize a newly declared, unsaved asset. `save()` uses
the path provided to `declare`; ordinary `add_instance` requires loaded data.

## Current scalability limits

Every submitted batch draws all its instances. There is no per-instance/chunk
visibility filtering, density LOD or distance-dependent shadow policy. Instance
data is repacked/uploaded for every render pass. Authors may partition layers,
but that alone does not add culling. GPU buffer caching must track data version
and device lifetime before this becomes a large-field rendering system.
