# Аудит чрезмерной C++-реализации в заголовках

Дата: 2026-07-12

## Границы аудита

Проверен проектный C++-код во всех модулях репозитория. Из анализа намеренно
исключены `sdk/` и build outputs, `termin-thirdparty/`, сгенерированный C#-код,
шаблоны, `constexpr`/small-value геометрия, а также тонкие C-ABI forwarding
wrappers. Их bodies либо обязаны быть видны в заголовке, либо слишком малы,
чтобы оправдать дополнительную единицу трансляции.

Цель ниже — не механически убрать каждый `inline`, а вынести тяжёлую
нетемплейтную логику, уменьшить coupling заголовков и повторный parsing в
потребляющих translation units.

## Приоритетные кандидаты

| Заголовок | Реализация, которую следует вынести | Предлагаемое направление |
| --- | --- | --- |

## Выполнено

- `termin-materials/include/termin/materials/glsl_preprocessor.hpp` —
  реализация preprocessing перенесена в существующий
  `src/glsl_preprocessor.cpp`; публичные out-of-line методы получили
  `TERMIN_MATERIALS_API` для Windows DLL.
- `termin-collision/include/termin/colliders/gjk.hpp` — нетемплейтные
  GJK/EPA, simplex/face processing и search loops перенесены в
  `src/termin/colliders/gjk.cpp`, зарегистрированный в target.
- `termin-physics/include/termin/physics/physics_world.hpp` и
  `rigid_body.hpp` — runtime-логика перенесена в `src/physics_world.cpp` и
  `src/rigid_body.cpp`; публичные классы экспортируются через
  `TERMIN_PHYSICS_API`.
- `termin-scene/include/termin/geom/general_transform3.hpp` — pool lookup,
  pose/hierarchy и transform helpers перенесены в существующий
  `cpp/geom/general_transform3.cpp`; handle-only layout сохранён, тип получил
  `ENTITY_API` для Windows DLL.
- `termin-graphics/include/tgfx2/internal/process_runner.hpp` — platform
  quoting, conversion и process launch перенесены в
  `src/tgfx2/internal/process_runner.cpp`. `termin_shaderc` теперь явно
  линкуется с `termin_graphics2`, а boundary имеет `TGFX2` visibility.
- `termin-render-passes/include/termin/lighting/lighting_ubo.hpp` — GPU
  lifetime, packing и upload вынесены в `src/lighting_ubo.cpp`; std140 layout
  остаётся публичным, `LightingUBO` экспортируется из shared library.
- `termin-collision/include/termin/collision/collision_world.hpp` — управление
  коллайдерами, contact queries, clipping и raycasting вынесены в
  `src/termin/collision/collision_world.cpp`; `CollisionWorld` экспортируется
  через `TERMIN_COLLISION_API`.
- `termin-cli/src/termin_python_backend.hpp` — platform-specific поиск Python,
  environment и fork/spawn перенесены в `src/termin_python_backend.cpp`;
  отдельный static target подключён к CLI-потребителям.
- `termin-app/cpp/termin/editor/gizmo_types.hpp` — ray intersections и
  geometry helpers вынесены в `gizmo_types.cpp`, добавленный в targets editor,
  tests и `_editor_native` binding module.
- `termin-openxr/src/openxr_android_scene_runtime.hpp` — единственный
  потребляющий TU теперь содержит scene-runtime implementation напрямую в
  `src/openxr_android_runtime.cpp`; implementation header удалён. Нужна
  платформенная Android/OpenXR сборка для окончательной верификации.
- `termin-voxels/termin/voxels/voxel_grid.hpp` — sparse chunks, полный
  triangle–AABB SAT, voxelization, flood fill, surface extraction и normal
  processing перенесены в `src/voxel_grid.cpp`; CMake target и Python binding
  собираются с новой implementation unit.
- `termin-app/cpp/termin/editor/selection_manager.hpp` — selection/hover
  normalization, pick-id synchronization и callbacks перенесены в
  `selection_manager.cpp`, добавленный в editor native bindings и C++ tests.

## Вторая очередь

Эти случаи меньше по объёму, но содержат обычную runtime-логику, которая не
обязана быть header-visible:

- `termin-engine/include/termin/render/viewport_render_state.hpp` — RAII/move и allocation/release texture ресурсов.
- `termin-graphics/include/tgfx2/backend_binding_plan.hpp` — около 90 строк policy mapping; подходящий `backend_binding_plan.cpp` уже есть.
- `termin-gui-native/include/termin/gui_native/document.hpp` — ownership, сериализация, исключения и Trent conversion.
- `termin-gui-native/include/termin/gui_native/document_snapshot.hpp` — RAII, move semantics и lookup.
- `termin-skeleton/include/termin/skeleton/skeleton_data.hpp` — rebuild name/root indexes.
- `termin-lighting/include/termin/lighting/light.hpp` — runtime light sampling и spot attenuation.
- `termin-render/include/termin/render/render_task.hpp` — allocative `RenderTask::set_resources`; небольшой, но может сократить coupling public header.

## Отдельный binding-кандидат

`termin-gui-native/python/bindings/gui_native_bindings_shared.hpp` содержит
более 1000 строк shared binding implementation и разбирается шестью binding
translation units. Вынести следует доступную нетемплейтную часть (RAII wrappers,
conversion helpers, Python widget/surface callback bodies), оставив в заголовке
то, что требует header-visible nanobind templates. Это наиболее перспективный
кандидат по compile-time эффекту, но потребует отдельного проектирования
linkage и visibility.

## Условия безопасной миграции

- Добавлять новые `.cpp` в соответствующие CMake targets одновременно с
  переносом, иначе public headers начнут компилироваться, но потребители не
  слинкуются.
- Сохранять `noexcept`, move semantics, export visibility и ABI layout public
  типов. Не переносить inline templates и small-value арифметику ради самого
  переноса.
- Для OpenXR и process runner сохранить платформенные guards в единственном
  implementation TU.
- После каждой логической группы собирать затронутый SDK/target и запускать
  релевантные тесты через `./run-tests.sh`.
