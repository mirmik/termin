# Layout-Only ColorPass Binding Migration

Date: 2026-06-11

## Problem

`ColorPass` is currently half-migrated to shader resource layouts. Some
resources are resolved through the active `tc_shader_resource_binding` layout,
while other engine resources are still bound through legacy numeric slots.

That mixed model leaks descriptors across draws. A direct tgfx2 drawable can
clear and bind a new shader layout, but numeric pass resources such as shadow
or lighting buffers can still be queued and later flushed against a pipeline
whose SPIR-V has no descriptor bindings. The visible symptom is repeated Vulkan
warnings like:

```text
RenderContext2: flush_resource_set skipping pipeline=... (descriptor_set_layout is null) with 1 pending bindings
```

The underlying bug is architectural: migrated code must not treat numeric
bindings as a fallback when a shader layout exists and does not declare the
resource.

## Target Contract

- A shader layout is the source of truth for migrated rendering paths.
- If a shader has resource layout metadata, pass code binds only resources
  present in that layout.
- Missing resources in a present layout are not silently replaced by numeric
  fallbacks.
- Numeric bindings remain only for explicit legacy/no-layout compatibility.
- `RenderContext2` should treat pending bindings that are incompatible with the
  current pipeline layout as an error signal, not normal control flow.

## Migration Steps

1. Add reusable shader-aware binding helpers for engine resources:
   `per_frame`, `shadow_block`, `shadow_maps`, `lighting`, `material`, and
   `draw_data`.
2. Update builtin shader catalog metadata so GLSL engine shaders declare the
   resources they actually use, including shadow block and shadow texture
   arrays.
3. Convert `ColorPass` to call the helpers instead of unconditional numeric
   `bind_uniform_buffer_ring()` / `bind_sampled_texture_array_element()`.
4. Keep numeric fallback only when the active shader has no layout metadata.
5. Tighten `RenderContext2` layout changes so draw/transient numeric bindings
   do not survive across incompatible shader layouts.
6. Add tests for:
   - layout-present/missing-resource no-op;
   - no numeric fallback when a layout exists;
   - direct line/debug draws in `ColorPass` do not inherit shadow or lighting
     descriptors;
   - catalog resource metadata matches shadow/lighting shader includes.

## Notes

This plan refines the broader scope-first plan in
`2026-06-11-slang-scope-first-binding.md`. It is intentionally narrower: finish
the `ColorPass` vertical slice first so runtime regressions stop appearing as
descriptor-set noise around unrelated drawables.

## Status: 2026-06-11

- `RenderContext2` now tracks descriptor-set-layout changes and rebuilds the
  resource set for the current pipeline layout, including default-filled sets
  when a layout has no explicit per-draw bindings.
- Vulkan resource set creation now normalizes sparse bindings to the full
  descriptor-set layout signature and supplies default descriptors for absent
  UBO/texture/sampler resources.
- `ColorPass` binds material draws in layout order:
  `clear -> bind_shader -> use_shader_resource_layout -> bind resources -> draw`.
- A shared shader binding policy now treats non-GLSL shaders with loaded
  layout metadata as layout-only. GLSL layout metadata remains transitional and
  may use legacy fallbacks until GLSL ColorPass shaders are retired.
- `draw_data` is strict for layout-only shaders: missing `draw_data` is logged
  as an error instead of silently falling back to slot 24.
- Remaining migration work is to port the ColorPass material shader set to
  Slang so GLSL sidecars no longer define the compatibility path.
