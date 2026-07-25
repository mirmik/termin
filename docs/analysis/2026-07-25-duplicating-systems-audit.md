# Сводный аудит дублирующих и параллельных систем Termin

Дата: 2026-07-25.

Статус: статический read-only аудит HEAD
`98e5754569404af37ad8772f6630991ff4f69b18`. Исходный код во время анализа
не изменялся. Обновление 2026-07-25: первый P0-хвост, editor/launcher tcgui
frontend (#437), удалён после live gate; второй runtime assembler `termin-app`
(#681) также удалён и заменён relocated SDK smoke. Исторические размеры и
ссылки ниже оставлены как исходная фиксация проблемы. Дублирующие Python
component/pass registries (#644) удалены; bootstrap теперь явно привязывает
Python-проекции к canonical runtime descriptors.

Связанные документы:

- [аудит оверинжиниринга и архитектурной хрупкости](2026-07-15-overengineering-and-architectural-fragility-audit.md);
- [аудит быстродействия render frame](2026-07-18-render-performance-audit.md);
- [аудит миграции UI редактора](2026-07-12-native-editor-ui-migration-audit.md);
- [аудит canonical C resource layer](2026-07-20-canonical-c-resource-layer-audit.md).

## Резюме

Опасение по поводу роста кодовой базы подтверждается, но основной источник
роста — не обычная копипаста. Проект систематически оплачивает новую архитектуру,
не удаляя предыдущую:

- старый и новый frontend одновременно входят в production payload;
- transitional host API собирается рядом с уже принятым replacement;
- один runtime artifact собирается двумя независимыми packager-ами;
- одна type/resource сущность регистрируется в двух каталогах;
- одна value-модель представлена тремя деревьями и конвертерами;
- кэшированный render graph сопровождается заново построенным execution plan;
- общий lifecycle primitive существует рядом с четырьмя локальными реализациями;
- subsystem callback протянут через C, C++ и Python без фактического потребителя.

Главный диагноз:

> В репозитории слишком много не сложной архитектуры, а промежуточной
> архитектуры без завершённого exit plan.

По снимку на дату аудита first-party production source, без third-party, tests,
docs и examples, содержит приблизительно 1 955 файлов и 413 082 строки.
От снимка перед 2026-06-25 до текущего HEAD чистый рост этой выборки составил
около 108 842 строк. Наиболее заметно выросли `termin-gui-native`,
`termin-app`, `termin-render` и `termin-build-tools`.

При этом exact-clone scan по репозиторию нашёл 461 clone и 8 572
дублированные строки, или около 1,95% проверенного текста. Следовательно,
буквальное копирование не объясняет масштаб роста. Основной объём находится в
семантически параллельных системах: код отличается синтаксически, но решает одну
и ту же lifecycle, ownership, registration, packaging или execution задачу.

## Что в этом документе считается дублированием

Система включена в аудит, если выполняется хотя бы одно условие:

1. Два production path предоставляют один пользовательский сценарий.
2. Два владельца хранят изменяемое представление одной сущности.
3. Старый compatibility layer остаётся частью default build после появления
   canonical replacement.
4. Статическая информация пересобирается повторно без изменения её входов.
5. Общий primitive уже существует, но несколько подсистем поддерживают свои
   реализации того же алгоритма.
6. Framework capability не имеет подтверждённого product consumer, но уже
   требует cross-module lifecycle, serialization или binding infrastructure.

Сам по себе большой файл, C ABI, число классов, backend-специфичный lowering или
наличие Python/C++ projection дублированием не считаются.

## Сводная матрица

| Приоритет | Параллельные системы | Целевой источник истины | Рекомендуемое действие | Трекинг |
| --- | --- | --- | --- | --- |
| P0 | `editor_tcgui` и native editor/launcher | native editor и native launcher | Выполнено 2026-07-25: legacy dispatch/frontend удалён; toolkit остаётся до миграции остальных consumers | #437 |
| P0 | `application_host` и explicit window/document composition | `DocumentRenderer` + optional window adapter | Выполнено 2026-07-25: ownership hosts удалены, consumers переведены на explicit composition | #593, #760 |
| P0 | host-derived `termin-app` bundle и canonical SDK tree | проверенное SDK install tree | Выполнено 2026-07-25: второй runtime assembler удалён, acceptance перенесён на relocated SDK | #633, #681 |
| P1 | `DefaultResourceManager` registries и native runtime descriptors | runtime type descriptor facets | Выполнено 2026-07-25: Python-каталоги удалены, bootstrap публикует class projections в canonical descriptors | #631, #644 |
| P1 | `nos::trent`, `tc_value`, `tc::trent` | `tc_value` storage + `tc::trent` C++ facade | вытеснить и удалить `nos::trent` и duplicate converters | #86 |
| P1 | cached framegraph и per-frame metadata rebuild | revisioned `PipelineExecutionPlan` | компилировать metadata только при invalidation | #554 |
| P1 | planner logical frame и per-job backend frames | `RenderingManager` frame scope | один submit на logical frame, frame-local scene cache | #556 |
| P1 | четыре local generational pool и `tc_pool` | расширенный `tc_pool` | мигрировать display/viewport/RT/pipeline storage | #847 |
| P1 | runtime и published local wheel builds | один artifact set с build identity | строить каждый local wheel один раз | #846 |
| P1 | core render-attachment callbacks и subsystem capability model | subsystem-owned render participation либо отсутствие callback | удалить callbacks, если внешний consumer не подтверждён | #798 |
| P2 | generic `FrameGraphResource`/`FBOMap` и typed execution maps | typed resource maps | удалить null-filled generic map и cast | #554 |
| P2 | широкая UI serialization framework и два зарегистрированных widgets | явно выбранный product persistence contract | заморозить расширение до решения; выбрать lean/narrow contract | #821 |
| P2 | два embedded-Python bootstrap в editor и launcher | общий `python_host` bootstrap | вынести SDK/PyConfig discovery в один helper | новый follow-up при планировании `termin-app` |
| P2 | source-player fallback scene construction и packaged player contract | сохранённая runtime scene configuration | удалить silent fallback и объединить neutral source loader | требует отдельного подтверждения |

## 1. Параллельные editor frontends

### Наблюдение

Production editor по умолчанию native, но старый frontend остаётся выбираемым:

- `termin-app/termin/editor/run_editor.py:22` рекламирует `--ui=BACKEND`;
- `termin-app/termin/editor/run_editor.py:34-42` принимает `tcgui`;
- `termin-app/termin/editor/run_editor.py:76-79` импортирует
  `termin.editor_tcgui`;
- `termin-app/termin/launcher/app.py:213-221` lazy-load-ит старый toolkit;
- `termin-app/termin/launcher/app.py:600-619` сохраняет второй selector;
- `termin-app/termin/launcher/app.py:637-732` содержит отдельный legacy run path;
- `build-system/application-python-payloads.json:8-16` включает legacy frontend
  в desktop payload;
- `build-system/packages.json:82-91` включает `tcgui` в SDK.

Текущий объём:

- `termin-app/termin/editor_tcgui`: приблизительно 17 482 строки Python;
- `termin-gui`: приблизительно 13 207 строк first-party production source;
- вместе: около 30 689 строк без legacy projection в launcher.

В старом и новом frontend найдено не менее 17 одноимённых модулей: about,
camera overlay, entity/material/pipeline inspectors, modules/project browser,
profiler, settings и другие панели. Это не exact clones, но две реализации
одного product surface.

### Вердикт

`termin.editor_tcgui` и production selector являются прямым migration tail.
После live gate их следует удалить, а comparison mode при необходимости
сохранять только как отдельный dev target, не входящий в installed payload.

Удаление всех 30,7 тысяч строк одним шагом некорректно: `termin-gui` всё ещё
имеет non-editor consumers, включая UIComponent, CSG, tcplot и nodegraph. Поэтому
граница должна быть следующей:

1. удалить editor/launcher legacy route и `editor_tcgui`;
2. инвентаризировать и мигрировать оставшихся toolkit consumers;
3. только затем удалить `termin-gui` как package.

Трекинг: #437, umbrella #244.

Обновление 2026-07-25: рекомендованный первый этап выполнен. Из production
editor/launcher удалены selector и imports, пакет `termin.editor_tcgui` и его
payload/tests удалены. `termin-gui` намеренно остаётся для `UIComponent`, CSG,
`tcplot` и nodegraph; это отдельный остаток umbrella #244.

## 2. Transitional application/window host внутри нового GUI

Обновление 2026-07-25: рекомендация выполнена в #745 и #760.

- Tally, showcase, launcher и editor используют явную композицию
  `WindowManager`/`GuiWindowAdapter` либо `OffscreenGuiComposition`;
- `GuiApplicationHost`, `GuiWindowHost`, `StandaloneGuiApplication`,
  `OffscreenGuiApplication` и Python ownership proxies удалены;
- старый target/export/install, bindings и compatibility tests удалены;
- `DynamicTextureLease` привязан к `DocumentRenderer`;
- Python core и offscreen CMake component не зависят от `termin-window`;
- `termin-display` разделён на headless-safe core и явный `window` component,
  поэтому headless editor не загружает SDL транзитивно.

Итоговая ownership-модель соответствует вердикту аудита: toolkit владеет
document/widget/layout/paint primitives, window adapter остаётся optional
leaf, а application loop и window collection принадлежат product host.

## 3. Два runtime assembler для editor application

### Наблюдение

Canonical SDK уже формируется из exact lock и offline wheelhouse, но
`termin-app` поддерживает отдельный standalone bundle:

- `termin-app/CMakeLists.txt:4-18` объявляет standalone bundle;
- `termin-app/CMakeLists.txt:26` включает `BUNDLE_PYTHON`;
- `termin-app/CMakeLists.txt:57-134` читает host `sys.prefix`, копирует
  `libpython` и stdlib;
- `termin-app/CMakeLists.txt:135-175` содержит ручные списки external и local
  packages;
- `termin-app/build.sh:109-120` конфигурирует bundle;
- `termin-app/build.sh:146-184` копирует SDK libraries, assets и
  site-packages поверх собранного дерева.

Таким образом, один runtime сначала выводится из ambient host Python и
hardcoded package lists, а затем частично заменяется проверенным SDK. Linux и
Windows scripts при этом реализуют разные детали.

Сам управляющий код `termin-app/CMakeLists.txt`, `build.sh` и `build.ps1`
занимает около 584 строк, но реальная стоимость выше: это второй dependency
resolver, второй layout contract и второй набор relocation assumptions.

### Вердикт

Единственным editor runtime artifact должен быть проверенный SDK install tree.
`termin-app` остаётся executable product и composition root, но не собирает
собственный Python distribution.

Допустимы:

- compile/link smoke приложения против установленного SDK;
- relocation smoke копии SDK;
- будущий отдельный product profile, только если он выводится из manifest
  проверенного SDK, а не из host environment.

Трекинг: #633, #681.

Обновление 2026-07-25: отдельные `termin-app/CMakeLists.txt`, `build.sh`,
`build.ps1` и install/run wrappers удалены вместе с `BUNDLE_PYTHON` control
plane. Старый host-Python smoke заменён одной реализацией SDK relocation
verification и тонкими Linux/Windows entrypoints. Проверка копирует SDK,
валидирует artifact/runtime/application manifests и запускает bundled hosts с
hostile Python environment из relocated working directory. Desktop project
bundle остаётся отдельным контрактом и в этот smoke не включён.

## 4. Повторная build/CI orchestration

### 4.1. Один SDK orchestrator владеет несвязанными стадиями

Обновление 2026-07-25: выполнено в #841. Из `sdk.py` вынесены SDK doctor,
bundled-Python preparation и relocated-SDK smoke orchestration. Модуль снова
укладывается в repository policy limit, а canonical repository-control check
проходит. Новые модули имеют собственные unit-тесты; command surface
`termin_build.sdk` сохранён.

### 4.2. Все local wheels строятся дважды

Обычный Linux `./build-sdk.sh`:

1. вызывает `_build_local_package_wheels(..., force=True)` для runtime
   wheelhouse в `sdk.py:891-911`;
2. позднее снова вызывает тот же forced build для `sdk/wheels` в
   `sdk.py:1606-1645,1716-1765,1885-1905`.

Это два PEP 517 build всех 53 local distributions в одном SDK run.
Runtime install и published wheelhouse должны потреблять один immutable artifact
set с общей build identity и hashes.

Трекинг: #846.

### 4.3. CI повторяет общий C++ и pip work

На отдельных fresh runners общий top-level CMake graph компилируется как минимум
в `build-sdk-cpp`, `run-tests-cpp` и `build-sdk-bindings`. Ccache логически
поддерживается, но setup action не устанавливает и не восстанавливает общий
cache.

`install-pip-packages.sh` вызывается три раза, а без `--target` запускает
отдельный `pip install` для каждого из 53 packages. Это до 159 pip процессов
после того, как bundled site-packages уже сформирован в `sdk-full`.

Раздельные configuration checks могут быть полезны, но повторная чистая
компиляция и повторная установка одного SDK не являются отдельными контрактами.
Следует переиспользовать build cache/artifacts и оставить source overlay
каноническим test-only механизмом.

### Что здесь не следует удалять

Не являются дублированием:

- exact runtime lock;
- offline wheelhouse;
- ABI identity и artifact manifests;
- 53 modular Python distributions как публичная library boundary;
- отдельные platform adapters для Linux, Windows, Android и Quest.

Проблема не в существовании этих контрактов, а в повторном получении одного
артефакта разными путями.

## 5. Двойные component/pass registries

### Наблюдение

Native runtime type registry уже хранит descriptor, owner, factory и facets.
Python binding публикует туда class, inspect fields и graph metadata:

- `termin-scene/cpp/bindings/component_registry_python.cpp:16-20,64-126`;
- `termin-render/src/tc_pass.c:27-32,212-243`;
- `termin-render/python/tc_pass_bindings.cpp:1061-1113`;
- `termin-render/python/termin/render_framework/python_pass.py:112-159,254-260`.

Параллельно существуют:

- `termin-scene/python/termin/scene/component_registry.py:14-55`;
- `termin-render/python/termin/render_framework/frame_pass_registry.py:10-51`.

Обе Python registry снова хранят `classes` и `owners`.
`DefaultResourceManager` создаёт их как собственные:

- `termin-default-assets/python/termin/default_assets/resource_manager.py:30-44`.

Editor и bootstrap публикуют классы в native registry, а затем отдельно в
manager. Module unload имеет два независимых cleanup participant:

- `termin-modules/python/termin_modules/module_context.py:217-229`;
- `termin-modules/python/termin_modules/module_context.py:274-320`.

Уже виден drift: `DefaultResourceManager.clear_runtime_state()` очищает
`classes`, но оставляет `owners`.

### Вердикт

Component/pass type metadata не принадлежит asset manager. Более того, второй
Python catalog не следует просто перенести в новый global owner.

Целевая модель:

1. runtime type descriptor является authoritative registration;
2. Python class/projection, graph/category и owner являются его facets;
3. editor запрашивает snapshot/query canonical registry;
4. module revoke удаляет один contribution;
5. `ComponentClassRegistry` и `FramePassRegistry` удаляются.

После этого `DefaultResourceManager` должен быть разобран по asset owners либо
остаться тонкой instance composition без process-global singleton и
cross-module teardown.

Трекинг: #631, #644.

### Завершение 2026-07-25

Карточка #644 выполнена:

- `ComponentClassRegistry` и `FramePassRegistry` удалены вместе с manager
  facade и вторым owner-cleanup participant;
- `DefaultResourceManager` больше не хранит и не очищает type metadata;
- player/editor bootstrap импортирует immutable provider specs и явно
  привязывает Python classes к уже зарегистрированным native descriptors;
- editor, player, runtime exporter и pass deserialization запрашивают классы
  непосредственно у canonical component/pass registries;
- shutdown освобождает Python class projections, а module revoke удаляет
  единственный owner contribution.

Оставшаяся декомпозиция asset-составляющих `DefaultResourceManager`
продолжает отслеживаться umbrella-карточкой #631.

## 6. Три value representation

### Наблюдение

В production одновременно используются:

1. `tc_value` — C tagged union и фактический ABI/storage;
2. `tc::trent`/`trent_view`/`trent_ref` — C++ RAII facade над `tc_value`;
3. `nos::trent` — отдельное C++ value tree с собственными parsers и memory
   semantics.

Rough current inventory показывает приблизительно:

- 1 093 production references к `tc_value`;
- 786 references к `nos::trent`;
- 112 references к `tc::trent`;
- более 100 production files, затрагивающих эти модели.

Core implementations, parsers и bridges занимают около 4 871 строки. На
границах встречается цепочка Python → `tc_value` → `nos::trent`, например в
`termin-scene/cpp/bindings/entity_bindings.cpp:70-72`.

### Вердикт

`tc_value` и `tc::trent` не являются двумя конкурирующими storage model:
первый нужен C ABI, второй должен быть безопасным C++ view/owner facade.
Удаляемой системой является `nos::trent` после переноса parser implementation,
а также локальные duplicate converters.

Целевой контракт:

- `tc_value` — единственное storage и C ABI representation;
- `tc::trent` — единственный публичный C++ facade;
- JSON/YAML parser возвращает `tc::trent`;
- Python binding работает с тем же деревом;
- ingress/egress conversion явный и fail-closed.

Трекинг: #86.

## 7. Cached framegraph и заново собранный execution plan

### Наблюдение

`tc_pipeline_get_frame_graph()` кэширует graph до dirty invalidation:

- `termin-render/src/tc_pipeline.c:818-833`.

Но каждый вызов
`RenderEngine::render_scene_pipeline_offscreen()` повторно:

- собирает и объединяет specs:
  `termin-render/src/render_engine.cpp:426-452`;
- перечисляет canonical resources и alias groups:
  `termin-render/src/render_engine.cpp:456-658`;
- строит texture/depth/view/composition maps:
  `termin-render/src/render_engine.cpp:703-812`;
- для каждого pass создаёт dependency vectors, несколько `unordered_map` и
  recursive resolvers:
  `termin-render/src/render_engine.cpp:1037-1110`;
- копирует `lights` в каждый `ExecuteContext`:
  `termin-render/include/termin/render/execute_context.hpp:57`.

Это не динамическая scene data, а преимущественно статическая metadata pipeline.
Она пересобирается, хотя revision pipeline не изменился.

Timing instrumentation также не полностью zero-overhead: часть
`steady_clock::now()` и local pass stats выполняется до проверки
`TERMIN_RENDER_ENGINE_TIMING`.

### Вердикт

Рядом с cached framegraph нужен immutable `PipelineExecutionPlan`:

- merged specs;
- canonical typed resource IDs и aliases;
- allocation/resource resolution program;
- готовые per-pass dependencies и bindings;
- явная revision/invalidation semantics.

Per-frame path должен выполнять только size-dependent `ensure`, подстановку
external handles и работу passes.

Трекинг: #554.

## 8. Logical frame и per-job backend frames

### Наблюдение

`OffscreenRenderPlanner` планирует dependency-ordered jobs:

- `termin-engine/src/render_frame_planner.cpp:209-273`.

`RenderingManager` выполняет каждый job отдельным вызовом RenderEngine:

- `termin-engine/src/rendering_manager.cpp:1006-1026`.

RenderEngine при отсутствии внешнего scope сам вызывает:

- `begin_frame`: `termin-render/src/render_engine.cpp:664-669`;
- `end_frame`: `termin-render/src/render_engine.cpp:1271-1274`.

`RenderContext2::end_frame()` делает submit:

- `termin-graphics/src/tgfx2/render_context.cpp:104-118`.

Следовательно, N pipeline/RT jobs одного logical frame дают N command lists и
N submits. Для одной сцены также повторяется обход light capabilities:

- manager call sites:
  `termin-engine/src/rendering_manager.cpp:1116-1128,1204-1235,1272-1302`;
- scene walk:
  `termin-engine/src/scene_light_collector.cpp:40-49`.

### Вердикт

Backend frame должен принадлежать `RenderingManager` и охватывать весь planner
execution для одного device/logical frame. Scene lights и другая immutable
frame-local collection должны кэшироваться по scene.

Особого внимания требуют debugger capture/readback и момент очистки transient
bindings, но текущий RenderEngine уже умеет работать внутри borrowed open frame.

Трекинг: #556; dirty target scheduling отдельно отслеживается в #562.

## 9. Четыре локальных generational pool рядом с `tc_pool`

### Наблюдение

Общий generation/state/free-list primitive существует:

- `termin-base/include/tcbase/tc_pool.h:24-71`;
- `termin-base/src/tc_pool.c:10-65,136-182`.

Тем не менее собственные variants реализованы в:

- display: `termin-display/src/tc_display.c:28-36,114-181`;
- viewport: `termin-display/src/tc_viewport.c:34-42,86-172`;
- render target: `termin-render/src/tc_render_target.c:48-54,140-223`;
- pipeline: `termin-render/src/tc_pipeline.c:19-29,142-241`.

Четыре owner files суммарно имеют около 3 021 строки. Не весь этот объём
дублируется: typed API, slot cleanup, pipeline-specific state и tests нужны.
Дублируются allocation, growth, free stack, generation checks и reuse lifecycle.

### Вердикт

Следует расширить `tc_pool` только необходимыми bounded-capacity,
allocator-hook и fault-injection возможностями, а затем мигрировать четыре
registry. Typed public handles и owner-specific cleanup остаются.

Трекинг: #847.

## 10. Generic framegraph resource map после перехода на typed resources

### Наблюдение

Generic virtual base:

- `termin-graphics/include/tgfx/frame_graph_resource.hpp:7-15`.

Repo-wide найден один production subclass:

- `ShadowMapArrayResource` в
  `termin-render/include/termin/lighting/shadow.hpp:28-37`.

`ResourceMap`/`FBOMap` сохраняются в
`termin-render/include/termin/render/frame_pass.hpp:44-45`, однако executor
кладёт реальный pointer только для shadow array. Color texture, depth texture,
FBO и unknown aliases представлены `nullptr`:

- `termin-render/src/render_engine.cpp:503-517,559,596,608,655`.

Позднее shadow resource снова извлекается через `dynamic_cast`, хотя
`ExecuteContext` уже имеет typed `ShadowArrayMap` и texture maps:

- `termin-render/include/termin/render/execute_context.hpp:27-50`;
- `termin-render/src/render_engine.cpp:1112-1128`.

Alias authority дополнительно распределена между framegraph, `FBOPool` и
debugger-only `PipelineRenderCache::texture_alias_to_canonical`.

### Вердикт

`FrameGraphResource` и null-filled `FBOMap` являются migration tail. Shadow
aliases следует сразу собирать в typed map, а canonical aliases хранить в
compiled execution plan.

Этот cleanup логично выполнить внутри #554, а не создавать четвёртую resource
abstraction.

## 11. Render-attachment lifecycle без потребителя

### Наблюдение

Core component vtable содержит engine-owned render lifecycle:

- `termin-scene/include/core/tc_component.h:30,65-68`.

Для Python он проходит через process-global wrapper и capsule fallback:

- `termin-scene/cpp/bindings/tc_component_python_bindings.cpp:20-31`;
- dynamic callbacks:
  `termin-scene/cpp/bindings/tc_component_python_bindings.cpp:206-237`;
- global setter:
  `termin-scene/cpp/bindings/tc_component_python_bindings.cpp:400-405`.

Repo-wide production search нашёл один C++ override:

- `termin-components/termin-components-render/src/mesh_renderer.cpp:706-709`.

Он игнорирует `RenderAttachmentContext` и только вызывает
`bind_mesh_component()`. Production override `on_render_detach` не найден.

При этом drawable, input, light и camera participation уже выражаются через
subsystem-owned capabilities/facets.

### Вердикт

Стоимость cross-module C/C++/Python bridge не подтверждена use case.
Предпочтительный результат — удалить `on_render_attach/on_render_detach` из core
vtable и перенести нужную регистрацию в render-owned participant lifecycle либо
существующую scene activation.

Сохранение допустимо только после явного указания внешнего consumer и контракта,
который нельзя выразить subsystem extension.

Трекинг: #798.

## 12. Native UI persistence опережает product requirement

### Наблюдение

`termin-gui-native` уже содержит:

- document serializer/restore:
  `termin-gui-native/src/tc_ui_serialization.c` — 486 строк;
- runtime widget registry:
  `termin-gui-native/src/tc_widget_registry.c` — 404 строки;
- public serialize/restore API:
  `termin-gui-native/include/termin/gui_native/tc_ui_serialization.h:11-19`.

При этом builtin registration охватывает только `TextInput` и `TextArea`:

- `termin-gui-native/src/builtin_widget_registration.cpp:96-98`.

Product call sites serialize/restore за пределами forwarding API, bindings,
README и tests не обнаружены. Одновременно публичный widget catalog содержит
десятки create paths, включая model/service-backed views, menus и dialogs. Полная
универсальная persistence потребует resolver context, two-phase restore,
callback/model policy и composite-child lifecycle.

### Вердикт

Это не доказанно лишний код, а опасная точка будущего роста. До появления
product consumer нельзя автоматически расширять serializer на все widgets.

Предпочтительны:

- lean registry с codec только для self-contained value widgets; или
- намеренно narrow persistence, расширяемая конкретными product vertical
  slices.

Full durable UI schema оправдана только отдельным продуктовым требованием.

Трекинг: #821.

## 13. Вторичные дублирования

### 13.1. Embedded Python bootstrap editor и launcher

Editor и launcher отдельно определяют SDK root, stdlib/site-packages, `PyConfig`
и environment:

- editor:
  `termin-app/cpp/app/main_minimal.cpp:49-103,171-281`;
- launcher:
  `termin-app/cpp/app/main_launcher.cpp:27-93,96-198`.

Реализации уже расходятся: launcher выбирает первый `python3.*`, editor строит
точный ABI path, включая `t` suffix. Общий `termin::python_host` bootstrap
позволит удалить ориентировочно 150-200 строк и убрать ABI drift.

### 13.2. Source player поддерживает silent compatibility runtime

Python source player синтезирует viewport/camera и использует editor-camera
state:

- `termin-player/termin/player/runtime.py:380-435,534-650`.

Packaged native host для отсутствующего viewport падает явно:

- `termin-player/src/player_runtime_host.cpp:1177-1180`.

Windowed и headless source paths также отдельно читают и нормализуют scene:

- `termin-player/termin/player/runtime.py:289-320`;
- `termin-player/termin/player/headless.py:168-212`.

Это не повод объединять source и packaged host: поверхности имеют разные
обязанности. Лишними являются silent fallback construction и два neutral scene
loader. Сохранённая runtime configuration должна быть обязательна, а legacy
conversion — явной командой.

### 13.3. Eager package facades тащат demo code в обычный import

`termin-app/termin/editor_native/__init__.py:3-169` eagerly импортирует почти все
панели. Поэтому import отдельного submodule из launcher сначала загружает весь
frontend package.

`termin-gui-native/python/termin/gui_native/__init__.py:328-341` всегда
импортирует showcase и большой `UiScript`; C++ showcase также входит в core
library через `termin-gui-native/CMakeLists.txt:46-50`.

Это небольшой объём по сравнению с параллельными frontends, но простой cleanup:
package `__init__` должен быть минимальным, а demo/showcase — example или
test-support target.

## Наблюдаемые последствия дублирования

Параллельные owners и ручная синхронизация уже привели к конкретным дефектам.
Они не являются самостоятельными аргументами удалить соответствующие системы,
но показывают, что стоимость дублирования не теоретическая.

### Capability detach повреждает scene index

`tc_component_detach_capability()` очищает `capability_prev/next` до scene
reindex:

- `termin-scene/src/tc_component_capability.c:138-160`.

Scene unlink нуждается в этих ссылках:

- `termin-scene/src/tc_scene.c:746-773,932-943`.

Для head список обрывается, для middle/tail остаются stale neighbor links.
Текущий test покрывает только component вне scene.

Трекинг: #842.

### Scene slot сохраняет state предыдущего поколения

Allocation/free вручную сбрасывают многие поля `tc_scene_slot`, но не `uuid`,
`layer_names` и `flag_names`:

- `termin-scene/src/tc_scene.c:81-106,236-280,295-340`.

Новая scene без явного UUID способна унаследовать metadata уничтоженной scene.
Тот же lifecycle хранит raw entity-pool pointer и при free восстанавливает
registry handle линейным поиском с fallback ownership.

Трекинг: #843.

### `pending_starts` копируется каждый editor frame

Незапущенный component добавляется в общий список:

- `termin-scene/src/tc_scene.c:507-529`.

Каждый `process_pending_start()` делает `malloc + memcpy`, но disabled и
runtime-only components оставляет в списке:

- `termin-scene/src/tc_scene.c:673-692`.

STOP scene обновляется каждый editor tick, поэтому очередь может копироваться
всю сессию без возможности запустить элементы.

Трекинг: #844.

### Initial `.meta` вызывает второй asset reload

Watcher добавляет resource file и sidecar как две candidates:

- `termin-assets/termin_assets/project_file_watcher.py:381-429`.

Основной preload уже читает `.meta`, но последующая candidate вызывает
`on_spec_changed()` и полный reload:

- `termin-assets/termin_assets/project_file_watcher.py:497-524`;
- `termin-assets/termin_assets/spec_file.py:15-29`.

Трекинг: #845.

## Что не следует схлопывать механически

### Graphics backends

OpenGL, Vulkan и D3D11 caches, command lists и resource lowering имеют реальные
backend-specific contracts. Общей должна быть lifecycle/invalidation policy, но
не implementation каждого backend.

### Три масштаба render planning

Это разные системы:

- `graph_compiler.cpp` компилирует authoring graph в template;
- `tc_frame_graph.c` планирует passes внутри runtime pipeline;
- `render_frame_planner.cpp` упорядочивает зависимости между targets/jobs.

Проблема находится не в их количестве, а в повторном построении неизменной
metadata и неправильной frame boundary.

### AssetStore, typed AssetRegistry и AssetCatalog

Они имеют разные роли:

- UUID ownership/canonical asset records;
- type/name index;
- external-only catalog.

Foliage действительно использует external catalog. Удалять следует parallel
caches и mixed owners, а не эти границы.

### `tc_value` и `tc::trent`

`tc_value` является C ABI/storage, `tc::trent` — C++ RAII facade над тем же
storage. Цель — удалить отдельное `nos::trent` tree, а не C representation.

### Modular packages и reproducible Python runtime

53 distributions и отдельные native packages поддерживают library subsets и
внешних consumers. Exact lock, wheelhouse и provenance нужны. Удаляется
повторная сборка/установка, а не воспроизводимость.

### Windowed и offscreen modes

Они обслуживают разные consumers. Лишним является общий owning
`ApplicationHost`, а не возможность headless composition.

### `EditorSession`

Staged teardown в
`termin-app/termin/editor_native/editor_session.py:22-175` является необходимым
owning lifecycle. Большой `run_editor.py` следует разделить на typed composers,
но не возвращать к неявному lifetime.

### Внешний consumer важнее repo-local call-site search

Отсутствие внутреннего call site не всегда означает, что package лишний.
Например, `termin-dispatch` используется внешним Diffusion Editor и потому не
включён в кандидаты на удаление. Для public API перед deletion требуется
проверить named external consumers, но абстрактная возможность будущего
consumer не должна бесконечно блокировать активную миграцию.

## Рекомендуемый порядок упрощения

### Этап 1. Удалить уже заменённые production paths

1. Завершить live gate и выполнить #437.
2. Удалить host-derived `termin-app` bundle по #633/#681.
3. Завершить consumers migration и удалить application-host API по #593/#760.

Это наиболее прямое сокращение: replacement уже существует, а работа в основном
состоит в закрытии compatibility surface.

### Этап 2. Устранить двойные источники истины

1. Удалить Python component/pass registries по #644.
2. Разобрать `DefaultResourceManager` по owners по #631.
3. Завершить value convergence по #86.
4. Принять remove/move решение по render-attachment callbacks в #798.

Для каждого шага должен остаться один изменяемый owner, а не новый facade,
переадресующий к двум реализациям.

### Этап 3. Устранить повторную steady-state работу

1. Скомпилировать render execution plan по #554.
2. Поднять frame ownership в `RenderingManager` по #556.
3. Перейти к dirty targets по #562.
4. Строить local wheels один раз по #846.
5. Переиспользовать CI artifacts/cache вместо повторной clean compilation.

### Этап 4. Консолидировать primitives

1. Мигрировать четыре generational registries на `tc_pool` по #847.
2. Удалить generic `FrameGraphResource`/`FBOMap` внутри #554.
3. Вынести общий embedded Python bootstrap.

### Этап 5. Не расширять speculative frameworks без решения

1. Выбрать narrow/lean/full UI persistence contract в #821.
2. Зафиксировать source/packaged player parity и удалить silent fallbacks.
3. Demo/showcase code держать вне core import/build graph.

## Правило завершения будущих миграций

Для предотвращения повторения проблемы каждой migration нужны:

1. Named canonical owner и replacement API.
2. Полный список production и external consumers.
3. Явный compatibility interval, а не бессрочный fallback.
4. Отдельная executable deletion card одновременно с landing replacement.
5. Default build, который не включает transitional path без активного
   consumer.
6. Acceptance, проверяющий отсутствие старых imports, exports, CMake targets,
   payload entries и docs.
7. Измеримый результат: удалённые owners/paths и отсутствие двойной записи, а
   не только появление нового facade.

Полезный организационный ограничитель — migration WIP limit: не начинать третье
поколение boundary, пока второе не стало canonical, а первое не удалено.

## Kanboard

Основной umbrella:

- #471 `[architecture] Track overengineering and architectural fragility`.

Уже существовавшие migration/cleanup cards:

- #437 — удалить editor/launcher tcgui routes;
- #593, #760 — отделить widget toolkit и удалить application host;
- #631, #644 — разобрать `DefaultResourceManager` и убрать component/pass
  registries;
- #633, #681 — удалить host-derived `termin-app` bundle;
- #86 — свести value model;
- #554, #556, #562 — execution plan, frame ownership и dirty targets;
- #798 — определить component core lifecycle и судьбу render attachment;
- #821 — выбрать UI persistence contract.

Созданы или уточнены в ходе этого аудита:

- #841 — восстановить source-size gate после повторного роста `sdk.py`;
- #842 — исправить capability detach из intrusive scene index;
- #843 — полностью сбрасывать `tc_scene_slot` при reuse;
- #844 — убрать per-frame копирование `pending_starts`;
- #845 — не reload-ить asset второй раз из-за initial `.meta`;
- #846 — собирать local wheels один раз;
- #847 — свести display/viewport/render-target/pipeline к `tc_pool`.

В #554, #556, #644 и #798 добавлены текущие evidence comments.

## Изменения относительно аудита 2026-07-15

Этот документ не повторяет уже устранённые проблемы:

- loose Python class-scanner loader удалён; `.pymodule` является canonical
  reload path;
- process-global EngineCore/SceneManager/RenderingManager locator API удалён;
- native editor уже имеет explicit `EditorSession` и staged teardown;
- часть parallel Python resource caches и cross-module reset logic удалена.

Поэтому старые выводы нельзя механически переносить в текущий backlog. Текущая
сводка концентрируется на параллельных системах, которые всё ещё присутствуют в
HEAD.

## Проверка и ограничения

Выполнено:

- current source/file-size inventory;
- month-over-month git diff inventory;
- exact clone scan через repository duplication check;
- repo-wide production call-site и override search;
- сопоставление с активными и закрытыми Kanboard cards;
- package manifest check;
- canonical repository-control check.

Результаты:

- package manifest: `OK`;
- repository-control check: исходный снимок падал на `sdk.py: 2328 lines`;
  после #841 gate восстановлен;
- worktree перед созданием этого документа был чист.

Полная сборка SDK и полный test suite не запускались: аудит не менял runtime
code. Оценки строк являются аналитическим снимком, а не постоянной policy
метрикой. Перед удалением public API необходимо повторно проверить external
consumers; это не должно превращаться в бессрочную поддержку неназванной
совместимости.
