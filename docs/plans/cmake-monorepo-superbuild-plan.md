# CMake Monorepo Build Status

## Summary

The SDK build has been migrated from a script-orchestrated per-module CMake loop to a single top-level CMake target graph built with `add_subdirectory()`.

The migration kept the public scripts as the user-facing entry points:

- `./build-sdk.sh`
- `./build-sdk-cpp.sh`
- `./build-sdk-bindings.sh`
- `./run-tests-cpp.sh`
- `./run-tests-python.sh`

The old term "superbuild" in this plan refers to the migration effort. The implemented solution is not an `ExternalProject_Add` superbuild; it is a monorepo CMake graph.

## Current Workflow

Full SDK build:

```bash
./build-sdk.sh --no-vulkan --sdl
```

C/C++ SDK stage:

```bash
./build-sdk-cpp.sh --no-vulkan --sdl
```

Python/nanobind bindings stage:

```bash
./build-sdk-bindings.sh --no-vulkan --sdl
```

C++ tests:

```bash
bash run-tests-cpp.sh --no-vulkan --sdl
bash run-tests-cpp.sh --no-vulkan --sdl --window-tests
```

Direct root CMake build:

```bash
cmake -S . -B build/Release \
  -DCMAKE_BUILD_TYPE=Release \
  -DTERMIN_BUILD_PYTHON=ON \
  -DTERMIN_BUILD_TESTS=OFF \
  -DTERMIN_ENABLE_VULKAN=OFF \
  -DTERMIN_ENABLE_SDL=ON
cmake --build build/Release --parallel
cmake --install build/Release
```

## Root Options

- `TERMIN_BUILD_MONOREPO=ON` enables the top-level monorepo graph.
- `TERMIN_BUILD_PYTHON=ON/OFF` controls nanobind extension targets.
- `TERMIN_BUILD_TESTS=ON/OFF` controls C/C++ tests.
- `TERMIN_BUILD_TGFX2_TESTS=ON/OFF` controls tgfx2 tests when tests are enabled.
- `TERMIN_BUILD_WINDOW_TESTS=ON/OFF` controls tests that create windows or GL contexts.
- `TERMIN_ENABLE_VULKAN=ON/OFF` controls Vulkan support.
- `TERMIN_ENABLE_SDL=ON/OFF` controls SDL support.
- `TERMIN_USE_CCACHE=ON/OFF` controls automatic `ccache` compiler launcher use when `ccache` is available.
- `TERMIN_ENABLE_UNITY_BUILD=ON/OFF` enables targeted unity build for selected C++-heavy targets.
- `TERMIN_BUILD_EDITOR_MINIMAL`, `TERMIN_BUILD_EDITOR_EXE`, and `TERMIN_BUILD_LAUNCHER` remain off for SDK builds.

## Completed

### C++ Graph

- The root `CMakeLists.txt` adds the C/C++ modules through `add_subdirectory()`.
- Internal dependencies can use already-existing CMake targets instead of requiring prior installation into `sdk/`.
- `build-sdk-cpp.sh` uses the top-level graph and installs into `sdk/`.
- The default build directory is `build/<BUILD_TYPE>`; for Release this is `build/Release`.
- Shell scripts use `ccache` automatically when available and select `Ninja` for new build directories when available.
- `--unity` enables targeted unity build for checked C++ targets (`termin_graphics2`, `termin_render`, `trent`, `entity_lib`, `render_lib`).
- Standalone module builds remain supported through normal `find_package(...)` paths.

### Tests

- `run-tests-cpp.sh` uses the top-level graph.
- `--vulkan/--no-vulkan` maps to `TERMIN_ENABLE_VULKAN`.
- `--window-tests/--no-window-tests` controls tests requiring a usable windowing/video backend.
- tgfx2 tests are wired into CTest.
- tgfx2 window tests and display window tests skip cleanly when the environment has no usable video backend.

### Python Bindings

- `TERMIN_BUILD_PYTHON=ON` configures, builds, and installs from the top-level graph.
- The root graph selects one Python interpreter and exports it through `Python_EXECUTABLE`.
- `termin-nanobind-sdk` is part of the root graph.
- `build-sdk-bindings.sh` uses the top-level graph instead of the old `modules.conf` loop and `termin-app/build.sh`.
- Project nanobind modules use the shared `libnanobind.so`; `nanobind-static` is no longer built for project modules.
- Python extension modules install under the SDK Python layout, not duplicated at the SDK root.
- Duplicate SDK `.so` verification passes.

### Install Layout

- `cmake --install build/Release` installs headers, shared libraries, CMake packages, Python extension modules, and Python package files into `sdk/`.
- The full `build-sdk.sh` path has been reported working after the migration.

## Open Work

### Python Test Workflow

Verify the editable Python workflow after root-built bindings:

```bash
./setup-test-venv.sh --force
bash run-tests-python.sh
```

This should confirm that rebuilt native extensions are copied into editable package sources and imported from the expected SDK.

### C# Stage

`build-sdk-csharp.sh` remains a separate stage. It should be evaluated separately if C# is brought into the monorepo graph.

Known C# constraints:

- The recommended C# SDK build is OpenGL-only: `--no-sdl --no-vulkan`.
- Existing C# CMake links against installed/imported targets.
- Generated SWIG output may still write into source-side generated directories.

### Vulkan

Vulkan tests and Vulkan-enabled builds are wired behind `TERMIN_ENABLE_VULKAN`, but the local environment still needs `shaderc` for a Vulkan-enabled build.

The remaining task is to improve the diagnostic or dependency policy for `--vulkan`, so failure is explicit and actionable.

### Documentation

Keep user-facing docs aligned with the current workflow:

- root CMake graph is the default SDK build backend;
- scripts remain the stable user entry points;
- Python tests should use the venv/editable flow;
- C# remains a separate stage unless explicitly migrated.

### Standalone Checks

Broaden standalone checks for selected modules to ensure the migration did not break package consumers that build modules outside the root graph.

## Historical Notes

The earlier migration phases were:

1. Add root CMake graph and dependency helpers.
2. Replace internal unconditional `find_package(...)` calls with target-aware helpers.
3. Build the full C++ graph.
4. Move C++ tests to the root graph.
5. Move Python/nanobind bindings to the root graph.
6. Verify install layout parity.

These phases are complete for the main SDK workflow.
