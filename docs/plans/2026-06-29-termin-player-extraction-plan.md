# termin-player extraction from termin-app

Date: 2026-06-29
Status: implemented

Implementation note: physical extraction landed in the same goal. The new
runtime-facing packages are `termin-player`, `termin-mcp` and
`termin-shader-runtime`; `termin-app` depends on them as a super-consumer, while
the packaged desktop runtime seed no longer includes `termin-app`.

Superseded packaged-execution note (2026-07-19): Python bundle mode and
`runtime_package_loader.py` were subsequently removed. References below are
historical migration inventory; packaged execution is owned by the native
`termin_player` host and `termin-runtime`.

## Goal

Вынести desktop/source/headless player слой из `termin-app` в отдельный
монорепозиторный модуль `termin-player`, не смешивая его с `termin-runtime`.

После миграции:

- `termin-app` содержит editor-specific и окологуишную editor-логику;
- `termin-player` содержит executable host, Python facade, source-project player
  CLI, headless runtime и player-only development services;
- `termin-runtime` остается нижним доменным runtime/package-loader слоем и не
  зависит от player/application concerns;
- SDK все еще устанавливает `bin/termin_player`;
- packaged desktop bundle больше не тащит `termin-app` как runtime
  distribution.

Цель можно закрыть одним goal, если держать scope как физический и dependency
вынос player слоя. Переписывание asset system, project build system и
headless runtime contract в тот же goal включать нельзя: это отдельные хвосты.

## Related Context

- [C++ termin_player migration plan](2026-06-24-cpp-termin-player-migration-plan.md)
  уже перевел packaged desktop player на native `PlayerRuntimeHost`.
- `termin-runtime` уже содержит C++ `RuntimePackageLoader` и должен оставаться
  canonical loader для packaged runtime package.
- Kanboard:
  - `#27 [build] Сделать desktop build настоящим standalone runtime bundle`;
  - `#32 [assets] Довести runtime package asset graph до desktop build needs`;
  - `#36 [architecture] Наметить следующий вынос из termin-app`;
  - `#40 [assets] Завершить вынос asset runtime из termin-app`;
  - `#54 [runtime] Оформить headless scene runtime contract`;
  - `#116 [sdk] Разделить standard и experimental Python packages`;
  - `#143 [editor/player] Run Standalone uses removed termin.main entrypoint`.

## Boundary Decision

Не смешивать `termin-player` и `termin-runtime`.

`termin-runtime` отвечает за:

- runtime package manifest/resource contract;
- native package loading into domain objects;
- resource keepalive for loaded package data;
- domain-level bootstrap needed by package loading;
- tests for package format parity.

`termin-player` отвечает за:

- desktop executable `termin_player`;
- app/bundle manifest parsing and player command line;
- embedded Python session for project modules;
- player-facing Python APIs, for example `termin.player.request_quit()`;
- SDL/offscreen window, display, input, frame loop and shutdown ownership;
- source-project run path used by `python -m termin.player`;
- headless player runtime until `#54` moves it to a neutral scene-runtime
  contract;
- player MCP/screenshot tooling, if kept.

Запрещенная зависимость:

```text
termin-runtime -> termin-player
termin-runtime -> termin-app
termin-player  -> termin-app
packaged bundle -> termin-app
```

Разрешенная зависимость:

```text
termin-app     -> termin-player as a super-consumer/integration layer
termin-player  -> termin-runtime
termin-player  -> termin-modules / engine / display / render / components
project_build  -> SDK capability "termin_player executable exists"
```

`termin-app` в текущей архитектуре остается супер-потребителем и может знать о
player. Это не хвост миграции само по себе. Хвостом считается обратная
зависимость `termin-player -> termin-app`, физическое владение player-файлами в
`termin-app` или попадание `termin-app` в packaged runtime bundle.

## Current Player Surface In termin-app

C++:

- `termin-app/cpp/app/termin_player.cpp`;
- `termin-app/cpp/termin/player/player_runtime_host.hpp`;
- `termin-app/cpp/termin/player/player_runtime_host.cpp`;
- `termin-app/cpp/CMakeLists.txt` target `termin_player`.

Python:

- `termin-app/termin/player/__init__.py`;
- `termin-app/termin/player/__main__.py`;
- `termin-app/termin/player/runtime.py`;
- `termin-app/termin/player/headless.py`;
- `termin-app/termin/player/project_runtime_support.py`;
- `termin-app/termin/player/runtime_package_loader.py`;
- `termin-app/termin/player/mcp_server.py`;
- `termin-app/termin/player/screenshot.py`.

Tests to move or split:

- `termin-app/tests/test_player_runtime_input.py`;
- `termin-app/tests/test_player_shader_runtime.py`;
- `termin-app/tests/test_player_manifest_assets.py`;
- `termin-app/tests/test_player_project_asset_scan.py`;
- `termin-app/tests/test_headless_runtime.py`;
- `termin-app/tests/test_mcp_base.py` player-specific cases;
- Python tests that import `termin.player.runtime_package_loader`;
- C++/packaged runtime smoke gates for `termin_player`.

Important call sites to update:

- `termin-app/termin/project_build/desktop_runtime_packager.py`;
- `termin-app/termin/project_build/capabilities.py`;
- `termin-app/termin/project_build/target_preflight.py`;
- `termin-app/termin/editor_tcgui/project_build_controller.py`;
- `termin-cli/src/termin_runner.cpp` (moved out of `termin-app` on 2026-06-29);
- `termin-app/docs/termin-cli.md`;
- `termin-app/docs/project-build-manifest.md`;
- `docs/build-system.md`;
- `scripts/gen-dependency-graph.py`;
- root `CMakeLists.txt`;
- `setup-test-venv.sh`.

## Target Layout

```text
termin-player/
  CMakeLists.txt
  AGENTS.md
  include/termin/player/
    player_runtime_host.hpp
    player_app_manifest.hpp
    player_python_session.hpp
    player_window_host.hpp
  src/
    app/termin_player.cpp
    player_runtime_host.cpp
    player_app_manifest.cpp
    player_python_session.cpp
    player_window_host.cpp
  termin/
    player/
      __init__.py
      __main__.py
      runtime.py
      headless.py
      project_runtime_support.py
      runtime_package_loader.py
      mcp_server.py
      screenshot.py
  tests/
```

`runtime_package_loader.py` не должен стать canonical packaged runtime loader.
Его допустимо перенести как legacy/source-project helper, но в том же goal надо
переименовать или документировать его назначение так, чтобы он не конкурировал с
`termin::runtime::RuntimePackageLoader`.

Если `termin.player.mcp_server` зависит от `termin.mcp`, shared MCP transport
надо вынести из `termin-app` в нейтральный пакет в рамках того же goal:

```text
termin-mcp/
  termin/mcp/
```

Иначе `termin-player` сразу получит скрытую runtime-зависимость на
`termin-app`.

## Phase 0: Contract Freeze

Перед переносом зафиксировать player contract:

- `termin_player --bundle <app.json>`;
- `termin_player --exit-after-frames N`;
- `python -m termin.player <project> --scene ...`;
- `python -m termin.player --headless ...`;
- `from termin.player import request_quit`;
- player MCP enablement through `TERMIN_PLAYER_MCP*`, если MCP оставляем.

Acceptance:

- есть список публичных player entrypoints;
- известно, какие entrypoints обязаны пережить перенос без изменения;
- известны entrypoints, которые можно удалить без fallback.

## Phase 1: Scaffold termin-player

Создать новый top-level module:

- `termin-player/CMakeLists.txt`;
- `termin-player/AGENTS.md`;
- Python install logic for `termin/player`;
- test discovery for `termin-player/tests`;
- root `CMakeLists.txt` includes `add_subdirectory(termin-player)` after
  `termin-runtime` and before `termin-app/cpp`.

CMake dependencies для `termin_player` остаются явными:

- `Python::Python`;
- `termin_bootstrap::termin_bootstrap`;
- `termin_runtime::termin_runtime`;
- `termin_display::termin_display`;
- `termin_engine::termin_engine`;
- `termin_render::termin_render`;
- `termin_render_passes::termin_render_passes`;
- `termin_collision::termin_collision`;
- component packages used by runtime scene load/render;
- `termin_modules::termin_modules`;
- `termin_modules_python`.

Acceptance:

- пустой `termin-player` модуль собирается в монорепозитории;
- SDK install получает Python package из `termin-player`;
- `termin-app` больше не отвечает за установку `termin/player`.

## Phase 2: Move C++ Player Host

Перенести:

- `termin-app/cpp/app/termin_player.cpp` ->
  `termin-player/src/app/termin_player.cpp`;
- `termin-app/cpp/termin/player/player_runtime_host.hpp` ->
  `termin-player/include/termin/player/player_runtime_host.hpp`;
- `termin-app/cpp/termin/player/player_runtime_host.cpp` ->
  `termin-player/src/player_runtime_host.cpp`.

В `termin-app/cpp/CMakeLists.txt` удалить target `termin_player` полностью.

Во время переноса стоит сразу разрезать большой host хотя бы на manifest/session
границы, если это не раздувает scope:

- `PlayerAppManifest`;
- `PlayerPythonSession`;
- `PlayerWindowHost`.

Acceptance:

- `termin_player` target создается только в `termin-player/CMakeLists.txt`;
- `rg "add_executable\\(termin_player" termin-app` ничего не находит;
- `sdk/bin/termin_player --help` или equivalent smoke по-прежнему работает;
- packaged smoke `--exit-after-frames 3` остается зеленым.

## Phase 3: Move Python termin.player

Перенести весь package `termin-app/termin/player` в
`termin-player/termin/player`.

Правила переноса:

- public imports `termin.player.*` сохраняются;
- не добавлять compatibility re-export из `termin-app`;
- если `runtime.py` остается только для source-project path, назвать это явно в
  module docstring или split-нуть на `source_runtime.py`;
- `headless.py` остается в `termin-player` только как временный player-owned
  runtime до закрытия `#54`;
- player MCP либо переносится вместе с нейтральным `termin.mcp`, либо отключается
  из player scope явно и с обновлением тестов/документации.

Acceptance:

- `rg "termin/player" termin-app` не находит исходников;
- `rg "from termin\\.player|import termin\\.player" termin-app` показывает
  только consumer/integration use, без доступа к player-private internals;
- `python -m termin.player --help` работает в test venv/SDK Python;
- `from termin.player import request_quit` работает без импорта editor modules.

## Phase 4: Move Tests And Split MCP Coverage

Перенести player-only tests в `termin-player/tests`.

Разделить mixed MCP tests:

- shared JSON-RPC/server/executor tests идут в нейтральный MCP package, если
  `termin.mcp` вынесен;
- editor MCP tests остаются в `termin-app/tests`;
- player MCP/screenshot tests уходят в `termin-player/tests`.

Acceptance:

- `termin-app/tests` не импортирует `termin.player`, кроме интеграционных
  editor-to-player command boundary тестов;
- `termin-player/tests` можно запускать отдельно;
- общий `./run-tests.sh` включает новые tests;
- test names больше не маскируют player/runtime tests как app tests.

## Phase 5: Packaging And SDK Runtime

Обновить desktop packager:

- заменить `termin-app` на `termin-player` в
  `TERMIN_PLAYER_RUNTIME_DISTRIBUTIONS`;
- убедиться, что `termin-app` не попадает в bundle через broad-copy policy;
- оставить `termin_player` capability как SDK tool, а не app-private detail;
- preflight diagnostics должны говорить о missing `termin_player`, а не о
  missing `termin-app`;
- copied runtime manifest должен перечислять `termin-player`.

Обновить SDK install/test environment:

- `setup-test-venv.sh` должен устанавливать test/runtime dependencies так, чтобы
  `termin-player` доступен без `termin-app`;
- root install не должен копировать `termin-app/termin/player`;
- bundled Python site-packages должны содержать `termin/player` из
  `termin-player`.

Acceptance:

- packaged desktop bundle запускается без установленного `termin-app`;
- `python_runtime_manifest.json` не содержит `termin-app`, если проект не
  использует editor-only modules;
- `termin build dev` не копирует stale `termin-app` player files;
- `termin-app` может отсутствовать из minimal runtime seed set.

## Phase 6: Editor Call Sites

Editor/app слой может запускать и интегрировать player как супер-потребитель,
но не должен владеть его кодом.

Обновить:

- Run Standalone/project build controller to call `termin_player` capability,
  `python -m termin.player` or a public `termin-player` API;
- docs and UI text that imply player is part of app;
- `termin_runner.cpp` forwarding to `termin.player`, если runner остается в
  `termin-app/cpp`, допустим как app-level consumer integration;
- task `#143` закрывать только после smoke against real command.

Acceptance:

- editor Run Standalone работает через public player command/API;
- `termin-app` не импортирует player-private internals;
- editor tests mock command/capability boundary instead of `PlayerRuntime`
  internals.

## Phase 7: Dependency Graph And Documentation

Обновить:

- `docs/build-system.md`;
- `termin-app/docs/termin-cli.md` или перенести player CLI часть в
  `termin-player/docs/termin-player-cli.md`;
- `termin-app/docs/project-build-manifest.md`;
- `docs/modules.md`, если есть module inventory;
- `scripts/gen-dependency-graph.py`;
- generated dependency graph artifacts, если они committed;
- this plan status after implementation.

Acceptance:

- dependency graph показывает `termin-player` отдельным узлом;
- `termin-app` больше не выглядит владельцем player/runtime bundle;
- документация не говорит, что `termin.player` живет в `termin-app`.

## Phase 8: Remove Old Files And Add Guards

Удалить старые locations, а не оставлять re-export/fallback:

- `termin-app/termin/player`;
- `termin-app/cpp/termin/player`;
- `termin-app/cpp/app/termin_player.cpp`;
- `termin_player` target block in `termin-app/cpp/CMakeLists.txt`.

Добавить guard tests/checks:

```bash
rg "add_executable\\(termin_player" termin-app
rg "termin-app/termin/player|termin-app/cpp/termin/player" .
rg "TERMIN_PLAYER_RUNTIME_DISTRIBUTIONS" termin-app/termin/project_build/desktop_runtime_packager.py
```

Acceptance:

- первые два поиска не находят old ownership;
- third check shows `termin-player`, not `termin-app`;
- old package files physically absent;
- no compatibility shim in `termin-app/termin/player/__init__.py`.

## Final Verification

Run:

```bash
./build-sdk.sh --no-wheels
./setup-test-venv.sh --force
./run-tests.sh
```

Player-specific smoke:

```bash
cd /home/mirmik/project/termin-chess
termin build dev
./dist/Chess/Chess --exit-after-frames 3
```

Python API smoke:

```bash
.venv/bin/python -m termin.player --help
.venv/bin/python -c "from termin.player import request_quit; print(request_quit)"
```

Bundle independence smoke:

```bash
rg "termin-app" /home/mirmik/project/termin-chess/dist/Chess
```

Expected final state:

- SDK build succeeds;
- all tests pass;
- packaged player exits with status 0;
- no nanobind leak report on normal player shutdown;
- `termin-app` is absent from packaged runtime distributions;
- `termin-app` contains no player source files;
- `termin-runtime` has no application/player dependency.

## Out Of Scope For This Goal

These are real follow-up tasks, but not blockers for closing this extraction:

- redesigning the asset system or finishing `#40`;
- making desktop bundle fully minimal beyond removing `termin-app`;
- moving `headless.py` into a neutral scene runtime package;
- rewriting `project_build` out of `termin-app`;
- replacing every old source-project `PlayerRuntime` behavior with native host
  code;
- deleting C# `PullRenderingManager` compatibility work.

## Feasibility

One goal is realistic if the goal is defined as:

> `termin-player` becomes the sole owner of player files, SDK `termin_player`,
> Python `termin.player`, player tests and runtime bundle seed distribution.

One goal is not realistic if it also includes:

- project build extraction from `termin-app`;
- full asset runtime extraction;
- new headless runtime architecture;
- broad package split between standard and experimental Python distributions.

The migration should deliberately leave those as named external cards instead
of hiding partial refactors in `termin-player`.
