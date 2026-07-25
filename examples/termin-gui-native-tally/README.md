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

The application owns a `WindowedGraphicsSession`, `WindowManager`, document and
`GuiWindowAdapter`; the adapter only translates events and renders the borrowed window.
Set `TERMIN_UI_FONT` to the installed `DroidSans.ttf` path. Use `--frames N` for a
bounded window/render smoke run; CTest uses this mode automatically.

## What the experiment exposes

The actual UI is small, and the surrounding application is now small as well. Tally owns the
lightweight native window, portable input pump, resizable render target, draw-list rendering,
presentation and GPU teardown through framework-neutral window and native-widget adapter APIs.
It contains no SDL types or engine scene/render/input integration from `termin-display`.
