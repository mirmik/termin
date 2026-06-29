# Аудит build/runtime системы

Дата: 2026-06-17

Обновлено 2026-06-29: legacy broad-copy `termin.project_builder`,
`build.json`/`assets/manifest.json`, `termin.player --build` и
`termin_runner --mode legacy-build` удалены. Editor `Build` / `Run Build`
переведен на desktop bundle через `termin.project_build`.

## Область

Проверены:

- C++ CLI: `termin_builder`, `termin_runner`, `termin`;
- Python build слой: `termin.project_build`;
- runtime package exporter/loaders: Python exporter, Python player loader, C++ `termin-runtime`;
- desktop bundle packager и `termin_player`;
- Android SDK/APK wrapper;
- Quest/OpenXR SDK/APK wrapper;
- документация и тесты вокруг этих путей.

Kanboard context уже содержит связанный кластер задач:

- #5, #7, #8 - Android/OpenXR smoke/regression/runtime checks;
- #26 - runtime shader artifacts в Project Build;
- #27-#33 - desktop standalone runtime bundle;
- #34 - shutdown crash packaged `termin_player`;
- #39 - explicit include policy для dynamic `from_name` ресурсов;
- #40 - вынос asset runtime из `termin-app`.

## Краткий вывод

Система уже ушла дальше состояния "как-то собирает": появился правильный
центральный артефакт `runtime package`, desktop build переведен на переносимый
bundle, а старый broad-copy build contract удален.

Главное направление cleanup: держать `termin.project_build` единственной build
оркестрацией и формализовать `runtime package` как версионированный контракт.

## Текущая карта pipeline

### Build Profile CLI

`termin_builder` читает `project_settings/build_profiles.json` и запускает
канонический Python profile backend:

```text
python3 -m termin.project_build.profile_build build ...
```

Код: `termin-cli/src/termin_builder.cpp`.

Старый переходный entrypoint `termin.project_builder.profile_build` и весь
`termin.project_builder` package удалены: profile dispatch теперь живет только
в `termin.project_build.profile_build`.

### Новый Project Build

`termin.project_build` содержит практические wrapper-ы:

- `build_desktop_project(...)`;
- `build_android_project(...)`;
- `build_quest_openxr_project(...)`;
- `export_runtime_package(...)`;
- packager Python modules/runtime SDK для desktop.

Все platform builds сначала пишут `package/manifest.json` через
`export_runtime_package(...)`, затем упаковывают platform-specific wrapper:

- desktop: `app.json`, `bin/termin_player`, `lib/`, bundled Python, `package/`;
- Android: `build-android-apk.sh` + `termin-android/platform`;
- Quest/OpenXR: `build-quest-openxr-apk.sh` + `termin-openxr/platform`.

### Runtime Package

Экспортер пишет:

- `manifest.json`;
- `scene.json`;
- `meshes/*.tmesh.json`;
- `materials/*.tmat.json`;
- `shaders/*.shader.json`;
- `shaders/vulkan/*.spv`;
- `shaders/opengl/*.glsl` для Slang/OpenGL;
- `pipelines/*.pipeline.json`;
- дополнительные engine shader artifacts.

Потребители:

- C++ `termin-runtime::RuntimePackageLoader`;
- Python `termin.player.runtime_package_loader`;
- Android runtime через C++ loader;
- OpenXR scene runtime через C++ loader плюс свой pipeline factory.

## Findings

### 1. Profile targets задокументированы шире, чем поддержаны

`termin-app/docs/termin-cli.md` показывает профиль:

```json
"quest": {
  "target": "quest_openxr",
  "entry_scene": "Main.scene",
  "output_dir": "dist/quest"
}
```

Но `termin_builder` отвергает все targets кроме `desktop`. Android и Quest build
доступны из editor UI/Python API, но не как нормальные profile targets CLI.

Риск: пользовательская модель `termin build PROFILE` расходится с кодом, а
Android/OpenXR остаются side-channel actions вместо равноправных build targets.

Направление:

- завести единый Python profile backend в `termin.project_build.profile_build`;
- поддержать `desktop`, `android`, `quest_openxr`;
- C++ `termin_builder` должен только резолвить профиль и передавать target,
  не содержать target-specific branching кроме ранней валидации;
- обновить `termin_runner` policy для non-desktop targets: build-only, install,
  deploy, run-on-device должны быть явными modes.

### 2. Старый broad-copy project build удален

Packaged build backend живет в `termin.project_build`. Editor generic build
теперь вызывает desktop bundle build, а старый `build.json/assets` contract
удален вместе с `termin.project_builder`.

Оставшийся риск: тесты и документация должны продолжать закреплять, что новый
desktop build чистит stale broad-copy output и не возвращает compatibility shim.

### 3. Runtime package contract существует в коде, но не как схема

`export_runtime_package(...)`, C++ `RuntimePackageLoader` и Python
`load_runtime_package_assets(...)` отдельно знают, что такое `manifest.json`,
`shader`, `mesh`, `material`, `pipeline`, `foliage_data`.

Расхождения уже видны:

- C++ loader пропускает `pipeline`, Python loader тоже пропускает, OpenXR отдельно
  читает pipeline artifacts для factory;
- C++ loader умеет `foliage_data`, Python player только логирует warning;
- C++ loader инферит material UBO layout из GLSL fragment source;
- Python loader читает shader artifact layout для material texture bindings;
- engine shader artifacts пишутся в package, но не являются полноценными
  manifest resources.

Риск: exporter может начать писать поле, которое один runtime понимает, а другой
молча пропускает или интерпретирует иначе. Для Android/OpenXR это особенно
опасно, потому что runtime feedback device-only.

Направление:

- описать `runtime_package.schema.json` или dataclass/pydantic-like contract без
  runtime imports;
- добавить schema validation в exporter до записи и в loaders перед загрузкой;
- добавить contract tests: один generated package должен проходить Python
  validation и C++ loader smoke;
- определить policy для optional resource types: unsupported должно быть
  explicit capability error, а не platform-specific warning.

### 4. Asset graph все еще опирается на live/editor registry

`build_desktop_project`, `build_android_project` и `build_quest_openxr_project`
перед export вызывают `preload_project_resources(...)`. Этот helper импортирует
`termin.default_assets.resource_manager.DefaultResourceManager` и
`termin.default_assets.default_preloaders.create_default_preloaders`, затем
сканирует файлы проекта.

`export_runtime_package(...)` собирает refs эвристикой по serialized scene JSON,
дополнительно включает все `.material` из проекта как workaround для dynamic
`TcMaterial.from_name(...)`, а при недоступном registry entry пишет fallback
mesh/material.

Риск: build correctness зависит от editor-side preloaders, текущего процесса,
порядка импортов и live registries. Fallback artifacts скрывают реальные
missing dependency ошибки и годятся только для раннего smoke, не для release.

Направление:

- build graph должен строиться из asset runtime API, а не из editor_core;
- #40 должен стать блокером для качественного build cleanup: `ResourceManager`,
  typed registries и default plugins должны выйти из `termin-app`;
- #39 должен стать явной include policy для dynamic resources;
- fallback mesh/material оставить только для `dev_smoke` profile, в normal/release
  profiles missing resource должен быть error;
- диагностика должна различать `warning` smoke fallback и `error` packaged build
  violation.

### 5. Desktop bundle продвинулся, но dependency policy еще не продуктовая

`build_desktop_project(...)` уже пишет `app.json`, `package/`, копирует
`termin_player`, native libraries, Python home и SDK Python overlay. Это хороший
новый основной путь.

Оставшиеся риски:

- third-party Python requirements копируются из текущего build environment через
  `importlib.metadata`, без lockfile/build isolation;
- native libs копируются glob-ами `*.so`, `*.so.*`, `*.dylib`, `*.dll`;
- Linux system libs явно не vendored;
- stale `build.json/assets` output должен удаляться новым desktop build.

Направление:

- ввести build profile tiers: `dev`, `portable-local`, `release`;
- requirements policy: lock/resolved manifest, build env validation, отчет о
  missing wheels/native deps;
- native dependency manifest: что bundled, что system prerequisite;
- не возвращать legacy `build.json` launcher path после relocated smoke.

### 6. Android и Quest/OpenXR имеют общий package, но разные asset delivery

Оба Python build wrapper-а используют `export_runtime_package(...)`.

Regular Android:

- Gradle берет `terminAndroidAssetsDir` как `assets.srcDir`;
- Java Activity передает asset root в JNI;
- `termin-android/src/bootstrap.cpp` грузит runtime package из asset root.

Quest/OpenXR:

- Gradle генерирует `termin_asset_index.txt`;
- NativeActivity копирует assets во внутренний data path;
- OpenXR runtime грузит package уже из скопированной директории.

Риск: platform bugs будут не только в render loop, но и в разных способах
доставки package files. В частности, OpenXR может ловить path/copy bugs, которых
нет в regular Android.

Направление:

- выделить общий Android asset package delivery helper/contract;
- сделать явный invariant: runtime package root всегда filesystem directory или
  всегда abstract asset provider;
- regular Android и OpenXR должны проходить один asset delivery smoke test;
- `build_quest_openxr_project(...)` нужен unit test уровня
  `test_build_android_project_exports_package_and_copies_apk`.

### 7. Quest/OpenXR пока остается smoke target, не полноценным build target

`build_quest_openxr_project(...)` собирает project package, но APK hardcodes:

- `applicationId "org.termin.openxr"`;
- NativeActivity;
- smoke naming/logging;
- отдельный `termin-openxr/platform`;
- fallback OpenXRScene pipeline в runtime.

`build-quest-openxr-apk.sh` проверяет наличие `termin_openxrConfig.cmake`, но
сам `termin-openxr` может быть собран как placeholder без OpenXR headers, если
headers не найдены при SDK build.

Риск: "Quest build succeeded" может означать "APK собрался", но не "runtime XR
path реально доступен". Это уже отражено в #8, но build layer тоже должен это
диагностировать.

Направление:

- SDK install должен экспортировать capability metadata: OpenXR headers/runtime
  enabled, Vulkan XR path enabled, loader linked/available;
- Quest APK build должен проверять capability metadata, а не только CMake config;
- отделить `quest_openxr_smoke` от будущего `quest_openxr_project`;
- добавить device smoke как отдельную release gate, не смешивать с assembleDebug.

### 8. Platform runtime содержит много build/runtime glue

`termin-android/src/bootstrap.cpp` и `termin-openxr/src/openxr_android_runtime.cpp`
делают не только platform bootstrap, но и:

- ручную регистрацию scene/component/render extensions;
- создание pipeline fallback;
- shader artifact root setup;
- runtime package loading;
- smoke renderer lifecycle;
- Android/OpenXR lifecycle handling.

Есть дубли, например `UIWidgetPass` в Android и OpenXR paths.

Риск: исправления build/runtime contract требуют править platform bootstrap,
а не общий runtime слой. Это замедляет стабилизацию Android/OpenXR.

Направление:

- выделить shared native player bootstrap: register runtime extensions, load
  runtime package, configure shader runtime, create pipeline factory;
- platform layer должен давать только window/XR swapchain/surface, filesystem
  package root и lifecycle events;
- smoke renderer оставить отдельной диагностической целью.

## Рекомендованный порядок cleanup

### Этап 1. Зафиксировать canonical contracts

1. Создать документ `runtime-package.md` или schema file рядом с exporter/loader.
2. Ввести contract validation и tests для `manifest.json`/resource specs.
3. Добавить test для `build_quest_openxr_project(...)`.
4. Обновить `termin-cli.md`: либо убрать `quest_openxr` из профиля до реализации,
   либо реализовать target routing сразу.

### Этап 2. Удержать единственный packaged build path

1. `profile_build.py` уже перенесен в `termin.project_build`; не возвращать
   старый `termin.project_builder.profile_build` entrypoint.
2. Сделать `termin.project_build` единственной публичной точкой packaged builds.
3. Не возвращать broad-copy exporter, `build.json` launcher path или
   `termin_runner` legacy mode.

### Этап 3. Построить нормальный asset graph

1. Продвинуть #40: вынести asset runtime из `termin-app`.
2. Продвинуть #39: explicit include policy для dynamic resources.
3. Убрать fallback mesh/material из normal build profiles.
4. Покрыть textures/fonts/audio/UI/navmesh/voxels/modules как package resources
   (#32).

### Этап 4. Сделать Android/OpenXR равноправными targets

1. Реализовать `target: "android"` и `target: "quest_openxr"` в profile backend.
2. Унифицировать Android asset delivery.
3. Добавить SDK capability metadata для OpenXR.
4. Разделить smoke APK и project APK semantics.
5. Ввести build smoke + device smoke gates.

## Практический следующий шаг

Самый полезный ближайший технический срез:

1. завести `termin.project_build.profile_build` с target dispatch;
2. переключить `termin_builder` на передачу `profile.target`;
3. добавить `quest_openxr` и `android` как build-only profile targets;
4. добавить tests на CLI/profile routing без реального Gradle через fake backend;
5. обновить `termin-cli.md`.

Это сразу снимет расхождение документации и CLI, не ломая текущую desktop bundle
работу, и даст нормальную рамку для последующих asset/runtime cleanup задач.
