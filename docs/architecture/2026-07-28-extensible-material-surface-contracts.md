# Extensible Material Surface Contracts

Date: 2026-07-28.

Status: accepted target architecture for the first deferred-rendering
prototype.

Related board decisions:

- #991 `[render/material] Определить полноценный SurfaceData contract`;
- #992 `[graphics/render] Определить backend-neutral MRT contract`.

Implementation is tracked by umbrella #1012
`[render] Prototype extensible deferred surface pipeline`:

- #1013 surface contract registry;
- #1014 `.shader` surface producer metadata;
- #1018 producer/consumer fragment assembly;
- #1016 project-owned contract extensibility smoke;
- #1021 `CookTorrancePBR` migration;
- #1020 `StandardGBufferPass`;
- #1015 `StandardDeferredLightingPass`;
- #1017 forward-only routing;
- #1022 offline surface-pass artifacts;
- #1019 `DeferredPrototype` integration.

The earlier readiness analysis lives in
[`../analysis/2026-07-28-deferred-rendering-readiness.md`](../analysis/2026-07-28-deferred-rendering-readiness.md).

## Decision

Termin will not define one closed engine-wide C++ `SurfaceData` structure.
Instead, the material pipeline will compose versioned shader-side surface
producer and consumer contracts.

The first built-in contract is:

```text
termin.surface.standard-pbr@1
```

It is implemented through the same public contract and pass APIs that
project-owned modules use. A game plugin may register another surface contract,
material evaluators, G-buffer encoder/decoder, and render passes without adding
its fields or shading model to an engine enum.

The first prototype adds a separate deferred pipeline alongside the existing
`Default` pipeline. It does not replace or silently alter `Default`.

## Baseline before implementation

Termin does not currently have a real surface-shader concept.

A parsed `.shader` phase owns complete executable vertex and fragment stages.
The material pipeline can assemble a modular vertex stage from a transform
provider and a pass-owned output adapter, but fragment selection is binary:

```text
use the candidate shader fragment stage unchanged
or
replace the complete fragment stage with a pass override
```

There is no material-owned `evaluate_surface()` entry, no declared fragment
output contract, and no way for a pass-owned fragment entry to consume
material-specific surface evaluation.

`MaterialPipelinePassContract::uses_material_fragment` is also misleading
today. It means “use the candidate shader fragment”; some geometry passes use
an engine shader as that candidate, so it is not necessarily material-owned
code.

The existing extension points are nevertheless useful:

- project-owned pass types can be registered through `tc_pass_registry`;
- phase marks are open project-owned representation labels;
- render items are planned against pass-owned shader contracts;
- vertex transform providers and output adapters already use modular assembly;
- resource ownership and bind-by-name reflection are backend-neutral;
- derived shader variants have canonical identities and stale-source
  invalidation;
- pass-aware shader usage collection feeds offline package builds.

The missing boundary was fragment producer/consumer composition.

## Implemented foundation

Cards #1013, #1014, #1018, and #1016 establish and verify the composition
boundary:

- exact versioned surface contracts are owner-aware registry entries;
- `.shader` phases publish evaluator-only producer metadata on `tc_shader`;
- a pass selects `FinalColor`, `SurfaceConsumer`, or `PassOwned` explicitly;
- `SurfaceConsumer` concatenates registered interface, evaluator, and consumer
  sources into one executable Slang fragment program;
- producer and consumer fragment inputs are validated against the selected
  vertex transform before shader creation;
- material, transform, adapter, consumer, and pass resources are merged into
  the executable shader contract;
- variant identity includes producer, interface, consumer, transform, adapter,
  resources, and composition mode;
- a producer cannot pass through the final-color planning fast path or compile
  directly as a GPU program.
- a separately built test plugin registers a project-owned surface with a
  custom field through public APIs, composes and compiles its final variant,
  then revokes the owner while the standard contract remains intact; future
  planning rejects the removed contract without reading stale registry data.

The later prototype cards still own standard consumers, G-buffer passes,
routing, package enumeration, and deferred-pipeline integration.

## Goals

1. Separate material evaluation from lighting and render-target encoding.
2. Let one surface material produce forward and G-buffer variants.
3. Let a plugin introduce a different `SurfaceData` without modifying engine
   source.
4. Keep G-buffer packing owned by the pipeline, not by material assets.
5. Keep final-color shaders as an explicit forward-only material class.
6. Preserve static, skinned, and foliage vertex-transform composition.
7. Produce deterministic offline shader artifacts for every material × pass ×
   transform variant.
8. Build a prototype deferred pipeline next to `Default` and render standard
   opaque PBR surfaces through it.

## Non-goals of the first prototype

- replacing the `Default` pipeline;
- transparent deferred rendering;
- deferred MSAA;
- compact or production-optimized G-buffer packing;
- multiple shading models inside the standard G-buffer;
- clearcoat, subsurface, anisotropy, hair, refraction, or decals;
- expressing the current nonstandard `u_diffuse_mul` and `u_subsurface`
  behavior through standard surface v1;
- an automatic fallback after a declared surface variant fails to assemble;
- a stable cross-SDK binary ABI for every current C++ material-pipeline type.

The prototype is allowed to change the appearance of `CookTorrancePBR`.
Correct contract boundaries are more important than preserving the current
shader's exact colors.

## Terminology

### Surface contract

A versioned shader ABI describing the semantic result of material evaluation:

```text
contract id + exact version + shader-side interface definition
```

The contract identity is opaque to the engine. The engine matches identities;
it does not inspect a universal list of surface fields or shading models.

### Surface producer

Material-owned shader code that declares which surface contract it produces
and provides its evaluator entry:

```slang
TerminStandardSurfaceV1 evaluate_surface(FragmentInput input);
```

Material textures, uniform parameters, sampling policy, and local formulas
remain private to the producer.

### Surface consumer

Pass-owned shader code that accepts one exact surface contract and turns it
into a pass output:

- forward lighting;
- G-buffer encoding;
- material debug output;
- a future coverage/depth policy.

### Final-color material

An authored material fragment that returns an executable `SV_Target` result
and declares no surface producer contract. It participates only in passes that
explicitly accept final-color fragments.

Absence of a surface contract is not an error and is not a failed deferred
fallback. It is an explicit material capability.

## Contract identity and registry

The public identity is conceptually:

```c
typedef struct tc_surface_contract_key {
    const char* id;
    uint32_t version;
} tc_surface_contract_key;
```

The first implementation should use exact version matching. Automatic
min/max-version compatibility is deferred until a real compatible evolution
exists.

A registered descriptor owns the shared shader-side interface source:

```c
typedef struct tc_surface_contract_desc {
    tc_surface_contract_key key;
    const char* debug_name;
    const char* surface_type_name;
    const char* interface_source;
    const char* source_identity;
} tc_surface_contract_desc;
```

The exact C API may use bounded owned strings rather than borrowed pointers.
The required invariants are:

- `(id, version)` is globally unique in one runtime;
- registering a different descriptor under an existing key is an error;
- `source_identity` changes when interface source changes;
- descriptors are owner-aware so a project module can be unloaded safely;
- built-in contracts register through the same path as project contracts;
- the registry never assigns semantic meaning to an arbitrary contract id.

For the prototype the assembler may concatenate registered interface source,
material evaluator source, and consumer source into one Slang translation unit.
This avoids making project-owned Slang import roots a hidden prerequisite.

Reusable project-owned Slang modules remain a desirable separate extension:
the current runtime dependency scanner resolves imports only from built-in
shader roots. A later module registry or package-owned shader-module root may
replace source concatenation, but the surface contract must not depend on
process-global ad hoc include paths.

## Material producer metadata

The `.shader` format gains explicit phase-level producer metadata. Proposed
authoring form:

```text
@surface contract=termin.surface.standard-pbr version=1
         type=TerminStandardSurfaceV1 entry=evaluate_surface
@surfaceInput world_pos float3
@surfaceInput normal_world float3
```

`@surface` is serialized on one line in the actual parser. The contract id and
version are normative. `type` and `entry` are validated against the registered
descriptor and evaluator source. Repeatable `@surfaceInput` directives declare
the producer's vertex-to-fragment semantic requirements explicitly; the pass
does not infer or supply them from source text.

The parsed phase carries a material fragment program separate from the final
executable shader contract:

```cpp
struct MaterialSurfaceProducerContract {
    SurfaceContractKey surface;
    std::string surface_type_name;
    std::string evaluator_entry;
    std::string evaluator_source;
    MaterialFragmentInterface required_fragment_input;
    std::vector<MaterialPipelineResourceDecl> resources;
};
```

The producer must declare its own fragment-input requirements. A pass must not
invent them on behalf of the material as the current
`material_pipeline_material_contract_from_shader(shader, required_input)` API
does.

The runtime representation must distinguish:

```text
Executable final-color fragment
Surface producer fragment program
```

A surface producer is authoring input for assembly, not a directly bindable GPU
fragment program. Attempts to bind it without a consumer must fail with an
error log.

The implementation may initially keep producer metadata on `tc_shader` to
reuse source identity, resource layout, variant invalidation, and material
phase references. If so, `tc_shader` needs an explicit program role; it must
not pretend that an evaluator-only source is an executable fragment entry.

## Pass consumer contract

Fragment selection becomes an explicit mode:

```cpp
enum class MaterialFragmentComposition {
    FinalColor,
    SurfaceConsumer,
    PassOwned,
};
```

The pass-owned consumer descriptor is conceptually:

```cpp
struct MaterialSurfaceConsumerContract {
    SurfaceContractKey accepted_surface;
    std::string consumer_source;
    std::string fragment_entry;
    std::string source_identity;
    MaterialFragmentInterface required_fragment_input;
    std::vector<MaterialPipelineResourceDecl> resources;
};
```

Meanings:

- `FinalColor`: use an executable material fragment unchanged;
- `SurfaceConsumer`: assemble a compatible material evaluator with the
  pass-owned consumer;
- `PassOwned`: ignore material fragment code and use a complete pass fragment.

This replaces the ambiguous `uses_material_fragment` boolean. Transitional
adapters may exist while built-in passes migrate, but new surface code must use
the explicit mode.

## Fragment assembly

For a surface consumer, assembly is:

```text
registered surface interface source
+ material evaluator source
+ pass consumer source
+ selected fragment entry
```

For the standard forward pass:

```slang
[shader("fragment")]
FragmentOutput termin_standard_forward_fs(FragmentInput input)
{
    TerminStandardSurfaceV1 surface = evaluate_surface(input);
    return termin_integrate_standard_pbr(surface, input.world_pos);
}
```

For the standard G-buffer pass:

```slang
[shader("fragment")]
TerminStandardGBufferOutput termin_standard_gbuffer_fs(FragmentInput input)
{
    TerminStandardSurfaceV1 surface = evaluate_surface(input);
    return termin_encode_standard_gbuffer(surface);
}
```

The consumer owns lighting, shadow sampling, output structures, target
semantics, and G-buffer packing. The material owns only surface evaluation.

Assembly validation must reject:

- unknown surface contract;
- producer/consumer key mismatch;
- a surface producer used by a final-color-only pass;
- a final-color material used by a surface-only pass;
- missing vertex-to-fragment semantics;
- duplicate or conflicting material/pass resources;
- missing evaluator or consumer entry;
- binding a surface producer without an executable consumer.

These failures are deterministic planning/build errors. They do not silently
route the item to another pass.

## Variant identity and artifacts

The canonical variant fingerprint includes:

- original material program UUID and source version;
- surface contract id and exact version;
- registered interface `source_identity`;
- evaluator entry and source identity;
- consumer entry and source identity;
- vertex transform provider and output adapter identities;
- merged resource contract;
- final fragment composition mode.

The resulting shader is an ordinary executable `tc_shader` variant with a
normal reflected resource layout.

The shader compiler does not need to understand the semantic fields of
`SurfaceData`. Slang type checking validates the composed source. Termin's
compiler and artifact paths need only:

- compile the final assembled entry;
- preserve reflected resources and scopes;
- include every composed source identity in staleness metadata;
- package every pass-aware executable variant;
- avoid compiling an evaluator-only producer as a GPU entry.

The existing usage collector already walks pipeline passes and render items.
It should enumerate final variants only; producer handles are dependencies, not
standalone GPU artifacts.

Runtime packages make this distinction explicit. Authoring shaders with a
surface producer use `artifact_role: surface_producer`: their evaluator and
exact contract/interface identities are serialized for runtime planning, but
they have no `artifacts` table and are never submitted to `termin_shaderc`.
Executable pass results retain normal backend artifacts. The manifest's
`pipeline_shader_requirements` table binds every collected result to its scene
and pipeline, including the composed-source identity; package validation checks
that each required spec, backend and stage exists before the runtime starts.

## Standard PBR surface v1

The first built-in interface is intentionally small and close to the common
metallic-roughness model:

```slang
struct TerminStandardSurfaceV1 {
    float3 base_color;
    float3 normal_world;
    float metallic;
    float perceptual_roughness;
    float occlusion;
    float3 emission;
    float opacity;
};
```

Semantic rules:

- colors and emission are linear;
- `normal_world` is normalized world space;
- `metallic`, `perceptual_roughness`, `occlusion`, and `opacity` are clamped to
  `[0, 1]`;
- the standard prototype handles only opaque geometry, so G-buffer encoding
  does not use `opacity`;
- world position is a fragment/pass input and is not duplicated in surface
  data;
- the contract identity already selects the standard PBR model, so v1 has no
  engine-owned shading-model discriminator.

`u_diffuse_mul`, `u_subsurface`, clearcoat, and other current or future
material-specific controls are not fields of v1. `CookTorrancePBR` will be
migrated toward the standard model. Appearance changes are accepted. The
previous artistic forward model remains available as the separate final-color
shader `CookTorrancePBRSubsurface`; it deliberately does not claim
compatibility with standard surface v1.

If a future material needs semantics that v1 cannot express, it should use a
new contract or remain forward-only. It must not grow undocumented spare
channels in the standard contract.

## Standard prototype G-buffer

The semantic surface contract is independent from packing. The first prototype
uses deliberately simple, high-precision planes:

```text
gbuffer_base_ao       RGBA16F: base_color.rgb, occlusion
gbuffer_normal_rough  RGBA16F: normal_world.xyz, perceptual_roughness
gbuffer_metal_emit    RGBA16F: metallic, emission.rgb
scene_depth           D32F
```

All planes are single-sample. This layout is intentionally inefficient but
avoids premature packed-format and color-space decisions. Production packing
is a later pipeline-owned change and does not change
`termin.surface.standard-pbr@1`.

World position is reconstructed from `scene_depth` and inverse view-projection.

## Prototype passes and routing

### `StandardGBufferPass`

Responsibilities:

- request the `opaque` drawable representation;
- accept only `termin.surface.standard-pbr@1` producers;
- use the standard surface G-buffer consumer;
- write the three named color planes and shared depth through the
  backend-neutral MRT contract;
- decline final-color and incompatible surface materials as a normal routing
  result, while logging compatible producers whose variant assembly fails;
- expose every plane to framegraph capture/debugging.

### `StandardDeferredLightingPass`

Responsibilities:

- read the three standard planes, depth, scene lights, and shadow resources;
- reconstruct world position;
- decode `TerminStandardSurfaceV1`;
- perform standard PBR lighting and apply per-light shadow visibility;
- add emission without direct-light shadowing;
- combine the lit result with a background input for pixels without geometry;
- write one HDR scene color texture.

It is a fullscreen pass and does not invoke material evaluators.

### Forward passes

The deferred pipeline still contains forward geometry passes:

- opaque final-color or incompatible materials render after deferred lighting;
- transparent materials render after opaque forward-only materials;
- both reuse the depth produced by `StandardGBufferPass`.

The route is based on explicit material fragment capability, not on a failed
G-buffer compilation:

```text
opaque + standard-pbr@1 producer -> StandardGBufferPass
opaque + final-color/other surface -> forward-only opaque
transparent -> forward transparent
```

For the prototype a representation may be skipped by one pass without logging
an error when it is intentionally claimed by the complementary forward pass.
Once a pass claims a compatible producer, variant assembly failure remains an
error.

## Prototype pipeline beside `Default`

The new pipeline is registered as a separate built-in/default asset, tentatively
named `DeferredPrototype`:

```text
ShadowPass
SkyBoxPass
StandardGBufferPass
StandardDeferredLightingPass
ForwardColorPass (opaque forward-only, shared scene_depth)
ForwardColorPass (transparent, far-to-near, shared scene_depth)
World2DPass
BloomPass
UIWidgetPass
PresentToScreenPass
```

`SkyBoxPass` writes an explicit background texture.
`StandardDeferredLightingPass` reads it and preserves it where `scene_depth`
contains no geometry. The prototype is single-sample throughout and therefore
does not insert `ResolvePass`. It must not introduce a hidden backbuffer
dependency.

`Default` remains:

```text
Shadow -> Skybox -> forward opaque -> forward transparent -> ...
```

The deferred prototype succeeds when the same test scene can select either
pipeline and a standard opaque PBR mesh moves from the forward color fragment
to G-buffer + deferred lighting without changing the material asset.

## Plugin-owned surface family

A project module should be able to provide:

```text
game.surface.weathered@1 descriptor
material assets producing game.surface.weathered@1
GameGBufferPass consuming game.surface.weathered@1
GameDeferredLightingPass decoding its G-buffer
pipeline template containing those passes
```

No engine switch statement gains `Weathered`, `Wetness`, or a project shading
model enum. The plugin owns:

- surface interface source;
- evaluation semantics;
- G-buffer formats and packing;
- encoder and decoder;
- lighting and shadow policy;
- pass types and resource names.

The engine owns:

- contract registration and exact matching;
- source composition;
- vertex/fragment interface validation;
- resource merging and binding;
- variant identity and artifact lookup;
- framegraph scheduling and MRT mechanics;
- diagnostics.

The prototype must include a test-only second surface contract with a field not
present in standard PBR. A project-owned producer and consumer must assemble
through public APIs without editing an engine enum or standard surface source.
This is the acceptance proof for extensibility.

## C and plugin ABI direction

The current `MaterialPipelinePassContract` contains C++ standard-library types
and is suitable only for modules built against the exact SDK. The first
prototype may use that boundary internally, but surface registration must have
a C-compatible descriptor projection or a clear wrapper path.

Long-term plugin-safe APIs need:

- owner-aware register/unregister;
- copied descriptor/source storage;
- no borrowed plugin pointers after unload;
- deterministic invalidation of variants that depend on an unloaded contract;
- stable opaque handles or versioned C descriptors;
- C++ and Python conveniences as projections, not separate registries.

This document does not require freezing the entire material-pipeline C ABI in
the first prototype.

## Impact on shader mechanics

The prototype requires meaningful Termin shader-system work, but it does not
require a new shading language or backend compiler:

| Layer | Required change |
| --- | --- |
| `.shader` parser | Parse surface producer metadata and evaluator-only fragment role. |
| Material/runtime metadata | Store producer contract, entry, source identity, inputs, and resources. |
| Material pipeline assembler | Compose interface + evaluator + consumer and validate exact contracts. |
| Variant cache | Add producer/consumer identities and contract version to the fingerprint. |
| `tc_shader` lifecycle | Distinguish authoring producer from executable shader variant. |
| Shader usage collection | Export executable variants, not evaluator-only producers. |
| Package builder | Compile/package forward and G-buffer variants selected by the pipeline. |
| `termin_shaderc` | No knowledge of PBR fields; continue compiling final Slang entries and reflecting resources. |
| Backends | No surface-specific logic; only the separate MRT foundation is required. |

The largest shader-side changes are therefore in Termin's parser, metadata,
assembly, and artifact enumeration. Vulkan, OpenGL, and D3D11 do not learn what
`SurfaceData` means.

## Dependency on MRT

Surface producer/consumer assembly can be implemented and tested before MRT.
The complete deferred prototype depends on #992.

The assumed MRT shape is:

- independent named framegraph texture resources;
- a pass-local ordered color attachment set;
- shared explicit depth attachment;
- pipeline cache identity containing the ordered color format array;
- per-attachment clear/load/store semantics;
- cross-backend `SV_TargetN` parity.

This document does not replace the detailed MRT architecture decision.

## Migration policy

1. Existing final-color materials remain valid in the `Default` pipeline.
2. A material declares surface production explicitly; no source-text guessing.
3. `CookTorrancePBR` becomes the first standard surface producer.
4. The standard forward consumer preserves the ability to render the migrated
   material in `Default`.
5. `CookTorrancePBRSubsurface` preserves the former wrapped-diffuse
   `u_subsurface` and `u_diffuse_mul` look as an independent final-color
   material; `NormalizedPBR` remains on that path.
6. `BlinnPhong`, normal-visualization, and other custom final-color shaders
   remain forward-only until deliberately migrated.
7. Declared surface incompatibility is a routing fact; declared compatibility
   followed by failed assembly is an error.
8. No automatic conversion between unrelated surface contracts is introduced.

## Verification

The implementation is not complete until all of the following exist:

- parser tests for valid and invalid surface declarations;
- registry duplicate/version/unload tests;
- assembler tests for standard and project-owned contracts;
- mismatch and evaluator-only bind diagnostics;
- static, skinned, and foliage standard-surface variants;
- forward and G-buffer variants from one `CookTorrancePBR` producer;
- resource reflection proving G-buffer variants omit lighting/shadow resources;
- pass-aware package export containing all final variants;
- three-target MRT smoke with shared depth on Vulkan, OpenGL, and D3D11;
- a pixel smoke for G-buffer encode/decode;
- a deferred shadow smoke;
- a pipeline test proving `Default` and `DeferredPrototype` coexist;
- a project-owned custom surface field compiled without engine modification;
- `./build-sdk.sh` and `./run-tests.sh`.

## Consequences

Positive:

- deferred is not tied to one engine-owned material struct;
- standard and project pipelines use the same assembly machinery;
- material authoring is independent from G-buffer packing;
- forward remains a first-class path rather than an emergency fallback;
- backends remain unaware of material semantics.

Costs:

- material shader phases gain an authoring-program concept in addition to
  executable shaders;
- fragment variant count grows by pass and transform;
- package builds must collect pipeline-specific variants accurately;
- project-owned reusable Slang modules will eventually need a first-class
  source/package registry;
- plugin-safe descriptor lifetime must be designed rather than borrowing C++
  strings across unload.
