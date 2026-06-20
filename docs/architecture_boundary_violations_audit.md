# Аудит нарушений границ модулей

**Дата:** 2026-05-20  
**Статус:** Research report — не исправлять автоматически

**Актуализировано:** 2026-05-24 — Qt/PyQt frontend удалён; часть старых пунктов закрыта.

## Исправления

### 2026-05-21

- **standard render passes частично вынесены из `termin-app`:** создан SDK-модуль `termin-render-passes`; `PresentToScreenPass`, `DebugTrianglePass`, `GrayscalePass`, `TonemapPass`, `BloomPass`, `ColorPass`, `ShadowPass`, `SkyBoxPass`, shadow camera helpers, shader skinning injection и material UBO apply helper перенесены из `termin-app/cpp/termin/render` в новый модуль, а app Python re-export переключен на `termin.render_passes`.
- **3.7 закрыто:** `termin.engine` и `termin.inspect` теперь вызывают `preload_sdk_libs(...)` перед импортом native modules.
- **3.6 закрыто частично по публичной поверхности:** приватные C-interop функции больше не входят в `termin.display.__all__`. Сами underscored imports оставлены для существующих внутренних call sites до появления публичного adapter API.
- **1.3 частично:** `EditorCameraUIController` перенесён из `termin.editor_core` в `termin.editor_tcgui`, а `EditorCameraManager` добавляет его только если компонент зарегистрирован frontend-слоем. В `editor_core` остаётся Qt-зависимость `SpaceMouseController` и более широкая проблема `termin.visualization/ui/widgets -> tcgui`.
- **2.1 частично:** прямые include paths на `termin-render/include` удалены из `termin-display` и `termin-components-render`, где уже есть CMake target dependency. Широкий `termin-app/cpp/termin` include в `termin-components-render` заменён точечным include path на `entity_helpers.hpp`. Прямые пути на `termin-app/core_c` оставлены как часть отдельной проблемы 1.2/ownership `core_c`.
- **4.1 закрыто:** дублирующийся `tc_registry_utils.h` вынесен в `termin-base/include/tcbase/tc_registry_utils.h`; копии из `termin-graphics` и `termin-mesh` удалены.
- **3.3 закрыто:** `tc_registry_utils.h`, `tc_resource.h` и generic handle include вынесены на `termin-base`; `termin-skeleton` больше не зависит от `termin_graphics`, старые resource includes в `termin-render` переведены на `tcbase`.
- **3.4 частично:** `install_requires` приведены к фактическим импортам для `termin-render`, `termin-input`, `termin-animation`, `termin-components-mesh`; `termin-navmesh` оставлен как отдельная задача разделения core/editor/visual слоёв.
- **1.2 частично:** singleton storage `.cpp` для `EngineCore`, `SceneManager`, `RenderingManager` перенесены из `termin-app/core_c/src` в `termin-engine/src`; `termin-engine` больше не компилирует исходники из `termin-app` и не добавляет `termin-app/core_c/include`.
- **core_c cleanup частично:** C geometry headers перенесены в `termin-base/include/geom`; skeleton/animation resource C headers перенесены в `termin-skeleton/include/resources` и `termin-animation/include/resources`; collision C headers/obsolete C impl удалены из `core_c`, актуальный владелец — `termin-collision`; `tc_input_event.h` перенесён в `termin-display`.
- **component binding ownership закрыто для skeleton/animation/render-components:** `_skeleton_native`, `_animation_native`, `_components_skeleton_native`, `_components_animation_native` больше не компилируют `.cpp` из `termin-app/cpp/termin/bindings`; source-файлы перенесены к владельцам. `_components_render_native` больше не добавляет include path на app binding helpers и использует `termin-scene/include/termin/bindings/entity_helpers.hpp`.

### 2026-05-24

- **Qt/PyQt frontend удалён:** `termin/editor/` оставлен только как compatibility entrypoint на tcgui, старые PyQt views/widgets и PyQt nodegraph удалены.
- **1.3 PyQt-пункты закрыты:** `SpaceMouseController` работает polling-only, `sdl_embedded.py` больше не содержит Qt embedding hooks, `Texture` больше не создаёт Qt preview objects.
- **3.9 закрыто как миграционная проблема:** расхождение Qt/tcgui больше не поддерживается; единственный frontend редактора — tcgui.

---

## Оглавление

1. [Критические нарушения](#1-критические-нарушения)
2. [Высокий приоритет](#2-высокий-приоритет)
3. [Средний приоритет](#3-средний-приоритет)
4. [Низкий приоритет](#4-низкий-приоритет)
5. [Что выглядит несложно поправить](#5-что-выглядит-несложно-поправить)
6. [Карта зависимостей](#6-карта-зависимостей)

---

## 1. Критические нарушения

### 1.1 RenderingManager — God Object (2145 строк)

**Где смотреть:**
- `termin-engine/src/rendering_manager.cpp`
- `termin-engine/include/termin/render/rendering_manager.hpp`
- `termin-engine/include/termin/render/pull_rendering_manager.hpp`
- `termin-engine/src/pull_rendering_manager.cpp`

**Проблема:** `RenderingManager` управляет всем:
- Display management (добавление/удаление дисплеев, фабрика) — ответственность termin-display
- Viewport state — состояния рендеринга для каждого viewport'а
- Render target management — создание, регистрация, очистка — ответственность termin-render
- Scene mounting — привязка сцен к дисплеям через viewport'ы (смешивание scene + display + render)
- Pipeline management — создание пайплайнов, factory-колбэки, recompilation
- Input routing — `DisplayInputRouter`, `ensure_display_router()` — ответственность termin-input/termin-display
- Default pipeline — `make_default_pipeline()` жёстко закодированный пайплайн Shadow→Skybox→Color→Transparent→Bloom→UI→Present
- Render target resolution sync — синхронизация динамического разрешения
- Scene pipeline compilation — компиляция ScenePipelineTemplate

**Дублирование:** `PullRenderingManager` имеет практически идентичный набор полей и методов:
- `render_engine_`, `owned_render_engine_`
- `displays_`, `viewport_states_`
- `add_display()`, `remove_display()`, `get_display_by_name()`
- `get_viewport_state()`, `get_or_create_viewport_state()`, `remove_viewport_state()`
- `render_viewport_offscreen()`, `collect_lights()`

Нарушение DRY — общая часть должна быть вынесена в базовый класс или mixin.

---

### 1.2 termin-engine компилирует .cpp из termin-app

**Где смотреть:**
- `termin-engine/CMakeLists.txt` — **Исправлено 2026-05-21:** больше не ссылается на `../termin-app/core_c/src`.
- `termin-engine/src/tc_scene_manager_instance.cpp` — **перенесено из `termin-app/core_c/src`**
- `termin-engine/src/tc_rendering_manager_instance.cpp` — **перенесено из `termin-app/core_c/src`**
- `termin-engine/src/tc_engine_core_instance.cpp` — **перенесено из `termin-app/core_c/src`**

**Было:** SDK-модуль `termin-engine` не мог быть собран без наличия `termin-app` в репозитории, потому что компилировал `.cpp` из `termin-app/core_c/src`.

**Статус 2026-05-21:** engine-часть исправлена. Singleton storage принадлежит `termin-engine`, а `termin-engine` больше не добавляет include path на `termin-app/core_c/include`.

Остаток проблемы: `termin-app/cpp` всё ещё экспортирует `core_c/include` как app compatibility surface (`termin_core.h`, `tc_opengl.h`, editor/render leftovers). После cleanup 2026-05-21 независимые SDK-модули `termin-engine`, `termin-display`, `termin-skeleton`, `termin-animation`, `termin-components-render` больше не добавляют `termin-app/core_c/include`, а `tc_picking.h` принадлежит `termin-render-passes`.

---

### 1.3 Утечка GUI в editor_core

**Где смотреть:**

| Файл | Нарушение |
|------|-----------|
| `termin-app/termin/editor_tcgui/editor_camera_ui_controller.py` | **Исправлено 2026-05-21:** файл перенесён из `editor_core` в tcgui frontend |
| `termin-app/termin/editor_core/spacemouse_controller.py` | **Исправлено 2026-05-24:** Qt notifier удалён, остался polling |
| `termin-app/termin/visualization/platform/backends/sdl_embedded.py` | **Исправлено 2026-05-24:** PyQt embedding hooks удалены |
| `termin-app/termin/visualization/render/texture.py` | **Исправлено 2026-05-24:** Qt preview удалён вместе с Qt editor |
| `termin-app/termin/visualization/ui/widgets/__init__.py` | Full re-export tcgui.widgets (иллюзия абстракции) |
| `termin-app/termin/visualization/ui/widgets/component.py` | `UIComponent` наследуется от `InputComponent` + импортирует `tcgui.widgets.ui.UI` |

**Проблема:** `editor_core` декларирует себя как UI-agnostic слой. PyQt-зависимости закрыты; остаточная проблема — `termin/visualization/ui/widgets` как tcgui re-export внутри app/SDK boundary.

**Статус 2026-05-21:** частично исправлено. Прямой tcgui-контроллер камеры убран из `editor_core`; оставшиеся пункты требуют отдельного adapter/API решения.

---

### 1.4 termin-gui Viewport3D лезет в SDK internals

**Где смотреть:**
- `termin-gui/python/tcgui/widgets/viewport3d.py` (строки 84, 168, 180, 208, 230)

```python
from termin.display import (
    _display_get_surface_ptr,
    _render_surface_get_input_manager,
)
from termin.display import _input_manager_on_mouse_move
from termin.display import _input_manager_on_scroll
from termin.display import _input_manager_on_mouse_button
from termin.display import _input_manager_on_key
```

**Статус 2026-06-19:** частично исправлено. `Viewport3D` больше не использует
app compatibility re-export `termin._native.render` и `FBOSurface` берет из
канонического `termin.display`. Остаточная проблема: виджет GUI-фреймворка всё
ещё вызывает приватные underscored C-interop функции вместо публичного input
adapter API.

---

## 2. Высокий приоритет

### 2.1 Прямые пути к include (bypass CMake зависимостей)

**Где смотреть:**

| Файл | Строки | Проблема |
|------|--------|----------|
| `termin-display/CMakeLists.txt` | 103-111 | **Исправлено 2026-05-21:** прямой путь к `../termin-render/include` удалён, используется target dependency |
| `termin-components/termin-components-render/CMakeLists.txt` | 58-60 | **Исправлено 2026-05-21:** широкий путь к `../../termin-app/cpp/termin` удалён; путь к `../../termin-app/core_c/include` также удалён |

**Проблема:** Жёсткая привязка к структуре репозитория. При сборке из пакетов или изменении структуры это сломается.

**Статус 2026-05-21:** исправлено для перечисленных SDK targets. Bypass include paths на `termin-render/include` удалены из library и Python binding targets; `termin-app/cpp/termin` также удалён из `termin-components-render`, потому что перекрывал публичные render headers старой app-копией; app/core_c путь удалён после переноса оставшихся headers к владельцам.

---

### 2.2 Утечка tgfx типов в публичном API termin-render

**Где смотреть:**

| Файл | Утечка |
|------|--------|
| `termin-render/include/termin/render/render_pipeline.hpp:9-11` | `<tgfx2/descriptors.hpp>`, `<tgfx2/i_render_device.hpp>`, `<tgfx2/texture_pool.hpp>` |
| `termin-render/include/termin/render/drawable.hpp:20-21` | `<tgfx/resources/tc_material.h>`, `<tgfx/tgfx_shader_handle.hpp>` |
| `termin-render/include/render/tc_render_target.h:11` | `<tgfx/resources/tc_texture.h>` |
| `termin-render/include/termin/render/fbo_pool.hpp` | tgfx2 типы |
| `termin-render/include/termin/render/render_engine.hpp` | tgfx2 типы |
| `termin-render/include/termin/render/render_context.hpp` | tgfx2 типы |
| `termin-render/include/termin/render/execute_context.hpp` | tgfx2 типы |
| `termin-render/include/termin/render/frame_pass.hpp` | tgfx2 типы |
| `termin-render/include/termin/render/tgfx2_bridge.hpp` | tgfx2 типы |
| `termin-render/include/termin/render/frame_graph_debugger_core.hpp` | tgfx2 типы |
| `termin-render/include/termin/render/shadow.hpp` | tgfx2 типы |
| `termin-render/include/termin/render/resource_spec.hpp` | tgfx2 типы |

**Проблема:** 30+ заголовков termin-render напрямую включают заголовки termin-graphics (`tgfx/`, `tgfx2/`). Любой потребитель termin-render автоматически получает зависимость от termin-graphics. termin-render должен абстрагировать графический бэкенд, а не экспонировать его типы.

**tc_mesh* в публичном API:**
`termin-render/include/termin/render/drawable.hpp`:
```cpp
virtual tc_mesh* get_mesh_for_phase(
    const std::string& phase_mark,
    int geometry_id
) const;
```
`tc_mesh` — тип из termin-mesh, возвращаемый как сырой указатель из интерфейса Drawable.

---

### 2.3 Бизнес-логика в биндингах

**Где смотреть:**

| Файл | Размер | Проблема |
|------|--------|----------|
| `termin-render/python/tc_pass_bindings.cpp` | 1030 строк | Полноценный Python/C++ interop runtime, а не binding layer |
| `termin-engine/bindings/scene_manager_bindings.cpp` | 364 строки | JSON I/O, scene copy, entity enumeration |
| `termin-render/python/tc_render_target_bindings.cpp` | 323 строки | Dynamic module imports, format parsing |
| `termin-inspect/python/bindings/inspect_module.cpp` | 369 строк | Pluggable extractors, tc_value конвертация |

**Массовое hasattr/setattr/getattr** (~69 вхождений в проверенных биндингах):
- `termin-render/python/tc_pass_bindings.cpp` — Python pass interop
- `termin-render/python/render_pipeline_bindings.cpp` — Python pass duck-typing
- Используется как duck-typing fallback — если Python объект не имеет атрибута, C++ молча пропускает

**Python обёртки с бизнес-логикой:**
| Файл | Проблема |
|------|----------|
| `termin-csg/python/termin/csg/cad_app.py` | Полноценное CAD-приложение в биндингах CSG |
| `termin-csg/python/termin/csg/procedural_document.py` | Document model (~336 строк) |
| `termin-app/termin/components/python_component.py` | Python Component base class (~250 строк) |

---

### 2.4 Дублирование биндингов

**Где смотреть:**
- `termin-base/python/bindings/geom/` vs `termin-app/cpp/termin/bindings/geom/` — одинаковые биндинги геометрии
- Смешанная стратегия: `Pose3` — C++ native, `Pose2` — чистый Python numpy

**Обновление 2026-06-20:** app-side legacy copies of `tc_pass_bindings.cpp`, `render_pipeline_bindings.cpp`, `resource_spec.cpp` and `graphics_backend.cpp` were removed from `termin-app`; render pass/pipeline ownership now lives in `termin-render`/`termin-render-framework`. The remaining duplication item here is the geom binding split.

---

### 2.5 Экспозиция внутренних типов через биндинги

**Где смотреть:**
- Биндинги экспонируют `tc_scene_handle`, `tc_pipeline_handle`, `tc_component*` как `uintptr_t`
- `tc_frame_graph_error`, `tc_value` — напрямую экспонируются в Python
- 58 вхождений `#include.*tc_` в файлах биндингов — зависимости от C-уровня (`tc_component`, `tc_scene`, `tc_pass`, `tc_value`, `tc_frame_graph`)
- Нет публичного C++ API слоя — биндинги идут напрямую к C-уровню

---

### 2.6 termin_core (C) дублирует termin-engine (C++)

**Где смотреть:**
- `termin-app/core_c/CMakeLists.txt`

`termin_core` зависит от 9 модулей:
```cmake
target_link_libraries(termin_core PUBLIC tgfx::termin_graphics tcbase::termin_base)
target_link_libraries(termin_core PUBLIC termin_scene::termin_scene)
target_link_libraries(termin_core PUBLIC termin_input::termin_input)
target_link_libraries(termin_core PUBLIC termin_inspect::termin_inspect)
target_link_libraries(termin_core PUBLIC termin_render::termin_render)
target_link_libraries(termin_core PUBLIC termin_display::termin_display)
target_link_libraries(termin_core PUBLIC termin_skeleton::termin_skeleton)
target_link_libraries(termin_core PUBLIC termin_animation::termin_animation)
```

**Проблема:** По сути дублирует termin-engine, но в C. Оба агрегируют один и тот же набор модулей. Смысл разделения неочевиден.

---

## 3. Средний приоритет

### 3.1 termin-engine включает внутренние заголовки нижних уровней

**Где смотреть:**
- `termin-engine/src/rendering_manager.cpp` (строки 14-29)
- `termin-engine/src/engine_core.cpp` (строки 10-11)
- `termin-engine/src/pull_rendering_manager.cpp` (строки 13-16)

```cpp
#include "core/tc_light_capability.h"       // termin-render include/core/
#include "core/tc_camera_capability.h"       // termin-render include/core/
#include "core/tc_scene.h"                   // termin-scene include/core/
#include "core/tc_scene_render_mount.h"      // termin-render include/core/
#include "core/tc_scene_pool.h"              // termin-scene include/core/
#include "core/tc_entity_pool.h"             // termin-scene include/core/
#include "core/tc_entity_pool_registry.h"    // termin-scene include/core/
#include "render/tc_viewport_pool.h"         // termin-display include/render/
#include "render/tc_viewport_input_manager.h"// termin-display include/render/
#include "render/tc_pass.h"                  // termin-render include/render/
#include "render/tc_pipeline.h"              // termin-render include/render/
#include "render/tc_render_target.h"         // termin-render include/render/
```

Паттерн `core/` и `render/` в путях говорит о деталях организации кода внутри модуля. Если termin-scene решит переструктурировать `core/`, termin-engine сломается.

---

### 3.2 EngineCore жёстко знает о scene extensions

**Где смотреть:**
- `termin-engine/src/engine_core.cpp` — **Исправлено 2026-05-21:** EngineCore больше не регистрирует конкретные scene extensions и не инициализирует `termin_collision`.
- `termin-engine/bindings/scene_manager_bindings.cpp` — **Исправлено 2026-05-21:** из engine bindings убраны конкретные ids расширений и `default_scene_extensions`.
- `termin-app/cpp/app/main_minimal.cpp` — прикладной composition root регистрирует нужные расширения до создания `EngineCore`.
- `termin-app/cpp/termin/bindings.cpp` / `termin-app/termin/visualization/core/scene/__init__.py` — прикладной Python API предоставляет `default_scene_extensions` на уровне `termin-app`, а не `termin-engine`.
- `termin-android/src/bootstrap.cpp` — Android composition root регистрирует нужные расширения до создания Android `EngineCore`.

**Было:** EngineCore напрямую инициализировал scene extensions из termin-render и termin-collision. Если появлялось новое расширение (например, termin-physics), EngineCore нужно было менять.

**Статус 2026-05-21:** частично исправлено. В `termin-engine` больше нет default scene extension profile и прямой зависимости от `termin_collision`; выбор и регистрация конкретных расширений вынесены в `termin-app`. Остаточный запах: `termin-engine/src/rendering_manager.cpp` всё ещё работает напрямую с render-specific scene extension (`tc_scene_render_mount`), это отдельная архитектурная задача для следующего прохода.

---

### 3.3 termin-skeleton зависит от termin_graphics для 2 заголовков

**Где смотреть:**
- `termin-skeleton/CMakeLists.txt` (строки 42-44)
- `termin-skeleton/src/tc_skeleton_registry.c:10` — **Исправлено 2026-05-21:** теперь `#include <tcbase/tc_registry_utils.h>`
- `termin-skeleton/include/termin/skeleton/tc_skeleton_handle.hpp:12` — `#include <tcbase/tgfx_intern_string.h>`

`tgfx_intern_string.h` лежит в termin-base (уже зависит). `tc_registry_utils.h` и `tc_resource.h` были продублированы в termin-graphics и termin-mesh.

**Статус 2026-05-21:** исправлено. `tc_registry_utils.h` и `tc_resource.h` вынесены в `termin-base/include/tcbase/`, C geometry headers перенесены в `termin-base/include/geom`, `tc_skeleton.h`/`tc_animation.h` принадлежат `termin-skeleton`/`termin-animation` и используют `tcbase/tc_binding_types.h`, старые resource includes в `termin-render` переведены на `tcbase`, а `termin-skeleton` больше не линкуется с `termin_graphics`.

---

### 3.4 Неявные зависимости между Python пакетами

**Где смотреть:**
Пакеты `termin-render`, `termin-input`, `termin-animation`, `termin-components-mesh` импортируют из других пакетов, не объявленных в `install_requires`:

- Импорты `termin.visualization.*` из пакетов, не являющихся termin-app
- Импорты `termin.cache`, `termin.voxels` из high-level Python слоя `termin-navmesh`
- high-level Python слой `termin-navmesh` всё ещё смешивает navigation utilities, visual/editor components и voxel/cache integration

**Проблема:** Работает в monorepo, но сломается при независимой установке pip-пакетов.

**Статус 2026-05-21:** частично исправлено. Для простых пакетов зависимости добавлены в metadata:
- `termin-render` → `tcbase`, `termin-scene`, `termin-inspect`
- `termin-input` → `termin-scene`
- `termin-animation` → `tcbase`
- `termin-components-mesh` → `tcbase`, `tmesh`, `termin-inspect`, `termin-scene` плюс уже существующие `tgfx`, `termin-csg`

`termin-navmesh` исправлен на уровне native ownership: C registry, Recast/Detour-backed scene components и `_navmesh_native` больше не принадлежат `termin-app`; app-слой оставляет у себя только editor-specific visual glue. Python-пакет всё ещё смешивает navigation utilities, visual/editor components, voxel/cache/render integration и требует отдельного разбиения.

**Новая проверка 2026-06-19:** `termin-navmesh/setup.py` содержит зависимости, нужные текущей смешанной публичной поверхности, но это фикс metadata, а не окончательная архитектурная граница. Самые крупные смешанные файлы остаются: `builder_component.py`, `pathfinding_world_component.py`, `display_component.py`.

---

### 3.5 termin-csg — самый проблемный Python пакет

**Где смотреть:**
- `termin-csg/python/termin/csg/` — содержит CSG-биндинги, документный API, полноценное GUI-приложение (`cad_app.py`), вьюпорт и камеру

**Проблема:** Требует разделения минимум на 2-3 пакета: чистые CSG-биндинги, документный API, GUI-приложение.

**Новая проверка 2026-05-21:** актуальный package path — `termin-csg/python/termin/csg/`, не `termin_csg`. Помимо `cad_app.py` и `procedural_document.py`, GUI/viewport слой заметно сидит в `cad_viewer.py` (~511 строк) и `viewer_camera.py`.

---

### 3.6 termin-display экспортирует приватные C-interop функции

**Где смотреть:**
- `termin-display/python/termin/display/__init__.py`

Экспортирует 20+ приватных C-interop функций через `__all__`. Утечка низкой абстракции.

**Статус 2026-05-21:** закрыто по `__all__`. Приватные функции больше не экспортируются wildcard-импортом из `termin.display`, но остаются импортируемыми по имени для существующего внутреннего кода.

---

### 3.7 termin-engine и termin-inspect пропускают preload_sdk_libs()

**Где смотреть:**
- `termin-engine/python/termin/engine/__init__.py`
- `termin-inspect/python/termin/inspect/__init__.py`

Не вызывают `preload_sdk_libs()`, что делает их хрупкими при отсутствии RPATH.

**Статус 2026-05-21:** исправлено. Актуальные пакеты `termin.engine` и `termin.inspect` вызывают `preload_sdk_libs("termin_engine")` и `preload_sdk_libs("termin_inspect")`.

---

### 3.8 Дублирование project management между Qt и tcgui

**Где смотреть:**

| Функциональность | Qt | tcgui |
|-----------------|-----|-------|
| Контроллер проекта | `EditorProjectController` (отдельный класс) | inline в `EditorWindowTcgui` |
| `_new_project` | `project_controller.py` | `editor_window.py:1598` |
| `_open_project` | `project_controller.py` | `editor_window.py:1611` |
| `_load_project` | `project_controller.py` | `editor_window.py:1644` |
| `_rescan_file_resources` | `editor_window.py:1095` | `editor_window.py:2339` |
| `SceneFileController` | отдельный класс | отсутствует |

---

### 3.9 Расхождение функциональности Qt vs tcgui

**Статус 2026-05-24:** закрыто удалением Qt/PyQt frontend. `termin/editor/` больше не является view-слоем, там остался только compatibility entrypoint на tcgui.

---

### 3.10 EditorWindow — God Object

**Где смотреть:**
- `termin-app/termin/editor/editor_window.py` (~2003 строки)
- `termin-app/termin/editor_tcgui/editor_window.py` (~2504 строки)

В обоих `EditorWindow` смешаны:
- Создание и управление UI-компонентами
- Бизнес-логика (undo/redo, scene management, project management)
- Инициализация подсистем (SpaceMouse, interaction system, rendering)
- Обработка событий (drag-drop, keyboard, viewport clicks)
- Диалоги и модальные окна

---

## 4. Низкий приоритет

### 4.1 Дублирование tc_registry_utils.h

**Где смотреть:**
- `termin-base/include/tcbase/tc_registry_utils.h`
- `termin-graphics/include/tgfx/tc_registry_utils.h` — **удалён 2026-05-21**
- `termin-mesh/include/tgfx/tc_registry_utils.h` — **удалён 2026-05-21**

Полностью идентичные файлы (byte-for-byte). Утилиты для индексного пакинга, генерации UUID и guard-макросов. Оба модуля зависят от termin_base — логичное место вынести туда.

**Статус 2026-05-21:** исправлено. Общий заголовок живёт в `termin-base`, потребители используют `<tcbase/tc_registry_utils.h>`.

---

### 4.2 C# биндинги — аналогичные паттерны проблем

**Где смотреть:**
- `termin-csharp/termin.i` (1402 строки) — SWIG интерфейс
- `termin-csharp/CSharpComponentRuntime.cs` — reflection-based component runtime

Аналогичные проблемы с бизнес-логикой в биндингах и экспозицией внутренних типов.

---

## 5. Что выглядит несложно поправить

Эти пункты не решают всю архитектуру, но дают локальный прогресс без распила `RenderingManager` или публичного render API.

### 5.1 Добавить публичный input adapter для `Viewport3D`

**Где смотреть:** `termin-gui/python/tcgui/widgets/viewport3d.py`

`Viewport3D` уже переключен с app compatibility `termin._native.render` на владельца символов `termin.display`. Но он всё ещё вызывает `_display_get_surface_ptr`, `_render_surface_get_input_manager`, `_input_manager_on_mouse_move`, `_input_manager_on_scroll`, `_input_manager_on_mouse_button`, `_input_manager_on_key` как приватные underscored functions.

Следующий небольшой правильный шаг: добавить публичный adapter в `termin.display` или `termin.visualization.platform.input_manager`, который принимает display/input-manager handle и предоставляет методы `mouse_move`, `scroll`, `mouse_button`, `key`. После этого `Viewport3D` перестанет знать о native symbol names. Это не уберёт весь interop, но перенесёт его в слой-владелец display/input.

### 5.2 Component binding targets больше не завязаны на `termin-app/cpp/termin/bindings`

**Где смотреть:**
- `termin-components/termin-components-animation/CMakeLists.txt`
- `termin-components/termin-components-skeleton/CMakeLists.txt`
- `termin-components/termin-components-render/CMakeLists.txt`
- `termin-animation/CMakeLists.txt`
- `termin-skeleton/CMakeLists.txt`

**Статус 2026-05-21:** локальная ownership-проблема закрыта. Binding source files для skeleton/animation перенесены к владельцам:
- `termin-skeleton/cpp/bindings/skeleton_module.cpp`
- `termin-animation/cpp/bindings/animation_module.cpp`
- `termin-components/termin-components-skeleton/cpp/bindings/skeleton_component_module.cpp`
- `termin-components/termin-components-animation/cpp/bindings/animation_component_module.cpp`

`termin-components-render` переключён с app-local `entity_helpers.hpp` на публичный helper из `termin-scene`.

### 5.3 Разделить high-level Python слой `termin-navmesh`

**Где смотреть:**
- `termin-navmesh/python/termin/navmesh/builder_component.py`
- `termin-navmesh/python/termin/navmesh/pathfinding_world_component.py`
- `termin-navmesh/python/termin/navmesh/display_component.py`
- `termin-navmesh/setup.py`

Native ownership уже перенесён в `termin-navmesh`: `termin_navmesh_components` и `termin.navmesh._navmesh_native` собираются там, а `termin-app` держит только editor-specific визуализацию off-mesh links. Следующий шаг — разделить Python exports на core/navigation и visual/editor/cache integration, чтобы metadata отражала выбранную публичную поверхность, а не временно смешанный слой.

### 5.4 Упростить render pass Python interop runtime

**Где смотреть:**
- `termin-render/python/tc_pass_bindings.cpp`

App-side legacy duplicate was removed; canonical ownership is now in `termin-render`. Следующий шаг — уменьшить бизнес-логику внутри `tc_pass_bindings.cpp`: вынести Python pass interop helpers в явный runtime/helper слой и оставить binding file тонкой регистрацией API.

### 5.5 Уточнить публичную поверхность `termin.display`

**Где смотреть:** `termin-display/python/termin/display/__init__.py`

`__all__` уже очищен, но приватные underscored функции импортируются в module namespace для внутренних call sites. Небольшой следующий шаг — перенести эти imports в отдельный внутренний модуль, например `termin.display._interop`, и постепенно переключать внутренний код на него. Это уменьшит случайную доступность приватных символов без немедленного удаления совместимости.

---

## 6. Карта зависимостей

### 6.1 C++ модули (из CMake target_link_libraries)

```
termin_base          (корень, 0 зависимостей)
termin_inspect       → termin_base
termin_mesh          → termin_base
termin_lighting      → termin_base (INTERFACE)
termin_navmesh       → termin_base
termin_scene         → termin_base, termin_inspect
termin_input         → termin_base, termin_scene
termin_modules       → termin_base
termin_graphics      → termin_base, termin_mesh
termin_csg           → termin_base
termin_collision     → termin_base, termin_inspect, termin_scene
termin_skeleton      → termin_base, termin_scene
termin_animation     → termin_base, termin_inspect, termin_skeleton
termin_physics       → termin_base, termin_collision
termin_render        → termin_base, termin_graphics, termin_scene, termin_inspect, termin_lighting
termin_display       → termin_base, termin_graphics, termin_scene, termin_input, termin_render
termin_materials     → termin_base, termin_graphics
termin_engine        → termin_base, termin_graphics, termin_scene, termin_render,
                       termin_display, termin_input
termin_android       → termin_base, termin_graphics, termin_scene, termin_mesh,
                       termin_render, termin_display, termin_engine,
                       termin_collision, termin_runtime, termin_materials,
                       termin_components_mesh, termin_components_render
termin_core (app)    → termin_base, termin_graphics, termin_scene, termin_input,
                       termin_inspect, termin_render, termin_display,
                       termin_skeleton, termin_animation
```

### 6.2 Нарушения направления зависимостей

```
termin-gui/ (GUI framework)
    ↓ НАРУШЕНИЕ: Viewport3D → termin.display underscored C-interop functions
termin/visualization/ (SDK-level, но в termin-app)
    ↓ НАРУШЕНИЕ: ui/widgets/ → tcgui (re-export, не абстракция)
    ↓ НАРУШЕНИЕ: ui/widgets/component.py → tcgui
termin/editor_core/ (декларирует UI-agnostic)
    ↓ НАРУШЕНИЕ: editor_camera_ui_controller.py → tcgui
termin/editor_tcgui/ (tcgui)
```

### 6.3 Правильные абстракции (положительные примеры)

| Файл | Что сделано правильно |
|------|----------------------|
| `termin-app/termin/editor_core/dialog_service.py` | ABC с двумя реализациями (QtDialogService, TcguiDialogService) |
| `termin-app/termin/editor_core/entity_operations.py` | Бизнес-логика вынесена в общий слой |
| `termin-app/termin/editor_core/signal.py` | Собственная реализация сигналов, не зависящая от Qt |
| `editor_core/` модели | `InspectorModel`, `RenderingModel`, `GameModeModel`, `ProjectOperations` |

---

## Сводная таблица

| # | Проблема | Модуль | Файл | Серьёзность |
|---|----------|--------|------|-------------|
| 1.1 | RenderingManager God Object + дублирование PullRM | termin-engine | rendering_manager.cpp | 🔴 Критическая |
| 1.2 | termin-engine компилирует .cpp из termin-app | termin-engine | CMakeLists.txt | 🟠 Частично исправлено |
| 1.3 | Утечка GUI в editor_core | termin-app | editor_camera_ui_controller.py, spacemouse_controller.py | 🔴 Частично исправлено |
| 1.4 | termin-gui Viewport3D → SDK internals | termin-gui | viewport3d.py | 🔴 Частично исправлено |
| 2.1 | Прямые пути к include в CMake | termin-display, termin-components-render | CMakeLists.txt | ✅ Исправлено |
| 2.2 | Утечка tgfx типов в публичном API | termin-render | render_pipeline.hpp, drawable.hpp (+ 30 хедеров) | 🟠 Высокая |
| 2.3 | Бизнес-логика в биндингах + hasattr/setattr | termin-* python bindings | tc_pass_bindings.cpp и др. | 🟠 Высокая |
| 2.4 | Дублирование/расхождение биндингов | termin-base, termin-app | geom/ | 🟠 Частично исправлено |
| 2.5 | Экспозиция внутренних типов через биндинги | termin-* python bindings | uintptr_t handles, tc_* типы | 🟠 Высокая |
| 2.6 | termin_core дублирует termin-engine | termin-app/core_c | CMakeLists.txt | 🟠 Высокая |
| 3.1 | Внутренние include из нижних уровней | termin-engine | rendering_manager.cpp | 🟡 Средняя |
| 3.2 | EngineCore жёстко знает о extensions | termin-engine | engine_core.cpp | 🟠 Частично исправлено |
| 3.3 | termin-skeleton → termin_graphics для 2 хедеров | termin-skeleton | CMakeLists.txt | ✅ Исправлено |
| 3.4 | Неявные зависимости Python пакетов | termin-* python | install_requires | 🟡 Частично исправлено |
| 3.5 | termin-csg — перегруженный пакет | termin-csg | cad_app.py, procedural_document.py, cad_viewer.py | 🟡 Средняя |
| 3.6 | termin-display экспортирует приватные функции | termin-display | __init__.py | ✅ Исправлено |
| 3.7 | Пропуск preload_sdk_libs() | termin-engine, termin-inspect | __init__.py | ✅ Исправлено |
| 3.8 | Дублирование project management | termin-app | editor/ vs editor_tcgui/ | 🟡 Средняя |
| 3.9 | Расхождение Qt vs tcgui функциональности | termin-app | 28 vs 10 файлов | 🟡 Средняя |
| 3.10 | EditorWindow God Object | termin-app | editor_window.py (2000-2500 строк) | 🟡 Средняя |
| 4.1 | Дублирование tc_registry_utils.h | termin-graphics, termin-mesh | tc_registry_utils.h | ✅ Исправлено |
| 4.2 | C# биндинги — аналогичные паттерны | termin-csharp | termin.i, CSharpComponentRuntime.cs | 🟢 Низкая |
