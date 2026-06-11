# Slang Scope-First Binding Migration

Date: 2026-06-11

## Decision

Termin should finish the Slang migration against a **scope-first,
bind-by-name** resource model.

The current Vulkan implementation uses a per-pipeline single descriptor set.
That is a valid transitional backend shape, but it is no longer the target
authoring/runtime model. Shader authors and render passes should not encode
backend set/binding numbers. They should describe and bind resources by stable
logical names, while generated layout metadata records each resource's update
scope and backend placement.

## Target Model

Shader resource identity is:

```text
logical name + kind + scope
```

Backend placement is generated metadata:

```text
Vulkan: (set, binding)
OpenGL: flat binding
D3D11: register class/index
```

The expected scopes are:

| Scope | Lifetime | Examples |
|---|---|---|
| `frame` | camera/frame constants | `per_frame` |
| `pass` | pass-wide resources | `lighting`, `shadow_block`, `shadow_maps` |
| `material` | material/phase resources | `material`, `albedo_texture`, `normal_texture` |
| `draw` | per-object/per-draw resources | `draw_data`, large object buffers |
| `transient` | pass-local scratch resources | fullscreen input/output textures |

Push constants remain the preferred path for small per-draw payloads that fit
within the 128-byte portability budget. Larger or backend-incompatible draw
data belongs in `draw` scope.

## Why Scope Before Multiple Sets

Moving all remaining code to bind-by-name while keeping one undifferentiated
resource bucket would preserve the wrong mental model: frame, pass, material,
and draw resources would still be rebuilt and rebound together.

Adding full Vulkan multiple descriptor sets first would also be too large a
step. It touches pipeline layout construction, descriptor set layout caches,
resource set allocation, command binding order, OpenGL flattening, tests, and
all active render passes at once.

The chosen sequence is therefore:

1. Add scope to shader layout metadata and runtime binding structures.
2. Split `RenderContext2` pending/dirty state by scope.
3. Keep Vulkan flattened to the current single set initially.
4. Migrate passes/materials to bind by name and scope-aware metadata.
5. Later map scopes to multiple Vulkan descriptor sets mechanically.

## Compatibility With Bind-By-Name

Bind-by-name remains the public API:

```cpp
ctx.bind_uniform("per_frame", per_frame_buffer);
ctx.bind_texture("albedo_texture", albedo);
```

The active shader layout resolves each name to kind, scope, and backend
placement. Callers should not pass numeric slots for migrated code paths.

Missing names, kind mismatches, and scope/backend layout mismatches must log
clear errors. Migrated Slang shaders marked artifact-required should fail
loudly when layout metadata is absent.

## Slang Scope Attributes

The preferred authored Slang spelling for explicit resource scope is a
Termin-provided user attribute imported from an engine prelude:

```slang
import termin_prelude;

[[TerminScope("frame")]]
ConstantBuffer<FrameData> per_frame;

[[TerminScope("material")]]
Texture2D albedo_texture;
```

Slang user-defined attributes are declared as attribute structs:

```slang
[__AttributeUsage(_AttributeTargets.Var)]
public struct TerminScopeAttribute
{
    string value;
}
```

This was verified with `slangc 2026.1-52-gc8ddf20bb` from Vulkan SDK
`1.4.341.1`. `slangc -reflection-json` emits the annotation on reflected
resource parameters as:

```json
"userAttribs": [
  {
    "name": "TerminScope",
    "arguments": ["frame"]
  }
]
```

Both `[TerminScope("frame")]` and `[[TerminScope("frame")]]` work. The
double-bracket form matches the style already used for some Slang/Vulkan
attributes, but it is still a Slang user attribute, not a backend layout
attribute.

Do **not** document or implement `[[termin::scope("frame")]]` as the target
syntax. A probe with a namespaced attribute definition compiled with warning
`unknown attribute 'termin_Scope'`, and the attribute was not present in
reflection JSON. If namespacing becomes important later, verify it against a
newer Slang release before changing the contract.

`termin_shaderc` should eventually read `userAttribs` from Slang reflection and
use `TerminScope` as the explicit source of truth. During migration it may also
accept `Scope` as a temporary alias and fall back to the current conservative
name/kind inference when no explicit scope attribute is present.

## Current State

- Author-authored `.slang` files should remain free of `[[vk::...]]` and
  `register(...)`.
- `termin_shaderc` emits `.layout.json` resource metadata beside generated
  artifacts.
- `tc_shader` can carry resource layout metadata loaded from sidecars.
- Scope metadata has been added to `tc_shader_resource_binding`, Python
  bindings, and generated `.layout.json` sidecars. Old sidecars without
  `scope` are still accepted and classified by conservative name/kind
  inference.
- A real `slangc` probe confirmed that Slang user attributes can carry
  resource scope through reflection JSON. The target explicit spelling is
  `[[TerminScope("frame")]]`, provided by an engine Slang prelude.
- `RenderContext2` already has initial symbolic binding methods.
- `RenderContext2` pending numeric/symbolic bindings are internally grouped
  by scope, then flattened back into the existing `ResourceSetDesc` backend
  shape at flush time.
- Grayscale, tonemap, and bloom use name-based bindings for their Slang
  post-process resources.
- Material/color rendering still contains numeric binding ABI for per-frame,
  shadows, material UBO/textures, and draw data.
- Vulkan currently builds one descriptor set layout per pipeline from SPIR-V
  reflection.

## Immediate Tasks

1. Add a Termin Slang prelude that defines `TerminScopeAttribute`, and teach
   `termin_shaderc` to read `TerminScope` from reflection `userAttribs`.
2. Broaden or replace default scope inference for known engine names:
   `per_frame -> frame`, lighting/shadows -> pass, `material` and material
   textures -> material, `draw_data` -> draw.
3. Add dirty-per-scope tracking on top of the scoped buckets. Existing backends
   may still receive a flattened resource set until Vulkan scoped sets land.
4. Update Slang/material generation so generated resource declarations do not
   encode Vulkan-only attributes. Push-constant use must become metadata or a
   backend-specific artifact decision, not authored/generated Slang source
   magic.
5. Migrate `ColorPass` and material UBO/texture binding to name-first lookup.
   Numeric fallback remains only for legacy GLSL paths.
6. Add validation for duplicate backend bindings with incompatible resource
   type/count/stage.
7. After the above is stable, introduce multiple Vulkan descriptor set layouts
   by scope and bind only dirty scopes.

## Retired Direction

The old two-set-vs-single-set debate is retired as a frontend/API decision.
Single-set remains an implementation detail of the current Vulkan backend.
Multiple Vulkan sets are useful as a later optimization and lifetime model
implementation, not as shader authoring syntax.

Do not revive a universal binding table or require Slang sources to carry
backend layout annotations.
