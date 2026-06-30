# Runtime package exporter responsibility split

Date: 2026-06-30
Status: active
Kanboard: `#161 [build/runtime] Разделить runtime_package_exporter responsibilities`

## Goal

Разделить `termin.project_build.runtime_package_exporter` на небольшие
модули с явными зонами ответственности, не меняя формат runtime package в
первом проходе.

После миграции верхний `export_runtime_package()` должен быть orchestration
layer: прочитать сцену, собрать refs, вызвать writers/providers, записать
manifest. Детали поиска project assets, live registry export, fallback policy,
builtin shader catalog и shader artifacts не должны жить в одном файле.

## Current State

`termin-project-build/python/termin/project_build/runtime_package_exporter.py`
содержит примерно 1675 строк и смешивает:

- чтение entry scene и сбор runtime refs;
- эвристики mesh/material refs по имени поля и имени ресурса;
- поиск `.material`, `.pipeline`, `.obj` и `.stl` в проекте;
- live export mesh/material/shader из runtime registries;
- `strict` / `dev_smoke` fallback policy;
- lookup transitional `engine-shader-catalog.json`;
- генерацию builtin/default shader artifacts;
- запись package resources, JSON файлов и manifest.

Главные запахи:

- `_looks_like_mesh_ref()` и `_looks_like_material_ref()` смешивают explicit
  metadata (`kind`, `role`) с legacy inference по именам;
- `_builtin_shader_catalog_path()` делает exporter ещё одним владельцем
  transitional engine shader catalog lookup;
- writer-функции принимают и мутируют shared `resources`, `diagnostics`,
  `shaders`, из-за чего границы ответственности не видны.

## Target Module Layout

Первый проход должен сохранить публичный импорт
`termin.project_build.runtime_package_exporter` и текущий package format, но
вынести внутренние обязанности:

```text
termin/project_build/
  runtime_package_exporter.py          # public API + orchestration
  runtime_package/
    __init__.py
    models.py                          # diagnostics, result, refs, shader specs
    package_files.py                   # clean dir, write_json, resource sorting
    scene_refs.py                      # scene reading and runtime ref collection
    pipelines.py                       # project pipeline lookup/export
    meshes.py                          # project/live/fallback mesh export
    materials.py                       # live/fallback material export
    shaders.py                         # shader specs/artifacts/compiler helpers
    builtin_shader_catalog.py          # transitional catalog/source lookup
```

The exact file names may change if the code shape suggests a cleaner split, but
the ownership boundaries should stay close to this structure.

## Phase 1: Behavior-Preserving Split

Move code in slices without changing outputs:

1. Extract shared dataclasses and constants needed across modules.
2. Extract package-file helpers:
   `_write_clean_package_dir`, `_write_json`, `_resource_sort_key`,
   `_project_relative_path`, `_append_project_file_diagnostic`.
3. Extract scene/ref collection:
   `_resolve_entry_scene`, `_read_scene_data`, `_collect_runtime_refs`,
   project material discovery, and legacy `_looks_like_*` helpers as-is.
4. Extract pipeline, mesh, material and shader writers one subsystem at a time.
5. Keep `runtime_package_exporter.py` as the compatibility facade for tests that
   import private helpers, re-exporting transitional private names only where
   existing tests or callers still need them.

Acceptance for Phase 1:

- `export_runtime_package()` output stays byte-compatible enough for existing
  tests;
- existing private helper imports used by tests keep working or tests are moved
  to the new module when the helper is no longer exporter-owned;
- `test_runtime_package_exporter.py` and Android exporter tests stay green;
- no new fallback behavior is introduced.

## Phase 2: Explicit Resource Ref Policy

After the split, tighten mesh/material ref classification:

- canonical refs use explicit metadata:
  - `{"type": "uuid", "kind": "tc_mesh", ...}`;
  - `{"type": "uuid", "kind": "tc_material", ...}`;
  - or `role: "mesh" | "material"` while old data migrates;
- field-name and resource-name inference becomes a legacy path with diagnostics;
- long term, legacy inference should be removable once scene/component
  serializers write typed metadata consistently.

Acceptance for Phase 2:

- tests cover explicit `kind`/`role` paths;
- tests cover legacy inference diagnostics;
- exporter no longer silently treats arbitrary UUID refs as mesh/material based
  only on ambiguous names without recording the migration debt.

## Phase 3: Built-In Shader Catalog Ownership

Use `docs/builtin-shader-catalog.md` as the target architecture:

- `engine-shader-catalog.json` remains transitional source identity metadata;
- exporter should not expand catalog responsibilities beyond source lookup;
- source lookup should be isolated behind one provider so later deletion of the
  JSON manifest affects only that provider;
- package exporter must prefer generated/installed builtin shader sources and
  artifacts where the SDK layout already provides them.

Acceptance for Phase 3:

- builtin shader source/catalog lookup is isolated;
- tests document whether the exporter reads repo sources, `TERMIN_SDK`, or
  `sys.prefix` fallback;
- no new inline engine shader strings are added to package/export code.

## Non-Goals

- Do not redesign runtime package manifest format in this card.
- Do not remove `dev_smoke` fallback policy in the split pass.
- Do not delete `engine-shader-catalog.json` before built-in shader source
  conventions cover all current exceptions.
- Do not fold project build, desktop packaging, or player runtime into the
  exporter split.

## Verification

Minimum verification for each substantial slice:

```bash
./run-tests-python.sh termin-project-build/tests/test_runtime_package_exporter.py
./run-tests-python.sh termin-project-build/tests/test_runtime_package_exporter_android.py
./run-tests-python.sh termin-project-build/tests/test_shader_tool_resolution.py
```

Final verification for closing #161:

```bash
./run-tests.sh
git diff --check
```
