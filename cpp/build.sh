#!/bin/bash
set -e

cd "$(dirname "$0")"

# Create build directory
mkdir -p build
cd build

# Configure
cmake .. -DCMAKE_BUILD_TYPE=Debug \
         -DCMAKE_INSTALL_PREFIX=../../termin

# Build
cmake --build . -j$(nproc)

# Install to python packages
cmake --install .

echo "Build complete!"
echo "  termin/geombase/_geom_native.so"
echo "  termin/colliders/_colliders_native.so"
echo "  termin/physics/_physics_native.so"
