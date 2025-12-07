@echo off
setlocal

cd /d "%~dp0"

:: Create build directory
if not exist build mkdir build
cd build

:: Configure (Visual Studio generator auto-detected)
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=..\..\termin

:: Build
cmake --build . --config Release -j %NUMBER_OF_PROCESSORS%

:: Install to python packages
cmake --install . --config Release

echo.
echo Build complete!
echo   termin\geombase\_geom_native.pyd
echo   termin\colliders\_colliders_native.pyd
echo   termin\physics\_physics_native.pyd

endlocal
