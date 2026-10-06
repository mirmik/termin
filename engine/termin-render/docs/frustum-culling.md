# CPU frustum culling

Undeformed MeshRenderer items and static spatial batches are culled by default.
The full immutable RenderItemSnapshot remains available to every pass. Selection
uses the final camera matrices of each pass, including named overrides. Mono
Color, Depth, DepthOnly, Normal, Id and StandardGBuffer use their own volume;
multiview Color accepts the union of the two eyes.

## Bounds contract

The producer opts in with TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS.
SkinnedMeshRenderer never opts in, even before its skeleton is available.
Non-mesh producers retain their existing behavior. Snapshot publication computes
world_bounds and bounds_state after static batching. Missing, unsupported and
invalid bounds keep the item visible. Geometry errors are logged without
repeating the same mesh version every frame.

termin-mesh caches indexed submesh-local AABBs by header.version. Geometry
setters, builder commit and default-submesh creation invalidate this cache.
Direct writes to CPU buffers require tc_mesh_bump_version, as GPU updates already
do. Queries support float32x3 position attributes with arbitrary valid offsets
and strides, including signed submesh vertex_offset. Standalone mesh owners must
call tc_mesh_clear_bounds_cache before manually freeing queried meshes.

World bounds use the item's actual affine model matrix, including mesh offset,
parent transforms, reflection, nonuniform scale and shear. Batches use the
merged chunk-local vertices and chunk model matrix, so geometry extending beyond
the chunk pivot remains conservative.

Frustum planes come from projection * view in the engine's clip convention:
X/Y in [-w,w], Z in [0,w]. Backend OpenGL remapping is irrelevant to this CPU
test. The maximum AABB support point is tested against each plane, with a
conservative numerical tolerance; a box containing the frustum remains visible.

Mono Color may retain an authored vertex shader. Its items stay visible unless
the pass uses the standard assembled transform, because arbitrary authored
vertex stages provide no conservative deformation bound. This is independent
of whether the producer supplies geometric bounds.

## Shadows

ShadowPass fits the original caster_offset-expanded light volume for every
directional-light cascade before shader planning. It prepares a task once if
any cascade requires that item, then selects draws separately for each cascade.
The main camera's visibility is never used as a caster list. Shadow fitting,
gameplay, shader-usage export and original object pick IDs are unchanged.

Pass sorting uses the original snapshot item index as the last key. Equal
priority/shader/distance draws therefore keep their relative order when culling
removes other items. This also preserves depth-test winners on coplanar geometry.

## Diagnostics

The C++ API is in termin/render/render_item_culling.hpp. Python inspection:

```python
from termin.render import _render_native as render
render.set_render_item_culling_enabled(False)  # A/B, default True
render.clear_render_item_culling_diagnostics()
# Allow the editor to render; then:
print(render.get_render_item_culling_diagnostics())
```

Records contain target, pass, view_index, candidates, tested, culled,
without_bounds and mesh_draws. mesh_draws counts successful mesh submissions
separately from candidate items. Mono/stereo records use view_index=-1; shadow
records use light_index*4+cascade_index. Records retain the latest invocation
for each key; clear them before changing the measured configuration.

tools/cargo_culling_probe.py contains reproducible prepare/sample helpers for
an isolated CargoTerminal editor in Play with editor pause. Collect at least
120 warmed frames for overview and hall, with identical viewport and batching.
Capture images and ID resources separately from performance sampling, and
disable debugger captures before timing. CPU wall spans include driver waits
and are not GPU timings.

Pass native_library="/path/to/sdk/lib/libtermin_base.so" to sample() to include
native GPU submission timestamps through the public tc_frame_profile C ABI.
The Python profiler wrapper currently omits these fields. The helper excludes
the newest eight frames from the GPU mean to allow asynchronous timestamp
publication; it records the matched frame count separately from the 120 CPU
frames. GPU durations include all submissions attributed to each retained frame.

CargoTerminal A/B results and captures:
[2026-10-07 report](../../../docs/analysis/2026-10-07-cargo-frustum-culling.md).
