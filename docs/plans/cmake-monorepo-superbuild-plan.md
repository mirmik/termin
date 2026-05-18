# CMake Monorepo Build Plan

## Goal

Move the C++ SDK development build from script-driven sequential module installs to a single top-level CMake graph built with `add_subdirectory`.

The existing standalone module builds and SDK install pipeline must keep working during the migration. The first target is a C++-only monorepo build; Python bindings, C# bindings, packaging, and install layout parity are later phases.

## Current Problem

`build-sdk-cpp.sh` configures, builds, and installs every module one after another. Parallel compilation only happens inside the current module, so independent parts of the SDK cannot build concurrently.

Most modules also assume dependencies are already installed into `sdk/` and discover them through `find_package(...)`. In a monorepo build those dependencies are already CMake targets, so unconditional `find_package(...) REQUIRED` calls become the main blocker.

## Target Shape

Root `CMakeLists.txt`:

```cmake
add_subdirectory(termin-base)
add_subdirectory(termin-modules)
add_subdirectory(termin-mesh)
add_subdirectory(termin-csg)
add_subdirectory(termin-navmesh)
add_subdirectory(termin-graphics)
add_subdirectory(termin-inspect)
add_subdirectory(termin-scene)
...
add_subdirectory(termin-app/cpp)
add_subdirectory(tcplot)
```

Each module supports both modes:

1. Standalone mode: dependencies are loaded through `find_package`.
2. Monorepo mode: dependencies are already available as local targets.

## Phase 1: C++-Only Configure Skeleton

Add shared CMake helpers:

- `cmake/TerminDependencies.cmake`
- `termin_require_package(<package> <target> [<target>...])`
- `termin_add_alias_if_missing(<alias> <target>)`

Add missing aliases required by existing target links:

- `tcbase::termin_base -> termin_base`
- `tgfx::termin_graphics -> termin_graphics`
- `tgfx::termin_graphics2 -> termin_graphics2`
- component aliases created by `termin_add_module`
- `termin::trent -> trent`
- `termin::entity_lib -> entity_lib`
- `termin::render_lib -> render_lib`
- `termin::termin_core -> termin_core`
- `termin::navmesh_lib -> navmesh_lib` when navmesh is enabled

Add a root `CMakeLists.txt` with conservative defaults:

- `TERMIN_BUILD_MONOREPO=ON`
- `TERMIN_BUILD_PYTHON=OFF`
- all module tests OFF by default
- editor executables OFF by default
- Vulkan and SDL controlled by root options

Expected result:

```bash
cmake -S . -B build/monorepo -G Ninja -DTERMIN_BUILD_PYTHON=OFF
```

configures far enough to expose real target/dependency issues.

## Phase 2: Replace Direct `find_package` Calls

Replace internal package lookups with `termin_require_package`:

- `termin_base`
- `termin_modules`
- `termin_mesh`
- `termin_graphics`
- `termin_inspect`
- `termin_scene`
- `termin_lighting`
- `termin_render`
- `termin_input`
- `termin_display`
- `termin_collision`
- `termin_physics`
- component packages
- `termin_skeleton`
- `termin_animation`
- `termin_navmesh`

External packages remain normal `find_package` calls:

- `Python`
- `nanobind`
- `OpenGL`
- `Vulkan`
- `SDL2`
- `PkgConfig`
- `Qt`

Expected result:

```bash
cmake --build build/monorepo --target termin_render termin_engine
```

builds selected mid-level targets without installing SDK artifacts.

## Phase 3: Build Full C++ Graph

Enable the full C++ graph:

- all core libraries
- component libraries
- `termin-app/cpp` libraries
- `tcplot`

Fix issues found during full graph generation:

- target name collisions
- global cache option collisions
- unsafe `CMAKE_SOURCE_DIR` usage
- `BUILD_SHARED_LIBS` leakage from third-party projects
- output directory assumptions
- RPATH assumptions

Expected result:

```bash
cmake --build build/monorepo --parallel
```

builds the C++ SDK graph without per-module install steps.

## Phase 4: Tests

Unify test options under a root switch:

- `TERMIN_BUILD_TESTS=OFF` by default
- `TERMIN_BUILD_TGFX2_TESTS=ON` controls tgfx2 tests when tests are enabled
- `TERMIN_BUILD_WINDOW_TESTS=OFF` controls tests that create windows or GL contexts
- module-specific test options remain available

Add a root target:

```bash
cmake --build build/monorepo --target test
ctest --test-dir build/monorepo --output-on-failure
```

Test failures must log useful diagnostics and must not be silently ignored.

Current status:

- `run-tests-cpp.sh` uses the top-level CMake graph.
- `--vulkan/--no-vulkan` maps to `TERMIN_ENABLE_VULKAN`.
- `--window-tests/--no-window-tests` controls tests that need a windowing system.
- tgfx2 window tests are present in CTest when window tests are enabled, but skip cleanly when the current environment has no usable video backend.
- Vulkan tgfx2 smoke tests are wired behind `TERMIN_ENABLE_VULKAN`; the local host still needs shaderc for a Vulkan-enabled build.

## Phase 5: Python Bindings

Enable Python bindings in the monorepo graph after C++-only is stable.

Known issues to fix:

- `CMAKE_SOURCE_DIR` usage in binding subdirectories
- Python module output directories
- nanobind target availability
- install destinations under `lib/python`
- copied `.py` package layout

Expected result:

```bash
cmake -S . -B build/monorepo-py -G Ninja -DTERMIN_BUILD_PYTHON=ON
cmake --build build/monorepo-py --parallel
```

## Phase 6: Install and SDK Layout

Keep install support but make it a separate step:

```bash
cmake --install build/monorepo --prefix sdk
```

Verify parity with the current SDK layout:

- headers
- shared libraries
- CMake package configs
- Python extension modules when enabled
- RPATH behavior

## Phase 7: C# and Packaging

Integrate C# only after C++ and Python are stable.

Known concerns:

- C# CMake currently links `termin::...` imported targets.
- SWIG output writes into source-side generated directories.
- Recommended C# SDK build uses `--no-sdl --no-vulkan`; mirror this as root options.

## Rollback Strategy

The existing scripts remain the source of truth until monorepo build reaches parity:

- `build-sdk-cpp.sh`
- `build-sdk-bindings.sh`
- `build-sdk.sh`
- `run-tests-cpp.sh`
- `run-tests-python.sh`

No existing build script should be removed during the migration.

## Success Criteria

The migration is complete when:

- standalone module builds still work;
- root C++ monorepo build works without install-before-use;
- root test run works;
- Python bindings can be built from the root;
- SDK install layout matches the current scripts;
- development docs mention both legacy and monorepo workflows.

## Current Status

Initial C++-only monorepo build is implemented.

Verified:

```bash
cmake -S . -B build/monorepo -G Ninja -DTERMIN_BUILD_PYTHON=OFF -DTERMIN_ENABLE_VULKAN=OFF -DTERMIN_ENABLE_SDL=ON
cmake --build build/monorepo --parallel 4
```

Result: full C++ graph configured and built successfully.

Also verified standalone configure still works for at least one dependent module:

```bash
cmake -S termin-render -B /tmp/termin-render-standalone-check -G Ninja -DCMAKE_PREFIX_PATH=/home/rfmeas/project/termin/sdk -DCMAKE_INSTALL_PREFIX=/tmp/termin-render-standalone-install -DTERMIN_BUILD_PYTHON=OFF -DTERMIN_RENDER_BUILD_TESTS=OFF
```

Remaining work:

- run broader standalone checks;
- add root documentation for the new workflow;
- enable and verify root C++ tests;
- migrate Python bindings;
- verify `cmake --install` SDK layout parity;
- address third-party option isolation more thoroughly, especially Manifold/Clipper2.
