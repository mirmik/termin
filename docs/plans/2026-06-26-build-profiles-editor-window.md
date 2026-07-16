# Build profiles editor window

Дата: 2026-06-26

> **Status: superseded in architecture and schema details.** The editor goal
> remains relevant, but the schema-v2 sketch, separate runtime backend/shader
> artifact fields, v1 migration and profile-owned toolchain/deploy capability
> fields below are historical. The current contract is
> [Build Profiles And Product Composition](../architecture/2026-07-16-build-profiles-and-product-composition.md),
> and execution is tracked by
> [Build Profiles And Product Build System Plan](2026-07-16-build-profiles-product-build-system-plan.md).

Связанные документы:

- `docs/plans/2026-06-17-build-system-target-architecture.md`
- `docs/build-system.md`
- `termin-app/docs/termin-cli.md`

Связанные задачи:

- #111 - текущий низкоуровневый хвост вокруг desktop shader targets.

## Проблема

Build profiles уже существуют как `project_settings/build_profiles.json`, но в
редакторе они почти не видны. Меню `Game` сейчас содержит отдельные действия
`Build Project`, `Build Android APK`, `Quest/OpenXR Build` и `Run Build`, хотя
это должны быть операции над одним выбранным build profile.

Вторая проблема - смешение разных осей конфигурации:

- host, на котором запускается build;
- target platform, для которого собирается artifact;
- runtime backend, который будет выбран при запуске;
- shader artifact targets, которые попадут в package;
- toolchain/capabilities, доступные локально или удаленно.

Из-за этого легко получить скрытую магию: Linux build случайно хочет D3D11
артефакты, Windows build кажется обязанным быть D3D11, а будущий Windows build
из-под Linux некуда аккуратно выразить.

## Цель

Сделать build profiles редактируемой проектной моделью и завести в редакторе
единое окно `Build Profiles`, из которого настраиваются и запускаются desktop,
Android и Quest/OpenXR сборки.

Главный contract: build backend не выбирает backend или shader targets по host
неявно. Host capabilities используются для валидации и diagnostics, но не
переписывают профиль.

## Non-goals

- Не делать полноценный remote/cross build сразу.
- Не удалять CLI `termin build PROFILE`.
- Не переносить build pipeline в editor code. Editor остается UI-wrapper над
  проектной build model.
- Не поддерживать старый broad-copy `project_builder` как primary path.

## Термины

- **Build target** - тип результата: `desktop`, `android`, `quest_openxr`.
- **Target platform** - OS/ABI/runtime family результата: например
  `linux/x86_64`, `windows/x86_64`, `android/arm64-v8a`.
- **Runtime backend** - backend, с которым запускается runtime host:
  `vulkan`, `opengl`, `d3d11`.
- **Shader artifact targets** - набор shader outputs, которые экспортируются в
  runtime package: `vulkan`, `opengl`, `d3d11`.
- **Toolchain** - локальный или будущий удаленный набор compiler/deploy tools.

## Profile contract

Текущий schema v1 может быть загружен как legacy input. Целевая форма должна
быть ближе к schema v2:

```json
{
  "version": 2,
  "profiles": {
    "linux-vulkan-dev": {
      "target": "desktop",
      "platform": {
        "os": "linux",
        "arch": "x86_64"
      },
      "configuration": "dev",
      "entry_scene": "Scenes/Main.scene",
      "output_dir": "dist/linux-vulkan-dev",
      "runtime": {
        "backend": "vulkan"
      },
      "shaders": {
        "language": "slang",
        "artifact_targets": ["vulkan"]
      },
      "python": {
        "package_policy": "minimal_strict",
        "requirements": []
      },
      "toolchain": {
        "execution": "local"
      }
    },
    "windows-d3d11-release": {
      "target": "desktop",
      "platform": {
        "os": "windows",
        "arch": "x86_64"
      },
      "configuration": "release",
      "entry_scene": "Scenes/Main.scene",
      "output_dir": "dist/windows-d3d11-release",
      "runtime": {
        "backend": "d3d11"
      },
      "shaders": {
        "language": "slang",
        "artifact_targets": ["d3d11"]
      },
      "toolchain": {
        "execution": "local"
      }
    },
    "quest": {
      "target": "quest_openxr",
      "platform": {
        "os": "android",
        "abi": "arm64-v8a",
        "api_level": 26
      },
      "configuration": "debug",
      "entry_scene": "Scenes/XR.scene",
      "output_dir": "dist/quest",
      "runtime": {
        "backend": "vulkan",
        "xr": "openxr"
      },
      "shaders": {
        "language": "slang",
        "artifact_targets": ["vulkan"]
      },
      "deploy": {
        "installable": true,
        "launchable": true
      }
    }
  }
}
```

Important policy decisions:

- `runtime.backend` is single-value for launch/run behavior.
- `shaders.artifact_targets` is a list because a package may include more than
  one backend family.
- `platform.os` is the target OS, not the current host OS.
- Local host capability failures are diagnostics. They do not mutate the
  profile.
- UI templates may prefill a local Linux/Vulkan or Windows/D3D11 profile, but
  the saved profile must contain explicit values.

Legacy v1 mapping:

- top-level `default_shader_language` -> `shaders.language`;
- top-level `shader_targets` -> `shaders.artifact_targets`;
- missing `shader_targets` stays a legacy value during load, but the editor
  should force an explicit artifact target choice before saving schema v2;
- `android.abi` and `android.platform` map into `platform.abi` and
  `platform.api_level`;
- `openxr.required` maps to `runtime.xr = "openxr"` for `quest_openxr`.

## Editor UI

Menu shape:

- Replace target-specific build entries with `Game > Build Profiles...`.
- Keep fast actions after the profile window exists:
  - `Build Selected Profile`
  - `Run Selected Profile`
  - `Install/Launch Selected Profile` only when selected profile supports it.

Window layout:

```text
Build Profiles

+------------------------------+-----------------------------------------+
| profiles table               | selected profile editor                 |
|                              |                                         |
| Name | Target | Platform ... | General | Runtime | Shaders | Toolchain |
|                              | Deploy  | Output  | Diagnostics          |
| [Add] [Duplicate] [Delete]   |                                         |
+------------------------------+-----------------------------------------+
| [Build] [Run] [Install] [Launch] [Dry Run] [Save] [Revert] [Close]     |
+------------------------------------------------------------------------+
```

Profiles table columns:

- name;
- build target;
- target platform;
- configuration;
- runtime backend;
- validation status.

General tab:

- profile name;
- build target (`desktop`, `android`, `quest_openxr`);
- configuration (`dev`, `debug`, `release`);
- entry scene;
- output dir;
- resource policy.

Runtime tab:

- desktop backend: `vulkan`, `opengl`, `d3d11`;
- window defaults, reusing project `player_window` as profile override source;
- MCP enable/default port only when needed later;
- Quest/OpenXR runtime fields: OpenXR enabled, application id/activity if
  exposed by profile.

Shaders tab:

- default shader language;
- artifact targets as independent checkboxes;
- derived compatibility diagnostics:
  - `d3d11` requires FXC or a configured Windows/cross toolchain;
  - Android/OpenXR currently accept Vulkan artifacts only;
  - selected runtime backend should have a matching shader artifact target.

Toolchain tab:

- execution: `local` now, `remote`/`cross` reserved;
- SDK root override;
- shader compiler override;
- Android Gradle/build script overrides;
- local capability report.

Deploy tab:

- Desktop: build/run/open output.
- Android: build/install/launch when deploy tools are configured.
- Quest/OpenXR: build/install/launch, replacing the current one-off
  `Quest/OpenXR Build` dialog.

Output tab:

- resolved CLI command;
- resolved normalized request summary;
- build log path;
- last diagnostics.

## Runtime behavior

`ProjectBuildController` should stop calling target wrappers directly from
separate menu actions. It should:

1. save the current scene;
2. load the selected profile through the shared profile store;
3. run `termin build PROFILE` or call the canonical profile backend;
4. stream build diagnostics into the window and editor console;
5. enable run/install/launch from profile capabilities.

The old Quest/OpenXR dialog can be kept temporarily as a thin wrapper around a
generated/selected `quest_openxr` profile, then removed after the unified window
has deploy actions.

## Implementation plan

1. Extract build profile persistence into a non-editor module, tentatively
   `termin.project_build.profiles`.
   It should provide typed dataclasses, schema load/save, v1 -> v2 migration,
   validation diagnostics, and normalized request conversion.
2. Update `profile_build.py` to consume the shared profile model instead of
   open-coding profile parsing.
3. Add editor model tests before UI:
   load profiles, select profile, edit target/backend/artifacts, validate
   diagnostics, save JSON.
4. Add `Build Profiles` tcgui dialog using existing `TableWidget`, `TabView`,
   `ComboBox`, `Checkbox`, `TextInput`, `SpinBox`, `TextArea`, and `Button`.
5. Wire menu and `ProjectBuildController` to the selected profile path.
6. Fold Android and Quest/OpenXR build actions into profile actions.
7. Update `docs/build-system.md` and `termin-app/docs/termin-cli.md`.

## Acceptance

- Editor can create, duplicate, delete, edit, save, and revert build profiles.
- Desktop profiles expose target OS, runtime backend, and shader artifact
  targets explicitly.
- Windows/D3D11 is selectable without making all Windows profiles D3D11-only.
- Linux desktop profiles can explicitly build Vulkan/OpenGL without D3D11.
- Android and Quest/OpenXR profiles are configured in the same window.
- Build/run/deploy actions use the selected profile.
- CLI and editor load the same profile schema.
- Tests cover schema migration, validation policy, editor model save/load, and
  profile action dispatch.
