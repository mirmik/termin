# Repository and SDK split: graphics platform and 3D engine

Date: 2026-08-07

Status: analysis and recommendations preserved; implementation not started.

## Decision

Разделение Termin на reusable graphics/application platform и зависящий от неё
3D engine является обоснованным целевым направлением. Текущая архитектура уже
содержит естественную границу: `TERMIN_SDK_PROFILE=graphics` строит `termin-base`,
graphics, window, visual scene, native GUI и plots без `termin-scene`,
`termin-render` и `termin-engine`.

Физический разрез git-репозитория не должен быть первым шагом. Сначала нужно
доказать границу через две независимые сборки и два install tree:

```text
termin-platform sources
        |
        v
termin-platform-sdk
        |
        +-----------------------> diffusion editor / other applications
        |
        v
termin-engine sources
        |
        v
termin-engine-pack
        |
        v
deterministic composition
        |
        v
termin-sdk-full
```

Таким образом, целевая модель — не две равноправные половины SDK, а базовый
platform SDK и engine extension pack. Полный SDK остаётся пользовательским
артефактом, но собирается как композиция этих слоёв, а не как третий независимый
набор исходников.

## Motivation

Reusable-часть нужна не только Termin Editor. GPU abstraction, windowing,
retained visual scene, widgets, plots и node graph могут использоваться в
отдельных приложениях, включая diffusion editor, без scene/ECS, physics,
3D runtime и editor-specific composition.

Физическая граница репозиториев полезна, если она обеспечивает:

- самостоятельную сборку и выпуск graphics/application platform;
- отсутствие случайных зависимостей reusable-кода на engine/editor;
- возможность использовать platform SDK в небольших приложениях;
- явный versioned contract между platform и engine;
- более понятный ownership ресурсов, Python packages и build tooling.

Разрез не должен приводить к двум копиям GPU API, GUI runtime, bundled Python
или shader toolchain.

## Existing evidence

### Graphics SDK profile

Корневой `CMakeLists.txt` уже объявляет `TERMIN_SDK_PROFILE` со значениями
`full` и `graphics`. Graphics profile включает:

- `termin-base`;
- `termin-dispatch`;
- `termin-image`;
- `termin-mesh`;
- `termin-inspect`;
- `termin-graphics`;
- optional `termin-window`;
- `termin-visual-scene`;
- `termin-gui-native`;
- `tcplot`;
- `tcplot-gui-native`;
- Python-only `termin-cli` composition.

Python payload closure отдельно описана в
`termin-build-tools/termin_build/sdk_profiles.py` и дополнительно содержит
build tools, nanobind support, assets, tween, shader runtime и pure-Python GUI.

Это означает, что предполагаемая граница уже исполняется хотя бы в одном
режиме root build. Физический split не требует сначала изобретать новый граф
модулей.

### Standalone CMake packages

Основные reusable-модули уже устанавливают CMake package configs. Например:

- `termin_graphicsConfig.cmake` находит `termin_base` и `termin_mesh`;
- `termin_visual_sceneConfig.cmake` находит base, inspect и graphics;
- `termin_gui_nativeConfig.cmake` находит base, graphics, visual scene и
  inspect, а window integration запрашивает отдельным component contract;
- `tcplotConfig.cmake` находит base, mesh, graphics и visual scene;
- `tcplot_gui_nativeConfig.cmake` находит GUI и tcplot.

Следовательно, engine можно перевести с `add_subdirectory()` reusable-исходников
на `find_package()` уже на текущей инфраструктуре.

### Dependency direction

`termin-engine` зависит от base, graphics, scene, render, display, input,
collision и modules. Graphics profile не включает scene/render/engine. На
верхнем уровне направление зависимости уже соответствует целевой модели:

```text
platform -> scene/render/components -> engine/runtime/editor
```

Обратная зависимость из platform в engine не должна появляться.

### Cross-boundary change rate

Грубая проверка последних 300 коммитов классифицировала изменения в reusable
graphics/UI домене и engine/editor домене. Из 186 коммитов, касавшихся хотя бы
одного из этих доменов:

- 57 касались только reusable-домена;
- 88 касались только engine-домена;
- 41 касался обеих сторон.

Около 22% domain-коммитов пересекали предполагаемую границу. Метрика не
различает обязательные API migrations и случайную связанность, но показывает,
что немедленный repository split создаст заметное число связанных PR и
несовместимых промежуточных состояний. Сначала нужен отлаженный cross-repository
build contract.

## Proposed repository ownership

Имена репозиториев условны. Название `termin-platform` точнее, чем
`termin-graphics`: нижний слой включает не только GPU API, но также windowing,
GUI, plots, common data types, Python runtime и tooling.

### Platform repository

Начальный состав platform repository должен повторять и расширять существующий
graphics SDK closure:

| Область | Модули и ответственность |
|---|---|
| Foundation | `termin-base`, `termin-dispatch`, common geometry/value/resource types |
| Data | `termin-image`, `termin-mesh`, reusable inspect contracts |
| GPU | `termin-graphics`, backend implementations, shader compiler/runtime |
| Host | `termin-window`, generic graphics/window sessions |
| UI | `termin-visual-scene`, `termin-gui`, `termin-gui-native` |
| Visualization | `tcplot`, `tcplot-gui-native` |
| Graph editing | `termin-nodegraph` |
| Generic Python/runtime support | nanobind SDK, bundled Python ownership, reusable build tools |
| Generic application support | assets, tween and other engine-neutral packages |

`termin-mesh` остаётся в platform не потому, что вся mesh domain относится к
GUI, а потому что `termin-graphics` публично зависит от canonical mesh data и
tcplot использует mesh для 3D visualization. Перенос mesh в engine создал бы
обратную зависимость platform на engine.

`termin-nodegraph` сейчас отсутствует в graphics profile, хотя его package
dependencies ограничены `termin-gui-native` и `termin-visual-scene`. Для
diffusion editor это часть reusable product closure и её следует добавить в
platform profile до разреза.

### Engine repository

Engine repository должен содержать:

- scene/ECS и prefab composition;
- materials и lighting domain;
- `termin-render` и concrete render passes;
- display/input routing, завязанный на engine composition;
- components;
- collision, physics, robotics, skeleton, animation, voxels, CSG, navmesh;
- `termin-engine`;
- framegraph remote target integration;
- bootstrap и runtime;
- player, editor, Android и OpenXR product hosts;
- engine-specific assets, shaders, importers and build/package logic.

`termin-render` на первом этапе остаётся в engine. Сейчас он владеет frame
graph, scene render mount data, engine views и render-state integration. Если
другому продукту понадобится generic frame graph, его нейтральную часть можно
позднее извлечь в отдельный platform module. Перенос всего render framework
авансом размоет границу.

## SDK artifact model

### Platform SDK

Platform build создаёт самостоятельный install tree:

```text
out/platform-sdk/
├── bin/
├── include/
├── lib/
│   ├── cmake/
│   └── python3.14t/site-packages/
├── share/termin/
├── wheels/
└── platform-sdk-manifest.json
```

Он содержит:

- headers и native libraries только platform-модулей;
- их CMake package configs;
- graphics backends и common native dependencies;
- bundled free-threaded Python runtime;
- platform wheels и exact runtime lock;
- platform-owned shader/resource packs;
- artifact hashes, target platform, enabled backends и Python ABI.

Diffusion editor и другие продукты должны иметь возможность использовать этот
артефакт без engine pack.

### Engine pack

Engine build получает platform SDK как read-only dependency и устанавливает
свой результат в отдельный prefix:

```text
out/engine-pack/
├── bin/
├── include/
├── lib/cmake/
├── share/termin/
├── wheels/
└── engine-pack-manifest.json
```

Engine pack не дублирует:

- bundled Python;
- base/graphics/UI libraries;
- platform headers;
- platform wheels;
- third-party GPU/window dependencies.

В ранней стадии активной разработки manifest должен требовать точный platform
build identity:

```json
{
  "kind": "termin-engine-pack",
  "engine_build_id": "...",
  "requires_platform_build_id": "...",
  "python_abi": "cp314t",
  "platform": "linux-x86_64"
}
```

Exact identity предпочтительнее преждевременного обещания стабильного ABI.
После стабилизации границы его можно заменить на ABI generation и допустимый
version range.

### Composed full SDK

Обычный Termin developer SDK создаётся отдельной deterministic composition
operation в новом пустом каталоге:

1. проверить platform manifest, hashes, target и Python ABI;
2. проверить требования engine pack;
3. скопировать platform artifacts;
4. добавить engine-owned artifacts;
5. отклонить неожиданные path collisions;
6. собрать объединённый exact wheel lock;
7. offline-установить wheels обоих слоёв в чистый `site-packages`;
8. записать итоговый artifact/runtime manifest;
9. выполнить relocation, import, player и editor smoke tests.

Композиция должна строить новый tree, а не мутировать platform SDK на месте.
Текущий bindings stage синхронизирует `bin`, `include`, `share` и `lib` через
`rsync --delete`; установка engine поверх platform prefix может удалить файлы,
которых нет в engine staging tree.

## Target build flow

Примерный пользовательский интерфейс после перехода:

```bash
SDK_PREFIX="$PWD/out/platform-sdk" \
BUILD_DIR="$PWD/build/platform" \
./build-sdk.sh --profile=platform

TERMIN_PLATFORM_SDK="$PWD/out/platform-sdk" \
SDK_PREFIX="$PWD/out/engine-pack" \
BUILD_DIR="$PWD/build/engine" \
./build-sdk.sh --profile=engine

./compose-sdk.sh \
    --platform out/platform-sdk \
    --engine out/engine-pack \
    --output out/full-sdk
```

Имена flags и scripts здесь иллюстративны. Важно разделение build directories,
install prefixes и ownership.

Engine root CMake должен прекратить добавлять reusable-модули через
`add_subdirectory()` и использовать только установленные packages:

```cmake
find_package(termin_base CONFIG REQUIRED)
find_package(termin_mesh CONFIG REQUIRED)
find_package(termin_graphics CONFIG REQUIRED)
find_package(termin_window CONFIG REQUIRED)
find_package(termin_visual_scene CONFIG REQUIRED)
find_package(termin_gui_native CONFIG REQUIRED)
```

Configure получает platform prefix через `CMAKE_PREFIX_PATH`. После физического
split исходников platform вообще не будет в checkout engine repository.

## Python packaging

Bundled Python runtime должен принадлежать platform SDK. Engine pack поставляет
только engine wheels и lock metadata.

При композиции нельзя копировать два готовых `site-packages` друг поверх друга.
Нужно offline-установить объединённый exact набор wheels в новое окружение.
Иначе остаются stale modules, неверные `dist-info/RECORD`, неоднозначный
ownership и непроверяемый provenance.

Большинство пакетов используют общий `termin.*` namespace. Корневой
`termin/__init__.py` сейчас поставляет `termin-app`, использует `extend_path` и
одновременно устанавливает editor-specific native preload hook. До split
желательно отделить эти ответственности:

- root namespace bootstrap не должен знать про editor native module;
- platform native dependency loading должен принадлежать platform runtime;
- editor-specific hooks должны устанавливаться editor package/application.

Ни один wheel из разных репозиториев не должен молча владеть одним и тем же
файлом namespace package.

## Shader and resource ownership

Текущее размещение built-in shaders является реальным препятствием чистому
split. `termin-graphics/resources/builtin_shaders` одновременно содержит:

- generic canvas, text, line и presentation shaders;
- tcplot shaders;
- lighting и shadow contracts;
- engine render passes и postprocessing;
- navmesh, voxel, foliage и picking shaders.

`termin-graphics/CMakeLists.txt` glob-ит и устанавливает весь каталог. В
результате platform module физически владеет engine-specific ресурсами, хотя не
зависит от engine code.

Целевая раскладка должна быть package-owned:

```text
share/termin/shaders/
├── platform/
│   ├── catalog.json
│   └── ...
├── tcplot/
│   ├── catalog.json
│   └── ...
└── engine/
    ├── catalog.json
    └── ...
```

Graphics runtime владеет загрузкой и компиляцией catalog format, но не списком
engine shaders. Он должен уметь регистрировать несколько catalog roots.
Аналогичное ownership rule следует применять к fonts, icons, templates и
другим общим install directories.

Названия reusable shaders вида `termin-engine-text2d` или
`termin-engine-tcplot-2d-line` следует заменить package-neutral identities.
Это не текущая code dependency, но semantic ownership после split будет
ошибочным.

## Build tooling ownership

Описание graphics profile сейчас распределено между:

- root `CMakeLists.txt`;
- `termin-build-tools/termin_build/sdk_profiles.py`;
- Linux shell scripts;
- PowerShell scripts;
- SDK doctor и verification logic.

Перед split нужен один декларативный source of truth для product closure и
artifacts. Platform repository может владеть generic SDK tooling и схемами
manifest, но engine-specific profile, doctor checks и application payloads
должны оставаться в engine repository.

Engine build tooling может зависеть от versioned `termin-build-tools` package,
но не должно импортировать Python modules через относительный путь в соседний
checkout.

## CI contract

До физического repository split обязательны следующие независимые jobs.

### Platform job

- checkout только текущего repository, но build graph ограничен platform
  closure;
- build and install platform SDK;
- platform native/Python tests;
- installed `find_package()` consumer smoke;
- relocated platform SDK smoke;
- verification отсутствия engine/editor artifacts.

### Engine-against-installed-platform job

- получить уже собранный platform SDK artifact;
- не добавлять platform source directories в CMake graph;
- build engine pack только через installed configs/headers/libraries;
- выполнить engine tests;
- проверить absence of undeclared source-relative includes/resources;
- проверить exact platform build identity.

### Composition job

- собрать новый full SDK из двух immutable artifacts;
- проверить file collision policy;
- установить объединённый wheelhouse offline;
- выполнить полную SDK verification;
- запустить editor/player smoke.

После физического split engine CI должен иметь две линии:

- blocking build с закреплённым platform release/build ID;
- early-warning build с текущей platform main/dev branch.

Вторая линия заранее показывает будущую несовместимость, не ломая
воспроизводимую основную сборку engine.

## Migration sequence

### Phase 1: make the logical product boundary truthful

1. Переименовать или переопределить `graphics` profile как platform product.
2. Сформировать канонический declarative module/package closure.
3. Добавить `termin-nodegraph` и другие доказанно reusable packages.
4. Добавить CI, запрещающий engine/editor artifacts в platform SDK.
5. Зафиксировать dependency direction и resource ownership rules.

### Phase 2: clean cross-boundary resources and runtime hooks

1. Разделить shader catalogs на platform/tcplot/engine packs.
2. Убрать engine-prefixed identities из reusable shaders.
3. Разделить generic Python namespace/runtime bootstrap и editor hooks.
4. Устранить source-relative resource lookups между будущими repositories.
5. Проверить ownership shared third-party dependencies.

### Phase 3: build the engine as an external consumer

1. Добавить отдельный engine build profile/root.
2. Заменить `add_subdirectory()` platform modules на `find_package()`.
3. Собирать engine в отдельный build directory и install prefix.
4. Запретить fallback на исходники platform из monorepo.
5. Сделать installed-platform build центральным test gate.

### Phase 4: deterministic SDK composition

1. Ввести platform и engine manifests.
2. Реализовать collision-aware compositor.
3. Объединять wheels через fresh offline install.
4. Перевести `full` SDK build на `platform -> engine -> compose`.
5. Сравнить функциональную полноту composed и старого monolithic SDK.
6. Удалить monolithic path после достижения parity.

### Phase 5: physical repository split

1. Разделить git history с сохранением истории выбранных путей.
2. Выпустить первый immutable platform SDK artifact.
3. Закрепить его exact build ID в engine repository.
4. Перенести CI на artifact-based dependency.
5. Удалить временные monorepo compatibility paths.

## Readiness criteria for repository split

Физический split готов, когда одновременно выполнены условия:

- platform SDK собирается, тестируется и используется самостоятельно;
- engine успешно собирается из checkout без platform sources;
- engine использует только installed public headers, configs, libraries и
  resources;
- platform не содержит engine/editor code или engine-owned shaders;
- full SDK детерминированно композируется из двух immutable artifacts;
- Python runtime и wheel provenance проходят полную проверку;
- Linux и Windows split-build являются штатными CI paths;
- Android/OpenXR build получает platform artifacts через тот же versioned
  contract или через явно документированный cross-build equivalent;
- смена platform build ID приводит к понятной диагностике, а не к случайной
  link/runtime ошибке;
- документация и module map отражают новое ownership.

## Risks and mitigations

### Paired changes across repositories

Graphics API migration может требовать одновременного изменения engine.
Снижать риск следует через additive API evolution, early-warning CI и
последовательность `platform release -> engine update`, а не через плавающую
зависимость на соседнюю ветку.

### ABI instability

На текущей стадии точный build ID безопаснее неформального ABI compatibility.
Раздельный semver следует вводить только после появления проверяемой ABI/API
policy.

### Resource collisions

Общие каталоги `share/termin` допускают независимые package-owned подкаталоги,
но compositor должен запрещать два разных файла по одному пути. Исключения
должны быть явными и проверяемыми, а не основанными на порядке копирования.

### Duplicate build tooling

Копирование build scripts в оба repository быстро приведёт к расхождению.
Generic orchestration и manifest schemas должны поставляться как versioned
tooling package; repository-specific configuration остаётся рядом с продуктом.

### Developer ergonomics

Раздельные repositories не должны заставлять разработчика вручную согласовывать
десятки prefixes. Engine repository должен уметь получить или собрать
закреплённый platform SDK одной штатной командой. При этом локальный override
на platform checkout допустим как явный development mode, но не как release
fallback.

## Open questions

- Окончательное имя нижнего продукта: `termin-platform`,
  `termin-graphics-sdk` или другое.
- Должны ли `termin-assets` и generic module/plugin runtime полностью перейти
  в platform или часть их contracts пока остаётся engine-specific.
- Нужен ли отдельный generic framegraph module platform-продуктам, либо
  `termin-render` целиком остаётся engine concern.
- Какой build identity используется до появления стабильного ABI: git commit,
  content hash или release artifact ID.
- Как разделить generic SDK doctor от engine product checks без дублирования
  tooling.
- Как platform artifact поставляется cross-compiled Android/OpenXR build:
  готовым target SDK или воспроизводимой dependency build stage.

Эти вопросы не блокируют логическое разделение build profiles. Они должны быть
решены до удаления monolithic build и физического split repositories.
