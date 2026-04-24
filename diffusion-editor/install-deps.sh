#!/bin/bash
# Install termin-base, termin-graphics, and termin-gui into the local venv.
# Run from the diffusion-editor directory.
set -e

cd "$(dirname "$0")"

VENV="./venv"
if [ ! -d "$VENV" ]; then
    echo "Creating venv..."
    python3 -m venv "$VENV"
fi

PIP="$VENV/bin/pip"

TERMIN_ENV="$(cd .. && pwd)"

echo "=== Installing termin-build-tools ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-build-tools"

echo ""
echo "=== Installing nanobind + termin-nanobind ==="
$PIP install --no-cache-dir nanobind
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-nanobind-sdk"

echo ""
echo "=== Installing termin-base (tcbase) ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-base"

echo ""
echo ""
echo "=== Installing termin-mesh (tmesh) ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-mesh"

echo ""
echo "=== Installing termin-graphics (tgfx) ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-graphics"

echo ""
echo "=== Installing termin-gui (tcgui) ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-gui"

echo ""
echo "=== Installing termin-inspect (transitive via termin-scene) ==="
# termin.scene.__init__ pulls in termin.scene.python_component which
# in turn needs termin.inspect.InspectField. The chain is forced by
# the nanobind cross-module registration below.
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-inspect"

echo ""
echo "=== Installing termin-scene (tc_scene_handle types) ==="
# `termin.display._display_native` hard-imports `termin.scene._scene_native`
# at nanobind init to resolve cross-module type references (tc_scene_handle
# in viewport bindings). Without it `termin.display.__init__` fails
# before `_platform_native` is reachable — we need termin-scene even
# though diffusion-editor only uses BackendWindow.
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-scene"

echo ""
echo "=== Installing termin-display (BackendWindow) ==="
# BackendWindow replaces the old SDL+GL bootstrap in main.py; under
# TERMIN_BACKEND=vulkan it acquires a VkSurfaceKHR and drives the
# swapchain. Must be installed alongside tgfx so the process shares
# a single IRenderDevice.
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-display"

echo ""
echo "=== Installing diffusion-editor requirements ==="
$PIP install --no-cache-dir --no-build-isolation -r requirements.txt

echo ""
echo "Done. All dependencies installed into $VENV"
