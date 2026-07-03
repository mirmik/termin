# TcMesh Submesh And Multi-Material GLB Plan

Date: 2026-07-03

Status: draft

## Goal

Add minimal first-class submesh support to `tc_mesh`, teach `MeshRenderer` to
draw submeshes with material slots, and update GLB instantiation so
`/home/mirmik/project/chronosquad-termin/test.glb` renders all glTF primitives
with their correct materials.

The target file currently has:

- one glTF scene and one node;
- one glTF mesh;
- four `mesh.primitives`;
- four materials, each primitive using its own material;
- no skins or animations.

This is standard glTF: each primitive is a separate draw section with one
material. Termin currently parses primitives as separate `GLBMeshData`, but
`instantiate_glb()` adds multiple `MeshComponent`/`MeshRenderer` pairs to the
same entity. `MeshRenderer` binds the first `MeshComponent`, so every renderer
can draw the first primitive instead of its own primitive.

## Non-Goals

- Do not build full Unity/Unreal-level mesh section tooling in this pass.
- Do not add LOD sections, per-section visibility flags, per-section bounds, or
  editor remap UI unless required by the minimal path.
- Do not introduce global `tc_submesh` registry entries or standalone
  `TcSubmeshHandle`.
- Do not preserve a long-term two-mode `tc_mesh` where some meshes are
  containers and some are not.
- Do not silently invent material fallbacks for invalid imported data. Log
  missing or out-of-range material slots.

## Target Model

`tc_mesh` becomes a submesh container in the data model:

```text
tc_mesh
  vertices
  indices
  submeshes[]
    first_index
    index_count
    vertex_offset
    material_slot
    draw_mode
    name
```

Every mesh should have at least one submesh. Legacy/simple meshes are normalized
to one default submesh:

```text
submesh[0] = {
  first_index = 0,
  index_count = mesh.index_count,
  vertex_offset = 0,
  material_slot = 0,
  draw_mode = mesh.draw_mode
}
```

External behavior for single-submesh meshes should remain unchanged:

- existing code that draws a whole mesh still draws the same geometry;
- `mesh.index_count` remains meaningful;
- `MeshRenderer.material` continues to map to material slot `0`;
- callers that do not know about submeshes see one drawable section.

Internally, new rendering code should iterate submeshes rather than treating
`mesh.index_count` as the only draw unit.

## Data Structures

Add `tc_submesh` as an owned value structure inside `tc_mesh`.

Initial C shape:

```c
typedef struct tc_submesh {
    uint32_t first_index;
    uint32_t index_count;
    int32_t vertex_offset;
    uint32_t material_slot;
    uint8_t draw_mode;
    char name[64];
} tc_submesh;
```

Notes:

- `name` is debug/editor metadata, not a stable material key.
- glTF primitives do not have standard names, so importer-generated names are
  acceptable: `<mesh_name>/primitive_0` or `<mesh_name>/<material_name>`.
- material ownership stays in renderer/material assets. `tc_submesh` stores only
  `material_slot`.
- `vertex_offset` should exist from the start because backend command lists
  already expose base-vertex style draw calls.

Add fields to `tc_mesh`:

```c
tc_submesh* submeshes;
size_t submesh_count;
```

Memory ownership follows existing mesh buffer ownership: `tc_mesh_set_data()`,
registry destroy, copy/update paths, and primitive mesh builders must free or
replace submesh arrays consistently.

## Mesh API

Add a small C API first:

```c
bool tc_mesh_set_submeshes(
    tc_mesh* mesh,
    const tc_submesh* submeshes,
    size_t submesh_count);

size_t tc_mesh_get_submesh_count(const tc_mesh* mesh);
const tc_submesh* tc_mesh_get_submesh(const tc_mesh* mesh, size_t index);
bool tc_mesh_ensure_default_submesh(tc_mesh* mesh);
```

Extend data creation APIs conservatively:

- keep existing `tc_mesh_set_data()` behavior and have it create/update the
  default submesh;
- add an extended setter only if needed by C++/Python call sites, for example
  `tc_mesh_set_data_with_submeshes(...)`;
- keep `TcMesh::from_interleaved(...)` as a single-submesh constructor;
- add `TcMesh::from_interleaved_with_submeshes(...)` for importers.

Python bindings should expose enough for tests and GLB import:

- read-only `submesh_count`;
- `submesh_at(index)` or a small `TcSubmesh` value binding;
- optional constructor support for a list of submesh specs.

Avoid `setattr`/`getattr`-style Python fallbacks when updating GLB code.

## Backend Draw Range

The backend already has lower-level indexed draw support with first-index and
vertex-offset parameters. The missing link is the `tc_mesh` bridge.

Add a draw-range path to the tgfx2 bridge:

```cpp
bool draw_tc_submesh(
    tgfx::RenderContext2& ctx,
    tc_mesh* mesh,
    size_t submesh_index,
    const VertexBufferLayout* layout_override);
```

Implementation should:

- wrap/upload the same mesh buffers as `draw_tc_mesh()`;
- validate `submesh_index`, `first_index`, and `index_count`;
- set topology from `submesh.draw_mode`, falling back to `mesh.draw_mode`;
- call `ctx.draw(...)` or a new bridge helper that can pass index offset/count;
- log errors for invalid ranges instead of drawing the whole mesh by accident.

If `RenderContext2::draw(...)` cannot express the range cleanly, add a narrow
overload rather than bypassing the context:

```cpp
ctx.draw_indexed_range(
    vertex_buffer,
    index_buffer,
    first_index,
    index_count,
    vertex_offset,
    index_type);
```

## MeshRenderer

Extend `MeshRenderer` with material slots while keeping the existing single
material path intact.

Minimal model:

```cpp
TcMaterial material;                // slot 0 / default material
std::vector<TcMaterial> materials;  // optional explicit slots
```

Material resolution:

```text
submesh.material_slot -> renderer.materials[slot] if present and valid
                      -> renderer.material for slot 0
                      -> logged fallback to renderer.material for invalid slot
```

Important behavior:

- `MeshRenderer.material` remains the canonical slot `0` field for old scenes.
- `materials` may be empty for old scenes; slot `0` then resolves to
  `material`.
- glTF instantiation should populate `materials` with per-material override
  copies or imported material assets.
- `_override_material` remains useful for single-material renderers. For
  submesh renderers, either migrate override data into slot `0` only in the
  minimal pass, or introduce per-slot override data if GLB import needs it.
  The minimal GLB path can avoid `_override_material` by constructing material
  slot instances directly.

`get_geometry_draws()` should return one draw call per phase per submesh:

```text
for submesh_index in mesh.submeshes:
  material = material_for_submesh(submesh_index)
  for phase in material.phases matching requested phase_mark:
    GeometryDrawCall(phase, geometry_id = submesh_index)
```

`get_mesh_for_phase(phase, geometry_id)` can keep returning the same mesh.
The pass must use `geometry_id` to draw the matching submesh range.

Add helper methods:

```cpp
size_t material_slot_count() const;
TcMaterial get_material_for_submesh(size_t submesh_index) const;
TcMaterial get_material_for_slot(size_t slot) const;
void set_material_slot(size_t slot, const TcMaterial& material);
```

Log missing material slots with mesh name, submesh name, slot index, and entity
name where available.

## Render Passes

Update passes that draw `MeshRenderer`/`Drawable` mesh geometry through
`geometry_id`:

- `ColorPass`;
- shadow pass;
- depth pass;
- normal pass;
- id pass if it uses mesh draw calls.

For mesh-backed drawables:

```text
mesh = drawable->get_mesh_for_phase(phase, geometry_id)
draw submesh geometry_id from mesh
```

Non-mesh drawables that use `geometry_id` for their own internal geometry should
continue to work. The submesh draw path should only be used when the drawable is
mesh-backed and returns a `tc_mesh*`.

## GLB Loader And Instantiator

The preferred minimal GLB shape is:

- one `GLBMeshData` per glTF mesh;
- one primitive/submesh record per glTF primitive;
- one `TcMesh` with combined buffers and submesh ranges;
- one `MeshRenderer` with material slots for all materials used by the mesh.

Add a GLB primitive metadata structure, for example:

```python
class GLBSubmeshData:
    def __init__(
        self,
        name: str,
        first_index: int,
        index_count: int,
        material_index: int,
    ):
        ...
```

Update `GLBMeshData`:

- keep flattened/interleaved geometry arrays for `TcMesh`;
- add `submeshes: list[GLBSubmeshData]`;
- keep `material_index` only as a compatibility shortcut for
  single-submesh meshes, or remove it after all call sites migrate.

When parsing glTF primitives:

1. Read primitive attributes and indices.
2. Expand or append vertices as the current loader does.
3. Append primitive-local indices adjusted by the current vertex base.
4. Add a `GLBSubmeshData` with `first_index`, `index_count`, and
   `material_index`.
5. Map `primitive.material` values to renderer material slots. A simple first
   pass may use glTF material index as `material_slot`, but a compact
   per-mesh slot table is better if material indices are sparse.

`scene_data.mesh_index_map` should map a glTF mesh index to one Termin mesh
index, not one index per primitive.

`instantiate_glb()` should:

- add one `MeshComponent` and one `MeshRenderer` for each glTF mesh instance;
- populate renderer material slots from the mesh submeshes' material indices;
- apply glTF PBR data to the corresponding material slot;
- avoid adding multiple `MeshComponent` instances to the same entity for one
  glTF mesh;
- keep skinned mesh handling equivalent, with `SkinnedMeshRenderer` using the
  same material slot/submesh machinery inherited from `MeshRenderer`.

For `test.glb`, the desired instance result is one entity with:

```text
MeshComponent(mesh = geometry_0.012)
MeshRenderer(materials = [Material_0.038, Material_0.034, Material_0.037, Material_0.024])
TcMesh.submeshes = 4 sections
```

Each color/depth/shadow draw pass then emits four draw calls for the mesh,
selecting the material by `submesh.material_slot`.

## Asset And Runtime Package Serialization

Update mesh export/import paths that serialize `tc_mesh`:

- project build mesh exporter;
- runtime package mesh parser/loader;
- any JSON/spec mesh format tests;
- C# binding structs only if they expose mesh data creation or metadata.

Serialized mesh data should include submeshes explicitly:

```json
{
  "layout": [...],
  "vertices": [...],
  "indices": [...],
  "submeshes": [
    {
      "first_index": 0,
      "index_count": 546387,
      "vertex_offset": 0,
      "material_slot": 0,
      "draw_mode": "triangles",
      "name": "geometry_0.012/Material_0.038"
    }
  ]
}
```

If `submeshes` is absent in old data, the parser should normalize to one
default submesh and log at debug/info level only if useful. This is migration
normalization, not a permanent two-mode model.

## Tests

Add focused tests before broad integration tests:

1. `tc_mesh` C/C++ test:
   - `tc_mesh_set_data()` creates one default submesh;
   - `tc_mesh_set_submeshes()` stores and validates ranges;
   - invalid ranges are rejected or logged consistently.

2. Python `tmesh` API test:
   - a mesh can expose `submesh_count`;
   - a test mesh with two submeshes reports expected ranges/material slots.

3. `MeshRenderer` C++/Python API test:
   - single-submesh mesh produces one geometry draw;
   - two-submesh mesh produces two geometry draws;
   - material selection follows `submesh.material_slot`.

4. GLB loader test:
   - synthetic `.gltf` with one mesh and two primitives loads as one
     `GLBMeshData` with two submeshes;
   - material indices are preserved.

5. GLB instantiator test:
   - one node with one multi-primitive mesh creates one `MeshComponent`;
   - renderer has material slots for both primitives;
   - no duplicate `MeshComponent` on that entity.

6. Render bridge/pass smoke:
   - construct a mesh with two colored submeshes sharing one buffer;
   - verify two draw calls use different index ranges and materials;
   - if a headless pixel test is practical, make the two triangles visibly
     different colors.

7. Real asset smoke:
   - load and instantiate
     `/home/mirmik/project/chronosquad-termin/test.glb`;
   - verify mesh count, submesh count `4`, material slot count `4`;
   - manually or screenshot-verify that all four material regions render.

## Execution Order

### 1. Add `tc_submesh` Storage And Default Normalization

Implement the owned submesh array in `tc_mesh`, update allocation/free paths,
and make all existing mesh constructors produce one default submesh.

Verification:

```bash
./run-tests.sh
```

If full tests are too slow during development, first run the affected C/C++
mesh tests and Python `tmesh` tests, then run the central script before closing.

### 2. Expose Submeshes Through C++ And Python

Add C++ `TcMesh` helpers and Python bindings. Keep old constructors source
compatible.

Verification:

```bash
./run-tests-python.sh termin-mesh/tests
```

### 3. Add Draw-Range Support To The tgfx2 Bridge

Thread submesh ranges into `draw_tc_mesh` or add explicit `draw_tc_submesh`.
Make invalid ranges fail loudly.

Verification:

```bash
./run-tests.sh
```

### 4. Teach `MeshRenderer` Material Slots And Geometry Draws

Add material slot storage/resolution and make `get_geometry_draws()` enumerate
submeshes. Keep old `material` behavior as slot `0`.

Verification:

```bash
./run-tests.sh
```

### 5. Update Render Passes To Draw `geometry_id` As Submesh Index

Use the bridge submesh draw path in color, shadow, depth, normal, and id passes.
Do not reinterpret `geometry_id` for non-mesh direct drawables.

Verification:

```bash
./run-tests.sh
```

### 6. Migrate GLB Mesh Data To One Mesh With Submeshes

Change loader and asset population so glTF `mesh.primitives[]` become
`TcMesh.submeshes[]`, not sibling `GLBMeshData` entries.

Verification:

```bash
./run-tests-python.sh termin-glb/tests
```

### 7. Update GLB Instantiation Material Slot Population

Create one renderer per glTF mesh instance and populate material slots from
submesh material indices. Apply PBR overrides per slot.

Verification:

```bash
./run-tests-python.sh termin-glb/tests
```

### 8. Update Runtime Package Mesh Serialization

Add explicit `submeshes` to mesh export/import, normalize old data, and update
tests.

Verification:

```bash
./run-tests.sh
```

### 9. Real `test.glb` Validation

After rebuilding SDK:

```bash
./build-sdk.sh --no-wheels
```

Use either a small script or editor run to instantiate
`/home/mirmik/project/chronosquad-termin/test.glb` and verify:

- one loaded Termin mesh for glTF mesh `geometry_0.012`;
- four submeshes;
- four material slots;
- four draw calls in color pass for the mesh;
- no repeated drawing of only primitive `0`;
- all material regions visible.

## Migration Notes

- Old mesh data without `submeshes` is normalized at load time to one default
  submesh.
- Existing primitive mesh builders should call the ordinary mesh setter and get
  default submesh behavior automatically.
- Existing `MeshRenderer` scenes keep using `material` as slot `0`.
- The GLB child mesh asset UUID model changes for multi-primitive glTF meshes:
  previously one child mesh could be created per primitive; after this plan one
  child mesh should be created per glTF mesh. Existing specs may need a one-time
  regeneration if they already captured per-primitive child mesh UUIDs.

## Risks And Follow-Ups

- `MeshRenderer` material override serialization currently assumes one
  overridden material. Per-slot overrides may need a follow-up format once
  editor material remapping matters.
- Picking/id pass may need to expose submesh id in hit/debug data. Minimal
  support can keep entity-level selection unchanged.
- Navmesh/collision systems should continue using whole `tc_mesh` geometry.
  If they later need material/section filtering, that should be a separate API.
- Submesh bounds are useful for culling and editor debug but not required for
  `test.glb`; add them after the first render-correct implementation.
- A future reimport workflow should use stable source keys such as
  `mesh:0/primitive:3`, not submesh names, for material remap stability.
