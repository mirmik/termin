@echo off
REM Build Termin documentation

REM Install dependencies if needed
pip install -r requirements.txt -q

REM Generate Doxygen XML
echo Running Doxygen...
doxygen Doxyfile

REM Build HTML
echo Running Sphinx...
sphinx-build -b html . _build/html

echo.
echo Build complete! Open _build/html/index.html
start _build/html/index.html
