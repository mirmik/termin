# GPU pipeline layout

Single source of truth for descriptor set bindings, UBO field offsets, vertex
input locations, and push constants across all engine passes.

**Authoritative C++ locations (verify here before changing anything):**

- `termin-graphics/src/tgfx2/vulkan/vulkan_render_device.cpp` — `create_shared_layouts()`
  builds the universal `VkDescriptorSetLayout` / `VkPipelineLayout`.
- `termin-app/cpp/termin/lighting/lighting_ubo.hpp` — `LightingUBOData`.
- `termin-app/cpp/termin/render/color_pass.cpp` — `PerFrameStd140`, `ShadowBlockStd140`.
- `termin-app/cpp/termin/render/shader_parser.cpp` — generated `MaterialParams` + `ColorPushBlock`.
- `termin-app/cpp/termin/render/{shadow,id}_pass.cpp`,
  `termin-components/termin-components-render/src/{depth,normal}_pass.cpp` —
  per-pass `PerFrame` + `PushStd140` variants.
- `termin-app/cpp/termin/render/shader_skinning.cpp` + `skinned_mesh_renderer.cpp` —
  `BoneBlock`.
- `termin-mesh/src/tgfx_types.c` — `tgfx_vertex_layout_*`.

Rule of thumb: **if you need a new UBO, add a new binding to
`create_shared_layouts()` first**, then mention the slot here, then use it in
the shader. Do not silently squat on an unused descriptor slot.

---

## 1. Descriptor set 0 (shared pipeline layout)

Single `VkDescriptorSetLayout` used by every graphics pipeline the engine
creates. On OpenGL each UBO binding maps directly to a GL UBO binding point;
samplers map to texture units by the same number.

| Binding | Type | Count | Stages | Name | Owner / writer |
|---|---|---|---|---|---|
| 0 | UBO | 1 | ALL | `LightingBlock` | `LightingUBO` (`lighting_ubo.hpp`) |
| 1 | UBO | 1 | ALL | `MaterialParams` | Synthesized per-shader by `shader_parser.cpp` from `@property` declarations; uploaded by `material_ubo_apply.cpp` |
| 2 | UBO | 1 | ALL | `PerFrame` | Per pass (`ColorPass::execute_with_data`, `ShadowPass`, `DepthPass`, `NormalPass`, `IdPass`) |
| 3 | UBO | 1 | ALL | `ShadowBlock` | `ColorPass::execute_with_data` |
| 4–7 | COMBINED_IMAGE_SAMPLER | 1 each | FS | material textures (`MATERIAL_TEX_SLOT_BASE = 4`) | `ColorPass::execute_with_data` + `apply_material_phase_ubo` |
| 8 | COMBINED_IMAGE_SAMPLER | `MAX_SHADOW_MAPS = 16` | FS | `u_shadow_map[16]` (array descriptor) | `ColorPass::execute_with_data` |
| 9–15 | COMBINED_IMAGE_SAMPLER | 1 each | FS | extra FS samplers (debug overlays, posteffect inputs) | caller-supplied |
| 16 | UBO | 1 | VS | `BoneBlock` | `SkinnedMeshRenderer::upload_per_draw_uniforms_tgfx2` |
| push | push-constants | 128 B | ALL_GRAPHICS | per-pass push block | per-pass writer |

**Notes:**

- Binding 8 is a single **array descriptor** with `descriptorCount = 16`. In
  GLSL: `layout(binding = 8) uniform sampler2DShadow u_shadow_map[16]`. No
  bindings 9..23 are consumed by it; 9..15 are free for extra samplers.
- OpenGL push constants ride a ring UBO at `TGFX2_PUSH_CONSTANTS_BINDING = 14`
  (GL's UBO binding space is disjoint from the sampler/texture-unit space,
  so reusing 14 there doesn't collide with sampler 14 on Vulkan).
- Bindings higher than 16 are not declared in the universal layout. If you
  need one, extend `create_shared_layouts()` first — otherwise SPIR-V pipeline
  creation fails with "binding N not declared in pipeline layout".

---

## 2. UBO structures (std140)

All offsets are in bytes. `static_assert` in the C++ source pins the size;
any mismatch will fail to compile.

### `LightingBlock` (binding 0, 688 B)

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

### `MaterialParams` (binding 1, variable size)

**Synthesised per-shader.** The parser scans `@property` lines in `.shader`,
packs them std140, and writes the block declaration into both GLSL and the
`tc_material_ubo_entry[]` metadata on `tc_shader`. Runtime uploader
(`tc_material_phase_apply_ubo_gl` / `_vk`) walks those entries and copies
values from `phase->uniforms[]` into the right offsets.

Block size is available from `shader->material_ubo_block_size`; fields from
`shader->material_ubo_entries[]`. Don't hardcode it.

### `PerFrame` (binding 2) — **per-pass**, different layouts

#### ColorPass `PerFrameStd140` (208 B)

```
0    mat4   u_view
64   mat4   u_projection
128  mat4   u_view_projection
192  vec4   u_camera_position.xyz + _pad
```

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

### `ShadowBlock` (binding 3, 2064 B)

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

### `BoneBlock` (binding 16, 8208 B)

```
0      mat4[128]  u_bone_matrices           # 128 * 64 = 8192 B
8192   int        u_bone_count
8196   pad[12]                              # block-end vec4 alignment
```

`MAX_BONES = 128`. Matrices are column-major (matches the C++ `Mat44f`
memory layout, so the CPU side writes straight into the UBO without
transpose).

---

## 3. Vertex input locations

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

## 4. Push constants (128 B max)

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

**GL emulation:** on OpenGL the push-constant range is backed by a ring UBO
at binding **14** (`TGFX2_PUSH_CONSTANTS_BINDING`). Parser converts
`layout(push_constant) uniform XxxPushBlock { ... }` to
`layout(std140, binding = 14) uniform XxxPushBlock { ... }` under the
`#ifndef VULKAN` branch.

---

## 5. Rules for adding a new UBO / sampler

1. **Check this document.** If your slot already has an owner, reuse the
   UBO instead of doubling up.
2. **Extend `VulkanRenderDevice::create_shared_layouts()`** with the new
   binding (type, count, stage flags). Without this step, Vulkan pipeline
   creation fails with "binding N not declared".
3. **Pick the narrowest `stageFlags`** you can. Skinning only writes from
   VS, so `BoneBlock` is `VK_SHADER_STAGE_VERTEX_BIT` only.
4. **Document the struct here** with offsets and a `static_assert(sizeof(...)
   == ...)` in the C++ source.
5. **Mirror GL.** If the UBO needs an explicit `set_block_binding`, make
   sure it's called after `bind_shader`; the `layout(std140, binding = N)`
   qualifier is honoured by most GL 4.2+ drivers but some need the
   explicit glUniformBlockBinding hook as belt-and-suspenders.
6. **Update this doc in the same commit as the C++ change.** Future
   debugging depends on the table matching reality.
