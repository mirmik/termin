# termin-materials intent

Дата: 2026-05-19

Статус: декларация о намерениях, не детальный migration checklist.

Обновление 2026-05-19:

- Создан первичный пакет `termin-materials`.
- В `termin-materials` вынесены C++ `shader_parser`, `glsl_preprocessor` и Python binding `termin.materials._materials_native`.
- В `termin-materials` вынесены Python bindings `TcRenderState`, `TcMaterialPhase`, `TcMaterial` и material registry helpers.
- Построение материала из `ShaderMultyPhaseProgramm` вынесено в явный module-level API `termin.materials.create_material_from_parsed(...)`. Legacy-forwarder `TcMaterial.from_parsed(...)` удалён 2026-06-27 после миграции downstream call sites.
- Python shader-parser imports внутри `termin-app` переведены на canonical `termin.materials`.
- `TcMaterial` binding больше не зависит от app-level `TextureHandle`: `set_texture` и `create_material_from_parsed(..., textures=...)` принимают `TcTexture`, а default white/normal texture lookup передается из app слоя через `default_white_texture` / `default_normal_texture`.
- `termin._native.render` пока сохраняет исторический export material/shader типов через импорт `termin.materials._materials_native`; это совместимость существующего пути, не новый owner.
- App-level GLSL fallback loader через `ResourceManager` удалён. Оставшийся
  `glsl_preprocessor` обрабатывает только явно зарегистрированные include-ы.

## Зачем

Текущая граница вокруг material/shader runtime размазана:

- низкоуровневые `tc_material*` структуры и `TcMaterial` handle лежат в `termin-graphics`;
- Python bindings `TcMaterial`, `TcMaterialPhase`, `TcRenderState` пока живут в `termin-app`;
- shader parser, GLSL preprocessor/include bank и material UBO synthesis тоже остаются в `termin-app`;
- render components и visualization импортируют material API через `termin._native.render`;
- concrete render passes пока смешаны с app/render runtime.

`termin-graphics` не должен становиться владельцем всей material-семантики. Его ответственность ближе к GPU/device/backend/texture/shader registry primitives. Материал же завязан на наш shader format, phases, render state, uniforms/textures, include/preprocessor rules и layout synthesis. Это отдельный домен.

Цель: выделить material/shader-format слой в самостоятельную библиотеку, условно `termin-materials`.

## Целевая форма слоев

```text
termin-graphics
  GPU/device/backend/runtime primitives
  texture registry and TcTexture
  low-level shader registry and TcShader
  tgfx2 handles/context/device

termin-materials
  TcRenderState
  TcMaterialPhase
  TcMaterial
  material registry API
  .shader parser and phase model
  GLSL preprocessor/include bank
  material UBO layout synthesis
  helpers for building material phases from shader sources

termin-render
  frame graph
  render pipeline contracts
  render targets
  render engine
  pass execution interfaces

termin-passes
  concrete pass implementations over termin-render + termin-materials
  postprocess passes
  scene/material/depth/id/shadow passes, split further if dependencies demand it

termin-components-render
  CameraComponent
  LightComponent
  MeshRenderer and drawable scene components
  component bindings over scene + render + materials
```

`termin-materials` is not a pass library. Concrete passes should not be moved into it.

## Boundary Rules

`termin-graphics` should not know about:

- `.shader` file syntax;
- material phases as authoring/runtime concept;
- engine include bank;
- material UBO synthesis rules;
- editor/resource-manager fallback behavior.

`termin-materials` may depend on:

- `termin-base`;
- `termin-graphics`;
- possibly `termin-inspect`, if kind registration is moved there intentionally;
- possibly `termin-render` only if a concrete need appears, but this should be treated with suspicion.

`termin-render` may depend on material C ABI/types only where pass execution contracts need them. It should not own shader-format parsing or material authoring logic.

`termin-passes` may depend on:

- `termin-render`;
- `termin-materials`;
- component libraries required by specific passes.

If pass dependencies become too broad, split pass packages by responsibility instead of pushing everything into `termin-render`.

## Migration Direction

Do not add new compatibility wrappers. When a domain moves, replace imports with the canonical path and remove the old binding/module owner where feasible. Existing historical re-exports can be removed later as a separate cleanup step.

Preferred staged migration:

1. Continue moving shader-format code from `termin-app` into `termin-materials`:
   - shader parser;
   - GLSL preprocessor;
   - include bank;
   - material UBO layout synthesis.
2. Replace Python imports from `termin._native.render` to the new canonical material package.
3. Keep app/resource-manager conveniences outside the core material binding:
   - default white/normal texture lookup;
   - resource-manager based material resolution;
   - editor-only inspection widgets.
4. Decide whether the low-level C material storage moves out of `termin-graphics`:
   - short term: `termin-materials` can own the high-level API while using C storage still exported by `termin-graphics`;
   - long term: move `tc_material.h`, `tc_material_registry.h`, and `tgfx_material_handle.hpp` into `termin-materials` if dependency graph allows it cleanly.
5. After material ownership is clean, revisit concrete render passes and create `termin-passes`.

## Open Questions

- Should `TcShader` stay in `termin-graphics`, or should shader registry move together with materials?
- Should material kind registration live in `termin-materials` or in an inspect integration package?
- How much of existing app-level `TextureHandle` compatibility should survive after material extraction?
- Do scene/material/depth/id/shadow passes belong in one `termin-passes` package, or should scene-dependent passes be separated from pure postprocess passes?

## Current Smells To Watch

- `termin-components-render` still includes app directories in CMake. This is a migration debt and should be removed.
- `termin._native.render` still exports material types and many concrete passes.
- `create_material_from_parsed` still does a lot in one function: phase creation, shader feature propagation, material UBO layout upload, default uniform application, texture defaults, and color overrides. The ownership is clearer now, but the implementation should eventually be split into smaller internal helpers.
- `termin-render` is already broad enough; avoid solving pass ownership by adding more concrete pass code there.
