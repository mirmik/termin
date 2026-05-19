# Runtime domain extraction audit

Дата: 2026-05-19

Статус: частичный аудит и план миграции runtime-доменов из `termin-app`.

## Правило миграции

В ходе этой миграции **не добавляем новые compatibility wrappers / re-export wrappers**.

Если домен переносится в актуальную библиотеку, переносим его чисто:

1. Код физически переезжает в новый canonical package.
2. Все импорты в репозитории сразу заменяются на новый canonical path.
3. Старый модуль удаляется из `termin-app`, если он больше не нужен.
4. Временные re-export слои не создаются.

Исключение возможно только для уже существующих исторических реэкспортов, которые удаляются отдельным последующим шагом. Новые враперы в рамках этой работы не добавлять.

## Контекст

Цель: уменьшить зависимость standalone player / Android runtime от `termin-app`.

Важно различать:

- Python namespace `termin.*`;
- физическую принадлежность к pip-пакету/подпроекту;
- compatibility exports через `termin._native`.

Часть доменов уже имеет отдельные canonical-библиотеки, но `termin-app` еще содержит старые импорты или реэкспорты. Другая часть пока действительно живет в `termin-app`, хотя по смыслу является runtime-слоем.

## `termin.engine`

Canonical package уже существует:

- `termin-engine/python/termin/engine/__init__.py`
- native module: `termin.engine._engine_native`

`termin-app` все еще реэкспортирует `EngineCore` через `termin._native`:

- `termin-app/cpp/termin/bindings.cpp` импортирует `termin.engine._engine_native`;
- затем публикует `m.attr("EngineCore") = engine_native.attr("EngineCore")`.

Старый путь:

```python
from termin._native import EngineCore
from termin._native.scene import SceneManager, SceneMode, default_scene_extensions
from termin._native.render import RenderingManager, ViewportRenderState
```

Canonical путь:

```python
from termin.engine import EngineCore, RenderingManager, SceneManager, ViewportRenderState
from termin.engine import scene as engine_scene
from termin.engine import render as engine_render
```

### План

1. Заменить импорты `EngineCore` в player/editor/profiler на `termin.engine.EngineCore`.
2. Заменить импорты `SceneManager`, `SceneMode`, `default_scene_extensions` на `termin.engine.scene`.
3. Заменить импорты `RenderingManager`, `ViewportRenderState` на `termin.engine` или `termin.engine.render`.
4. После полной замены удалить re-export из `termin._native`, если downstream код больше его не использует.

### Риск

Низкий. `termin._native.EngineCore` уже является реэкспортом `termin.engine._engine_native.EngineCore`; функционально объект тот же.

## `termin.modules`

Низкоуровневый canonical package уже есть:

- `termin-modules/python/termin_modules/__init__.py`
- native module: `termin_modules._termin_modules_native`

Но `termin.modules` в `termin-app` не является простым реэкспортом. Он содержит app-level/runtime integration:

- `ProjectModulesRuntime`;
- singleton `get_project_modules_runtime()`;
- `upgrade_scene_unknown_components(scene)`;
- SDK/environment configuration;
- C++/Python backend registration;
- event/build-output listener glue.

Главный оставшийся app-coupling:

- `TermModulesIntegration` физически живет в `termin-app/cpp/termin/modules`;
- биндинг живет в `termin-app/cpp/termin/bindings/modules`;
- Python получает его как `termin._native.modules.TermModulesIntegration`.

По смыслу `TermModulesIntegration` должен жить рядом с `termin_modules`, потому что он связывает `ModuleRuntime` с scene unknown-component upgrade/degrade.

### План

1. Перенести `TermModulesIntegration` C++ из `termin-app/cpp` в `termin-modules`.
2. Добавить binding `TermModulesIntegration` в `termin_modules._termin_modules_native`.
3. Перенести `ProjectModulesRuntime` из `termin-app/termin/modules/runtime.py` в canonical место.

Варианты canonical path:

```python
from termin_modules import ProjectModulesRuntime, get_project_modules_runtime
```

или, если хотим сохранить namespace `termin.*` без app:

```python
from termin.modules import ProjectModulesRuntime, get_project_modules_runtime
```

Во втором случае пакет `termin-modules` должен начать поставлять `termin.modules` напрямую, а старый `termin-app/termin/modules` удаляется.

Предпочтение для чистого переноса: `termin-modules` поставляет `termin.modules`, чтобы существующая публичная семантика namespace осталась, но физическая принадлежность стала корректной. После переноса все импорты продолжают указывать на `termin.modules`, но модуль уже не принадлежит `termin-app`.

4. Заменить все обращения к `termin._native.modules.TermModulesIntegration` на canonical import из `termin_modules` или `termin.modules`.
5. Удалить `termin-app/termin/modules`.

### Риск

Средний. Нужно проверить CMake-зависимости `termin-modules`: после переноса integration начнет зависеть от scene/unknown-component APIs. Это может усилить зависимость `termin-modules` от `termin-scene` и связанных библиотек.

## `termin.assets`

Текущий `termin-assets` package содержит только контракты:

- `termin_assets.AssetTypeRegistry`;
- `AssetImportPlugin`;
- `AssetRuntimePlugin`;
- `PreLoadResult`;
- spec-file helpers.

Полноценный runtime resource layer сейчас действительно живет в `termin-app`:

- `termin-app/termin/assets/asset.py`
- `termin-app/termin/assets/data_asset.py`
- `termin-app/termin/assets/resource_handle.py`
- `termin-app/termin/assets/resources/*`
- `termin-app/termin/assets/default_plugins.py`
- asset implementations: texture, material, shader, mesh, glb, prefab, pipeline, navmesh, skeleton, audio, ui, voxel grid.

`termin.assets` сильно связан с:

- `termin.core.identifiable`;
- texture bindings from `termin-graphics` (`tgfx`);
- `termin.visualization.render.framegraph`;
- `termin.render_framework`;
- `termin.engine`;
- `termin.loaders`;
- asset-specific runtime packages: navmesh, skeleton, animation, audio, voxels, ui.

### План

Не переносить `termin.assets` одним большим шагом.

Порядок:

1. Вынести низовые классы:
   - `Asset`;
   - `DataAsset`;
   - `AssetRegistry`;
   - `ResourceHandle`;
   - `Identifiable`, если он остается единственной причиной держать `termin.core`.

2. Вынести `ResourceManager` core:
   - registry/accessors/base;
   - без editor file watcher;
   - без project browser/editor concerns.

3. Вынести asset types группами:
   - shader/material/pipeline;
   - texture;
   - mesh/glb;
   - prefab;
   - navmesh/skeleton/animation;
   - audio/ui/voxel grid.

4. `project_file_watcher` не переносить в базовый assets runtime без отдельного решения. Это ближе к editor/dev tooling.

5. После каждого переноса заменить все импорты на новый canonical package и удалить старые файлы из `termin-app`.

### Риск

Высокий. Это центральный runtime слой, которым пользуются player, editor, project builder, visualization, loaders и тесты.

## `termin.texture`

Сейчас лежит в `termin-app`, но является чистым re-export wrapper над `tgfx`:

```python
from tgfx import TcTexture, tc_texture_declare, ...
```

### План

Не переносить `termin.texture` как отдельный пакет. Это создало бы новый wrapper/re-export слой, что противоречит правилу миграции.

После переноса:

1. Заменить все импорты `from termin.texture import ...` на прямые импорты из `tgfx`.
2. Удалить `termin-app/termin/texture`.
3. Не добавлять `termin.texture` в `termin-graphics`.

### Риск

Низкий. Модуль не содержит app/editor логики и не добавляет собственной семантики поверх `tgfx`.

## `termin.geombase`

Сейчас лежит в `termin-app`, но по смыслу ближе к base/math runtime.

Содержит:

- re-export `tcbase._geom_native`;
- `Pose2`;
- `Screw`, `Screw2`;
- `TransformAABB`;
- дополнительные импорты `GeneralTransform3` из `termin.scene` и `Ray3` из `termin.colliders`.

### План

Перенести в `termin-base` или отдельный math/base package.

Возможный staged split:

1. Перенести чистую часть:
   - `_geom_native.py`;
   - `pose2.py`;
   - `screw.py`;
   - `transform_aabb.py`.

2. Проверить зависимости `GeneralTransform3` и `Ray3`.
   Если `termin-base` не должен зависеть от `termin-scene`/`termin-collision`, эти re-export imports надо убрать из `termin.geombase.__init__` или перенести в более высокий слой.

3. Заменить все импорты и удалить старые файлы из `termin-app`.

### Риск

Средний. Сам код легкий, но `__init__.py` сейчас смешивает base geometry с scene/collision типами.

## `termin.visualization`

Это главный runtime-хвост, который удерживает player в `termin-app`.

Содержит:

- scene/entity/display/viewport Python wrappers;
- rendering manager integration;
- framegraph Python passes;
- materials/posteffects/shadow/lighting glue;
- platform backends;
- UI component integration.

Сейчас активно импортирует `termin._native.render`, хотя часть этих типов уже должна идти через `termin.engine.render`, `termin.render_framework`, `termin.display`, `termin.viewport`, `termin.render_components`.

### Аудит `termin._native.render`

Первые безопасные замены уже очевидны:

- `Display`, `FBOSurface`, `DisplayInputRouter` и низовые input/surface helpers имеют canonical owner `termin.display`;
- `RenderPipeline`, `ResourceSpec`, `ExecuteContext`, `RenderContext`, pipeline/pass registry helpers и `compile_graph_from_json` имеют canonical owner `termin.render_framework`;
- `RenderingManager` и `ViewportRenderState` уже должны идти через `termin.engine`.

Оставшиеся группы пока не имеют подтвержденного clean canonical owner:

- material layer: `TcMaterial`, `TcMaterialPhase`, `TcRenderState`, material registry helpers;
- shader/parser layer: `GlslPreprocessor`, `glsl_preprocessor`, shader parser/property types;
- app-bound render runtime: `RenderEngine`, `ImmediateRenderer`, `SolidPrimitiveRenderer`;
- concrete passes still bound in `termin-app`: `ColorPass`, `ShadowPass`, `IdPass`, `ColliderGizmoPass`, `DebugTrianglePass`, `PresentToScreenPass`, `BloomPass`, `GrayscalePass`, `SkyBoxPass`, `TonemapPass`;
- shadow helpers/resources still bound in `termin-app`;
- `termin-components-render` still depends on `termin._native.render` for `TcMaterial`/`TcRenderState` and `SkinnedMeshRenderer`.

Это значит, что следующий C++-перенос должен начинаться не с `visualization`, а с material/shader/pass ownership. Иначе `termin-components-render` и `termin.visualization.render` продолжат держаться за `termin-app`.

### План

Не начинать с полного переноса `termin.visualization`.

Сначала уменьшить legacy imports:

1. `termin._native.render.RenderingManager` -> `termin.engine.RenderingManager` (уже сделано для текущих Python-потребителей).
2. `termin._native.render.Display/FBOSurface/input helpers` -> `termin.display`.
3. `termin._native.render.RenderPipeline/ResourceSpec/ExecuteContext/RenderContext/registry helpers` -> `termin.render_framework`.
4. Для concrete passes разделить ownership:
   - generic framegraph/runtime passes в `termin-render`;
   - geometry/material/depth/normal passes в `termin-components-render`;
   - editor/debug-only passes оставить отдельно или вынести в editor/runtime package.
5. Material/shader APIs вынести из `termin-app` раньше render-components cleanup, потому что `termin-components-render` уже зависит от этих типов.

После этого определить новый package, например:

```text
termin-runtime
  termin.visualization.*
```

или разложить:

```text
termin-render-runtime
  termin.visualization.render.*

termin-scene-runtime
  termin.visualization.core.*
```

### Риск

Высокий. Это слой, который одновременно нужен editor, player и потенциально Android runtime.

## Player impact

Текущий player зависит от `termin-app` не из-за editor, а из-за runtime-доменов:

- `termin.visualization`;
- `termin.assets`;
- `termin.modules`;
- direct `tgfx` texture APIs;
- `termin.geombase`;
- исторически `termin._native.EngineCore`.

После первых переносов можно быстро уменьшить app-coupling:

1. `EngineCore` импортировать из `termin.engine`.
2. Разобрать `termin.texture`: заменить импорты на `tgfx` и удалить пакет из `termin-app`.
3. `termin.geombase` вынести из `termin-app`.
4. `termin.modules` перенести в `termin-modules`.

После этого у player останутся два крупных runtime-хвоста:

- `termin.assets`;
- `termin.visualization`.

Именно их надо будет выносить перед настоящим `termin-player` package / Android bootstrap.

## Рекомендуемый порядок работ

1. `termin.engine` import cleanup.
2. `termin.texture` removal.
3. `termin.geombase` physical move.
4. `termin.modules` integration move.
5. Аудит `termin._native.render` references и замена на canonical owners.
6. `termin.assets` split/move.
7. `termin.visualization` move.
8. Только после этого выделять `termin-player` как самостоятельный package.

## Проверки после каждого этапа

Минимально:

```bash
bash run-tests-python.sh termin-app/tests/test_player_manifest_assets.py
bash run-tests-python.sh termin-app/tests/test_game_mode_model.py
bash run-tests-python.sh termin-app/tests/test_default_pipeline_specs.py
```

Плюс targeted tests по перенесенному домену.

Для C++/binding переносов:

```bash
./build-sdk-bindings.sh
./setup-test-venv.sh --force
bash run-tests-python.sh
```

Если меняются CMake-зависимости библиотек, сначала прогонять C++ configure/build целевого SDK.
