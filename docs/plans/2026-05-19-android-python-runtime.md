# Android build and embedded Python runtime plan

Дата: 2026-05-19

Статус: рабочая архитектурная заметка. Это не финальная спецификация, а карта решений и рисков для Android-порта Termin.

## Короткий вывод

Android-порт лучше разделить на два независимых слоя:

1. **Android native SDK/runtime**: C/C++ библиотеки Termin, собранные Android NDK toolchain под нужные ABI.
2. **Android app/APK**: Activity, Android lifecycle, surface, assets, embedded Python runtime и упаковка.

Gradle не обязан владеть сборкой C++ SDK. CMake должен остаться владельцем native-графа. Gradle нужен только как практичный упаковщик APK/AAB: manifest, assets, resources, JNI libs, variants, signing.

Для первого этапа разумнее начать вообще без Gradle:

1. Научить CMake собирать Android runtime libraries.
2. Проверить, какие цели ломаются на Android toolchain.
3. После этого добавить минимальный Android wrapper project.

## Фактическая проверка NDK

Проверено 2026-05-19 на Android SDK в `/home/mirmik/Android/Sdk`:

- установлен NDK `27.2.12479018` (`r27c`);
- первый configure полного monorepo-графа уперся в desktop OpenGL: `termin-graphics` безусловно вызывает `find_package(OpenGL REQUIRED)`;
- добавлен CMake-флаг `TERMIN_PLATFORM_ANDROID`, который включает native Android profile без Python, тестов, desktop SDL, editor/launcher и desktop app/executable стека;
- добавлен отдельный CMake-флаг `TERMIN_ENABLE_OPENGL`; при `OFF` monorepo не ищет и не линкует desktop `OpenGL::GL`, но оставляет Vulkan render/editor targets в графе;
- Android smoke build под `arm64-v8a` успешно сконфигурирован, собран и установлен в тестовый prefix `/tmp/termin-android-smoke`.
- Android render build под `arm64-v8a` успешно сконфигурирован, собран и установлен в тестовый prefix `/tmp/termin-android-render`.

Расширенный Android render profile теперь собирает:

- `termin-graphics` / `termin_graphics2` без OpenGL;
- Vulkan backend через NDK `libvulkan.so`;
- `termin-materials`;
- `termin-render`;
- `termin-display` без SDL;
- `termin-components-render`;
- `termin-engine`.

Для Android `TGFX2_ENABLE_SHADERC` по умолчанию выключен: NDK содержит Vulkan headers/libs, но не готовую target-библиотеку `shaderc`. Vulkan runtime на Android принимает precompiled SPIR-V bytecode. Host-сборка теперь имеет первый offline shader compilation path: редактор собирает используемые сценой `TcShader`/варианты, вызывает host `termin_shaderc`, кладет SPIR-V в `assets/shaders/vulkan/<shader-uuid>.<stage>.spv`, а Vulkan runtime ищет эти artifacts перед fallback на runtime GLSL.

Рабочий вызов через корневой helper:

```bash
./build-sdk-android.sh \
  --ndk /home/mirmik/Android/Sdk/ndk/27.2.12479018 \
  --abi arm64-v8a \
  --platform android-26
```

По умолчанию он собирает `build/android/<ABI>` и устанавливает Android SDK prefix в `sdk/android/<ABI>`.

Эквивалентный ручной CMake вызов:

```bash
cmake -S . -B build/android/arm64-v8a \
  -DCMAKE_TOOLCHAIN_FILE=/home/mirmik/Android/Sdk/ndk/27.2.12479018/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-26 \
  -DCMAKE_BUILD_TYPE=Release \
  -DTERMIN_PLATFORM_ANDROID=ON

cmake --build build/android/arm64-v8a --parallel 8

cmake --install build/android/arm64-v8a --prefix /tmp/termin-android-smoke
```

Для проверки расширенного профиля использовался тот же build directory и install prefix `/tmp/termin-android-render`:

```bash
cmake --build build/android/arm64-v8a --parallel 8
cmake --install build/android/arm64-v8a --prefix /tmp/termin-android-render
```

Собранные `.so` в первом Android smoke-профиле:

```text
libtermin_base.so
libtermin_modules.so
libtermin_mesh.so
libtermin_csg.so
libtermin_navmesh.so
libtermin_inspect.so
libtermin_scene.so
libtermin_input.so
libtermin_collision.so
libtermin_physics.so
libtermin_components_mesh.so
libtermin_components_collision.so
libtermin_components_kinematic.so
```

Дополнительно в расширенном Android render profile собираются и устанавливаются:

```text
libtermin_graphics.so
libtermin_graphics2.so
libtermin_materials.so
libtermin_render.so
libtermin_display.so
libtermin_components_render.so
libtermin_engine.so
```

Ограничение этого результата: это пока не player/runtime с Android surface/app wrapper. `termin-app/cpp`, skeleton/animation components и `tcplot` остаются вне Android-графа. Offline shader pipeline уже закрывает первый SPIR-V path для `termin-app` project builder, но Android wrapper еще должен упаковывать эти assets и выставлять shader artifact root при запуске runtime.

No-OpenGL host editor smoke build:

```bash
cmake -S . -B build/no-opengl-editor \
  -DCMAKE_BUILD_TYPE=Release \
  -DTERMIN_ENABLE_OPENGL=OFF \
  -DTERMIN_ENABLE_VULKAN=ON \
  -DTERMIN_BUILD_PYTHON=OFF \
  -DTERMIN_BUILD_TESTS=OFF \
  -DTERMIN_BUILD_EDITOR_MINIMAL=ON \
  -DTERMIN_BUILD_LAUNCHER=ON \
  -DTERMIN_BUNDLE_PYTHON=ON

cmake --build build/no-opengl-editor --parallel 8
```

This builds `termin_editor` and keeps `libvulkan.so.1` / `libshaderc.so.1` dependencies while avoiding direct `libGL` linkage. SDK scripts also accept `--no-opengl`. As of the WPF/D3D11 C# migration, `build-sdk-csharp.sh` no longer skips this mode; it builds C# bindings with legacy OpenGL entrypoints disabled.

## Что сейчас мешает Android

Часть desktop-центричных зависимостей уже снята, но оставшиеся риски важны:

- SDL2 ищется как desktop/system package через `find_package(SDL2)` или `pkg-config`; Android-профиль сейчас собирает `termin-display` без SDL.
- Vulkan path на Android собран через NDK `libvulkan.so`, но runtime GLSL compilation отключен без `shaderc`.
- Python-пакеты устанавливаются через host `pip` и предполагают `$TERMIN_SDK`.
- `termin-app` содержит desktop/editor код, включая SDL desktop backend и tooling.

Это означает, что следующий слой должен быть не очередным desktop executable, а отдельный Android wrapper/lifecycle/surface profile.

## Предлагаемый native Android profile

В CMake стоит добавить явный флаг:

```cmake
option(TERMIN_PLATFORM_ANDROID "Build Termin for Android" OFF)
```

При `TERMIN_PLATFORM_ANDROID=ON`:

- `TERMIN_BUILD_PYTHON=OFF` для первого native smoke build.
- `TERMIN_BUILD_TESTS=OFF`.
- `TERMIN_BUILD_EDITOR_MINIMAL=OFF`.
- `TERMIN_BUILD_LAUNCHER=OFF`.
- `TERMIN_BUNDLE_PYTHON=OFF` на первом шаге.
- desktop SDL выключен.
- desktop OpenGL не требуется.
- собираются только runtime-библиотеки, нужные viewer/app.

Пример первого CMake вызова:

```bash
cmake -S . -B build/android/arm64-v8a \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-26 \
  -DCMAKE_BUILD_TYPE=Release \
  -DTERMIN_PLATFORM_ANDROID=ON \
  -DTERMIN_BUILD_PYTHON=OFF \
  -DTERMIN_BUILD_TESTS=OFF \
  -DTERMIN_BUILD_EDITOR_MINIMAL=OFF \
  -DTERMIN_BUILD_LAUNCHER=OFF \
  -DTERMIN_BUNDLE_PYTHON=OFF
```

## APK/App layer

Для реального приложения нужен тонкий Android wrapper. Android-specific код держим в отдельном модуле `termin-android`, чтобы не размазывать Activity/JNI/assets/lifecycle glue по runtime-библиотекам.

Первый native слой уже заведен как CMake module:

```text
termin-android/
  include/termin/android/bootstrap.h
  src/bootstrap.cpp
```

Его текущая ответственность:

- хранить Android bootstrap config (`app_data_dir`, `asset_root`, `native_lib_dir`);
- принимать `ANativeWindow` lifecycle callbacks;
- выставлять shader artifact root в tgfx2 через `tgfx2_set_shader_artifact_root`;
- собираться только при `TERMIN_PLATFORM_ANDROID=ON`.

Следующий Gradle/JNI слой должен жить рядом:

```text
termin-android/platform/
  settings.gradle
  build.gradle
  app/build.gradle
  app/src/main/AndroidManifest.xml
  app/src/main/java/.../MainActivity.kt
  app/src/main/cpp/CMakeLists.txt
```

Возможны два режима:

1. Gradle `externalNativeBuild` напрямую подключает monorepo CMake.
2. `build-sdk-android.sh` собирает SDK отдельно, а Gradle только копирует/линкует готовые `.so`.

Для Termin второй режим выглядит чище на старте: CMake SDK остается отдельной проверяемой единицей, Gradle отвечает только за Android package.

## Window/surface model

Текущий desktop путь через SDL/OpenGL не надо считать Android-основой.

Для MVP нужен отдельный Android backend:

- Java/Kotlin `Activity`.
- `SurfaceView` или `NativeActivity`.
- C++ получает `ANativeWindow`.
- native слой управляет surface lifecycle, resize, pause/resume.
- Python не владеет окном и lifecycle.

## Render backend choice

### OpenGL ES

На Android доступен OpenGL ES, но текущий graphics path завязан на desktop OpenGL/GLAD и `OpenGL::GL`. Значит GLES потребует отдельного backend/адаптации API.

Это возможно, но не является "простой Android-сборкой".

### Vulkan

Vulkan выглядит более реалистичным первым backend для Android, потому что уже есть tgfx2 Vulkan path. Но есть отдельный риск: текущий path зависит от `shaderc` во время runtime/build. Для Android лучше уйти к offline shader compilation:

- хост-компиляция GLSL/HLSL в SPIR-V на этапе сборки;
- SPIR-V кладется в assets или compiled resources;
- Android runtime только загружает готовые shader blobs.

Статус 2026-05-19: первый GLSL -> SPIR-V path реализован для editor project build. `Drawable` получает API объявления shader usages, `SkinnedMeshRenderer` объявляет базовый и skinned-вариант, `collect_scene_shader_usages` собирает usages из сцены, `termin.project_builder.shader_build` пишет временные `.build/shaders/source/*.glsl` и готовые `assets/shaders/vulkan/*.spv`. Следующий недостающий кусок для Android: packaging/lifecycle layer должен передать runtime путь к unpacked assets через `tgfx2_set_shader_artifact_root` или `TERMIN_SHADER_ARTIFACT_ROOT`.

## Как подключать Python

Python на Android должен быть embedded runtime внутри native app, а не самостоятельная среда с `pip install`.

Общая схема:

```text
Android Activity
  -> JNI / libtermin_android.so
    -> Termin native runtime
      -> embedded CPython
        -> termin_android_bootstrap.py
          -> termin.* Python packages
            -> nanobind extension modules
            -> libtermin_*.so
```

Важно: Android/C++ владеют lifecycle, surface, render loop, input, pause/resume. Python получает callbacks и управляет сценой/логикой.

## Что упаковывать в APK/AAB

Нужно четыре слоя:

1. **CPython runtime под Android**
   - `libpython3.x.so`.
   - standard library.
   - `site.py`, `importlib`, `encodings`, `zipimport` и прочие обязательные части runtime.

2. **Pure-Python packages**
   - selected `termin-app/termin/...`.
   - `termin-gui/python/tcgui/...`, если нужен in-game UI.
   - Python wrappers из `termin-base`, `termin-scene`, `termin-render`, etc.

3. **Nanobind extension modules**
   - `_base_native.so`.
   - `_scene_native.so`.
   - `_render_native.so`.
   - `_display_native.so`.
   - другие extension modules, собранные под конкретный Android ABI.

4. **Native Termin SDK libraries**
   - `libtermin_base.so`.
   - `libtermin_scene.so`.
   - `libtermin_graphics.so`.
   - `libtermin_render.so`.
   - остальные runtime `.so`.

## Где хранить Python-файлы

### Вариант A: assets + unpack on first run

```text
assets/python/stdlib/...
assets/python/site-packages/termin/...
assets/python/site-packages/tcgui/...
```

На первом запуске копировать в:

```text
/data/data/<package>/files/python/
```

Потом выставлять:

```python
sys.path = [
    "/data/data/<package>/files/python/stdlib",
    "/data/data/<package>/files/python/site-packages",
]
```

Плюсы:

- просто отлаживать;
- обычные Python-файлы лежат на файловой системе;
- меньше сюрпризов с импортами.

Минусы:

- первый запуск копирует много файлов;
- нужен version marker, чтобы обновлять распакованный runtime после апдейта APK.

### Вариант B: pure-Python в zip

```text
assets/python/stdlib.zip
assets/python/termin_runtime.zip
```

Плюсы:

- меньше файлов;
- потенциально быстрее упаковка.

Минусы:

- native extension modules из zip импортировать нельзя;
- часть кода может ожидать реальные файлы рядом с модулем.

Для первого MVP лучше вариант A.

## Почему не pip внутри APK

Текущий `install-pip-packages.sh` хорошо подходит для desktop SDK:

- собирает thin pip packages;
- копирует nanobind `.so` из `$TERMIN_SDK`;
- runtime ищет SDK через `TERMIN_SDK`, `./sdk`, `/opt/termin`.

На Android это плохо ложится:

- `$TERMIN_SDK` как системный путь отсутствует;
- host wheels не подходят для Android ABI;
- `pip` в runtime не нужен и усложняет app;
- зависимости должны быть предсобраны и явно упакованы.

Нужен отдельный staging step:

```text
build-sdk-android.sh
  -> builds native C++ libs
  -> builds nanobind modules against Android CPython
  -> stages Python packages
  -> stages jniLibs/<abi>/*.so
  -> stages assets/python/*
```

## Android-aware preload_sdk_libs

Сейчас многие пакеты вызывают:

```python
from termin_nanobind.runtime import preload_sdk_libs
preload_sdk_libs(...)
```

На Android надо добавить ветку поиска native libraries:

- не через `$TERMIN_SDK/lib`;
- а через `nativeLibraryDir`, который Java/Kotlin может передать в Python bootstrap;
- либо через app-private unpack directory, если библиотеки распаковываются вручную.

Нужен явный bootstrap config, например:

```python
termin_nanobind.runtime.configure_android(
    native_library_dir="/data/app/.../lib/arm64",
    python_home="/data/data/<package>/files/python",
)
```

После этого `preload_sdk_libs()` должен грузить зависимости из Android library dir.

## Python entrypoint

Нужен отдельный Android entrypoint, не desktop editor launcher:

```python
# termin_android_bootstrap.py

def initialize(app_data_dir: str, assets_dir: str, native_lib_dir: str) -> None:
    ...

def resize(width: int, height: int) -> None:
    ...

def input_event(event: dict) -> None:
    ...

def frame(dt: float) -> None:
    ...

def shutdown() -> None:
    ...
```

JNI/native слой вызывает эти функции.

## Render loop ownership

Python не должен владеть главным циклом.

Предпочтительная модель:

```text
Android Choreographer / native loop
  -> C++ begin_frame
  -> Python update(dt)
  -> C++ render
  -> present
```

Python может управлять:

- сценой;
- компонентами;
- UI-логикой;
- загрузкой проекта;
- пользовательскими скриптами.

C++/Android должны управлять:

- lifecycle;
- surface;
- swapchain/context;
- pause/resume;
- resize;
- input source translation;
- present.

## Внешние Python-зависимости

Для Android нужен отдельный runtime profile.

Исключить из Android runtime:

- desktop editor modules;
- desktop SDL backends;
- `pysdl2` как обязательную runtime-зависимость;
- инструменты, требующие desktop filesystem/dialogs.

Осторожно подключать:

- `numpy`: используется во многих местах, но требует Android wheel/build.
- `Pillow`: полезен для загрузки изображений, но лучше не делать обязательным в первом MVP.
- `PyYAML`: можно использовать, если есть pure-Python fallback или заранее упакованный wheel.

Возможный Android package profile:

```text
termin-runtime-android:
  include:
    termin_nanobind
    tcbase
    termin.scene
    termin.render
    termin.engine
    tcgui core, если нужен in-game UI
  exclude:
    termin.editor
    desktop SDL backend
    desktop launchers
    heavy tooling
```

## Предлагаемый порядок работ

1. Собрать Android native SDK без Python.
2. Добавить embedded CPython и выполнить `print("hello from Termin Android")`.
3. Добавить pure-Python import без native modules.
4. Добавить одну nanobind module, например `tcbase`.
5. Научить `preload_sdk_libs()` Android library lookup.
6. Подключить scene/runtime.
7. Подключить render surface и render loop.
8. Подключить project/assets bootstrap.
9. Подключить `tcgui`, если нужен in-game UI.
10. Отдельно решить `numpy`, `Pillow`, `PyYAML`.

## Основные риски

- Попытка упаковать весь desktop Python environment в APK приведет к проблемам с PyQt, SDL, numpy, Pillow и путями.
- Desktop OpenGL path нельзя считать Android-compatible.
- Runtime shader compilation через shaderc на Android может стать тяжелой зависимостью; лучше планировать offline SPIR-V.
- Нужен явный Android runtime profile, иначе editor/tooling imports будут постоянно ломать мобильную сборку.
- `preload_sdk_libs()` сейчас мыслит в терминах SDK prefix; Android требует app-local library discovery.

## Первый проверочный критерий

Минимальная техническая цель:

```text
Android device/emulator:
  app starts
  libtermin_android.so loads
  embedded CPython starts
  termin_android_bootstrap.initialize(...) runs
  tcbase native module imports successfully
  logcat shows Termin log line from Python
```

До этого момента не стоит подключать editor, project UI или полный render pipeline.
