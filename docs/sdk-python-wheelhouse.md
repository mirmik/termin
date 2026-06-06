# SDK Python Wheelhouse

`./build-sdk.sh` exports Termin Python wheels into:

```text
sdk/wheels/
```

These wheels are SDK-backed. They contain Python packages and native binding
modules copied from the CMake build output, but shared runtime libraries remain
in `sdk/lib`. This avoids duplicating the same C++ libraries into every wheel.

External Python projects should install Termin packages from the wheelhouse with
`TERMIN_SDK` pointing at the SDK:

```bash
TERMIN_SDK=/path/to/termin/sdk \
python -m pip install --find-links /path/to/termin/sdk/wheels tcgui termin-display
```

`pip` will resolve the Termin dependency chain from `sdk/wheels`. Non-Termin
dependencies such as `numpy`, `Pillow`, `PyYAML`, and `nanobind` are still
normal Python dependencies and can come from PyPI or another package source.

For local development from source, `./install-pip-packages.sh` remains the
host-environment install path. It uses the same package list as
`./build-sdk-wheels.sh`.
