# Система сборки

## Обзор

Проект содержит множество C/C++ libraries и Python distributions. Каждый
package владеет своими targets и локальным `CMakeLists.txt`, но не объявляет
второй самостоятельный проект: SDK собирается единым корневым CMake-графом.
Корневые `core/`, `graphics/`,
`physics/`, `engine/`, `editor/` и `platform/` задают владение пакетами, а не
самостоятельные build roots.

Публичная точка входа — корневой `Taskfile.yml`: полная сборка выполняется
`task build`, Core SDK — `task build:core`, Graphics SDK —
`task build:graphics`. Профили выбирают замкнутое множество пакетов из одного
checkout. Установочные prefixes различаются намеренно:

| Профиль | Команда | Prefix |
|---|---|---|
| `core` | `task build:core` | `sdk-core/` |
| `graphics` | `task build:graphics` | `sdk-graphics/` |
| `full` | `task build` | `sdk/` |

Корневой Taskfile сохраняет единый публичный интерфейс, а определения операций
разнесены по тематическим файлам в `taskfiles/`. Имя файла определяет раздел в
каталоге. Команда `task` (или `task help`) показывает сгруппированный каталог
операций. Каталог можно отфильтровать, например `task help -- python` или
`task help -- quality`. Штатный плоский список по-прежнему доступен через
`task --list`, подробности конкретной операции — через
`task --summary <имя>`.

Отдельно от SDK существует первоначальная Linux-операция упаковки Python
Graphics product:

```bash
task package:graphics:python
```

По умолчанию операция последовательно строит матрицу CPython `cp314` и
free-threaded `cp314t`. Для быстрой целевой пересборки одного варианта можно
выбрать его явно:

```bash
task package:graphics:python -- --python-abi cp314
task package:graphics:python -- --python-abi cp314t
```

Она повторно использует declarative closure профиля `graphics` (исключая
build-only `termin-build-tools`) и единый
корневой CMake-граф, но собирает их в собственные
`build/products/graphics-python/<abi>/{native-prefix,cmake-build,...}`. У каждого
ABI также свои build environment и wheelhouse внешних runtime-зависимостей, так
что несовместимые binary wheels не смешиваются. Внутренние modular wheels
используются как проверяемый staging-граф, после чего их payload без внутренних
`.dist-info` объединяется в один `termin-graphics` wheel на ABI. Готовые два
wheel публикуются атомарно в `dist/graphics-python/`; product manifest описывает
оба ABI, их раздельные `native_build_id` и происхождение каждого wheel.
Внутренний ресурсный слой `termin-graphics-profile` единолично владеет общей
native closure (это не даёт разным extensions загрузить дублирующие C++ registries), font resources и
предварительно собранными Vulkan/OpenGL shader artifacts. Продукт всегда
включает `termin-window`, GUI window adapter и собранный из pinned submodule
SDL2; `--no-sdl` для этой операции является ошибкой. Headless остаётся режимом
исполнения той же поставки. `termin_shaderc`,
`slangc` и библиотеки Slang являются только build-time inputs и в runtime wheel
не входят. Эта команда создаёт локальный `linux_x86_64` product и предназначена
для быстрой разработки, а не для публикации в package index. Канонический
Python полного/editor SDK при этом остаётся free-threaded `cp314t`; dual-ABI
matrix относится только к standalone product.

Release-кандидат для PyPI собирается отдельным обязательным gate:

```bash
task package:graphics:python:manylinux
```

Команда требует Docker на Linux x86_64 и всегда строит полную матрицу `cp314` +
`cp314t`; focused ABI здесь запрещён, чтобы нельзя было случайно выпустить
неполный набор. Builder основан на digest-pinned официальном
`manylinux_2_28_x86_64`. Пути и версии обоих интерпретаторов, версия
`auditwheel`, исходник software Vulkan ICD и release license inventory
закреплены в `build-system/graphics-python-manylinux-lock.json`.

Для независимого headless gate builder по SHA-256 собирает Mesa lavapipe в
отдельном Docker stage. Этот драйвер проверяет настоящий Vulkan showcase без
GPU хоста и не входит в wheel payload. Pinned Slang archive получает локальную
build-only compatibility library для старого libstdc++ baseline; Slang также
не публикуется.

После сборки внутреннего raw-графа payload каждого ABI сворачивается в один
публичный wheel. Только эти два итоговых wheel проходят `auditwheel show` и
`auditwheel repair --plat manylinux_2_28_x86_64`; общая native closure остаётся
в `termin_graphics_profile/lib`, а внешние системные зависимости добавляются
один раз на ABI. Затем repaired wheel устанавливается без сети в чистый venv
каждого ABI и проходит `pip check`, проверку относительных RPATH, Vulkan
headless render и SDL-offscreen OpenGL frame.

Успешный набор атомарно появляется в `dist/graphics-python-manylinux/`. Его
`termin-graphics-python-product.json` фиксирует SHA-256 всех wheel’ов, теги ABI,
base/builder image identity, версии Python, audit provenance и SHA-256 всех
вложенных license files. Это готовый к загрузке набор артефактов; сама загрузка
в PyPI намеренно не является частью build task.

Единая публичная версия всех Termin distributions хранится в
`build-system/version.toml`. Первый выпуск использует `0.5.0`; локальные SDK
wheel’ы по-прежнему получают отдельный PEP 440 suffix `+sdk<native_build_id>`.
Graphics публикуется одним PyPI project `termin-graphics` и содержит всю
замкнутую внутреннюю dependency graph. Выпуск состоит ровно из двух файлов:
`cp314` и `cp314t`. Внутреннее имя distribution, владеющего import-пакетом
`termin.graphics`, — `termin-graphics-core`; оно, как и остальные модульные
distributions, не является частью публичной PyPI-поверхности.

Перед ручной публикацией кандидат проверяется без сетевых операций:

```bash
task publish:graphics:python
```

Команда принимает только manifest-declared wheel’ы из
`dist/graphics-python-manylinux/` и сверяет schema, глобальную версию, полный
единственный distribution, два ABI wheel, metadata, manylinux tags и SHA-256.
Старый 40-wheel, неполный, дополненный посторонним wheel’ом или изменённый после
сборки каталог отвергается. Для дополнительной проверки metadata через Twine используется
`task publish:graphics:python -- --check`.

Состояние частично опубликованного выпуска можно безопасно сверить с публичным
PyPI JSON API без загрузки:

```bash
task publish:graphics:python -- --remote-status
```

Удалённый файл считается уже опубликованным только при точном совпадении имени
и SHA-256 с manifest-кандидатом. Конфликт digest или посторонний файл той же
версии останавливает процедуру.

Фактическая загрузка требует одновременно явного флага и подтверждения версии:

```bash
task publish:graphics:python -- --upload --confirm-version 0.5.0
```

По умолчанию используется Twine repository `pypi`; другой именованный
repository задаётся `--repository`. Учётные данные берутся самим Twine из
окружения или пользовательского `.pypirc` и в репозитории не хранятся. Скрипт
не использует слепой `--skip-existing`: перед продолжением он читает удалённые
metadata и пропускает только совпавшие файлы. Оба pending wheel’а загружаются
одной группой единственного distribution.
HTTP 429 и подтверждённый частичный upload повторяются с экспоненциальной
паузой; перед каждой повторной попыткой удалённое состояние и hashes читаются
заново. Поэтому та же команда `--upload --confirm-version 0.5.0` является
штатной resume-командой после сетевого сбоя или rate limit. Параметры
`--upload-delay`, `--retry-base-delay` и `--max-retries` позволяют изменить
период ожидания. Для пользовательского Twine repository необходимо также
передать соответствующий `--repository-json-base-url`.

Внешний Core SDK и `--core-sdk` для обычной монорепозиторной сборки не
требуются.

Android и Web строятся тем же root orchestration через `task build:android` и
`task build:web`. Опции installed Core SDK остаются внутренней возможностью
platform-рецептов для проверки или будущей композиции артефактов, но не
являются входом штатного CI. `native_build_id` и platform manifest продолжают
фиксировать ABI, target system, architecture, Android API и toolchain.

Сборка через `task build --` проходит в четыре стадии:

Перед первой стадией оркестратор закреплённым build-Python устанавливает или
проверяет закреплённый `slangc` из `build-system/slang-toolchain-lock.json` в
`build/toolchains` и передаёт его стадиям через `TERMIN_SLANGC`. Поэтому чистая
сборка SDK не требует заранее собранного `sdk/bin/termin_python` или вручную
установленного Slang compiler. Повторная сборка использует проверенный локальный
toolchain; при первой установке требуется доступ к архиву из lock-файла.

1. **C/C++ библиотеки + Python bindings** — shared libraries, заголовки, CMake config, nanobind-модули и Python-исходники
2. **C# bindings** — на Windows включены по умолчанию, на Linux включаются флагом `--csharp` и требуют SWIG и `dotnet`; Linux-сборка содержит только `Termin.Native`, без WPF
3. **Bundled Python site-packages** — установка Python-пакетов в bundled runtime SDK
4. **SDK Python wheelhouse** — атомарная публикация в `<sdk-prefix>/wheels` того же
   проверенного набора wheels, из которого Stage 3 установила bundled runtime

Внутри root build зависимости между модулями выражены CMake targets. Внешние
consumers используют `find_package()` и передают выбранный `sdk/`, `sdk-core/`
или `sdk-graphics/` через `CMAKE_PREFIX_PATH`.

### Канонический Python toolchain

SDK не использует системный Python как целевой runtime. Host Python нужен
только для запуска `termin_build`; перед CMake-стадией оркестратор
материализует exact-pinned CPython 3.14t из
`build-system/python-toolchain-lock.json`:

- Linux x86_64 собирается из закреплённого source archive с проверкой SHA-256,
  `--disable-gil` и shared `libpython3.14t`;
- Windows x86_64 использует закреплённый официальный
  `python-freethreaded` NuGet development/runtime input;
- runtime кешируется в `build/python-toolchain/runtimes`, причём fingerprint
  включает artifact, configure profile и версию build recipe;
- disposable build frontend в `build/python-runtime/build-env` всегда создаётся
  именно от выбранного target runtime. Совпадения только `major.minor` или
  SOABI недостаточно: смена точного base interpreter пересоздаёт environment.

Перед использованием toolchain проверяются Python 3.14, `Py_GIL_DISABLED`,
free-threaded marker `t` в SOABI и изначально выключенный GIL. Проверка
опирается на кроссплатформенный SOABI, поскольку `sys.abiflags` отсутствует
в Windows CPython.
Root CMake build дополнительно требует ABI 3.14t и останавливается, если ему
передан обычный cp314 либо старый Python.

Установленный prefix содержит development artifacts того же ABI: заголовки в
`<sdk-prefix>/include/python3.14t`, а на Windows — точную import library
`<sdk-prefix>/lib/python314t.lib`. Поэтому standalone CMake-модули могут требовать
компоненты FindPython `Development`, `Development.Module` и
`Development.Embed`, не подмешивая host Python.

CPython 3.14t является единственным Python runtime contract проекта. CMake не
предоставляет переключатель на GIL-enabled профиль, все first-party Python
packages объявляют `Requires-Python >=3.14`, а standalone editor build получает
тот же exact-pinned build interpreter через `termin_build`. Системный Python
остаётся только bootstrap-интерпретатором для запуска оркестратора.
Граница между free-threaded interpreter и последовательным engine API
зафиксирована в
[Python Runtime and Threading Contract](architecture/2026-07-24-python-runtime-contract.md).

Toolchain можно подготовить отдельно:

```bash
PYTHONPATH=core/termin-build-tools \
  python3 -m termin_build.sdk --repo-root . prepare-python-toolchain
```

После первого заполнения кеша acquisition/build проверяется без сети:

```bash
TERMIN_PYTHON_TOOLCHAIN_OFFLINE=1 \
  PYTHONPATH=core/termin-build-tools \
  python3 -m termin_build.sdk --repo-root . prepare-python-toolchain
```

`TERMIN_PYTHON_TOOLCHAIN_BUILD_DIR` переносит generated cache в другой
каталог. Сетевой runtime lock/wheelhouse — отдельный слой и управляется
`TERMIN_PYTHON_RUNTIME_OFFLINE`; toolchain и runtime dependencies намеренно
не смешиваются.

Типичная сборка SDK:

```bash
task build -- --sdl
```

First-party wheels собираются ровно один раз за полный проход. Результат
снабжается manifest с `native_build_id`, Python ABI и SHA-256 каждого wheel,
устанавливается в bundled runtime, а затем без повторного PEP 517 build
публикуется в `<sdk-prefix>/wheels`. Финальная проверка отвергает отсутствующий,
устаревший, повреждённый или смешанный набор.

Чтобы дополнительно собрать cross-platform C# bindings на Linux:

```bash
task build -- --sdl --csharp
```

Для SDK, содержащего Core, графическое ядро, visual scene, native widgets,
portable GLB/skeleton/animation и 2D/3D charts без engine runtime, используется
профиль `graphics`. Backend-флаги
ортогональны профилю; Windows D3D11 остаётся доступен, когда SDL, Vulkan и
legacy OpenGL выключены:

```powershell
task build:graphics -- --no-sdl --no-vulkan --no-opengl
```

Профиль включает современный tgfx2 target `tgfx::termin_graphics2` и
scene-neutral package `termin-render-core`. Последний предоставляет C/C++
framegraph и render execution без Python distribution и без engine scene
adapter. Профиль исключает engine scene/components/render adapters, physics,
CSG, navmesh, audio, editor/player/launcher и их Python packages; portable
`termin-skeleton`, `termin-animation` и `termin-glb` в него входят. На
Windows оркестратор автоматически выбирает существующий C#
профиль `plot-d3d11`, который генерирует API только для
`tcplot`/`Termin.Wpf` и копирует требуемые D3D11 shader artifacts.

Standalone native stages принимают тот же профиль в форме
`--profile=graphics`:

```bash
task build:cpp -- --profile=graphics --no-sdl --no-vulkan --no-opengl
task build:bindings -- --profile=graphics --no-sdl --no-vulkan --no-opengl
```

`Termin.Wpf` собирается только Windows-скриптом и multitarget-ится под `netcoreapp3.1` и `net8.0-windows`. Управляемые сборки в SDK раскладываются по `sdk/csharp/lib/<tfm>/`; плоские `sdk/csharp/lib/*.dll` оставлены для старых потребителей и содержат `netcoreapp3.1`-вариант `Termin.Wpf`. Linux `build-sdk-csharp.sh` намеренно пакует только cross-platform `Termin.Native` и native runtime `.so`.

Только C/C++ стадия:

```bash
task build:cpp -- --sdl
```

Только Python/nanobind bindings:

```bash
task build:bindings -- --sdl
```

Прямой CMake-вариант:

```bash
cmake -S . -B build/Release \
  -DCMAKE_BUILD_TYPE=Release \
  -DTERMIN_BUILD_PYTHON=ON \
  -DTERMIN_ENABLE_VULKAN=ON \
  -DTERMIN_ENABLE_SDL=ON
cmake --build build/Release --parallel
cmake --install build/Release
```

### Ускорение C/C++ компиляции

Root CMake-граф поддерживает несколько ускорителей сборки:

- `ccache` включается автоматически, если бинарь найден в `PATH`. Отключение: `--no-ccache` или `-DTERMIN_USE_CCACHE=OFF`.
- Для новых build-dir shell-скрипты по умолчанию оставляют CMake default generator. `Ninja` включается явно через `--ninja`, `TERMIN_CMAKE_GENERATOR=Ninja` или `CMAKE_GENERATOR_NAME=Ninja`. Уже существующий build-dir не меняет генератор; для смены генератора нужен `--clean` или новый `BUILD_DIR`.
- `BUILD_JOBS=<N>` задаёт общий бюджет параллелизма для `cmake --build`.
  Для Visual Studio generator этот бюджет применяется и к независимым
  MSBuild-проектам, и к единицам трансляции внутри одного `vcxproj` через
  общий `MultiToolTask` scheduler. Это избегает как последовательной
  компиляции крупных targets, так и перемножения двух уровней параллелизма.
- `--no-parallel` принудительно задаёт один job, в том числе для Visual
  Studio generator; режим полезен для диагностики воспроизводимых ошибок
  сборки.
- `--unity` включает CMake unity build для выбранных C++-тяжёлых целей. Флаг экспериментальный и не включён по умолчанию.
- `--pch` включает precompiled headers для выбранных C++-тяжёлых целей и включён по умолчанию. Отключение: `--no-pch` или `-DTERMIN_ENABLE_PCH=OFF`. C++-тяжёлые runtime-библиотеки (`termin_engine`, `termin_navmesh_components`) сохраняют свой локальный PCH.
- Глобальный CMake unity build (`-DCMAKE_UNITY_BUILD=ON`) поддерживается для root graph после cleanup внутренних helper/state имён. Vendored `Recast`/`Detour` targets явно собираются без unity.

Примеры:

```bash
BUILD_JOBS=8 task build:cpp -- --sdl
BUILD_DIR=build/Release-ninja task build:cpp -- --sdl --ninja
BUILD_DIR=build/Release-unity task build:cpp -- --sdl --unity
BUILD_DIR=build/Release-no-pch task build:cpp -- --sdl --no-pch
```

PowerShell SDK-скрипты на Windows используют тот же root CMake graph:

```powershell
$env:BUILD_JOBS=8; task build:cpp -- --sdl
$env:BUILD_DIR="build\Release-unity"; task build:cpp -- --sdl --unity
$env:BUILD_DIR="build\Release-no-pch"; task build:cpp -- --sdl --no-pch
```

На Windows PowerShell-скрипты по умолчанию не выбирают Ninja автоматически и оставляют CMake default generator (обычно Visual Studio/MSVC). Ninja можно включить явно через `$env:TERMIN_CMAKE_GENERATOR="Ninja"`, но тогда CMake возьмёт компилятор из окружения/PATH; старый LLVM `clang-cl` может быть несовместим с текущим MSVC STL.

Windows SDK, C# bindings, C++ tests и D3D11 validation используют общий
PowerShell build helper, поэтому `BUILD_JOBS` и `--no-parallel` имеют
одинаковую семантику во всех штатных точках входа.

Прямой CMake-вариант:

```bash
cmake -S . -B build/Release-unity -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DTERMIN_ENABLE_VULKAN=ON \
  -DTERMIN_ENABLE_SDL=ON \
  -DTERMIN_USE_CCACHE=ON \
  -DTERMIN_ENABLE_UNITY_BUILD=ON \
  -DTERMIN_ENABLE_PCH=ON
cmake --build build/Release-unity --parallel 8
```

Script-level `--unity` intentionally applies only to selected targets where it has been checked for developer iteration: `termin_graphics2`, `termin_render`, `termin_engine`, `trent`. For a full audit/experiment use direct CMake with `-DCMAKE_UNITY_BUILD=ON`.

Script-level `--pch` applies to selected C++ targets with broad STL-heavy include usage: `termin_graphics2`, `termin_render`, `termin_engine`, `trent`, `tcplot`. It deliberately avoids C-only libraries and third-party vendored targets.

---

## Структура SDK

Ниже показан layout полного профиля в `sdk/`. `sdk-core/` и `sdk-graphics/`
имеют тот же установленный контракт, но другую package closure.

```
sdk/
├── bin/            # Исполняемые файлы, включая termin_python; DLL на Windows
├── lib/            # Import libraries (.lib), shared libraries на Linux (.so), cmake configs
│   ├── cmake/      # find_package() конфиги для каждого модуля
│   └── python3.14t/site-packages/
│       # Python-пакеты (native-модули + .py исходники) на Linux
├── include/        # C/C++ заголовки
└── python/Lib/site-packages/
    # Python-пакеты на Windows; Windows stdlib живёт в <sdk-prefix>/python/Lib/
```

### Артефактные manifests

Native Python artifacts имеют два разных schema-v3 контракта:

- `<sdk-prefix>/termin-artifacts.json` — поставляемый relocatable SDK manifest. Поле
  `path` всегда относительно корня SDK; entry фиксирует kind, extension,
  target, SHA-256 и bundled/external runtime dependencies. Top-level
  `python_abi` однозначно задаёт `version`, `soabi`, `free_threaded` и
  `py_gil_disabled` для всего набора. Manifest не содержит checkout,
  `build_dir`, `sdk_prefix` или других абсолютных путей.
- `build/<config>/termin-build-artifacts.json` — внутренний developer manifest
  с точными абсолютными путями build tree. Он не поставляется как часть SDK.

Оба manifest фиксируют content-derived `native_build_id`. Для SDK он вычисляется
из канонической Python ABI identity, SHA-256 всех native extensions и
транзитивно bundled shared libraries, а не из mtimes. Этот ID становится PEP
440 suffix `+sdk<id>` и без пересчёта
используется runtime wheels, `python-runtime-manifest.json` и public
`<sdk-prefix>/wheels`. Повторный wheel-stage сохраняет ID, пока native payload не
изменился. Финальная SDK verification сопоставляет версии и байты native
payloads во всех трёх представлениях и отвергает stale или смешанный wheelhouse.

Setuptools consumer выбирает установленный контракт только через
`TERMIN_SDK=/path/to/sdk`. Явный build-tree режим включается через
`TERMIN_ARTIFACT_MANIFEST=/path/to/termin-build-artifacts.json`. После выбора
manifest никакого поиска в checkout, соседнем SDK, `/opt` или `PATH` нет:
отсутствующий artifact, выход path за корень SDK, неверные kind/target/ABI или
hash завершают сборку с ошибкой. Поэтому перенос SDK в другой каталог безопасен,
а stale build tree не может незаметно подменить поставляемый binary.

### Bundled Python и тестовый контур

`<sdk-prefix>/bin/termin_python` — SDK-relative isolated launcher. Он игнорирует
`PYTHONHOME`, `PYTHONPATH` и user site-packages, использует bundled stdlib и
site-packages, а `--termin-info` печатает диагностический JSON с SDK root,
Python ABI и активными путями.

Все C++ процессы, встраивающие CPython (`termin_python`, `termin_launcher`,
`termin_editor`, `termin_player` и standalone Python module backend), используют
общий `termin-python-host`. Модуль конфигурирует интерпретатор только через
`PyConfig`, до старта задаёт home/argv/isolation policy и после старта сверяет
фактические `major.minor`, SOABI и free-threaded marker с ABI сборки. Старые
process-global API `Py_SetPythonHome`, `PySys_SetArgvEx`,
`Py_NoSiteFlag`/`Py_IgnoreEnvironmentFlag` в product paths запрещены.

Runtime population разделён на build и install:

- `build-system/python-sdk-build-requirements.txt` фиксирует инструменты
  disposable build environment `build/python-runtime/build-env`;
- `build-system/python-runtime-lock.txt` содержит exact pins для всех
  third-party distributions, поставляемых с SDK, включая `pytest` и его
  транзитивные зависимости;
- external wheels материализуются в `build/python-runtime/external-wheels`
  во временном каталоге, проверяются по exact lock и supported tags целевого
  Python, после чего атомарно заменяют предыдущий wheelhouse;
- все Termin wheels собираются из `build-system/packages.json` в
  `build/python-runtime/termin-wheels`;
- SDK `site-packages` очищается и устанавливается одним offline-проходом с
  `--no-index --no-deps`;
- offline-проход повторяет проверку полноты lock и отвергает native wheels с
  несовместимым ABI, включая обычный `cp314` при целевом `cp314t`;
- editor/launcher Python-код устанавливается после library wheels из явно
  перечисленных roots в `build-system/application-python-payloads.json`;
  этот шаг также возвращает `_editor_native` из native build tree и пишет
  `sdk/application-python-payloads.json` с hashes всех app-owned файлов;
- `sdk/python-runtime-manifest.json` фиксирует Python ABI, lock hash, полный
  набор distributions и hashes их `RECORD`.

Artifact, runtime, installed application-payload и checkout-overlay manifests
используют один и тот же объект `python_abi`. Проверка сравнивает все четыре
поля, поэтому одинаковые `major.minor` не позволяют смешать обычный `cp314` с
free-threaded `cp314t`. Native wheels дополнительно проверяются по ABI tag из
их `WHEEL` metadata до import.

SDK verification сверяет manifest с фактическими metadata и payload hashes и
падает на лишнем, отсутствующем или изменённом distribution. Application
payload проверяется отдельно: без фиктивной `.dist-info`, с hostile-environment
imports и `--termin-python-layout-smoke` через bundled `termin_editor` и
`termin_launcher`. Копирование runtime-пакетов из host `site-packages`
запрещено. После первичного заполнения wheelhouse population можно проверить
без сети:

```bash
TERMIN_PYTHON_RUNTIME_OFFLINE=1 \
  PYTHONPATH=core/termin-build-tools \
  python -m termin_build.sdk --repo-root . install-python
```

Developer/test environment не является вторым runtime venv. Команда

```bash
task test:python:setup --
```

создаёт disposable слой `build/python-envs/test`: pinned Ruff и прочие
test-only dependencies; `pytest` доступен прямо из bundled SDK. Затем создаётся
`overlay.json`. Manifest-driven finder загружает Python-исходники
Termin из checkout, но ищет native extensions прежде всего в соответствующем
SDK. Overlay привязан к hash `sdk/termin-artifacts.json` и Python ABI; устаревший
overlay завершается ошибкой вместо неявного смешивания сборок.

Test-only `site-packages` также является exact производным артефактом:
`test-environment.json` фиксирует полный test lock, ABI, free-threaded marker,
платформу и архитектуру. SDK Python и isolated build frontend обязаны иметь
одинаковую runtime identity. При изменении lock, ABI или состава установленного
каталога окружение собирается в чистом staging-каталоге и заменяется только
после успешной установки; удалённые зависимости не остаются затенять SDK.
Задача `task test:python` проверяет этот manifest до запуска pytest и при
устаревшем окружении требует явно повторить `task test:python:setup`.
Верхнеуровневая `task test` сама вызывает `task test:python:setup` перед
Python-фазой: после новой SDK-сборки он обновляет fingerprint overlay, не
переустанавливая неизменившийся test-only слой. Прямой вызов
`task test:python` остаётся строгим и только сообщает каноническую команду
восстановления.

Прямые режимы запуска:

```bash
# Разработка и тесты из checkout поверх SDK runtime
task run:python -- -m pytest

# Произвольный скрипт из checkout с тем же SDK + overlay
task run:python -- path/to/script.py

# Проверка только установленного SDK, без checkout overlay
sdk/bin/termin_python -c "import termin.base, termin.engine"
```

На Windows первые две команды также выполняются через `task run:python`.
`TERMIN_SDK`, `PYTHON_BIN` и `TERMIN_PYTHON_OVERLAY` позволяют launcher-скрипту
использовать нестандартное расположение SDK или manifest.

Старые `setup-test-venv.*` и корневой `.venv` workflow удалены. Новый workflow
не копирует `.so`/`.pyd` в source tree и не требует `--force` после пересборки
bindings; обычный вызов `task test:python:setup` сам определяет, нужно ли
пересобрать test-only слой или достаточно перегенерировать overlay.

### Mutable CI SDK release

Workflow `.github/workflows/publish-sdk-ci.yml` по ручному запуску независимо
собирает canonical SDK на Linux и Windows, но публикует release только после
успеха обеих платформ. Контракт release фиксирует ровно четыре asset:

- `termin-sdk-linux-x86_64-py314t-latest-ci.tar.zst` и `.sha256`;
- `termin-sdk-windows-x86_64-py314t-latest-ci.zip` и `.sha256`.

Общий упаковщик `python -m termin_build.sdk_release` требует schema 3 для
`python-runtime-manifest.json`, bundled `termin_python[.exe]`, `lib`, `wheels`,
free-threaded CPython 3.14t и единый `native_build_id` runtime/artifact/wheel
manifests. Он запускает relocated-SDK verification до упаковки, создаёт archive
во временном каталоге, распаковывает его и повторяет ту же проверку. Только
после этого archive и checksum атомарно заменяют предыдущие локальные outputs.
Поэтому ошибка сборки, ABI, payload hashes или упаковки не может затереть
готовый coherent asset.

После загрузки полного набора workflow посылает `repository_dispatch` в
Diffusion Editor с точными полями `asset`, `asset_checksum`, `windows_asset` и
`windows_asset_checksum`. Windows SDK собирается с SDL и D3D11, но без
Vulkan/OpenGL: `--no-vulkan --no-opengl`. Профиль `--no-sdl` остаётся только
для C#-ориентированных локальных сборок и непригоден для native player.

Локальный Linux publisher `task ci:publish-sdk` использует тот же
упаковщик и больше не имеет отдельного legacy `py310` контракта.

---

## Куда что ставится

### C/C++ библиотеки

На **Linux** shared library (`.so`) — это одновременно и библиотека для линковки, и файл, загружаемый в runtime. Она ставится в `lib/`.

На **Windows** shared library разделяется на два файла:
- **Import library** (`.lib`) — используется при компиляции/линковке → ставится в `lib/`
- **DLL** (`.dll`) — загружается в runtime → ставится в `bin/`

В CMake это контролируется тремя строками install:

```cmake
install(TARGETS mylib
    LIBRARY DESTINATION lib    # .so на Linux
    ARCHIVE DESTINATION lib    # .lib на Windows (и .a для статических)
    RUNTIME DESTINATION bin    # .dll на Windows
)
```

`RUNTIME DESTINATION` на Linux игнорируется для shared libraries (`.so` — это LIBRARY, не RUNTIME). Но на Windows DLL — это именно RUNTIME-артефакт. Если по ошибке указать `RUNTIME DESTINATION lib`, DLL окажется в `lib/` и не будет найдена при запуске.

### Python-пакеты

Python-пакет состоит из двух частей:
- **Native-модуль** (`.pyd` на Windows, `.so` на Linux) — компилированный C++ код
- **Python-исходники** (`.py`) — `__init__.py`, обёртки, утилиты

Порядок установки SDK-пакетов и canonical internal distribution names живут в
`build-system/packages.json`. Политика именования и полный инвентарь
`repo path / distribution / import namespace` описаны в
[Python Package Naming](./python-package-naming.md). В `install_requires` нужно
указывать distribution name из manifest (`termin-graphics-core`, `termin-mesh`,
`termin-base`, ...), а не
repo path (`termin-graphics`, `termin-mesh`, `termin-base`) и не случайный
import namespace.

Обе части устанавливаются в versioned `site-packages`: на Linux в
`lib/pythonX.Y/site-packages/<package>/`, на Windows в
`python/Lib/site-packages/<package>/`. Старое staging-дерево
`sdk/lib/python/termin/` удалено и не должно использоваться новыми install
rules.

```cmake
# Native-модуль
install(TARGETS _mylib_native DESTINATION lib/python${PYTHON_VERSION}/site-packages/termin/mylib)

# Python-исходники (без этого пакет не будет импортироваться!)
install(DIRECTORY python/termin/mylib/
    DESTINATION lib/python${PYTHON_VERSION}/site-packages/termin/mylib
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
)
```

### Заголовки

Заголовки ставятся в `include/`. Каждый модуль устанавливает свою поддиректорию.

### CMake configs

Каждый модуль генерирует CMake config в `lib/cmake/<module>/`, что позволяет downstream-модулям делать `find_package(<module> REQUIRED)`.

---

## Экспорт символов на Windows

На Linux все символы shared library видны по умолчанию. На Windows — наоборот: ничего не экспортируется, пока явно не указано.

Для этого используются макросы `__declspec(dllexport)` (при сборке библиотеки) и `__declspec(dllimport)` (при использовании). Переключение происходит через compile definition, который определяется только при сборке самой библиотеки (`PRIVATE`).

В проекте два уровня:

1. **C API** — единый макрос `TC_API`, переключается через `TC_EXPORTS`. Каждая библиотека, экспортирующая C-функции через `TC_API`, должна определять `TC_EXPORTS` в своих compile definitions.

2. **C++ классы** — каждая библиотека определяет свой макрос (например `MYLIB_API`), переключаемый через свой define (например `MYLIB_EXPORTS`). Это нужно потому что один модуль может экспортировать свои классы и одновременно импортировать классы из зависимостей.

`WINDOWS_EXPORT_ALL_SYMBOLS` считается временным миграционным механизмом для старых целей. Новые и обновляемые библиотеки должны экспортировать публичный ABI через явные `*_API`/`TC_API` макросы, иначе CMake начинает экспортировать лишние C++-символы вроде vtable/RTTI и на MSVC появляются дублирующиеся export-spec warnings.

На Linux оба макроса раскрываются в пустую строку (или `__attribute__((visibility("default")))`), поэтому ошибки экспорта на Linux не проявляются — они видны только при сборке на Windows.

---

## Поиск DLL в runtime

### Linux

Используется RPATH — путь поиска shared libraries, зашитый в ELF-бинарь. Настраивается через cmake-хелперы из `cmake/TerminRpath.cmake`. Типичный RPATH: `$ORIGIN` (директория самого бинаря) + `${CMAKE_INSTALL_PREFIX}/lib`.

### Windows

Windows не использует RPATH. Начиная с Python 3.8, DLL ищутся только:
- В директории исполняемого файла
- В директориях, явно зарегистрированных через `os.add_dll_directory()`
- В системных директориях

Переменная `PATH` по умолчанию **не используется** для поиска DLL в Python 3.8+.

Поэтому runtime-регистрация DLL должна добавлять директории с нативными библиотеками: package-local `lib/` для standalone pip-пакетов и `sdk/bin/`/`sdk/lib/` для SDK layout. SDL2 поставляется как нативная зависимость SDK; Python-код не должен загружать отдельный PySDL2 runtime.

---

## Сборка Python bindings

### Принцип разделения

C++ часть каждого модуля полностью самодостаточна и не зависит от Python. Флаг `-DTERMIN_BUILD_PYTHON=ON` добавляет дополнительные targets (nanobind-модули), но **не изменяет основную C++ библиотеку** — ни её исходники, ни compile definitions, ни зависимости. Python bindings пристраиваются сбоку, линкуясь к уже собранной библиотеке.

Это означает, что при переключении `TERMIN_BUILD_PYTHON` с OFF на ON основная библиотека не пересобирается — cmake инкрементально добавляет только новые targets.

### Две стадии сборки

Сборка разделена на две стадии (C++ → bindings) не потому что они конфликтуют, а для практического удобства: если Python или nanobind не установлены, хотя бы C++ часть соберётся. Технически можно собирать всё сразу с `-DTERMIN_BUILD_PYTHON=ON` — результат будет идентичным для SDK layout.

Обе стадии используют один и тот же build directory (`build/Release`). Вторая стадия переконфигурирует cmake, но благодаря инкрементальности C++ часть не пересобирается.

### Структура модуля с биндингами

Биндинги строятся через [nanobind](https://github.com/wjakob/nanobind). Каждый модуль может опционально собирать Python-расширение при `-DTERMIN_BUILD_PYTHON=ON`.

В SDK build project-модули используют один shared nanobind runtime (`NB_SHARED`):
`libnanobind-ft.so`. `termin-nanobind-sdk` требует Python 3.14t и
централизованно добавляет `NB_FREE_THREADED` всем модулям. Установленный CMake
package отвергает другой Python ABI и не позволяет собрать локальную вторую
копию runtime. Финальная SDK verification в hostile Python environment
проверяет выключенный GIL до первого импорта, последовательно импортирует все
manifest native extensions, затем editor/launcher/engine/player/headless
корни product graph и проверяет GIL после каждого шага. Предупреждение CPython
о загрузке extension без free-threaded opt-in является ошибкой; диагностика
называет первый импорт и фактические version/SOABI/Py_GIL_DISABLED.

Тот же gate входит в центральные `task test --` и `task test` на Windows. Отдельно
его можно запустить без полной SDK verification:

```bash
sdk/bin/termin_python --termin-overlay build/python-envs/test/overlay.json \
  -m termin_build.sdk --repo-root . \
  verify-python-import-graph --sdk-prefix sdk
```

```
mylib/
├── CMakeLists.txt
├── src/                    # C/C++ исходники библиотеки
├── include/                # Заголовки
└── python/
    ├── bindings/           # C++ код биндингов (nanobind)
    └── termin/mylib/       # Python-исходники пакета
        ├── __init__.py
        └── utils.py
```

---

## Bundled Python

> Проверенное SDK install tree является единственным editor/launcher runtime
> artifact. `termin-app` — application product с внутренним Python payload, а
> не самостоятельный library wheel. Wheel, distribution metadata и отдельный
> host-derived standalone packager удалены в #680/#681. См.
> [протокол совета](architecture-council/2026-07-19-termin-app-product-boundary.md).

Launcher и editor — это C++ исполняемые файлы, которые встраивают
Python-интерпретатор. SDK orchestration устанавливает в единое SDK tree:
- Python stdlib (`python/Lib/` на Windows, `lib/python3.14t/` на Linux)
- Внешние pip-пакеты в `python/Lib/site-packages/` на Windows или
  `lib/pythonX.Y/site-packages/` на Linux
- DLL/so Python-рантайма

Launcher при запуске:
1. Определяет, есть ли bundled Python (ищет stdlib рядом с собой)
2. Если есть — вызывает `Py_SetPythonHome()` чтобы Python использовал bundled stdlib
3. Добавляет bundled `site-packages` в `sys.path`
4. Запускает Python-код приложения

Stage 3 SDK build устанавливает exact-locked runtime offline из подготовленного
wheelhouse, затем устанавливает editor payload по отдельному app manifest.
Library distributions проверяются через `python-runtime-manifest.json`, а
editor payload — через `application-python-payloads.json`. Копирование из
ambient host `site-packages` запрещено. Отдельный top-level `termin-app`
Отдельного `termin-app` install tree больше нет. Cross-platform
`scripts/smoke-relocated-sdk` и `scripts/smoke-relocated-sdk.ps1` копируют SDK
в новый root и запускают общую manifest/runtime verification. Bundled
`termin_python`, `termin_player`, `termin_editor` и `termin_launcher`
проверяются из relocated tree с hostile `PYTHONHOME`, `PYTHONPATH`, user site и
рабочей директорией вне checkout. Это editor SDK smoke; desktop project bundle
остаётся отдельным product contract.

Нижележащие library packages продолжают собираться отдельными wheels. В
частности, graphics/display/GUI subset должен устанавливаться из `sdk/wheels`
без `termin-app`; внешний Diffusion Editor является consumer gate этого
контракта. Финальная wheelhouse verification устанавливает representative
`termin-base`/`termin-graphics-core`/`termin-display`/`termin-gui-native` subset в чистый target и
отвергает `termin-app` wheel или dependency.

---

## Project build profiles и runtime package gate

`termin_builder` является тонкой CLI-точкой входа для project build: он находит
project root и делегирует чтение, проверку и компиляцию профиля Python backend-у
`termin.project_build.profile_build`. C++ CLI и `termin_runner` не имеют
собственного JSON-представления схемы. Target-specific логика живет в Python
wrapper-ах для `desktop`, `android` и `quest_openxr`.

Локальный capability report доступен через тот же установленный launcher:
`termin_builder capabilities <profile> --project <dir> [--json]`. Команда
принимает те же toolchain overrides, что и `build`, и возвращает exit code 0
для buildable report либо 2, если report содержит capability diagnostics.

Schema-v2 и ее persistence API принадлежат toolkit-neutral модулю
`termin.project_build.profiles`. `BuildProfileStore` загружает и перечисляет
профили, разрешает project-relative пути и атомарно сохраняет детерминированный
JSON. Он принимает только `version: 2`, отклоняет v1 без runtime-миграции,
неизвестные поля и поля чужого target-варианта. Импорт profile store не
загружает argparse и target build wrappers, поэтому модель можно напрямую
использовать в editor UI.

Профиль состоит из:

- обязательных `configuration`, `target` и `content`;
- optional project-relative `output_dir`, по умолчанию `dist/<profile-name>`;
- target-варианта `desktop`, `android` или `quest_openxr`;
- `content.entry_scene` и явного списка корневых `content.scenes`;
- явных root-модулей, дополнительных Python requirements и resource includes;
- единственного ordered desktop-списка `runtime.backends`, который одновременно
  задает приоритет runtime backend-ов и семейства пакуемых shader artifacts.

Для desktop `target` обязательно задает `os` и `arch`. Android и Quest задают
ABI и числовой `ndk_api`, но не имеют конфигурируемого `runtime`: Vulkan/OpenXR
являются частью фиксированного product target. Пути к SDK, компиляторам, Gradle
и build scripts в профиль не входят; их передает локальный `ToolchainContext`.

`ToolchainContext` собирается одной provider chain. Приоритет отдельных полей
от высшего к низшему: явные параметры конкретного запуска, environment, общие
пользовательские настройки Termin, SDK installation defaults. После слияния
roots незаданные tools выводятся из итоговых `sdk_root`, `termin_root`,
Termin `android_sdk_root`, Google `android_home` и `PATH`.
Поэтому смена SDK не оставляет compiler path от прежней установки. Контекст
включает `termin_shaderc`, FXC, Android/Quest scripts, Gradle и ADB, но никогда
не сохраняется в `build_profiles.json`.

Канонический пользовательский конфиг Termin находится в
`~/.config/termin/settings.json` на Linux и
`%APPDATA%/termin/settings.json` на Windows. Редактор хранит там как свои
пользовательские параметры, так и provider из
**Edit > Settings... > Build Toolchain**: локальные корни Termin SDK/source,
Termin Android SDK slice, Google Android SDK, Android NDK, JDK и overrides для
`termin_shaderc`, FXC, Android/Quest build scripts, Gradle и ADB.

Android-пути намеренно разделены:

| Назначение | Environment | User setting |
|---|---|---|
| cross-compiled Termin Android SDK | `TERMIN_ANDROID_SDK_ROOT` | `Build/androidSdkRoot` |
| Google Android SDK | `ANDROID_HOME`, затем `ANDROID_SDK_ROOT` | `Build/androidHome` |
| Android NDK | `ANDROID_NDK_HOME`, затем `ANDROID_NDK_ROOT` | `Build/androidNdkRoot` |
| JDK для Gradle | `JAVA_HOME` | `Build/javaHome` |
| Gradle | `GRADLE_BIN` | `Build/gradle` |
| ADB | `ADB` | `Build/adb`, затем `<androidHome>/platform-tools/adb` |

`task build:android` выбирает NDK
в порядке `--ndk`, `ANDROID_NDK_HOME`, `ANDROID_NDK_ROOT`, затем
`Build/androidNdkRoot` из этого файла. Сохранение не меняет project-owned
файлы. Build Profiles немедленно пересчитывает capabilities, а `termin build`
читает тот же `Build/*` section, если соответствующий явный аргумент не задан.
Standalone Android/Quest APK wrappers используют ту же последовательность и
принимают явные `--android-home`, `--ndk-root`, `--java-home`, `--gradle` и
другие overrides. Запуск через `GRADLE_BIN=...` для обычной работы не требуется.

Cross-сборка самого SDK требует установленный Android Core того же ABI/API:

```bash
task build:android -- \
  --ndk /absolute/path/to/android-ndk \
  --core-sdk /absolute/path/to/core-sdk/android/arm64-v8a
```

Скрипт не имеет source fallback. При установке проверенный Core tree копируется
в результирующий Android SDK, после чего поверх него устанавливается
domain-слой.

Канонический `inspect_profile_capabilities()` возвращает тот же stable-code
report для CLI и editor consumers. `capability.*.missing` означает отсутствие
настройки/обнаружения, `capability.*.invalid` — заданный путь неправильного
типа или не существует; отдельные коды описывают SDK target, Android ABI,
Quest/OpenXR и host-platform mismatch. Build останавливается до target pipeline,
если report не buildable, а команды `profile`, `resolve` и `build --dry-run`
по-прежнему позволяют инспектировать корректный foreign-platform profile.

Android и Quest/OpenXR остаются разными продуктами со своими Gradle-проектами,
manifest-ами и entry point-ами, но используют общий APK pipeline. Конфигурации
`dev` и `debug` запускают Gradle variant `debug`, а `release` — variant
`release`. Готовый artifact определяется по Gradle `output-metadata.json`,
включая проверку `applicationId`; фиксированное имя `app-debug.apk` не является
частью контракта.

Публичные wrapper-ы APK platform-specific: `build-android-apk.sh` и
`build-quest-openxr-apk.sh` на Linux, соответствующие `.ps1` на Windows.
`ToolchainContext` выбирает suffix текущего host-а, а общий APK pipeline
запускает PowerShell wrapper через `pwsh -NoProfile -File`. Обе Windows-команды
поддерживают тот же набор `--assets-dir`, `--sdk-root`, `--abi`, `--platform`,
`--gradle`, `--variant` и application/version аргументов; Quest wrapper
дополнительно поддерживает `--adb`, `--install` и `--launch`.

Оба Android-family target-а читают один `application` из канонического
`project_settings/project.json`: base application ID, launcher label,
целочисленный Android version code и отображаемый version name. Новому проекту
эти поля записываются сразу; для старого проекта без блока `application`
детерминированный ID и label выводятся из имени проекта. Android и Quest одного
проекта намеренно используют одинаковую base identity; profile suffix пока не
добавляется, поскольку контракт одновременной установки вариантов не заявлен.
Явно заданные некорректные identity/version values отклоняются, а не
подменяются молча.

Release APK всегда должен быть подписан. Для обоих продуктов используются
одинаковые обязательные переменные окружения:

- `TERMIN_ANDROID_SIGNING_KEYSTORE` — путь к keystore;
- `TERMIN_ANDROID_SIGNING_KEY_ALIAS`;
- `TERMIN_ANDROID_SIGNING_STORE_PASSWORD`;
- `TERMIN_ANDROID_SIGNING_KEY_PASSWORD`.

При отсутствии любого параметра release build завершается до запуска Gradle с
явной диагностикой. Debug signing при этом остается штатным поведением Android
Gradle Plugin.

Парсер v2 представляет сцены, модули, Python requirements и resource includes
типизированными полями. Явные scene roots участвуют в build: exporter пакует
каждую выбранную сцену и объединяет найденные в них resource/shader
dependencies. Desktop build также строит единый индекс `.module`/`.pymodule`,
разрешает dependency-first closure из `content.modules` и пакует только его
Python packages, готовые native artifacts и requirements в `package/modules`.
`package/modules/modules.json` и `runtime.modules` в `app.json` фиксируют exact
roots и closure. Для Android/Quest выбранные project modules, а для всех
target-ов explicit dynamic resource roots пока завершаются diagnostic
`profile.feature_pending`, а не молча игнорируются.

Project-level `world_controller` не является полем build profile. Значение
`null` либо точная пара `{module, type}` читается из
`project_settings/project.json` и без изменений записывается в runtime package.
Desktop build автоматически добавляет выбранный owner module в module roots,
проверяет его присутствие в packaged closure и после загрузки сверяет facet,
owner и abstract-флаг выбранного типа. Поэтому профиль не может случайно
выкинуть контроллер из bundle. Android/Quest до появления project-module
packaging отклоняют непустой выбор на preflight с явной диагностикой; `null`
остается переносимым общим контрактом.

Project-level defaults для окна standalone player хранятся в
`project_settings/project.json` в поле `player_window`:

```json
{
  "application": {
    "id": "com.example.game",
    "label": "Example Game",
    "version_code": 1,
    "version_name": "0.1.0"
  },
  "player_window": {
    "width": 1280,
    "height": 720,
    "fullscreen": true,
    "vsync": true
  }
}
```

Desktop bundle `app.json` записывает эти значения в `runtime.window`.
Schema v2 `app.json` также повторяет project selection в
`runtime.world_controller`; packaged player требует точного совпадения с
runtime package manifest.
Python `termin.player` и C++ `termin_player` используют их как дефолт, а
CLI-флаги `--width`, `--height`, `--fullscreen` и `--windowed` остаются явными
override-ами для smoke/manual runs.
Поле `vsync` выбирает construction-time presentation mode окна: `true`
соответствует `VSync`, `false` — `Immediate`. Для старых project/app manifests
без этого поля сохраняется VSync-on поведение.
На D3D11 оба режима используют flip-model swapchain. `Immediate` разрешён
только при `DXGI_FEATURE_PRESENT_ALLOW_TEARING`: swapchain и каждый resize
сохраняют `DXGI_SWAP_CHAIN_FLAG_ALLOW_TEARING`, а present использует
`Present(0, DXGI_PRESENT_ALLOW_TEARING)`. Если capability отсутствует, player
завершается с явной ошибкой вместо неявного перехода обратно на VSync.

Для desktop profile `runtime.backends` одновременно задаёт набор поставляемых
shader artifact families и порядок выбора backend на целевой машине. Runtime
package export пишет артефакты только для запрошенных backend targets и
добавляет тот же ordered список в `target_requirements.backends`, а `app.json`
повторяет его как `runtime.backends`. Валидатор требует точного равенства списка
и shader artifact families. Packaged player проверяет равенство обоих
манифестов и пробует backend-ы по порядку только во время начального создания
graphics session/window, логируя каждую неудачу. `TERMIN_BACKEND`/`--backend`
выбирает ровно один packaged backend и запрещает fallback.

SDK записывает целевые `platforms.desktop.os` и `platforms.desktop.arch` в
`termin-sdk-capabilities.json`. Desktop preflight отклоняет SDK, target которого
не совпадает с typed profile; `app.json` и runtime package manifest повторяют
согласованные `os/arch`, поэтому host defaults не могут незаметно изменить
profile intent.
D3D11-артефакты генерируются как `shaders/d3d11/<uuid>.vs.cso` /
`shaders/d3d11/<uuid>.ps.cso` и остаются opt-in, чтобы обычные Linux/Android
сборки не требовали Windows SDK `fxc`.

`content.resources.policy: strict` является default contract для packaged build.
Отсутствующие mesh/material resources становятся build diagnostics уровня
`error`; exporter не пишет placeholder artifacts и не добавляет synthetic
resource entries в manifest. Placeholder/fallback artifacts разрешены только
при явном `resource_policy: dev_smoke` и сопровождаются diagnostics уровня
`warning`.

Единый Python pipeline выполняет:

```text
project preflight
-> target preflight
-> output preparation
-> runtime package export
-> runtime package validation
-> target packaging
```

Runtime package validation является gate перед target packaging. Если export
или validation вернули diagnostic с `level == "error"`, target packaging не
запускается: desktop bundle/APK не должны создаваться из заведомо битого
runtime package. CLI backend печатает diagnostics и возвращает non-zero exit
code при `error` diagnostics.

Runtime package manifest schema v3 задаёт multi-scene и world-controller
contract явно:

```json
{
  "version": 3,
  "entry_scene": "Scenes/Main.scene",
  "world_controller": null,
  "scenes": [
    {
      "identity": "Scenes/Main.scene",
      "path": "scenes/Scenes/Main.scene.json"
    },
    {
      "identity": "Scenes/Menu.scene",
      "path": "scenes/Scenes/Menu.scene.json"
    }
  ],
  "resources": []
}
```

`identity` — нормализованный project-relative путь исходной `.scene`; он
остаётся стабильным после переноса bundle. `path` указывает только внутрь
package. `entry_scene` обязан присутствовать в таблице. Валидатор проверяет
каждую сцену и полный объединённый resource closure, а native runtime загружает
и регистрирует всю таблицу. Player начинает engine-owned `RuntimeSession`,
привязывает к ней все сцены, активирует entry scene через
`WorldContext.transition_to(entry_scene)` и оставляет остальные сцены неактивными
до такого же запроса из игрового кода. Включённая в package, но ещё не
материализованная сцена может быть поднята `SceneManager`-provider'ом из
package catalog; физическая раскладка bundle не входит в игровой API. Сам
переход выполняется только в safe point `EngineCore::tick_and_render()`;
player не содержит отдельной машины состояний транзита. Build profile задаёт
только export closure и не влияет на Editor Play или source `termin play`.
Поле `world_controller` обязательно даже при отсутствии контроллера: допустимы
только `null` и объект ровно с непустыми нормализованными строками `module` и
`type`. Старые schema versions не угадываются и не мигрируют в runtime.

Для packaged scene closure включает исполняемые фабрики, а не только файлы.
Допустимые component factories определяются возможностями target host:
native-only targets принимают только C++, а desktop player принимает также
Python factories из builtin runtime или из точного module closure выбранного
профиля. Desktop build формирует этот closure до factory validation, загружает
выбранные модули в отдельной build-сессии и сверяет owner каждой Python factory
с содержимым bundle. Поэтому фабрика из невыбранного модуля не может случайно
пройти проверку через process-global registry. Отсутствующая фабрика, ошибка
загрузки selected module и неподдерживаемый target-ом factory kind остаются
fatal validation errors.

`ui_document.type_dependencies` должны точно совпадать с recipe и разрешаться
в C++ widget factories с native UiScript contract; Python widget factories в
packaged UiScript по-прежнему не поддерживаются. Во время анализа сцены
exporter временно публикует только те скомпилированные UI documents, которых
ещё нет в process registry, и снимает эти регистрации сразу после анализа.

Desktop target packaging больше не должен копировать SDK `site-packages`
целиком по умолчанию. В `minimal_strict` bundle получает Python stdlib из SDK
без `site-packages`, затем создаёт чистый `site-packages` и добавляет только
явный Termin player runtime seed плюс requirements из выбранного module closure
и профиля. Транзитивное замыкание строится из wheel metadata (`Requires-Dist`),
поэтому runtime-зависимости native/Python-пакета должны быть перечислены в его
package metadata; например, `termin-components-kinematic` явно требует
`termin-robotics`, `termin-scene` и `termin-inspect`.
Состав записывается в `python-runtime.json`. Если временно нужен старый broad
copy для диагностики, профиль должен явно указать:

```json
"runtime": {
  "backends": ["vulkan", "opengl"],
  "python_package_policy": "sdk_broad_copy"
}
```

---

## Компонентные библиотеки

Для однотипных компонентных модулей есть cmake-хелпер `TerminModule.cmake` с макросом `termin_add_module()`. Он автоматизирует создание shared library, настройку экспортов, RPATH и install-правил.

---

## C/C++ тесты

C/C++ тесты собираются через root CMake graph:

```bash
task test:cpp
```

По умолчанию runner использует тот же `build/<BuildType>`, что и
`task build`. После включения тестов CMake planner разрешает
выбранные CTest registrations в точные executable targets и сверяет весь набор
с CMake-generated манифестом capability-aware целей `termin_native_tests` или
`termin_native_tests_with_window`. При несовпадении составов runner падает до
сборки. Эти цели исключают Python-binding tests из нативного прогона и собирают
зарегистрированные тесты с их зависимостями одним графом backend build system,
не обходя общие зависимости заново для каждого тестового executable.
Уже собранные библиотеки ядра и third-party переиспользуются инкрементально;
отдельный полный `build/Release-tests` для обычного прогона не создаётся.
`BUILD_DIR` по-прежнему позволяет явно выбрать изолированный граф для
sanitizer/coverage или другого несовместимого профиля.

Флаги:

- без флагов запускается рабочий набор CTest без тестов, создающих окна;
- `--full` включает полный C++ набор, включая window/video backend tests;
- `--vulkan` / `--no-vulkan` управляют `TERMIN_ENABLE_VULKAN`; Vulkan
  включён по умолчанию и является основным тестовым путём;
- `--window-tests` / `--no-window-tests` точечно управляют тестами, которым нужен windowing/video backend;
- tgfx2 тесты подключены к CTest и являются частью основного C++ test workflow;
  backend-independent проверки вроде `tgfx2_sdf_test` остаются в обычном
  headless наборе, а тесты, создающие окна/GL-контексты, включаются только
  через `--window-tests` / `--full`.

Window tests настроены так, чтобы пропускаться в headless-окружении без usable video backend, а не валить весь прогон.

## Общий тестовый цикл

Центральная точка проверки репозитория:

```bash
task test --
```

По умолчанию это рабочий набор: C/C++ tests без window tests, Python tests без
тестов с маркером `full`, без editor-process smoke. Полный набор запускается
явно:

```bash
task test -- --full
```

Python suite roots больше не перечисляются в публичной задаче `task test:python`.
Их source of truth — `build-system/test-suites.json`.
Локальные runners вызывают `termin_build.repository_control`: профиль `pr`
применяет pytest-выражение `not full`, а `linux-full` и `windows-d3d11`
снимают этот фильтр на соответствующей платформе. Каждая suite запускается
отдельно; planner продолжает прогон после ошибки и печатает общий список
упавших suites.

Suite manifest описывает только реально исполняемый scheduling contract:
`executor`, `roots`, `profiles`, `platforms` и диагностический `reason`.
Общих полей `environment` и `capabilities` нет: planner не создаёт отдельное
окружение и не фильтрует обычные suites по таким декларациям, поэтому старые
поля отклоняются как schema error. Единственное executor-specific исключение —
`required_capabilities` у `process-smoke`: этот список непосредственно
проверяется process adapter перед запуском. CTest requirements по-прежнему
принадлежат configured `termin:capability:*` labels и native source
classifications, а не suite-level metadata.

Проверка manifests и orphan-test gate не требует запуска самих тестов:

```bash
PYTHONPATH=core/termin-build-tools \
python3 -m termin_build.repository_control --repo-root . check
```

Gate сканирует repository-owned `test_*.py` и `*_test.py`. Каждый найденный
файл обязан принадлежать ровно одному объявленному pytest root. Generated,
SDK, venv и third-party roots исключены явно в manifest. План можно проверить
до исполнения:

```bash
PYTHONPATH=core/termin-build-tools \
python3 -m termin_build.repository_control --repo-root . \
plan pr --platform linux --json
```

Команда `plan --json` выдаёт канонический expected manifest
`termin-test-expected` для текущего checkout, profile и platform. Поле `suites`
содержит применимые suites, а `inapplicable` — неприменимые suites с
детерминированной причиной несовпадения profile/platform. `fingerprint` —
SHA-256 канонического содержимого manifest; executor result принимается только
для того expected manifest, fingerprint которого он явно указывает. Поэтому
manifest с другим test inventory нельзя случайно принять за результат текущего
набора.

Каждый естественный executor (`pytest`, `ctest`, `process-smoke`) формирует
отдельный `termin-test-execution` manifest и не передаёт управление тестами
универсальному runner. Общий suite-level контракт содержит:

- `executor`, `profile`, `platform` и `expected_fingerprint`;
- `selected` — suites, которые adapter принял к исполнению;
- ровно один terminal outcome для каждой применимой suite: `executed`,
  `skipped` или `failed`;
- обязательную непустую `reason` для каждого `skipped` outcome;
- executor-specific подробности, например CTest registrations или pytest
  diagnostics, в необязательном `details`, не меняющем suite-level результат.

`missing` не записывается самим executor: его вычисляет verifier как разность
между locally computed expected coverage и terminal outcomes. Это не позволяет
сломавшемуся adapter объявить потерянную suite корректно обработанной.
Неизвестная suite, несовпадающий fingerprint, отсутствие selection/result,
`failed`, дублирующий outcome или skip без причины делают verification красной.
Неприменимые suites учитываются из expected manifest и уже несут валидированную
причину.

Несколько независимых execution manifests проверяются одной командой:

```bash
sdk/bin/termin_python -m termin_build.repository_control \
  verify-execution \
  --expected build/expected-pr-linux.json \
  --manifest build/python-execution-manifest.json \
  --manifest build/ctest-execution-manifest.json
```

Команда возвращает ненулевой exit code при неполном или неуспешном покрытии и
печатает `termin-test-verification` report с `selected`, `executed`, `skipped`,
`failed`, `missing`, `inapplicable` и неожиданными результатами. Адаптеры и
canonical runners строят selection непосредственно из manifest текущего
checkout. Они не принимают внешний `--plan-file` и не поддерживают неявный
subset/sharding: отдельный job не может подменить локально применимый набор
suites устаревшим artifact. CI сохраняет и передаёт между jobs только execution
manifests; verification job заново вычисляет expected manifest из своего
checkout и сравнивает с fingerprints executor results. CTest adapter агрегирует
registration-level JUnit outcomes в suite-level `termin-test-execution`, сохраняя
исходные registrations и причины skip/failure в `details`.

Focused-вызов `task test:python -- <pytest-target ...>` остаётся прямым pytest
запуском и не меняет repository inventory.

Полный набор дополнительно запускает editor-process smoke tests:

- `scripts/smoke-python-module-hot-reload`
- `scripts/smoke-cpp-module-cascade-hot-reload`
- `scripts/smoke-sdk-editor-shaders`
- `scripts/smoke-editor-mcp-offscreen`
- `scripts/smoke-editor-virtual-display`, когда доступен capability
  `virtual-display`.

Module-reload и shader smoke на headless Linux используют
`scripts/termin-editor-virtual-display`, если display не настроен. Wrapper
проверяет Xvfb, Mesa llvmpipe, OpenGL/GLSL и SDK shader compiler до запуска
редактора; каждый процесс получает отдельные display, MCP port и session file.
Shader smoke запускает два полных кадра на OpenGL 4.5 / GLSL 450 с пустыми
project- и XDG-cache, ждёт штатного завершения редактора и сохраняет временный
каталог с полным editor log при ошибке.
`scripts/smoke-editor-mcp-offscreen` отдельно проверяет production
`--headless` composition без Xvfb/SDL: два параллельных редактора получают
разные agent-owned MCP sessions, исполняют команду, отдают непустой Vulkan PNG
и штатно удаляют descriptors при shutdown.
Для полного прогона без editor MCP стадии:

```bash
task test -- --full --no-editor-smoke
```

Повторяемая матрица targeted smoke-checks для render/shader/backend/runtime
изменений описана в [Smoke Checks](smoke-checks.md).

---

## Портабельность

Некоторые POSIX-функции (например `strdup`) считаются устаревшими в MSVC. Для них используются портабельные обёртки (`tc_strdup`), которые на Windows вызывают `_strdup`, а на Linux — оригинальный `strdup`.

MSVC-специфичные warnings (C4251 — STL-члены в dllexport-классах, C4275 — не-dllexport базовый класс) подавляются через `/wd4251 /wd4275`. Они безопасны при условии, что вся сборка использует один и тот же CRT.

---

## Чеклист для нового модуля

- [ ] C/C++ экспорт: определить `TC_EXPORTS` (и свой `*_EXPORTS` для C++ классов)
- [ ] Install: `RUNTIME DESTINATION` в `bin`, не в `lib`
- [ ] MSVC: подавить C4251/C4275, добавить `_CRT_SECURE_NO_WARNINGS`
- [ ] RPATH: использовать хелперы из `cmake/TerminRpath.cmake`
- [ ] Python: установить и `.pyd`/`.so`, и `.py` файлы
- [ ] Добавить модуль в `build-system/packages.json` в правильное место для pip/package workflow, если модуль имеет Python-пакет
- [ ] Добавить модуль в корневой `CMakeLists.txt`, если он должен участвовать в SDK build graph

---

## WebAssembly core profile

Браузерный runtime начинается с намеренно небольшой статической композиции:
`termin-base`, `termin-inspect`, `termin-mesh`, `termin-scene`, minimal-only
`termin-bootstrap`, minimal-only `termin-runtime` и минимального среза
`termin-graphics`. Профиль CMake
`TERMIN_PLATFORM_WEB` включает два tgfx2 presentation path: WebGPU через
закреплённый Emscripten port `emdawnwebgpu` и WebGL2 через общий constrained-GL
backend. Профиль исключает desktop renderer stack, windowing,
Python, editor и launcher targets, чтобы платформенные зависимости не
просачивались в WebAssembly-граф.

Точная версия Emscripten закреплена в
`build-system/emscripten-version.txt`. В чистом checkout toolchain
устанавливается, а артефакт собирается командой `build:web`. Node и browser
smoke запускаются отдельными тестовыми задачами. Native `termin_shaderc` и
wasm32 runtime собираются из того же checkout: Core
входит в их CMake-граф как исходный район, а не как внешний SDK input:

```bash
task build:web -- --setup
```

Повторные сборки используют `build/toolchains/emsdk`,
`build/web-core-host-tools` и `build/web-core`. Детерминированный Node lifecycle
smoke запускается явно:

```bash
task test:web
```

Для обязательного прогона в настоящем браузере нужен Chromium-family browser:

```bash
task test:web:browser
```

Этот запуск является обязательным Chromium gate и сохраняет machine-readable
отчёт `build/web-core/bin/browser-gate-report.json` с версиями окружения,
raw/gzip-размерами artifacts и package, startup/frame/input/resize metrics.
CI запускает тот же wrapper в job `web-runtime-chromium`. Полный contract,
Firefox manual scenario и правила deployment описаны в
[Web Runtime Browser Gate](./web-runtime-browser-gate.md). Safari в текущую
compatibility matrix не входит.

Если Chromium отсутствует в `PATH`, `TERMIN_WEB_BROWSER` должен указывать на
его executable. `build/web-core/bin/termin-web-core.mjs` — стабильная внешняя
ESM-точка входа; `termin_web_core.mjs` и `termin_web_core.wasm` являются
генерируемыми деталями. Рядом устанавливается `termin-web-host.mjs`: он одним
HTTP-запросом загружает `package.trpkg`, передаёт blob нативному
`RuntimePackageReader` без построения копии directory tree в MEMFS и вызывает
общий `RuntimePackageLoader`. Индекс blob содержит portable relative path,
offset, size и SHA-256 каждого entry; reader до загрузки manifest проверяет
уникальность путей, непрерывность bounds и content hashes. Directory reader
остаётся каноническим путём native hosts, а оба provider-а используют общую
валидацию manifest/resources/scenes. Кадры исполняются
через настоящий `requestAnimationFrame`; `reload()` и `teardown()` останавливают
цикл и уничтожают native scenes; blob освобождается вместе с package result.
Provider API оставляет точку расширения для HTTP range/cache reader, но runtime
не содержит автоматических fallback-слоёв или speculative streaming policy.

Node smoke детерминированно проверяет этот lifecycle поверх настоящего Wasm,
включая repeated load, cleanup, HTTP 404/path traversal и fail-closed отказ
неподдерживаемых component/resource domains. Browser smoke управляет живой
страницей через Chrome DevTools и принимает только фактический terminal marker
из DOM; наличие marker-текста в исходнике страницы не считается успехом. После
host lifecycle он выбирает графический backend для
`#termin-canvas`, загружает strict-export package с camera/mesh/texture/material,
рендерит его через `EngineCore`/`RenderingManager` и проверяет пиксели canvas,
reload, teardown, resize и финальный shutdown. В Emscripten показ выполняется
browser в конце RAF callback, зарегистрированного через HTML5 API;
`wgpuSurfacePresent` там вызывать нельзя. WebGL2 рисует тем же engine path в
offscreen texture и переносит её в default framebuffer canvas. После
`await host.teardown()` владелец модуля может вызвать `core.shutdown()`: метод
освобождает graphics state и
полностью выключает Render registry bootstrap. Shutdown идемпотентен, а
последующая загрузка package заново поднимает registry; вызов во время
асинхронной инициализации graphics backend отклоняется с записью ошибки в лог.

Host по умолчанию использует `graphicsBackend: "auto"`: сначала проверяет
реальный WebGPU adapter, а при его отсутствии выбирает WebGL2. Поэтому
публичной странице не нужны Chromium command-line flags, а WebGPU secure-context
ограничение не делает её недоступной в браузере с WebGL2. Выбор виден в
`host.graphicsBackend`, metrics, DOM `data-graphics-backend` и startup log.
Для диагностики можно передать `graphicsBackend: "webgpu"` или `"webgl2"`; в
`visual-scene.html` тому же служит query `?backend=auto|webgpu|webgl2`. Явно
выбранный backend не переключается молча на другой.

Для ручной проверки рядом с smoke harness устанавливается `viewer.html` —
полноэкранная пользовательская оболочка над тем же host и strict package:

```bash
cd build/web-core/bin
python3 -m http.server 8062 --bind 127.0.0.1
# открыть http://127.0.0.1:8062/viewer.html
```

`termin-web-input.mjs` является отдельным browser adapter, а не частью scene
domain. Он переводит pointer/mouse/wheel/keyboard/text events в существующий
Termin display input contract, управляет pointer capture и синхронизирует
canvas backing size с CSS-размером и `devicePixelRatio`. В web fixture левая
кнопка мыши вращает камеру, правая перемещает target, колесо меняет дистанцию;
обычный desktop default контроллера сохраняет вращение средней кнопкой.
Web host, как и desktop player, создаёт и владеет
`tc_viewport_input_manager` для каждого runtime viewport с input mode
`simple`/`basic`. Одного display router недостаточно: без viewport manager
события принимаются adapter-ом и учитываются в метриках, но не доходят до
scene input handlers.
ResizeObserver и window resize ведут к повторной конфигурации WebGPU surface
либо WebGL2 drawing buffer и общего offscreen display; blur/visibility loss
сбрасывают зажатые кнопки и клавиши. Device/context loss переводит host в
ошибочное состояние с записью причины в лог.
Browser smoke проверяет этот путь сквозным жестом: кадр обязан измениться после
orbit/wheel input, а backing surface — после CSS resize. При проверке viewer
HUD скрывается, поэтому изменение счётчика событий не может дать
ложноположительный результат вместо изменения самой сцены.

`TERMIN_PLATFORM_WEB` принудительно включает render-only варианты bootstrap,
runtime, render components, render passes и default pipeline. Web closure
содержит scene, mesh, image codecs, texture/material/shader loaders, display и
engine, но исключает editor/app/Python, audio, prefab, foliage, UI, voxels,
navmesh и FEM. Runtime сохраняет тот же публичный `RuntimePackageLoader` и
package-v2 contract; offline export обязан приложить WGSL artifacts и sidecar
v3. Обычная native-сборка сохраняет full profile по умолчанию. Host выбирает
профиль явно через `RuntimePackageLoadOptions::bootstrap_profile`; minimal
profile принимает core-only package-v2 scene и до десериализации отклоняет
неподдерживаемые resources, components и scene extensions с логированной
ошибкой.

### Offline WGSL audit

Web shader gate использует общий закреплённый Slang toolchain, а Naga
независимо парсит и валидирует полученный WGSL. Slang зафиксирован в
`build-system/slang-toolchain-lock.json`, специфичный для Web-аудита Naga — в
`build-system/web-shader-toolchain-lock.json`. Полный каталог built-in Slang
shaders проверяется одной командой:

```bash
task check:webgpu-shaders -- --setup
```

Web-аудит устанавливает Slang и Naga в игнорируемый репозиторием
`build/toolchains`, поэтому `build-web-core.sh --setup` работает до сборки SDK и
не изменяет пользовательские настройки редактора. Общий native workflow по-
прежнему использует `setup-slang-toolchain.sh` и `Shader/slangCompiler`. WGSL,
reflection и machine-readable report пишутся в `build/web-shader-audit`.
Проверка требует явных уникальных
`@group`/`@binding`, std140 lowering для uniform buffers, валидного matrix
lowering и отдельных texture/sampler bindings. Текущий полный отчёт лежит в
[Built-in Slang → WGSL audit](analysis/2026-08-02-builtin-slang-wgsl-audit.md).

### Constrained GL shader artifacts

`TERMIN_BUILTIN_SHADER_ARTIFACT_TARGETS` accepts `opengl330` and `webgl2` in
addition to the modern backend targets. Both targets require the repository
submodule `termin-thirdparty/spirv-cross`; the host `termin_shaderc` links its
GLSL translator directly, so SDK and offline builds do not depend on an
ambient `spirv-cross` executable.

The output roots are `share/termin/shaders/opengl330/` for GLSL 330 and
`share/termin/shaders/webgl2/` for GLSL ES 300. Runtime package profiles use
the same target names, keeping constrained artifacts separate from modern
OpenGL artifacts.

Desktop SDK builds with OpenGL enabled always compile and install the
`opengl330` matrix. This makes the installed constrained tier an offline
runtime: build-host tools produce the artifacts, while the deployed editor or
application only reads `sdk/share/termin/shaders/opengl330`. `--no-opengl`
keeps the SDK source-only for GL and does not require Slang. Windows OpenGL SDK
builds add `opengl330` alongside the existing D3D11 artifact matrix.

GLSL 3.30 / ES 3.00 lack the binding and cross-stage location facilities used
by the modern profile. `termin_shaderc` therefore emits stable symbolic block
and varying names and compact per-program texture/UBO bindings in their layout
sidecars. The runtime resolves those names after program link; logical
cross-backend binding numbers must not be passed directly to GL texture units.

Web build не компилирует Slang в браузере. `task build:web` сначала строит
native host-tool `termin_shaderc`, использует закреплённые `slangc` и Naga, а
затем один раз генерирует полные `webgpu` и `webgl2` builtin matrices в
`build/web-core-host-tools/share/termin`. Версионированный
`builtin-shader-artifacts.json` перечисляет каталог, stage artifacts, layout
sidecars и их SHA-256. Browser fixture и внешние runtime-package exporters
берут built-in стадии из этого общего корня; несовместимый, неполный или
изменённый корень отвергается до упаковки.

Package-specific material/pipeline stages по-прежнему собираются во время
export, потому что зависят от содержимого сцены. Exporter принимает
`shader_artifact_cache_dir`: content-addressed key включает compiler и внешние
toolchains, target/language/stage/entry/debug name и содержимое полного набора
program sources. В логе каждая холодная стадия отмечается как `compiling` с
длительностью, а повторная — как `cache hit`. Готовый `package.trpkg` остаётся
самодостаточным и не требует compiler toolchain или сети в браузере.

`termin_web_visual_scene_browser_smoke` принудительно использует software
WebGL2 только внутри headless CI, проверяет retained VisualScene2D, packaged 3D
runtime, пиксели и resize. Это не требование к flags конечного браузера. Старый
`termin_web_core_browser_smoke` остаётся отдельной WebGPU-регрессией.

### Offline WebGPU shader artifacts

Audit проверяет совместимость исходников и upstream-компиляторов, а production
artifact path проходит через `termin_shaderc --target webgpu`. Компилятор
принимает Slang vertex, fragment и compute stages, нормализует все ресурсы в
WebGPU bind group 0, разделяет combined texture/sampler placement, записывает
sidecar contract version 3 и только затем принимает WGSL после независимой
проверки Naga. Geometry stages завершаются явной ошибкой.

Общий Slang toolchain можно установить независимо от Web-аудита:

```bash
task toolchain:slang
```

На Windows используется эквивалентная команда:

```powershell
task toolchain:slang
```

Скрипт проверяет checksum и версию закреплённого официального архива,
устанавливает его по умолчанию в
`${XDG_DATA_HOME:-~/.local/share}/termin/toolchains/slang-<version>` и записывает
полный путь к `slangc` через `tcbase.Settings("termin")`. Python- и C++-хосты
читают строковый ключ `Shader/slangCompiler` из того же
`~/.config/termin/settings.json`; переменная `TERMIN_SLANG_TOOLCHAIN_DIR`
переопределяет только каталог установки. На Windows официальный ZIP
устанавливается без прав администратора в
`%LOCALAPPDATA%\Termin\Toolchains\slang-<version>`, а общий Settings API пишет
тот же ключ в `%APPDATA%\termin\settings.json`.

Source-project editor проверяет `slangc` до загрузки проектных shader sources.
Если compiler отсутствует, редактор показывает одно warning-окно со ссылкой на
`Edit > Settings... > Slang Compiler` (`Shader/slangCompiler`), а CLI/player
пишет тот же actionable warning в лог. Неверный configured path выводится
целиком. Artifact-only runtime этот dev-toolchain check не выполняет.

CLI также принимают явные `--slangc` / `TERMIN_SLANGC` и
`--wgsl-validator` / `TERMIN_WGSL_VALIDATOR`; fallback в runtime-компиляцию не
предусмотрен. После `task check:webgpu-shaders -- --setup` полный built-in набор
можно сгенерировать напрямую, подставив путь из настройки:

```bash
sdk/bin/termin_python termin-graphics/cmake/compile_builtin_shader_artifacts.py \
  --shaderc build/Release/bin/termin_shaderc \
  --slangc "$HOME/.local/share/termin/toolchains/slang-2026.5.2/bin/slangc" \
  --wgsl-validator build/toolchains/naga-30.0.0/bin/naga \
  --source-dir termin-graphics/resources/builtin_shaders \
  --output-root build/webgpu-builtin-artifacts \
  --target webgpu
```

Для SDK staging тот же target включается на configure:

```bash
TERMIN_SLANGC="$HOME/.local/share/termin/toolchains/slang-2026.5.2/bin/slangc" \
TERMIN_WGSL_VALIDATOR="$PWD/build/toolchains/naga-30.0.0/bin/naga" \
cmake -S . -B build/webgpu-sdk \
  -DTERMIN_BUILD_BUILTIN_SHADER_ARTIFACTS=ON \
  -DTERMIN_BUILTIN_SHADER_ARTIFACT_TARGETS=webgpu
```

Project runtime package exporter также принимает явный `webgpu` в
`shader_targets` и пишет `.wgsl` вместе с обязательным соседним
`.layout.json`. WebGPU backend потребляет WGSL и sidecar v3 напрямую; runtime
Slang compiler и скрытый reflection fallback в браузер не входят.
