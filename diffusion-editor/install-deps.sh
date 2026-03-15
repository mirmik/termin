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
echo "=== Installing diffusion-editor requirements ==="
$PIP install --no-cache-dir --no-build-isolation -r requirements.txt

echo ""
echo "Done. All dependencies installed into $VENV"
