# Целевая архитектура project build/runtime packaging

Дата: 2026-06-17

Связанные документы:

- `docs/analysis/2026-06-17-build-runtime-system-audit.md`
- `docs/plans/2026-06-07-build-system-refactor.md`
- `docs/plans/2026-05-20-termin-runtime-package-loader.md`
- `docs/plans/2026-05-20-android-scene-build-export.md`
- `docs/plans/2026-05-20-quest-openxr-foundation.md`

Связанные задачи:

- #27-#33 - desktop standalone runtime bundle;
- #39 - include policy для dynamic resources;
- #40 - asset runtime split;
- #41 - profile target dispatch для `android`/`quest_openxr`.

## Назначение

Этот документ описывает не текущее состояние, а целевую форму build system для
проектов Termin: как из project source tree и build profile получить проверяемый
runtime artifact для desktop, Android и OpenXR.

Важно разделять два уровня:

1. **SDK build** - сборка самого Termin SDK: CMake targets, Python packages,
   bindings, wheelhouse, Android SDK install tree. Этот слой уже описан в
   `2026-06-07-build-system-refactor.md`.
2. **Project build** - сборка пользовательского проекта в runtime package,
   desktop bundle, APK или другой deployable artifact.

Дальше речь идет о втором уровне.

## Главная идея

Project build должен быть обычным compiler pipeline с явными входами, фазами,
артефактами и диагностикой:

```text
Project source
  + build profile
  + SDK capability manifest
  + build environment
    |
    v
Analyze project graph
    |
    v
Compile runtime artifacts
    |
    v
Write runtime package
    |
    v
Package target wrapper
    |
    v
Validate + smoke contract
```

Ни editor file watcher, ни live `ResourceManager` registry, ни случайно
импортированные Python modules не должны быть источником истины для packaged
build. Editor может запускать build, показывать лог и сохранять сцену, но не
должен сам владеть графом ресурсов или platform packaging.

## Цели

- Единая модель build profiles для desktop, Android, Quest/OpenXR и будущих
  targets.
- Runtime package как стабильный версионированный контракт между build side и
  runtime side.
- Build graph строится из project files и asset metadata, а не из editor state.
- Runtime package валидируется до упаковки в bundle/APK.
- Desktop, Android и OpenXR используют один runtime package, различаясь только
  platform wrapper/runtime host.
- Ошибки missing resources, неподдержанных features, несовместимых profiles и
  неполного SDK обнаруживаются на build stage, а не device/runtime stage.
- Старый broad-copy project build становится явным `dev_export`, не primary
  packaged build.

## Не-цели

- Не переписывать весь CMake SDK graph.
- Не требовать одинакового runtime host для desktop window, Android surface и
  OpenXR swapchain.
- Не запрещать Python gameplay на desktop.
- Не обещать Python runtime на Android до отдельного подтвержденного решения.
- Не сохранять бесконечную compatibility с недособранными legacy artifacts.

## Термины

- **Project source** - исходный каталог проекта: `.terminproj`, scenes, assets,
  scripts, modules, settings.
- **Build profile** - декларативное описание цели сборки: target, entry scene,
  output, mode, include policy, runtime options.
- **Build graph** - нормализованный граф ресурсов, модулей и зависимостей,
  построенный из project source.
- **Runtime package** - target-independent набор compiled/runtime artifacts,
  читаемый runtime loader-ами.
- **Target wrapper** - platform-specific оболочка: desktop bundle, Android APK,
  Quest/OpenXR APK.
- **Runtime host** - executable/activity/native runtime, который читает runtime
  package и запускает сцену.
- **SDK capability manifest** - машинно-читаемый отчет установленного SDK:
  собранные modules, supported backends, OpenXR availability, Python runtime,
  shader compiler, platform SDKs.

## Целевая структура модулей

Идеальная форма после миграции:

```text
termin-build-tools/
  termin_build/
    sdk.py                         # SDK build orchestrator, already exists
    project/
      profiles.py                  # build profile schema/loading
      capabilities.py              # SDK capability checks
      graph.py                     # project build graph
      diagnostics.py               # structured diagnostics
      pipeline.py                  # phase orchestration
      reports.py                   # build report writer

termin-assets-runtime/             # name tentative
  termin/assets_runtime/
    resource_graph.py
    resource_ids.py
    import_plugins.py
    compilers/

termin-runtime/
  include/termin/runtime/
    runtime_package.hpp
    runtime_package_schema.hpp     # generated/static contract helpers
  src/
    runtime_package.cpp

termin-app/
  termin/editor_tcgui/
    project_build_controller.py    # thin UI wrapper only
```

Short-term implementation may keep Python APIs under `termin.project_build`,
but the ownership boundary should be clear: build/runtime packaging is not
editor-specific and should not remain owned by `termin-app` long term.

## Build Profile Contract

Profiles live in:

```text
project_settings/build_profiles.json
```

Target schema should be explicit and versioned:

```json
{
  "version": 1,
  "profiles": {
    "dev": {
      "target": "desktop",
      "configuration": "dev",
      "entry_scene": "Scenes/Main.scene",
      "output_dir": "dist/dev",
      "resource_policy": "dev",
      "python": {
        "enabled": true
      },
      "runtime": {
        "backend": "vulkan"
      }
    },
    "quest": {
      "target": "quest_openxr",
      "configuration": "debug",
      "entry_scene": "Scenes/XR.scene",
      "output_dir": "dist/quest",
      "resource_policy": "strict",
      "android": {
        "abi": "arm64-v8a",
        "platform": "android-26"
      },
      "openxr": {
        "required": true
      }
    }
  }
}
```

Supported targets:

- `desktop`
- `android`
- `quest_openxr`
- future: `server`, `web`, `headless_test`, if needed.

Supported configurations:

- `dev` - fastest local build, may allow explicit smoke fallbacks.
- `debug` - debuggable deploy artifact, no fake resources.
- `release` - strict diagnostics, deterministic resource set, no dev-only
  source path dependencies.

`termin_builder` should not hardcode target-specific behavior. It should:

1. find project root;
2. load profile;
3. invoke one Python backend with profile name/path;
4. return backend exit code.

The target dispatch belongs in Python because Python already owns Gradle
wrappers, package export, diagnostics and tests.

## Pipeline Phases

### Phase 0: Preflight

Input:

- project root;
- profile;
- SDK root;
- target platform;
- build environment.

Checks:

- profile schema valid;
- entry scene exists and is under project root;
- output dir is safe to clean/write;
- SDK capability manifest supports target;
- required tools are available:
  - `termin_shaderc`;
  - Gradle/Android SDK/NDK for Android;
  - OpenXR headers/loader/capability for Quest/OpenXR;
  - bundled Python runtime for desktop Python builds.

Output:

- normalized `BuildContext`;
- fatal diagnostics if target cannot be built.

Status 2026-06-18: initial Quest/OpenXR target preflight exists as
`termin.project_build.target_preflight.preflight_quest_openxr_build`. It resolves
the Quest build script, Android SDK root and Gradle path before package export,
and reports fatal environment problems through structured diagnostics carried by
`TargetPreflightError`. Current checks cover target root marker, build script
existence, Android SDK root, requested ABI, ABI `lib` directory, OpenXR CMake
package and explicitly configured Gradle paths. Remaining Phase 0 work: Android
preflight, desktop SDK/Python runtime preflight, profile entry/output safety and
SDK capability manifest integration.

### Phase 1: Project Graph Analysis

Input:

- project source tree;
- entry scene;
- profile include policy.

Responsibilities:

- load `.terminproj` and `project_settings`;
- parse scenes without editor runtime side effects;
- resolve serialized handles by UUID/name;
- collect referenced resources;
- apply explicit include rules for dynamic resources;
- collect project Python/C++ module descriptors;
- collect stdlib/runtime dependencies;
- detect duplicate UUIDs/names where runtime lookup can be ambiguous.

The graph must be deterministic:

- sorted traversal;
- no dependency on in-memory singleton state;
- no dependency on editor file watcher order;
- no silent fallback to "whatever is already loaded".

Output:

```text
build/
  graph.json
  diagnostics.json
```

`graph.json` is an internal build artifact, not the runtime package manifest.

### Phase 2: Resource Compilation

Compile source assets into runtime artifacts.

Examples:

- `.scene` -> `scene.json` or future compiled scene format;
- mesh sources -> `.tmesh` binary or JSON transition format;
- materials -> `.tmat` with phases, uniforms, texture refs;
- shaders/material phases -> per-target artifacts:
  - Vulkan SPIR-V;
  - OpenGL GLSL;
  - layout sidecars;
- pipelines -> runtime pipeline artifacts;
- textures -> runtime texture artifacts or copied source with metadata;
- fonts/UI/audio/navmesh/voxels/foliage -> typed runtime artifacts;
- Python modules -> packaged module tree + `modules.json`.

No compiler should hide missing inputs by creating placeholder assets in strict
profiles. Placeholder/fallback artifacts are only allowed under an explicit
`resource_policy: dev_smoke` style option and must produce visible diagnostics.

Output:

```text
package/
  scene.json
  manifest.json
  meshes/
  materials/
  shaders/
  pipelines/
  textures/
  audio/
  fonts/
  ui/
  navmesh/
  voxels/
  foliage/
  python/
```

### Phase 3: Runtime Package Validation

The runtime package must validate before target packaging.

Checks:

- `manifest.json` schema version known;
- all resource paths are relative and stay inside package root;
- all listed resources exist;
- all referenced shader artifacts exist for target;
- no duplicate UUIDs in manifest;
- material phases reference packaged shaders;
- meshes have supported layouts for target;
- scene references resolve against packaged resources;
- platform capability requirements match profile.

Validation should be implemented once and used by:

- exporter tests;
- desktop build;
- Android build;
- Quest/OpenXR build;
- runtime loader as defensive validation.

Status 2026-06-18: initial Python validator exists as
`termin.project_build.runtime_package_validator.validate_runtime_package`.
It validates manifest readability/object shape, schema `version: 1`, relative
scene/resource paths staying inside the package root, listed file existence,
duplicate resource UUIDs, and listed shader resource artifact paths under
`*.shader.json`. Desktop, Android and Quest/OpenXR build wrappers now run this
validator after `export_runtime_package(...)` and aggregate diagnostics before
target packaging. Remaining Phase 3 work: material/pipeline graph checks,
target capability checks, and reuse from runtime loader paths.

### Phase 4: Target Packaging

#### Desktop

Desktop output:

```text
dist/<profile>/
  app.json
  bin/
    termin_player
  lib/
    *.so / *.dll / *.dylib
    python3.x/
      site-packages/
  package/
    manifest.json
    ...
  share/
    termin/
```

Desktop wrapper responsibilities:

- include runtime package;
- include `termin_player`;
- include SDK native runtime libs;
- include bundled Python if profile enables Python;
- include project Python modules and third-party requirements;
- write `app.json` with only relative paths;
- write a dependency report: bundled libs vs system prerequisites.

Desktop runtime host responsibilities:

- find bundle root;
- configure native library paths;
- configure Python home/path if enabled;
- configure shader runtime;
- load runtime package;
- load project modules;
- start player loop.

#### Android Surface

Android output:

```text
dist/android/<profile>/
  package/
  apk/
    <app>-debug.apk
  logs/
    android-build.log
```

Target wrapper responsibilities:

- use the same runtime package;
- embed or deliver package assets through a unified Android package delivery
  contract;
- include native libs from Android SDK install;
- set project-derived application id and label unless profile overrides them.

Runtime host responsibilities:

- expose a filesystem-like package root to `termin-runtime`;
- configure Vulkan/surface lifecycle;
- load runtime package;
- render through the normal scene/render pipeline.

#### Quest/OpenXR

Quest/OpenXR output:

```text
dist/quest_openxr/<profile>/
  package/
  apk/
    <app>-quest-openxr-debug.apk
  logs/
    quest-openxr-build.log
```

Target wrapper responsibilities:

- require SDK capability `openxr.enabled == true`;
- package runtime assets using the same Android delivery contract;
- include OpenXR runtime native libs;
- expose OpenXR-specific app metadata from profile.

Runtime host responsibilities:

- own OpenXR lifecycle and swapchains;
- map OpenXR frame/view state into Termin runtime camera/origin state;
- load the same runtime package;
- select XR render target/pipeline from scene metadata;
- fail loudly if the scene has no XR-compatible camera/origin/pipeline.

The smoke app and project OpenXR app should be separate profile targets or
separate configurations:

- `quest_openxr_smoke` - validates OpenXR stack;
- `quest_openxr` - runs project runtime package.

Status 2026-06-18: Android and Quest/OpenXR Python wrappers no longer share
private target-specific helpers. Common root discovery, Gradle discovery and log
tail helpers live in `termin.project_build.target_build_common`; Quest/OpenXR
root discovery keys off `build-quest-openxr-apk.sh`, not Android APK scripts.

## Runtime Package Contract

Runtime package should be target-independent where possible, target-aware where
necessary.

Root manifest sketch:

```json
{
  "schema": "termin.runtime_package",
  "version": 2,
  "package_id": "com.example.game",
  "project_name": "Game",
  "entry_scene": "scene.json",
  "shader_artifact_root": "shaders",
  "targets": {
    "desktop": {
      "graphics": ["vulkan", "opengl"]
    },
    "android": {
      "graphics": ["vulkan"]
    },
    "quest_openxr": {
      "graphics": ["vulkan"],
      "xr": true
    }
  },
  "resources": [
    {
      "type": "shader",
      "uuid": "shader-uuid",
      "path": "shaders/shader-uuid.shader.json"
    }
  ],
  "diagnostics": []
}
```

Resource specs should be versioned too:

- `*.shader.json`
- `*.tmat.json`
- `*.tmesh.json`
- `*.pipeline.json`
- future binary sidecars.

Runtime loaders should treat unknown major versions as fatal. Unknown optional
minor fields can be ignored only if schema marks them optional.

## Asset Graph and Include Policy

The build graph needs explicit resource inclusion rules.

Default source categories:

- entry scene and scene dependencies;
- referenced prefabs;
- referenced meshes/materials/textures/shaders/pipelines;
- referenced audio/UI/fonts/navmesh/voxel/foliage assets;
- project modules referenced by project/module descriptors;
- stdlib resources required by selected materials/pipelines/runtime.

Dynamic resource categories:

- `TcMaterial.from_name(...)`;
- `TcMesh.from_name(...)`;
- scripts loading by UUID/name;
- resources selected by gameplay data;
- DLC/mod/plugin resources.

These cannot be inferred reliably from serialized scene graph. They need profile
include policy:

```json
{
  "resource_includes": [
    {"type": "material", "glob": "Materials/**/*.material"},
    {"type": "texture", "glob": "Textures/UI/**/*.png"},
    {"type": "audio", "name": "MoveSound"}
  ]
}
```

Policies:

- `dev`: broad include allowed, warnings for suspicious dynamic refs.
- `debug`: explicit dynamic includes required when not statically reachable.
- `release`: no unresolved dynamic names, duplicate names are errors.

## Diagnostics Model

Diagnostics should be structured and stable:

```json
{
  "level": "error",
  "code": "resource.missing",
  "path": "Scenes/Main.scene",
  "message": "Material uuid '...' is referenced but not included",
  "hint": "Add the material file or resource_includes entry"
}
```

Levels:

- `info`
- `warning`
- `error`
- `fatal`

Rules:

- Build returns non-zero on `error`/`fatal`.
- `warning` is allowed for dev/debug only when profile policy permits it.
- Every fallback emits diagnostic with code.
- Logs are for humans; diagnostics are for tools/tests/UI.

## SDK Capability Manifest

SDK install should expose a machine-readable file:

```text
sdk/termin-sdk-capabilities.json
```

Example:

```json
{
  "version": 1,
  "sdk_version": "0.1.0",
  "platforms": {
    "desktop": {
      "vulkan": true,
      "opengl": true,
      "sdl": true,
      "python_runtime": true
    },
    "android": {
      "abis": ["arm64-v8a"],
      "vulkan": true,
      "python_runtime": false
    },
    "quest_openxr": {
      "abis": ["arm64-v8a"],
      "openxr_headers": true,
      "openxr_loader": true,
      "vulkan": true
    }
  },
  "tools": {
    "termin_shaderc": "bin/termin_shaderc",
    "termin_player": "bin/termin_player"
  }
}
```

Build targets should check this before doing expensive work.

## Cache and Incrementality

The target system should support clean correctness first, then incremental
speed.

Cache keys should include:

- source file content hash;
- compiler/tool version;
- target backend;
- profile configuration;
- relevant SDK capability/version;
- compiler options.

Cache directories:

```text
<project>/.termin/build-cache/
<project>/.termin/build-reports/
```

Build outputs under `dist/` should be reproducible products, not cache.

## CLI Shape

Canonical commands:

```bash
termin profiles [--project PROJECT]
termin profile PROFILE [--project PROJECT]
termin build PROFILE [--project PROJECT]
termin run PROFILE [--project PROJECT]
termin deploy PROFILE [--project PROJECT]
termin doctor PROFILE [--project PROJECT]
```

Semantics:

- `build` creates target artifact.
- `run` runs local runnable targets, mainly desktop/project mode.
- `deploy` installs/runs device targets.
- `doctor` checks profile + SDK + environment without building.

For target-specific options, prefer profile fields over long CLI flags. CLI
flags may override profile fields for local iteration but should be included in
the build report.

## Editor Integration

Editor build UI should be a thin caller:

- save scene/project state;
- select profile;
- call project build backend;
- stream logs;
- display structured diagnostics;
- expose output paths and deploy actions.

Editor should not:

- traverse asset dependencies itself;
- call Gradle directly;
- mutate runtime package internals;
- depend on singleton preloaders for build correctness.

## Tests and Gates

Minimum test matrix:

### Unit/contract tests

- profile schema validation;
- build graph duplicate/missing resource diagnostics;
- runtime package schema validation;
- shader artifact target matrix;
- Python module packaging;
- Android/Quest profile routing with fake build scripts.

### Integration tests

- export small scene package and load with Python loader;
- export same package and load with C++ `termin-runtime`;
- desktop bundle has no absolute source project paths;
- relocated desktop bundle smoke;
- Android APK assemble with fake/minimal package;
- Quest/OpenXR APK assemble with fake/minimal package.

### Device/manual gates

- Android logcat smoke;
- Quest/OpenXR runtime smoke;
- render pipeline visual sanity;
- shader/resource missing errors absent from logs.

## Migration Plan

### Stage 1: Target profile backend

Status target: short-term.

Tasks:

- move profile backend to `termin.project_build.profile_build`;
- dispatch `desktop`, `android`, `quest_openxr`;
- make C++ `termin_builder` target-agnostic;
- update `termin-cli.md`;
- add fake-backend routing tests.

Related: #41.

### Stage 2: Runtime package schema

Tasks:

- add schema/model for root manifest and resource specs;
- validate package after export;
- validate in runtime loaders;
- add Python/C++ contract tests;
- document versioning policy.

### Stage 3: Legacy build split

Tasks:

- rename old broad-copy `termin.project_builder` path as dev/legacy export;
- update editor UI naming;
- remove implicit legacy run path from `termin_runner` or gate it behind
  explicit mode;
- keep compatibility imports for one transition window.

Related: #27.

### Stage 4: Asset runtime graph

Tasks:

- move build-safe asset/resource graph APIs out of editor/app layer;
- replace `preload_project_resources(...)` dependency on editor preloaders;
- implement explicit dynamic include policy;
- make fallback resources opt-in dev-only;
- expand package resource coverage.

Related: #32, #39, #40.

### Stage 5: Platform delivery unification

Tasks:

- define Android package delivery contract;
- share asset copy/index/provider logic between Android and OpenXR;
- add SDK capability manifest;
- split `quest_openxr_smoke` and `quest_openxr` semantics.

Related: #5, #7, #8.

### Stage 6: Release-grade packaging

Tasks:

- Python requirement lock/resolve policy;
- native dependency report and host OS prerequisite policy;
- deterministic package reports;
- reproducible build mode;
- release smoke matrix.

## Open Questions

- Runtime scene format: keep editor JSON as runtime scene, or introduce compiled
  scene format after handle/kind serialization is stable?
- Binary mesh/material artifacts: when to switch from JSON transition format?
- Python on Android: explicit non-goal for now or future optional target?
- Plugin/resource compilers: loaded from SDK entry points, project plugins, or
  both?
- Build graph storage: JSON-only first, or typed Python model with generated
  JSON schema?
- Release dependency policy: vendor system libs where possible, or document host
  prerequisites?

## Success Criteria

The architecture is in good shape when:

- every `termin build PROFILE` goes through one project build backend;
- build output is explainable from profile + source tree + SDK capabilities;
- runtime package is schema-validated and loader-compatible;
- desktop/Android/OpenXR share the same package contract;
- editor build actions are thin wrappers over CLI/backend behavior;
- missing resources fail as structured diagnostics, not as device-only surprises;
- old broad-copy build path is clearly legacy/dev-only or removed.
