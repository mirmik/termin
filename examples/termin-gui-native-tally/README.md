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

The configure step records the selected SDK and `slangc` locations as development hints.
`TERMIN_SDK`, `TERMIN_SHADERC`, `TERMIN_SLANGC`, and `TERMIN_UI_FONT` override those hints.
Use `--frames N` for a bounded window/render smoke run; CTest uses this mode automatically.

## What the experiment exposes

The actual UI is small. Most of `src/main.cpp` is currently application plumbing: SDL event
translation, the render target and frame loop, font discovery, and runtime shader compiler
setup. `termin-gui-native` provides widgets, document/layout, painting, and the draw-list
renderer, but it does not yet provide a high-level native application/window host. That is the
main source of complexity in the smallest standalone utility.
