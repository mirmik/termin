# Termin Tally

A deliberately small, standalone C++ utility built on the installed Termin SDK. It has one
piece of state, a label, and two buttons: reset the tally or increment it.

The example is intentionally a real downstream CMake project. It does not use the monorepo
target graph or compile Termin sources with `add_subdirectory()`.

## Build

From the repository root:

```bash
cmake -S examples/termin-gui-native-tally \
      -B build/examples/termin-gui-native-tally \
      -DCMAKE_PREFIX_PATH="$PWD/sdk"
cmake --build build/examples/termin-gui-native-tally --parallel
```

Run it from any working directory:

```bash
./build/examples/termin-gui-native-tally/termin_tally
```

The application host resolves its font and shader tools relative to the loaded SDK.
`TERMIN_SDK`, `TERMIN_SHADERC`, `TERMIN_SLANGC`, and `TERMIN_UI_FONT` provide explicit
runtime overrides. Use `--frames N` for a bounded window/render smoke run; CTest uses this
mode automatically.

## What the experiment exposes

The actual UI is small, and the surrounding application is now small as well. The installed
`termin_gui_native::application_host` owns the lightweight native window, portable input,
resizable render target, draw-list rendering, presentation, font/shader runtime defaults and
GPU teardown. Tally contains no SDL types, graphics-device setup, asset lookup or render-loop
plumbing and still avoids the engine scene/render/input integration from `termin-display`.
