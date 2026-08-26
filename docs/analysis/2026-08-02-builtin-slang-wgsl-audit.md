# Built-in Slang → WGSL audit

Generated: 2026-08-26

## Result

The pinned matrix is **PASSED**: 102/102 Slang stages passed Slang WGSL generation, independent Naga parsing, and binding-contract checks.

Catalog coverage: 60/60 identities. 1 non-Slang program source is classified separately.

Reproduce from the repository root:

```bash
task check:webgpu-shaders -- --setup
```

Toolchain: Slang 2026.5.2, Naga CLI 30.0.0.

## WebGPU capability profile

- Accepted stages: vertex, fragment, compute. Geometry/tessellation stages are hard blockers.
- Every WGSL resource must have an explicit, unique `@group`/`@binding` pair per stage.
- Constant buffers are emitted as `var<uniform>` with explicit WGSL alignment; Naga validates the resulting layout.
- Slang matrix lowering is accepted only when the generated storage structs and matrix reconstruction pass Naga.
- Textures and samplers remain separate WGSL bindings; no combined-sampler compatibility layer is assumed.
- This is an offline source gate. Browser device limits and render-pipeline creation belong to the WebGPU runtime smoke gate.

Observed across passing stages: 92 uniform-buffer declarations, 25 texture declarations, 25 sampler declarations, and 60 stages using matrices.
All reflected resources are currently placed in bind group 0; the largest binding index is 4. That matches the current single-set backend contract while preserving semantic Termin scopes in sidecar reflection.

## Catalog classification

| UUID | Language | Stages | Classification |
|---|---|---|---|
| `termin-engine-fsq` | slang | vertex | passed |
| `termin-runtime-default-color` | slang | vertex, fragment | passed |
| `termin-engine-shadow` | slang | vertex, fragment | passed |
| `termin-engine-debug-triangle` | slang | vertex, fragment | passed |
| `termin-engine-present-blit` | slang | vertex, fragment | passed |
| `termin-engine-immediate` | slang | vertex, fragment | passed |
| `termin-engine-static-mesh` | slang | vertex, fragment | passed |
| `termin-engine-static-mesh-textured` | slang | vertex, fragment | passed |
| `termin-engine-static-mesh-smooth` | slang | vertex, fragment | passed |
| `termin-engine-static-mesh-textured-smooth` | slang | vertex, fragment | passed |
| `termin-engine-point-cloud` | slang | vertex, fragment | passed |
| `termin-engine-tcplot-3d` | slang | vertex, fragment | passed |
| `termin-engine-tcplot-2d-line` | slang | vertex, fragment | passed |
| `termin-engine-tcplot-2d-styled-line` | slang | vertex, fragment | passed |
| `termin-engine-tcplot-2d-scatter` | slang | vertex, fragment | passed |
| `termin-engine-canvas2d-solid` | slang | vertex, fragment | passed |
| `termin-engine-canvas2d-texture` | slang | vertex, fragment | passed |
| `termin-engine-world2d` | slang | vertex, fragment | passed |
| `termin-engine-text2d` | slang | vertex, fragment | passed |
| `termin-engine-text2d-sdf` | slang | vertex, fragment | passed |
| `termin-engine-text3d` | slang | vertex, fragment | passed |
| `termin-engine-screen-line` | slang | vertex, fragment | passed |
| `termin-engine-screen-line-cap` | slang | vertex, fragment | passed |
| `termin-engine-screen-line-join` | slang | vertex, fragment | passed |
| `termin-engine-screen-line-round-join` | slang | vertex, fragment | passed |
| `termin-engine-world-line` | slang | vertex, fragment | passed |
| `termin-engine-world-line-cap` | slang | vertex, fragment | passed |
| `termin-engine-world-line-join` | slang | vertex, fragment | passed |
| `termin-engine-world-line-round-join` | slang | vertex, fragment | passed |
| `termin-engine-world-line-lit` | slang | fragment | passed |
| `termin-engine-line-default` | slang | vertex, fragment | passed |
| `termin-engine-navmesh-debug` | slang | vertex, fragment | passed |
| `termin-engine-off-mesh-link-debug` | slang | vertex, fragment | passed |
| `termin-engine-voxel-display` | slang | vertex, fragment | passed |
| `termin-engine-voxelizer-line` | slang | vertex, fragment | passed |
| `termin-engine-pick-material` | slang | vertex, fragment | passed |
| `termin-engine-shadow-material` | slang | vertex, fragment | passed |
| `termin-engine-depth-material` | slang | vertex, fragment | passed |
| `termin-engine-id` | slang | vertex, fragment | passed |
| `termin-engine-normal` | slang | vertex, fragment | passed |
| `termin-engine-depth` | slang | vertex, fragment | passed |
| `termin-engine-depth-only` | slang | vertex, fragment | passed |
| `termin-engine-depth-to-color` | slang | fragment | passed |
| `termin-engine-frame-graph-presenter` | slang | fragment | passed |
| `termin-engine-color-to-depth` | slang | fragment | passed |
| `termin-engine-skybox` | shader | — | excluded: program source has no staged Slang entries |
| `termin-engine-bloom-bright` | slang | fragment | passed |
| `termin-engine-highlight` | slang | fragment | passed |
| `termin-engine-gizmo-mask` | slang | vertex, fragment | passed |
| `termin-engine-ground-grid` | slang | vertex, fragment | passed |
| `termin-engine-solid-primitive` | slang | vertex, fragment | passed |
| `termin-engine-grayscale` | slang | fragment | passed |
| `termin-engine-bloom-downsample` | slang | fragment | passed |
| `termin-engine-bloom-blur-vertical` | slang | fragment | passed |
| `termin-engine-bloom-upsample` | slang | fragment | passed |
| `termin-engine-bloom-composite` | slang | fragment | passed |
| `termin-engine-tonemap` | slang | fragment | passed |
| `termin-engine-output-transform` | slang | fragment | passed |
| `termin-engine-multiview-tonemap` | slang | fragment | passed |
| `termin-engine-multiview-output-transform` | slang | fragment | passed |

## Blockers and exclusions

- No Slang-stage WGSL blockers were found in the current catalog.
- `termin-engine-skybox` is a legacy `.shader` program and is outside the Slang-stage matrix. It needs a dedicated WebGPU artifact path or migration to staged Slang before the offline package can be complete.

## Interpretation

The current built-in Slang catalog is viable for an offline WGSL path. This does not yet prove pipeline creation on a real WebGPU device, bind-group compatibility with tgfx2, or visual parity. Those checks remain runtime integration work; this audit deliberately makes them separate gates.
