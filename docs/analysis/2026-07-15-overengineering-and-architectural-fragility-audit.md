# Аудит оверинжиниринга и архитектурной хрупкости Termin

Дата: 2026-07-15.

Статус: статический read-only аудит. Код во время анализа не изменялся.

## Резюме

Оверинжиниринг в текущем репозитории носит системный характер, но его основной
источник — не само количество классов, C ABI или размер кодовой базы. Проект
одновременно поддерживает несколько поколений архитектуры:

- multi-runtime API поверх process-global state;
- generation handles вместе с долгоживущими raw pointers;
- старый и новый ownership/tracking одной сущности;
- loose Python reload и полноценные `.pymodule` modules;
- собственный build/test control plane поверх CMake, CTest, pytest и pip.

Сложность новой архитектуры уже оплачена, но её гарантии ещё не получены.
Наиболее опасны места, где система выглядит многосессионной или транзакционной,
но фактически остаётся глобальной и пошагово мутирующей.

Главный системный диагноз: репозиторию мешает не недостаток архитектуры, а
избыточное количество промежуточной архитектуры. Несколько моделей identity,
ownership, registration и lifecycle продолжают работать параллельно вместо
того, чтобы миграция заканчивалась удалением старого пути.

## Область и методика

Проверялись:

- C/C++ runtime, graphics, render, scene и registration layers;
- Python editor, project/scene lifecycle, assets и module hot reload;
- SDK packaging, artifact discovery, runtime dependency lock;
- repository control plane, test inventory и CI orchestration;
- текущие активные карточки Kanboard, чтобы отделить новые проблемы от уже
  зафиксированных миграций.

Выводы ниже основаны на конкретных state/lifetime paths. Большой файл или
абстракция сами по себе не считались проблемой без наблюдаемого failure mode
или дублирования контракта.

## Основные находки

### 1. Critical: GPU handles не содержат identity устройства

#### Наблюдение

Все `tgfx2` handles содержат только `uint32_t id`:

- `termin-graphics/include/tgfx2/handles.hpp:7`;
- OpenGL allocation начинается с `1` в
  `termin-graphics/include/tgfx2/opengl/opengl_render_device.hpp:81`;
- Vulkan allocation начинается с `1` в
  `termin-graphics/include/tgfx2/vulkan/vulkan_render_device.hpp:118`;
- D3D11 allocation начинается с `1` в
  `termin-graphics/include/tgfx2/d3d11/d3d11_render_device.hpp:63`.

C interop при этом использует один process-global `g_tgfx2_device`:

- `termin-graphics/src/tgfx2_interop.cpp:23`;
- `termin-graphics/src/tgfx2_interop.cpp:360`.

`RenderRuntime` перезаписывает этот указатель и при destruction только обнуляет
его, не восстанавливая предыдущий runtime:

- `termin-graphics/src/tgfx2/render_runtime.cpp:83`.

В коде уже документированы cross-pool grey viewport/crash:

- `termin-render/src/render_engine.cpp:272`;
- `termin-graphics/python/bindings/tgfx2_bindings.cpp:629`.

#### Риск

Devices A и B независимо создают `TextureHandle{1}`. Передача handle A в B
обращается к чужому slot или уничтожает чужой ресурс. Временный runtime B может
перезаписать global device, а при destruction оставить живой runtime A без
interop device. Сырой global pointer также допускает use-after-free.

#### Более простое направление

Нужно честно выбрать один из двух контрактов:

1. Строго один device/runtime с fail-fast при создании второго.
2. Настоящий multi-runtime: `device/domain id + slot + generation` в handle и
   явный `DeviceContext`/opaque runtime handle в C ABI.

Нынешняя модель сложнее обоих вариантов и не гарантирует ни один.

#### Трекинг

- #472 `[graphics/arch] Give tgfx2 handles a runtime domain`;
- связанная capability-декомпозиция: #95.

### 2. High: у runtime/project/editor нет единственного владельца lifecycle

#### Наблюдение

`EngineCore` уже владеет `SceneManager` и `RenderingManager` как полями:

- `termin-engine/include/termin/engine/engine_core.hpp:20`.

Но `EngineCore`, `SceneManager` и `RenderingManager` дополнительно назначают
себя process-global singleton. `RenderingManager` безусловно перезаписывает
текущий singleton, а destructor лишь обнуляет его:

- `termin-engine/src/rendering_manager.cpp:64`;
- `termin-engine/src/scene_manager.cpp:16`;
- `termin-engine/src/engine_core.cpp:15`.

Project activation публикует новый context до завершения fallible sync и module
load:

- `termin-app/termin/editor_core/project_session_controller.py:84`;
- `termin-app/termin/editor_core/project_session_controller.py:117`.

Reused watcher меняет root, но не очищает tracked files, processor preload
results и asset catalog:

- `termin-assets/termin_assets/project_file_watcher.py:334`.

Native editor composition root разросся до одного `init_editor_native()` от
`termin-app/termin/editor_native/run_editor.py:185` практически до конца файла.
Он экспортирует большой service bag в console, удерживает объекты dummy tuple в
`run_editor.py:1670` и вручную закрывает десятки сервисов с
`run_editor.py:1728`.

#### Риск

Временный manager B перезаписывает A, а при destruction оставляет `nullptr`
вместо восстановления A. Project switch A → B сохраняет assets, module paths,
registrations или shader roots проекта A и способен позднее unregister-нуть
одноимённый объект проекта B. Ошибка посередине initialization публикует
смешанный old/new state.

#### Более простое направление

Нужен небольшой owning `RuntimeDomain`/`ProjectSession`, который явно владеет
manager, watcher, module runtime, asset registry, artifact store и settings.
Session сначала полностью строится в staging state, затем одним commit заменяет
предыдущую и целиком закрывается.

Это не должен быть новый service locator. Достаточно обычного агрегата с явным
construction/destruction order и зависимостями по ссылкам. Если продукт
поддерживает только один runtime на процесс, второй construction должен
fail-fast вместо частичной multi-instance семантики.

#### Трекинг

- #473 `[runtime/arch] Establish an explicit RuntimeDomain lifecycle`;
- #391 `[editor/project] Make project activation transactional`;
- #233 `[render/arch] Split RenderingManager responsibilities`.

### 3. High: loose Python hot reload пытается реализовать unload CPython

#### Наблюдение

Scanner помещает новый module в `sys.modules` до `compile/exec`:

- `termin-scene/python/termin/scene/class_scanner.py:133`.

Определение Python component уже меняет native component/inspect registries:

- `termin-scene/python/termin/scene/python_component.py:247`.

После этого scanner ловит любое исключение и возвращает `[]`, а processor
считает операцию успешной и очищает dirty state:

- `termin-scene/python/termin/scene/class_scanner.py:335`;
- `termin-app/termin/editor_core/file_processors/component_processor.py:134`.

Живые instances мигрируются best-effort через `gc.get_referrers` и замену
`obj.__class__`:

- `termin-scene/python/termin/scene/class_scanner.py:241`.

Параллельно `PythonModuleBackend` вручную владеет global import state. Он
добавляет paths с ownership только внутри одного handle, а unload удаляет все
совпадающие `sys.path` entries:

- `termin-modules/src/module_python_backend.cpp:44`;
- `termin-modules/src/module_python_backend.cpp:84`.

`collect_imported_module_subtree()` захватывает всё package subtree, включая
pre-existing imports, а unload удаляет их без identity check:

- `termin-modules/src/module_python_backend.cpp:139`;
- `termin-modules/src/module_python_backend.cpp:725`.

#### Риск

- Syntax error заменяет старый module пустым объектом, но Play gate проходит.
- Exception после объявления класса оставляет частичную native registration.
- Удалённый класс остаётся в registries.
- Unload одного module удаляет shared paths или package другого module.
- Старые и новые instances одного класса получают split identity.

#### Более простое направление

Наиболее простая надёжная стратегия — удалить loose-loader и оставить
`.pymodule` с явным lifecycle. Если in-process reload необходим, compile должен
происходить до publication, registrations — в source-owner transaction, а
module/path ownership — отслеживаться runtime-wide с identity/refcount и полным
rollback. Ещё более надёжная граница — отдельный interpreter/process.

#### Трекинг

- #129 `[arch] Изолировать hot-reload компонентов`;
- #474 `[modules/python] Make import-state ownership unload-safe`.

### 4. High: type registry защищается от собственной топологии

#### Наблюдение

Composition root уже явно регистрирует packages в порядке зависимостей:

- `termin-bootstrap/src/bootstrap_core.cpp:216`.

Но package bootstrap повторно регистрирует зависимости. Например, render
снова вызывает mesh и skeleton registration:

- `termin-components/termin-components-render/src/components_bootstrap.cpp:20`.

Collision, navmesh и animation bootstrap также повторяют dependency
registrations. Некоторые конкретные types повторно вызывают `register_type`
родителя.

Сам registry содержит ambient global `current_owner`, generations, facets,
tombstones, intrusive instance lists и `adopt unowned shell`:

- `termin-inspect/src/tc_runtime_type_registry.c:17`;
- `termin-inspect/src/tc_runtime_type_registry.c:206`;
- `termin-inspect/include/tc_inspect_cpp.hpp:201`.

Особенно опасен `ensure_inspect_facet`: при ошибке он возвращает общий mutable
static fallback, который caller продолжает изменять:

- `termin-inspect/include/tc_inspect_cpp.hpp:306`.

#### Риск

Регистрация становится зависимой от неявного ambient owner и порядка повторных
idempotent writes. Ошибка установки facet может быть залогирована lower layer,
но caller продолжит работу с shared fallback и создаст скрытое повреждение
registration state. Clean bootstrap уже выдаёт duplicate/unowned diagnostics.

#### Более простое направление

Каждый package bootstrap регистрирует только собственные types. Composition
root вызывает packages ровно один раз в топологическом порядке. Полный
immutable `TypeDescriptor` с explicit owner, parent и facets сначала
валидируется, затем устанавливается одной операцией. Shared fallback и partial
shell adoption удаляются.

#### Трекинг

- #475 `[inspect/arch] Make runtime type registration atomic`;
- #429 `[bootstrap] Eliminate duplicate builtin registrations`.

### 5. High: fallible transitions мутируют active state до валидации

#### Наблюдение

Scene loading закрывает и отсоединяет текущую scene до чтения JSON, repair и
`load_from_data()` новой:

- `termin-app/termin/editor_core/scene_file_controller.py:176`;
- `termin-app/termin/editor_core/scene_file_controller.py:189`.

Play выставляет playing state до завершения detach/attach и игнорирует `bool`
результаты connector operations:

- `termin-app/termin/editor_core/game_mode_model.py:119`.

Stop закрывает game scene и сбрасывает flag до успешного восстановления
editor/render attachment:

- `termin-app/termin/editor_core/game_mode_model.py:156`.

Статус 2026-07-17: shader artifact root вынесен в runtime-scoped
`ShaderArtifactResolver`. Runtime package loader возвращает конфигурацию в
staging result, а host применяет её к конкретному `RenderEngine` только после
успешной загрузки. Указанный ниже process-global дефект устранён; частичная
мутация global resource registries остаётся отдельной проблемой package
transaction:

- `termin-runtime/src/runtime_package.cpp:996`;
- `termin-runtime/src/runtime_package.cpp:1015`.

#### Риск

Malformed scene безвозвратно уничтожает текущую in-memory scene. Ошибка render
attach оставляет editor, renderer и mode flag в разных состояниях. Ошибка
package B меняет shader root работающего package A и может частично мутировать
совпавшие global resources.

#### Более простое направление

Здесь не нужен универсальный transaction framework. Достаточно трёх локальных
протоколов одинаковой формы:

1. `prepare` создаёт staging object без process-wide mutation;
2. `validate` полностью проверяет результат;
3. `commit` одной операцией заменяет active state;
4. failure уничтожает только staging state.

#### Трекинг

- #476 `[editor/scene] Stage scene load before replacing active scene`;
- #477 `[editor/play] Make Play and Stop transitions transactional`;
- project-level transition: #391;
- package/session ownership: #473.

### 6. High: одна сущность имеет несколько источников истины

#### Asset identity

`AssetRegistry` индексирует object по name и UUID, но same-name replacement не
удаляет UUID index старого object:

- `termin-assets/termin_assets/asset_registry.py:105`.

Player делает split identity напрямую: `register_material()` создаёт и
регистрирует один `MaterialAsset`, после чего `_assets_by_uuid` получает другой
object:

- `termin-player/termin/player/runtime_package_loader.py:344`.

Lookup по name и UUID начинает возвращать разные assets; unregister первого не
удаляет второй из UUID map из-за identity check.

#### Render-target component identity

Render target хранит одновременно stable entity handle и borrowed
`tc_component*`, но getter возвращает pointer без generation validation:

- `termin-render/src/tc_render_target.c:15`;
- `termin-render/src/tc_render_target.c:689`.

Render path передаёт pointer в capability lookup:

- `termin-engine/src/render_target_context_builder.cpp:237`.

Native `RenderingManager` связывает target с camera, не поддерживая reverse
viewport list, на которую рассчитывает `CameraComponent` teardown:

- `termin-engine/src/rendering_manager.cpp:535`;
- `termin-components/termin-components-render/src/camera_component.cpp:199`.

#### Риск

Asset lookup возвращает разные logical objects в зависимости от index. Delete
или hot reload камеры при живом target оставляет dangling component pointer и
может привести к use-after-free на следующем frame.

#### Более простое направление

У каждой сущности должна быть одна canonical identity. Secondary indexes
обновляются атомарно только через один owner API. Runtime references хранят
generation-validated handles и разрешаются через owner registry на use; raw
pointers не переживают frame/transition.

#### Трекинг

- #478 `[assets] Enforce canonical name and UUID identity`;
- #479 `[render] Resolve render-target components through stable handles`.

### 7. High: ownership migrations оставлены работающими параллельно

#### Наблюдение

`tc_component` одновременно содержит:

- `ref_vtable` с retain/release/drop;
- `factory_retained`;
- старые intrusive `type_prev/type_next` и `tc_type_entry/type_version`;
- новый `runtime_type_link`;
- старый `registry_node` с TODO удалить его после retirement старого tracking.

См. `termin-scene/include/core/tc_component.h:30` и
`termin-scene/include/core/tc_component.h:81`.

При этом entity уже описан как единственный владелец, а `tc_pass` и widgets
частично или полностью перешли на single-owner contract.

Pipeline pool демонстрирует практическое расхождение teardown. Обычный
`tc_pipeline_pool_free` вызывает `render_cache_destructor`:

- `termin-render/src/tc_pipeline.c:202`.

`tc_pipeline_pool_shutdown` проходит отдельным путём и destructor не вызывает:

- `termin-render/src/tc_pipeline.c:101`.

Cache создаётся через `new PipelineRenderCache` с delete callback:

- `termin-render/src/render_pipeline.cpp:69`.

#### Риск

Refcount imbalance, cycles, двойные instance lists и stale hot-reload links
остаются возможными до завершения миграции. Global shutdown теряет C++ render
cache и связанные GPU resources. Две процедуры destruction будут продолжать
расходиться.

#### Более простое направление

Завершить single-owner migration одним непрерывным проходом и физически удалить
старые trackers/refcount API. Container removal/destruction вызывает один
deleter ровно один раз; external references — borrowed или generation handles.
Для pipeline нужен один `destroy_pipeline_slot`, используемый free-one и
clear-all, плюс безопасный двухфазный grow.

#### Трекинг

- #223 `[arch] Replace tc_component/tc_pass refcount with single-owner lifetime`;
- #480 `[render] Unify pipeline slot destruction`.

### 8. High: packaging декларирует контракты, которые выполняются fallback-ами

#### PEP 517 contract

Многие package `pyproject.toml` объявляют только setuptools/wheel, но
`setup.py` импортирует `termin_build`. Например:

- `termin-base/pyproject.toml:1`;
- `termin-base/setup.py:3`.

SDK orchestrator обходит декларацию, добавляя checkout `termin-build-tools` в
`PYTHONPATH` и принудительно используя `--no-build-isolation`:

- `termin-build-tools/termin_build/sdk.py:1293`.

Обычный `pip wheel ./termin-base` или `python -m build` в clean environment
получает ложный PEP 517 contract.

#### Runtime dependency closure

SDK устанавливает local wheels и runtime lock с `--no-deps`:

- `termin-build-tools/termin_build/sdk.py:802`.

Verification проверяет наличие, версии и RECORD, но не сопоставляет
`Requires-Dist` с runtime lock:

- `termin-build-tools/termin_build/sdk_runtime_metadata.py:211`;
- `termin-build-tools/termin_build/sdk_verification.py:163`.

`termin-qopt`/`termin-pga` требуют SciPy, а `termin-build-tools` требует
setuptools; этих dependencies нет в runtime lock. Test-only requirements
добавляют их и маскируют дефект.

#### Artifact provenance

`termin-artifacts.json` записывает абсолютные `build_path` и `install_path`:

- `termin-build-tools/termin_build/sdk.py:534`.

Consumer при недоступном build path ищет binary по checkout build roots, SDK и
`/opt`:

- `termin-build-tools/termin_build/cmake_ext.py:161`;
- `termin-build-tools/termin_build/cmake_ext.py:212`.

После relocation manifest протухает, а fallback может выбрать stale binary,
разрушив provenance, ради которого manifest существовал.

#### Более простое направление

- Выбрать честный contract: настоящий versioned build backend/requirement или
  один monorepo-only backend без псевдосамостоятельных package roots.
- После wheel build читать `METADATA/Requires-Dist` и fail-closed проверять
  external closure выбранного runtime profile.
- Поставляемый artifact manifest должен содержать только SDK-relative install
  path, artifact kind и content hash. При отсутствии или mismatch — ошибка без
  discovery fallback.

#### Трекинг

- #481 `[build/python] Make package build contracts self-contained`;
- #482 `[sdk/python] Validate runtime dependency closure`;
- #483 `[build] Make SDK artifact manifests relocatable and authoritative`;
- #116 `[sdk] Разделить standard и experimental Python packages`;
- связанные dependency-policy карточки: #225 и #226.

### 9. Medium: test control plane стал вторым тестовым фреймворком

#### Наблюдение

`repository_control.py` уже содержит discovery, validation, planning, pytest и
process executors, CTest/JUnit reconciliation и CLI. `build_plan` при этом
фильтрует только profile/platform и игнорирует suite `environment` и
`capabilities`:

- `termin-build-tools/termin_build/repository_control.py:877`.

`run_pytest_plan` запускает suites одним interpreter/overlay/environment:

- `termin-build-tools/termin_build/repository_control.py:990`.

CI передаёт JSON plan artifact, а consumer заново строит тот же локальный plan
и требует полного совпадения списка IDs:

- `.github/workflows/ci.yml:18`;
- `termin-build-tools/termin_build/repository_control.py:903`.

Artifact не может выбрать subset или shard и фактически проверяется против
самого себя. Windows C++ runner обходит часть Linux inventory/report path:

- `run-tests-cpp.ps1:177`;
- `run-tests-cpp.sh:203`.

#### Риск

Metadata создаёт ложное ощущение environment/capability isolation, CI платит за
upload/download plan без scheduling-выигрыша, а platform paths имеют разные
gates. Дальнейшее развитие control plane рискует продублировать возможности
pytest, CTest и CI scheduler.

#### Более простое направление

Сохранить полезное ядро:

- orphan Python/native test discovery;
- configured CTest inventory;
- fail-closed report gates;
- отдельный pytest process там, где он действительно изолирует nanobind
  shutdown/leaks.

Plan следует строить локально в job. `environment/capabilities` либо реально
исполняются разными executors, либо удаляются до появления такой потребности.
Linux и Windows должны использовать одинаковые inventory gates.

#### Трекинг

- #484 `[qa] Simplify test planning to enforced capabilities`;
- umbrella #263 `[repo/qa] Build manifest-driven repository control plane`.

## Дополнительные признаки незавершённых миграций

### Value model

В production одновременно видны `nos::trent`, C `tc_value` и новый C++ слой
`tc::trent`/`trent_view`/`trent_ref`:

- `termin-base/include/tcbase/tc_value.h:14`;
- `termin-base/include/tcbase/tc_trent.hpp:13`;
- `termin-base/include/tcbase/tc_value_trent.hpp:1`.

JSON/YAML facade всё ещё проходит через `nos::trent`, prefab APIs смешивают
`nos::trent`, `tc::trent` и `tc_value`. Это создаёт naming collision, лишние
tree copies и неочевидные numeric conversion boundaries.

Предпочтительное упрощение: один публичный RAII `Value`/canonical facade;
`tc_value` остаётся C ABI representation, а `nos::trent` — приватной parser
implementation на transport boundary. Трекинг: #86.

### Render surface migration

Core render-surface vtable смешивает OpenGL-specific FBO/context API с
backend-neutral texture и документирует legacy fallback:

- `termin-display/include/render/tc_render_surface.h:35`;
- `termin-display/include/render/tc_render_surface.h:74`.

Presenter fallback уже не реализует и завершает present с ошибкой:

- `termin-engine/src/display_presenter.cpp:43`.

Это следует завершить обязательным backend-neutral `PresentationTarget`, а
legacy OpenGL adapter вынести из core interface, либо действительно восстановить
заявленный fallback. Оставлять два расходящихся контракта нельзя.

### Параллельные editor frontends

Native и tcgui frontends продолжают дублировать крупные composition/lifecycle
участки. Это допустимая временная стоимость миграции, но только при наличии
конкретного parity gate и даты/условия удаления старого frontend. Без exit
criterion расхождение поведения будет расти.

## Что не следует упрощать механически

Не вся обнаруженная сложность лишняя:

- C ABI и compact handles оправданы для cross-DLL identity и hot paths; проблема
  только в отсутствии runtime domain/generation.
- Package-isolated pytest processes могут быть полезны для точной диагностики
  nanobind shutdown leaks.
- Orphan-test и configured-CTest inventory gates реально предотвращают
  false-green CI.
- Bundled/system codec branches оправданы portability; проблема начинается у
  feature flags с fail-open semantics.
- Dual frontend допустим как ограниченная миграция, но не как бессрочный режим.

Удаление этих частей целиком принесло бы регрессии. Упрощать нужно ownership,
ambient state и декоративные protocol layers вокруг полезного ядра.

## Общие причины сложности

1. **Не выбран честный multiplicity contract.** API допускает несколько
   runtime/device/session, а storage и registration остаются process-global.
2. **Identity дублируется.** Handle и pointer, name и UUID, wrapper и pool slot
   параллельно считаются источником истины.
3. **Миграции не заканчиваются удалением.** Новая модель добавляется рядом со
   старой, после чего обе синхронизируются indefinitely.
4. **Fallible work публикуется слишком рано.** Active state меняется до полной
   validation и не имеет единой commit point.
5. **Infrastructure metadata опережает executors.** Поля и artifacts существуют,
   но не влияют на выполнение и поэтому создают ложные гарантии.

## Рекомендуемый порядок упрощения

1. Зафиксировать single-runtime или настоящий multi-domain contract. Добавить
   fail-fast guards до больших миграций.
2. Исправить GPU handle domain identity и убрать dependency от active global
   device.
3. Ввести настоящие `RuntimeDomain`/`ProjectSession` boundaries и staged
   project/scene/package transitions.
4. Удалить loose Python reload либо изолировать его interpreter/process
   boundary.
5. Сделать type registration и asset identity атомарными.
6. Завершить component/pipeline ownership migration с физическим удалением
   старых trackers и duplicate destruction paths.
7. Сузить value/render-surface/frontend migrations до одной target model и
   явного exit criterion.
8. После стабилизации runtime invariants упростить packaging и test control
   plane, сохранив fail-closed inventory gates.

Не рекомендуется начинать с универсального service locator, transaction
framework или очередного registry facade. Это добавит ещё один слой. Нужны
небольшие domain owners, один canonical identity и локальные commit boundaries.

## Карточки Kanboard

Для аудита создана отдельная swimlane `Architecture` и umbrella #471
`[arch] Track overengineering and architectural fragility`.

Новые карточки:

| ID | Карточка | Размер |
| --- | --- | --- |
| #472 | `[graphics/arch] Give tgfx2 handles a runtime domain` | L |
| #473 | `[runtime/arch] Establish an explicit RuntimeDomain lifecycle` | XL |
| #474 | `[modules/python] Make import-state ownership unload-safe` | L |
| #475 | `[inspect/arch] Make runtime type registration atomic` | L |
| #476 | `[editor/scene] Stage scene load before replacing active scene` | M |
| #477 | `[editor/play] Make Play and Stop transitions transactional` | M |
| #478 | `[assets] Enforce canonical name and UUID identity` | M |
| #479 | `[render] Resolve render-target components through stable handles` | M |
| #480 | `[render] Unify pipeline slot destruction` | M |
| #481 | `[build/python] Make package build contracts self-contained` | L |
| #482 | `[sdk/python] Validate runtime dependency closure` | M |
| #483 | `[build] Make SDK artifact manifests relocatable and authoritative` | M |
| #484 | `[qa] Simplify test planning to enforced capabilities` | M |

В swimlane также перенесены существующие релевантные карточки без создания
дублей:

- #86 value model;
- #116 standard/experimental Python packages;
- #129 component hot reload;
- #223 single-owner component/pass lifetime;
- #233 RenderingManager responsibilities;
- #263 repository control plane;
- #391 transactional project activation;
- #429 duplicate builtin registrations.

## Ограничения проверки

Аудит был статическим и read-only. Полная SDK build/test matrix не запускалась,
поскольку код не изменялся, а локальный SDK предшествовал текущему HEAD.

Проверки

```text
PYTHONPATH=termin-build-tools python3 -m termin_build.repository_control --repo-root . check
PYTHONPATH=termin-build-tools python3 -m termin_build.package_manifest --repo-root . check
```

проходят. Поэтому findings не являются следствием базового manifest drift или
упавшего CI; это архитектурные state, identity и ownership paths, обнаруженные
непосредственно в исходниках.
