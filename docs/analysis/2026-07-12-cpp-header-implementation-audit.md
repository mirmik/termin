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
| `termin-scene/include/termin/geom/general_transform3.hpp` | Почти весь `GeneralTransform3`: pool lookup, local/global pose, hierarchy и transform helpers (строки ~20–340). | Перенести в существующий `cpp/geom/general_transform3.cpp`; оставить только тривиальное хранение handle и минимальные accessors. |
| `termin-collision/include/termin/collision/collision_world.hpp` | Управление коллайдерами, queries/raycast, box-box clipping и генерация контактов (строки ~62–580). | Добавить `collision_world.cpp`, зарегистрировать в CMake. |
| `termin-collision/include/termin/colliders/gjk.hpp` | Нетемплейтные GJK/EPA, simplex/face processing и циклы поиска (строки ~20–563). | Добавить `gjk.cpp`; сохранить в заголовке объявления и типы. |
| `termin-physics/include/termin/physics/physics_world.hpp` | Lifecycle, stepping, синхронизация коллайдеров и contact generation (строки ~54–260). | Добавить `physics_world.cpp`. |
| `termin-physics/include/termin/physics/rigid_body.hpp` | Factory methods, inertia, force/impulse и integration (строки ~44–220). | Добавить `rigid_body.cpp`; оставить inline только простые accessors. |
| `termin-voxels/termin/voxels/voxel_grid.hpp` | Работа с sparse chunks, voxelization/SAT, flood fill и mark-surface (примерно с 142-й строки до конца). | Добавить `voxel_grid.cpp`. |
| `termin-materials/include/termin/materials/glsl_preprocessor.hpp` | Рекурсивный regex preprocessing, detection cycles и diagnostics (строки ~32–140). | Перенести методы в существующий `src/glsl_preprocessor.cpp`. |
| `termin-cli/src/termin_python_backend.hpp` | Поиск Python/runtime path, environment и fork/spawn process implementation (строки ~27–270). | Сделать private declarations header + `termin_python_backend.cpp`; обновить CMake CLI. |
| `termin-openxr/src/openxr_android_scene_runtime.hpp` | Около 841 строки полной scene-runtime реализации, при этом заголовок включается единственным TU. | Слить реализацию в `openxr_android_runtime.cpp` или вынести в отдельный `.cpp`; сохранить Android/OpenXR guards. |
| `termin-graphics/include/tgfx2/internal/process_runner.hpp` | Около 245 строк platform-specific quoting, conversion и process launch; один потребитель. | Добавить `process_runner.cpp` в graphics target. |
| `termin-render-passes/include/termin/lighting/lighting_ubo.hpp` | GPU lifetime, packing восьми источников и upload (строки ~86–196). | Добавить `lighting_ubo.cpp`; public layout structs оставить в заголовке. |
| `termin-app/cpp/termin/editor/gizmo_types.hpp` | Около 250 строк ray intersections для sphere/cylinder/torus/quad и geometry helpers. | Добавить `gizmo_types.cpp` в termin-app. |

## Вторая очередь

Эти случаи меньше по объёму, но содержат обычную runtime-логику, которая не
обязана быть header-visible:

- `termin-engine/include/termin/render/viewport_render_state.hpp` — RAII/move и allocation/release texture ресурсов.
- `termin-graphics/include/tgfx2/backend_binding_plan.hpp` — около 90 строк policy mapping; подходящий `backend_binding_plan.cpp` уже есть.
- `termin-gui-native/include/termin/gui_native/document.hpp` — ownership, сериализация, исключения и Trent conversion.
- `termin-gui-native/include/termin/gui_native/document_snapshot.hpp` — RAII, move semantics и lookup.
- `termin-app/cpp/termin/editor/selection_manager.hpp` — selection/hover normalization и callbacks.
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
