#!/bin/bash
set -e

cd "$(dirname "$0")"

# Create build directory
mkdir -p build
cd build

# Configure
cmake .. -DCMAKE_BUILD_TYPE=Release \
         -DCMAKE_INSTALL_PREFIX=../../termin/geombase

# Build
cmake --build . -j$(nproc)

# Install to python package
cmake --install .

echo "Build complete! Module installed to termin/geombase/_geom_native.so"
