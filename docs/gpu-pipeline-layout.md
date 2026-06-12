# GPU pipeline layout

Reference for CPU-side UBO struct layouts, vertex input locations, and push
constant payloads across engine passes.

**Pipeline layout architecture** is documented separately in
`termin-graphics/docs/architecture/pipeline-layout.md`. The short version:
there is no universal binding table. Slang migration target is
**scope-first bind-by-name**: shader resources are identified by logical names
and scopes, while backend set/binding numbers are generated layout metadata.

The current Vulkan backend still flattens reflected shader resources into one
per-pipeline descriptor set. Treat that as implementation state, not a shader
authoring rule.

**Authoritative C++ locations (verify here before changing anything):**

- `termin-graphics/docs/architecture/pipeline-layout.md` — architecture and data flow.
- `docs/plans/2026-06-11-slang-scope-first-binding.md` — active migration plan.
- `termin-graphics/src/tgfx2/vulkan/vulkan_render_device.cpp` — per-pipeline
  `VkDescriptorSetLayout` built from SPIR-V reflection at `create_pipeline()` time.
- `termin-render-passes/include/termin/lighting/lighting_ubo.hpp` — `LightingUBOData`.
- `termin-render/include/termin/render/frame_uniforms.hpp` — `EnginePerFrameStd140`.
- `termin-render-passes/src/color_pass.cpp` — `ShadowBlockStd140`.
- `termin-app/cpp/termin/render/shader_parser.cpp` — generated `MaterialParams` + `ColorPushBlock`.
- `termin-render-passes/src/{shadow,id}_pass.cpp`,
  `termin-components/termin-components-render/src/{depth,normal}_pass.cpp` —
  per-pass `PerFrame` + `PushStd140` variants.
- `termin-render-passes/src/shader_skinning.cpp` + `termin-app/cpp/termin/render/skinned_mesh_renderer.cpp` —
  `BoneBlock`.
- `termin-mesh/src/tgfx_types.c` — `tgfx_vertex_layout_*`.

Rule of thumb: **new Slang code declares named resources, not backend slots.**
Legacy GLSL can still carry `layout(binding=N)` while it remains on the old
numeric path. Migrated code should bind by logical name and let the generated
layout sidecar describe backend placement.

---

## 1. UBO structures (std140)

All offsets are in bytes. `static_assert` in the C++ source pins the size;
any mismatch will fail to compile.

### `LightingBlock` (688 B)

```
Offset  Size  Type          Field
0       640   LightData[8]  lights        # 8 * 80 B per light
640     16    vec4          ambient (rgb) + ambient_intensity
656     16    vec4          camera_position (xyz) + light_count
672     16    vec4          shadow_method, shadow_softness, shadow_bias, _pad
```

Per-light `LightData` (80 B):

```
0   vec4  color.rgb + intensity
16  vec4  direction.xyz + range
32  vec4  position.xyz + type
48  vec4  attenuation.xyz + inner_angle
64  vec4  outer_angle + cascade_count + cascade_blend + blend_distance
```

### `MaterialParams` (variable size)

**Synthesised per-shader.** The parser scans `@property` lines in `.shader`,
packs them std140, writes the block declaration into GLSL/Slang source, and
stores the byte layout in `tc_material_ubo_entry[]` metadata on `tc_shader`.
For Slang, backend binding is not authored into the source. `termin_shaderc`
writes resource metadata into the compiled artifact sidecar and the runtime
merges that into `tc_shader_resource_binding[]`, including resource scope
(`frame`, `pass`, `material`, `draw`, `transient`). Runtime uploaders
(`material_ubo_apply.cpp` in `termin-app` and `material_ubo_runtime.cpp` in
`termin-render`) walk those entries and copy values from `phase->uniforms[]`
into the right offsets.

Block size is available from `shader->material_ubo_block_size`; fields from
`shader->material_ubo_entries[]`. Don't hardcode it.

### `PerFrame`

For parser-generated material shaders, `shader_parser.cpp` injects this
shared block and `frame_uniforms.cpp` uploads it. This is what `ColorPass`
and `MaterialPass` bind for ordinary `.shader` materials.

#### `EnginePerFrameStd140` (352 B)

```
0    mat4   u_view
64   mat4   u_projection
128  mat4   u_view_projection
192  mat4   u_inv_view
256  mat4   u_inv_proj
320  vec4   u_camera_position.xyz + _pad
336  vec2   u_resolution
344  float  u_near
348  float  u_far
```

#### Standalone geometry/debug passes

Some built-in passes compile their own shaders and use smaller `PerFrame`
blocks. Those layouts are local to those passes and must stay matched with
their shader sources:

#### ShadowPass / IdPass / NormalPass `*PerFrameStd140` (128 B)

```
0    mat4   u_view
64   mat4   u_projection
```

#### DepthPass `DepthPerFrameStd140` (144 B)

```
0    mat4   u_view
64   mat4   u_projection
128  float  u_near
132  float  u_far
136  _pad[8]
```

### `ShadowBlock` (2064 B)

```
0      int       u_shadow_map_count
4      pad[12]
16     mat4[16]  u_light_space_matrix      # 1024 B
1040   ivec4[16] u_shadow_light_index      # scalar in vec4 slot
1296   ivec4[16] u_shadow_cascade_index
1552   vec4[16]  u_shadow_split_near
1808   vec4[16]  u_shadow_split_far
```

The shader sees the `[16]` arrays as scalar arrays — it reads only the `.x`
(or `[0]`) component of each 16-byte slot.

### `BoneBlock` / `bone_block` (8208 B)

```
0      mat4[128]  u_bone_matrices           # 128 * 64 = 8192 B
8192   int        u_bone_count
8196   pad[12]                              # block-end vec4 alignment
```

`MAX_BONES = 128`. Matrices are column-major (matches the C++ `Mat44f`
memory layout, so the CPU side writes straight into the UBO without
transpose).

Runtime binding is name-first. New Slang shaders should declare a draw-scope
resource named `bone_block`; legacy GLSL skinned variants still declare
`BoneBlock` at binding 16, and the renderer accepts that name only as a
compatibility path.

---

## 2. Vertex input locations

Same numbers across all vertex layouts in `tgfx_types.c`. A mesh whose
layout doesn't declare a given slot leaves that input unconsumed; shaders
are free to declare an `in` at it but should tolerate zero data.

| Location | Attribute | Used by |
|---|---|---|
| 0 | `position` (vec3) | all |
| 1 | `normal` (vec3) | lit, skinned, shadow (partial) |
| 2 | `uv` (vec2) | color, depth, normal |
| 3 | `tangent` (vec4, xyz = tangent, w = handedness) | PBR color, skinned |
| 4 | *(reserved — do not reuse; historical skinning joints lived here)* | — |
| 5 | `color` (vec4) | `pos_normal_uv_color` layout only |
| 6 | `joints` (vec4, indices stored as floats) | skinned |
| 7 | `weights` (vec4) | skinned |

`tgfx_vertex_layout_skinned()` covers locations 0, 1, 2, 3, 6, 7 — stride 80 B.
If the GLB source has no tangent, the loader fills zeros at location 3; the
PBR shader's `length(a_tangent.xyz) > 0.001` check handles that case.

---

## 3. Push constants (128 B max)

All graphics stages share a single push-constant range of **128 bytes**. This
is the Vulkan 1.0 minimum guaranteed by `maxPushConstantsSize` — don't exceed
it.

Each pass declares its own `*PushStd140` struct that fits in 128 B, typed so
the CPU side and the shader stay in sync:

| Pass | Struct | Contents | Size |
|---|---|---|---|
| ColorPass | `ColorPushBlock` (parser-generated) | `mat4 _u_model` | 64 B |
| ShadowPass | `ShadowPushStd140` | `mat4 u_model` | 64 B |
| DepthPass | `DepthPushStd140` | `mat4 u_model` | 64 B |
| IdPass | `IdPushStd140` | `mat4 u_model`, `vec4 u_pickColor` | 80 B |
| NormalPass | `NormalPushStd140` | `mat4 u_model` | 64 B |
| SolidPrimitive | `SolidPushBlock` | `mat4 u_mvp`, `vec4 u_color` | 80 B |
| Immediate | `ImmediatePushBlock` | `mat4 u_mvp` | 64 B |
| Text2D | `Text2DPushBlock` | `mat4 u_projection`, `vec4 u_color` | 80 B |
| UIRenderer | `UIPushBlock` | `mat4 u_projection`, `vec4 u_tint`, flags | ≤80 B |

**OpenGL emulation:** on OpenGL the push-constant range is backed by a ring UBO
at binding **14** (`TGFX2_PUSH_CONSTANTS_BINDING`). Parser converts
`layout(push_constant) uniform XxxPushBlock { ... }` to
`layout(std140, binding = 14) uniform XxxPushBlock { ... }` under the
`#ifndef VULKAN` branch.

**D3D11 emulation:** D3D11 has no native push constants. Slang/HLSL targets
must receive the same data through a small per-draw cbuffer. Reserve
`register(b14)` for that emulation so it mirrors the OpenGL UBO binding.

---

## 4. Rules for adding a new UBO / sampler

1. **Check this document** for existing struct layouts — reuse a UBO instead
   of doubling up.
2. **Pick a logical resource name and scope.** Examples: `per_frame` is
   `frame`, shadow resources are `pass`, material properties/textures are
   `material`, large object constants are `draw`, and skinning data is
   `bone_block` in `draw`.
3. **For new Slang, do not author backend layout attributes.** Add the resource
   declaration by name, annotate explicit scope with `[[TerminScope("...")]]`
   from the Termin Slang prelude, and let artifact layout metadata carry
   backend placement. Legacy GLSL may still use `layout(binding=N)` until
   migrated.
4. **Pick the narrowest `stageFlags`** you can. Skinning only writes from
   VS, so `BoneBlock` is `VK_SHADER_STAGE_VERTEX_BIT` only.
5. **Document the struct here** with offsets and a `static_assert(sizeof(...)
   == ...)` in the C++ source.
6. **Mirror GL.** If a legacy GLSL UBO needs an explicit `set_block_binding`, make
   sure it's called after `bind_shader`; the `layout(std140, binding = N)`
   qualifier is honoured by most GL 4.2+ drivers but some need the
   explicit glUniformBlockBinding hook as belt-and-suspenders.
7. **Update this doc in the same commit as the C++ change.** Future
   debugging depends on the table matching reality.
