# termin-bootstrap startup plan

Дата: 2026-06-23

Статус: предварительный архитектурный план.

## Цель

Создать небольшой верхнеуровневый пакет `termin-bootstrap`, который явно
инициализирует runtime/editor/player окружение Termin:

- inspect kind registrations для runtime handle/resource типов;
- scene extension registrations;
- inspect adapters и pointer extractors;
- Python component callback wiring;
- профильные bootstrap-последовательности для runtime, player и editor.

Главная цель - убрать скрытые side effects из `import termin._native`,
`import termin.animation._animation_native`, `import termin.skeleton._skeleton_native`
и похожих импортов. Программы должны явно вызывать startup-регистрацию в своей
composition root, а не получать измененное глобальное состояние от случайного
импорта.

## Почему отдельный пакет

`termin-bootstrap` - это integration/composition layer. Он не владеет
ресурсами, компонентами или asset plugins, но владеет порядком старта
приложения.

Это лучше, чем складывать регистрации в `termin-default-assets`, потому что:

- `termin-default-assets` отвечает за стандартные asset adapters и resource
  manager, а не за базовый scene/inspect/runtime contract;
- kind registrations нужны и C++ runtime path, и Python player/editor path;
- player/runtime не должны зависеть от `termin-app`;
- low-level пакеты (`termin-mesh`, `termin-inspect`, `termin-materials`) не
  должны получать лишние обратные зависимости только ради bootstrap.

## Non-goals

- Не переносить asset import/runtime plugins из `termin-default-assets`.
- Не делать `termin-bootstrap` владельцем `TcMesh`, `TcMaterial`,
  `TcSkeleton`, `TcAnimationClip`, etc.
- Не добавлять implicit registration при импорте `termin.bootstrap`.
- Не менять scene JSON schema в рамках первого шага.

## Текущее состояние

Сейчас startup-регистрации размазаны по нескольким местам.

`termin._native` при импорте выполняет:

- `register_tc_mesh_kind()` в `termin-app/cpp/termin/bindings.cpp`;
- `termin::bind_render(render_module)`, внутри которого регистрируются render
  scene extensions и `tc_material`;
- `termin::init_domain_inspect()`;
- `termin::init_python_component_callbacks()`;
- `termin::init_asset_kind_handlers()`.

Дополнительные side effects:

- `termin-animation/cpp/bindings/animation_module.cpp` регистрирует
  `tc_animation_clip` при импорте `_animation_native`;
- `termin-skeleton/cpp/bindings/skeleton_module.cpp` регистрирует
  `tc_skeleton` при импорте `_skeleton_native`;
- `termin-voxels/python/bindings/voxels_bindings.cpp` регистрирует
  `voxel_grid_handle` при импорте `_voxels_native`;
- `termin-app/cpp/termin/assets/assets_bindings.cpp` дублирует регистрацию
  `tc_material`, `tc_skeleton` и `entity`;
- `termin-runtime/src/runtime_package.cpp` уже локально регистрирует
  `tc_mesh` и `tc_material` перед scene deserialization. Это хороший образец
  явного runtime policy.

## Target Package Shape

### C++ target

Новый target:

- library: `termin_bootstrap`
- namespace target: `termin_bootstrap::termin_bootstrap`
- package config: `termin_bootstrapConfig.cmake`

Предполагаемый C++ API:

```cpp
namespace termin::bootstrap {

struct RuntimeKindOptions {
    bool mesh = true;
    bool material = true;
    bool skeleton = true;
    bool animation = true;
    bool voxel_grid = true;
    bool entity = true;
};

struct SceneExtensionOptions {
    bool render_mount = true;
    bool render_state = true;
    bool collision_world = true;
};

void register_runtime_kinds(const RuntimeKindOptions& options = {});
void register_scene_extensions(const SceneExtensionOptions& options = {});
void init_inspect_adapters();
void init_python_component_callbacks();

void bootstrap_runtime();
void bootstrap_player();
void bootstrap_editor();

} // namespace termin::bootstrap
```

All functions must be idempotent. Repeated calls from tests, editor reload
paths, embedded player startup, or C++ runtime package loaders must be safe.

### Python package

Python namespace:

- `termin.bootstrap`
- native extension: `termin.bootstrap._bootstrap_native`

Expected Python API:

```python
from termin.bootstrap import (
    bootstrap_runtime,
    bootstrap_player,
    bootstrap_editor,
    register_runtime_kinds,
    register_scene_extensions,
    init_inspect_adapters,
    init_python_component_callbacks,
)
```

Importing `termin.bootstrap` must not register anything. Only explicit function
calls may mutate global registries.

## Dependency Policy

`termin-bootstrap` is allowed to have broad dependencies because it is a top
integration layer. Lower-level packages must not depend on it.

Initial C++ dependencies likely include:

- `tcbase::termin_base`
- `termin_inspect::termin_inspect`
- `termin_inspect::termin_inspect_python` when Python bindings are enabled
- `termin_scene::termin_scene`
- `termin_engine::termin_engine`
- `termin_render::termin_render`
- `termin_components_mesh::termin_components_mesh`
- `termin_components_render::termin_components_render`
- `tmesh::termin_mesh`
- `tgfx::termin_graphics`
- `termin_skeleton::termin_skeleton`
- `termin_animation::termin_animation`
- `termin_voxels::termin_voxels`

If this becomes too wide for a specific target, split the API into smaller
profiles instead of moving registrations back into low-level packages.

## Bootstrap Profiles

### `bootstrap_runtime()`

Minimal scene/runtime deserialization support:

- register builtin inspect core kinds;
- register C++ resource handle kinds required by exported scenes:
  `tc_mesh`, `tc_material`, and later `tc_skeleton`, `tc_animation_clip`,
  `voxel_grid_handle`;
- register scene extensions needed by runtime scenes;
- initialize inspect component/pass adapters if scene deserialization needs
  them.

This profile should be usable by `termin-runtime` without `termin-app`.

### `bootstrap_player()`

Runtime profile plus Python-facing wiring:

- `bootstrap_runtime()`;
- Python kind handlers and Python type mappings;
- Python component drawable/input callbacks;
- pointer extractors needed by Python player diagnostics or runtime UI.

`termin.player.PlayerRuntime.initialize()` and `HeadlessRuntime.initialize()`
should call this before loading modules/assets/scenes.

### `bootstrap_editor()`

Player profile plus editor-only integration:

- `bootstrap_player()`;
- editor-specific pointer extractors or diagnostics;
- any editor-only callback wiring currently hidden behind `termin._native`.

Editor startup should call this before opening a project or deserializing the
first scene.

## Resource Kind Registration Strategy

Kind handlers for UUID-backed handles should use one reusable template where
possible:

```cpp
template<typename H>
void register_runtime_handle_kind(const std::string& kind_name) {
    tc::KindRegistryCpp::instance().register_kind(
        kind_name,
        [](const std::any& value) -> tc_value {
            const H& handle = std::any_cast<const H&>(value);
            return handle.serialize_to_value();
        },
        [](const tc_value* value, void* context) -> std::any {
            H handle;
            handle.deserialize_from(value, context);
            return handle;
        }
    );
}
```

This already exists locally in `termin-runtime/src/runtime_package.cpp`.
`termin-bootstrap` should own the shared version so runtime, player and editor
do not each carry their own copy.

Python kind handlers can be registered only in Python-enabled profiles. They
must map canonical Python classes to kind names explicitly:

- `tmesh.TcMesh` -> `tc_mesh`
- `termin.materials.TcMaterial` -> `tc_material`
- `termin.skeleton.TcSkeleton` -> `tc_skeleton`
- `termin.animation.TcAnimationClip` -> `tc_animation_clip`
- `termin.voxels.TcVoxelGrid` -> `voxel_grid_handle`

## Migration Plan

### Phase 1: Add package without changing behavior

1. Create `termin-bootstrap` CMake/Python package.
2. Move or duplicate the generic runtime handle kind helper from
   `termin-runtime` into `termin-bootstrap`.
3. Add `bootstrap_runtime()`, `bootstrap_player()`, and `bootstrap_editor()`
   as idempotent functions.
4. Keep old side effects in place temporarily.
5. Add focused tests proving explicit calls register `tc_mesh` and
   `tc_material` before scene/resource deserialization.

### Phase 2: Switch consumers to explicit bootstrap

1. `termin-runtime` calls `termin::bootstrap::bootstrap_runtime()` instead of
   local `register_runtime_kinds()`.
2. `termin.player.PlayerRuntime.initialize()` calls
   `termin.bootstrap.bootstrap_player()` before resource and scene loading.
3. `termin.player.HeadlessRuntime.initialize()` calls
   `termin.bootstrap.bootstrap_player()` before scene loading.
4. Editor startup calls `termin.bootstrap.bootstrap_editor()` before project
   load.
5. Tests that need scene/kind global state use explicit bootstrap fixtures.

### Phase 3: Remove `termin._native` import side effects

1. Stop calling `register_tc_mesh_kind()` from `_native` import.
2. Stop calling `termin::bind_render(render_module)` for side effects; keep
   `_native.render` only as compatibility re-export surface.
3. Stop calling `init_domain_inspect()`,
   `init_python_component_callbacks()`, and `init_asset_kind_handlers()` from
   `_native` import.
4. Keep explicit compatibility functions in `_native` only if old user code
   still needs them during migration.

### Phase 4: Remove domain native import side effects

1. Replace auto-registration in `_animation_native` with an explicit
   `register_animation_runtime_kinds()` function.
2. Replace auto-registration in `_skeleton_native` with an explicit
   `register_skeleton_runtime_kinds()` function.
3. Replace auto-registration in `_voxels_native` with an explicit
   `register_voxel_runtime_kinds()` function.
4. Have `termin-bootstrap` call these explicit domain functions as part of the
   selected profile.

### Phase 5: Delete duplicate app registrations

1. Remove duplicate `tc_material` registration from
   `termin-app/cpp/termin/bindings/render/material.cpp` and
   `termin-app/cpp/termin/assets/assets_bindings.cpp`.
2. Remove duplicate `tc_skeleton` registration from
   `termin-app/cpp/termin/assets/assets_bindings.cpp`.
3. Move or remove `entity` kind registration after deciding whether it is a
   runtime scene kind or editor-only domain helper.
4. Update `docs/plans/2026-06-23-termin-app-native-reexport-cleanup-plan.md`
   once `_native` becomes a pure compatibility module.

## Open Questions

- Does `entity` kind belong in runtime bootstrap, scene bootstrap, or editor
  bootstrap only?
- Should `tc_texture` / `texture_handle` and `tc_shader` receive first-class
  inspect kind handlers, or remain asset/resource-manager-only handles?
- Should `termin-bootstrap` expose fine-grained feature options, or only
  profile-level calls?
- Should Python kind handlers be available from C++ embedded Python startup
  before `Py_Initialize()`, or only after Python is initialized?
- Which bootstrap profile should Android/OpenXR use once those runtimes stop
  relying on fallback scenes?

## Verification Gates

Each migration phase should keep these checks green:

- `./build-sdk.sh --no-wheels`
- `./setup-test-venv.sh --force` after binding changes
- focused tests for runtime package loading, player startup, headless scene
  loading, and `_native` compatibility
- `./run-tests.sh`
- `rg` check that no new production code depends on `_native` import side
  effects

