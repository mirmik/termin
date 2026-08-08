# SrgbColor / LinearColor Refactor Plan

Date: 2026-08-09

Related umbrella: Kanboard `#1045 [render] Нормализовать linear HDR и color-space тракт`.

This plan covers typed scalar color values. Texture encoding is already covered
by `docs/plans/2026-07-29-texture-encoding-contract-plan.md`; scene HDR and the
display output boundary are covered by the completed `#1380` slice of `#1045`.

## Motivation

Termin currently uses several untyped four-float representations for values
which have incompatible meanings:

- `termin::Color4` is used for authored colors, linear shader values, HDR clear
  values, debug geometry and text;
- `tc_ui_color` stores user-facing UI colors but does not state their encoding;
- shader `@property Color` is parsed and stored as a `Vec4` and reaches the
  material UBO without an sRGB-to-linear conversion;
- material, Python and C# convenience APIs accept raw RGBA floats under names
  such as `set_color`, so the conversion boundary cannot be checked;
- the color picker works in HSV/RGB but its public result has no declared color
  encoding.

This makes both missing and duplicate conversions easy. It also makes a
correct linear renderer visually unstable whenever one subsystem changes its
implicit convention.

## Migration policy

The goal is **not** to preserve the current image or the current numeric shader
inputs. The goal is to restore the expected color contract.

In particular:

- existing values which were authored as ordinary colors keep their authored
  sRGB numbers, but shaders receive their decoded linear values;
- values which are already linear remain numerically unchanged;
- HDR linear values above `1.0` remain representable and are not clamped;
- scenes may become darker, less washed out, or otherwise visibly different
  when an accidental display-space calculation is removed;
- lighting, exposure and material defaults are not adjusted merely to imitate
  the old result;
- any later artistic recalibration is a separate, explicit task performed
  against reference scenes after this contract passes its numeric tests;
- no permanent compatibility alias, silent fallback or heuristic conversion is
  retained for legacy `Color`/`Color4` values.

Tracked repository assets and declarations are migrated together with the code.
Unsupported legacy declarations fail with a logged diagnostic so that an
ambiguous value cannot silently continue through the renderer.

## Target contract

Termin has one renderer working space:

> linear RGB using the sRGB primaries and D65 white point.

The public value types are plain standard-layout structures:

```cpp
struct SrgbColor {
    float r;
    float g;
    float b;
    float a;
};

struct LinearColor {
    float r;
    float g;
    float b;
    float a;
};

LinearColor srgb_to_linear(SrgbColor value);
SrgbColor linear_to_srgb(LinearColor value);
```

There is no inheritance, template parameter or runtime encoding field.

### `SrgbColor`

- represents an authored/display-referred SDR color encoded with the IEC sRGB
  transfer function;
- RGB is normally in `[0, 1]`;
- alpha is linear coverage/opacity and is never passed through the sRGB transfer
  function;
- is used by color pickers, hexadecimal/CSS colors, UI themes, material base
  colors and tints;
- is not accepted directly by low-level shader uniform upload or linear color
  arithmetic.

### `LinearColor`

- represents linear RGB in the single Termin working space;
- RGB can exceed `1.0` for HDR and is not clamped by the value type;
- alpha remains linear;
- is used for lighting, blending, render-target clear values, shader-visible
  colors and internal render data.

### `Vec4`

- remains four uninterpreted numeric components;
- never receives a color conversion;
- must not be accepted by APIs whose contract is specifically a color.

### HSV

HSV remains a local coordinate model of the color picker. The picker converts
between HSV and sRGB RGB and exposes `SrgbColor` at its public boundary. HSV is
not a material property, renderer uniform or general engine color format.

## Conversion ownership

There are three distinct boundaries:

1. File textures carry `TextureEncoding`; native sRGB texture formats decode
   RGB during sampling. This plan does not duplicate that conversion on CPU.
2. Authored scalar colors are stored and serialized as `SrgbColor`. The
   material packing boundary converts them to `LinearColor` before writing the
   material UBO.
3. Linear display-referred render output is encoded once by the output
   transform established by `#1380`.

No backend uniform function, raw `Vec4` setter or shader source silently guesses
that a value is sRGB.

## Shader and material property model

The ambiguous shader property type is replaced:

```text
@property SrgbColor  u_color = SrgbColor(1.0, 1.0, 1.0, 1.0)
@property LinearColor u_radiance = LinearColor(1.0, 1.0, 1.0, 1.0)
@property Vec4        u_coefficients = Vec4(1.0, 1.0, 1.0, 1.0)
```

All three map to a shader-side `float4`, but their property metadata and CPU
storage remain distinct.

- `SrgbColor` is serialized with its authored components and decoded while
  packing the material UBO;
- `LinearColor` is copied without conversion;
- `Vec4` is copied literally;
- old `@property Color` becomes a parser error after tracked shaders and
  fixtures are migrated;
- old `set_color(float, ...)` convenience APIs are replaced by explicitly typed
  color setters or typed property assignment;
- a raw uniform setter remains numeric and never accepts `SrgbColor` by
  implication.

The material source of truth must retain the authored `SrgbColor`; converting
and overwriting it at edit time would break picker and serialization round
trips. Packed/cached UBO bytes may contain the converted linear value.

## Property classification

The migration classifies properties by their actual use rather than their
names:

- base color, diffuse color, tint, picker-selected specular color, skybox
  colors and emission chromaticity are `SrgbColor`;
- emission intensity stays a separate linear scalar, so HDR emission is the
  decoded chromaticity multiplied by that intensity;
- computed radiance, irradiance and internal lighting colors are
  `LinearColor`;
- masks, coefficients and unrelated four-component values remain `Vec4`;
- texture properties continue to use their existing
  `encoding(srgb|linear)` contract.

Every ambiguous built-in declaration must be reviewed. It must not be migrated
solely by replacing the token `Color` mechanically.

## UI and editor contract

- hex input and CSS colors produce `SrgbColor`;
- HSV/RGB color picker state is interpreted in sRGB component space;
- the picker public result and UI theme/style colors are sRGB;
- the material inspector preserves the authored sRGB value during edit,
  serialization and reload;
- `LinearColor` properties use a numeric/HDR-capable editor rather than the SDR
  picker unless a later explicit HDR picker is introduced;
- UI draw-list colors are converted exactly once before linear texture tinting
  and alpha composition;
- UI composition remains before the display output transform.

The C UI API should use an explicitly named standard-layout color type rather
than leaving `tc_ui_color` semantically undocumented. The final spelling is
`tc_ui_srgb_color` unless implementation shows that the value is already past
the linearization boundary, in which case that boundary receives
`tc_ui_linear_color` instead.

## Render and graphics contract

- public immediate/debug/text/component APIs accepting artist-selected colors
  take `SrgbColor`;
- their GPU vertex/uniform payload is `LinearColor`;
- LineRenderer and other non-surface renderers use the same conversion contract
  as surface materials and do not receive pass-specific exceptions;
- render-target clear values are `LinearColor`, including HDR values above
  `1.0`;
- backend APIs never infer encoding from four floats;
- sRGB attachment clear behavior is verified numerically on every backend;
- the universal `Color4` type is removed after all call sites are classified.

## Implementation slices

### 1. Color value foundation

- introduce the two standard-layout types and explicit conversion functions;
- define finite/range policy without implicit clamping;
- add C++ and Python bindings required by downstream slices;
- add IEC sRGB numeric and alpha tests.

### 2. Shader property schema

- teach the parser and reflection schema about `SrgbColor` and `LinearColor`;
- keep their std140 representation compatible with `float4`;
- reject old `Color` and invalid constructor/type combinations;
- carry the property kind through C/Python/runtime-package metadata.

### 3. Material storage and UBO packing

- add distinct material uniform kinds and typed setters/getters;
- preserve typed values through clone, hot reload, serialization and package
  loading;
- convert `SrgbColor` at UBO packing and copy `LinearColor`/`Vec4` literally;
- remove ambiguous `set_color` APIs after callers migrate;
- make conversion failures and type mismatches logged errors.

### 4. Built-in shader and asset migration

- classify every built-in/test `Color` declaration;
- migrate canonical PBR, Blinn-Phong, skybox, text/tint and web fixtures;
- migrate tracked material data without recalibrating it to the old image;
- reject remaining legacy declarations in repository validation.

### 5. Editor authoring migration

- make picker and hex boundaries explicitly sRGB;
- use typed values in material inspector snapshots and setters;
- preserve exact authored-value save/reload round trips;
- give linear/HDR properties a non-SDR editing path;
- update Python bindings and editor tests.

### 6. Component and immediate rendering migration

- migrate LineRenderer, world text, gizmos, debug geometry and immediate
  renderer public inputs;
- convert authored colors once into linear GPU payloads;
- remove direct `Vec4`/raw-float color setters from these paths;
- add pixel coverage for surface and non-surface parity.

### 7. UI linear composition migration

- replace or split `tc_ui_color` at its semantic boundary;
- convert theme, CSS, picker and draw-list colors exactly once;
- ensure texture tint and alpha blending operate on linear RGB while alpha is
  unchanged;
- verify native UI, render-target UI panels and final editor composition.

### 8. Graphics boundary cleanup

- type clear colors as `LinearColor` across Vulkan, OpenGL, D3D11 and WebGPU;
- classify remaining `Color4` users and replace numeric uses with vector/data
  types;
- remove `Color4` and ambiguous color APIs;
- add numeric clear tests for linear UNORM, sRGB and RGBA16F targets.

### 9. Integration gate

- run the full SDK build and central test suite;
- run numeric material UBO and backend pixel tests;
- validate editor reference scenes and Quest OpenXR showcase;
- verify LineRenderer, text, UI panel tinting and alpha composition;
- prove one sRGB decode for authored inputs and one output encoding;
- verify HDR values survive until their intended tone/output boundary;
- document deliberate visual differences and create separate calibration cards
  only where the new correct pipeline exposes weak artistic defaults.

## Kanboard decomposition

The executable slices are tracked under umbrella `#1045`:

| Card | Scope |
|---|---|
| `#1389` | `[base/color] Ввести SrgbColor и LinearColor` |
| `#1390` | `[shaders/color] Разделить цветовые типы в property schema` |
| `#1391` | `[materials/color] Сохранить семантику цвета до UBO` |
| `#1393` | `[shaders/color] Мигрировать built-in color properties` |
| `#1394` | `[editor/color] Сделать authoring цветов явно sRGB` |
| `#1392` | `[render/color] Мигрировать component и immediate color paths` |
| `#1395` | `[ui/color] Провести sRGB UI через linear composition` |
| `#1396` | `[graphics/color] Удалить Color4 и типизировать clear boundaries` |
| `#1397` | `[qa/color] Проверить end-to-end color value contract` |

The dependency graph is:

```text
#1389 foundation
  ├─> #1390 property schema ─> #1391 material/UBO
  │                              ├─> #1393 built-in shaders ─┐
  │                              ├─> #1394 editor authoring ─┤
  │                              └─> #1392 render paths ─────┼─> #1396 cleanup ─┐
  └─> #1395 UI composition ──────────────────────────────────┘                 │
                                                                                ├─> #1397 gate
  #1392, #1393, #1394 and #1395 also feed the final gate directly ─────────────┘
```

Only `#1389` is initially Ready. Cards with a complete scope but unresolved
typed prerequisites remain in Blocked and move to Ready as their implementation
prerequisites reach the board's implementation-complete state.

## Verification matrix

At minimum, automated tests cover:

| Case | Expected result |
|---|---|
| `SrgbColor(0.5)` packed into a material UBO | RGB approximately `0.214041` |
| `LinearColor(0.5)` packed into a material UBO | RGB exactly `0.5` within float tolerance |
| `Vec4(0.5)` packed into a material UBO | components remain `0.5` |
| alpha `0.5` in either color type | alpha remains `0.5` |
| `LinearColor(4.0, ...)` | value reaches the HDR target unclamped |
| picker `#808080` save/reload | returns the same authored hex value |
| picker `#808080` shader input | RGB approximately `0.21586` for byte value 128 |
| sRGB texture multiplied by sRGB tint | both operands are linear at multiplication |
| UI alpha blend | linear RGB composition, unchanged alpha semantics |
| output transform | exactly one linear-to-sRGB encode |

Backend verification covers Vulkan and OpenGL locally, D3D11 on Windows when
available, and Quest Vulkan/OpenXR for the device integration gate. A backend
or device result is judged against numeric/reference expectations, not against
the pre-migration screenshot.

## Commit discipline

The expected commit sequence is:

1. `base: add SrgbColor and LinearColor value types`
2. `materials: add typed color property schema`
3. `materials: preserve color semantics through UBO packing`
4. `shaders: migrate built-in color properties`
5. `editor: make authored colors explicitly sRGB`
6. `render: migrate component and immediate color paths`
7. `ui: linearize authored UI colors at the composition boundary`
8. `graphics: type clear colors and remove legacy Color4`
9. `tests: verify the end-to-end color value contract`

Intermediate commits may temporarily keep an old API only as an in-branch
migration scaffold when required to keep each commit buildable. The final
state has no compatibility alias or fallback, and no released/documented API
may depend on the scaffold.

## Completion criteria

This plan is complete when:

- every scalar color crossing an authoring, material, UI or graphics boundary
  is explicitly `SrgbColor` or `LinearColor`;
- raw vectors are never implicitly interpreted as colors;
- old `Color`, `Color4`, `tc_ui_color` and ambiguous `set_color` APIs are gone;
- authored scalar sRGB colors decode exactly once before linear rendering;
- display output encodes exactly once;
- HDR linear values remain unclamped until their declared output stage;
- all tracked assets and fixtures use the new contract;
- automated and device verification passes against the expected contract;
- visual changes caused by fixing the contract are accepted as migration
  output, while any desired artistic recalibration is tracked separately.
