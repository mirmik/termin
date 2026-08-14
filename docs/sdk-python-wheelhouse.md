# SDK Python Wheelhouse

`task build --` exports Termin Python wheels into:

```text
sdk/wheels/
```

These wheels are SDK-backed. They contain Python packages and native binding
modules copied from the CMake build output, but shared runtime libraries remain
in `sdk/lib`. This avoids duplicating the same C++ libraries into every wheel.
The editor application is deliberately absent: `termin-app` has no wheel, and
its `termin.editor`/launcher payload is installed only into the SDK application
runtime from `build-system/application-python-payloads.json`.

External Python projects should install Termin packages from the wheelhouse with
`TERMIN_SDK` pointing at the SDK:

```bash
TERMIN_SDK=/path/to/termin/sdk \
python -m pip install --find-links /path/to/termin/sdk/wheels termin-gui-native termin-display
```

The minimal native cgltf importer is available independently of the editor
asset stack:

```bash
TERMIN_SDK=/path/to/termin/sdk \
python -m pip install --find-links /path/to/termin/sdk/wheels termin-glb-native
```

It provides `termin.glb.native.NativeGLBDocument` and `build_mesh`; install the
optional `termin-glb` distribution when `GLBAsset`, resource publication, or
scene instantiation is required.

`pip` will resolve the Termin dependency chain from `sdk/wheels`. Non-Termin
dependencies such as `numpy`, `PyYAML`, and `nanobind` are still normal Python
dependencies and can come from PyPI or another package source. Runtime image
decoding is provided by `termin-image` backed by native codec libraries instead
of Pillow.

For local development from source, use `task install:packages`. It uses the
same package list as `task build:wheels --` and therefore installs library
distributions only.
