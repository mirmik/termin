#!/usr/bin/env python3
"""Generate library dependency graph from CMakeLists.txt and setup.py files.

Parses:
- C/C++ deps from target_link_libraries() in CMakeLists.txt
- Python deps from install_requires in setup.py

Outputs docs/library-dependencies.dot, .png, .svg
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Map CMake target namespaces to directory names
CMAKE_TARGET_TO_DIR = {
    "tcbase": "termin-base",
    "termin_base": "termin-base",
    "tgfx": "termin-graphics",
    "termin_graphics": "termin-graphics",
    "termin_mesh": "termin-mesh",
    "termin_scene": "termin-scene",
    "termin_render": "termin-render",
    "termin_display": "termin-display",
    "termin_input": "termin-input",
    "termin_inspect": "termin-inspect",
    "termin_collision": "termin-collision",
    "termin_engine": "termin-engine",
    "termin_physics": "termin-physics",
    "termin_skeleton": "termin-skeleton",
    "termin_animation": "termin-animation",
    "termin_modules": "termin-modules",
    "termin_components_render": "termin-components-render",
    "termin_components_mesh": "termin-components-mesh",
    "termin_components_collision": "termin-components-collision",
    "termin_components_kinematic": "termin-components-kinematic",
    "termin_components_physics": "termin-components-physics",
    "termin_components_skeleton": "termin-components-skeleton",
    "termin_components_animation": "termin-components-animation",
    "termin": "termin",
}

# Map Python package names to directory names
PYTHON_PKG_TO_DIR = {
    "tcbase": "termin-base",
    "tgfx": "termin-graphics",
    "tmesh": "termin-mesh",
    "tcgui": "termin-gui",
    "tcnodegraph": "termin-nodegraph",
    "termin_modules": "termin-modules",
    "termin": "termin",
}

# External deps to skip
EXTERNAL_PKGS = {
    "numpy", "scipy", "Pillow", "PyOpenGL", "glfw", "pyassimp",
    "PyQt6", "PyYAML", "sdl2", "pysdl2-dll",
}

# Map Python import paths to directory names.
# Longer prefixes are matched first (most specific wins).
PYTHON_IMPORT_TO_DIR = {
    # Standalone packages
    "tcbase": "termin-base",
    "tgfx": "termin-graphics",
    "tmesh": "termin-mesh",
    "tcgui": "termin-gui",
    "tcnodegraph": "termin-nodegraph",
    "termin_modules": "termin-modules",
    "diffusion_editor": "diffusion-editor",
    # termin.* submodules → actual library
    "termin.geombase": "termin-base",
    "termin.collision": "termin-collision",
    "termin.colliders": "termin-components-collision",
    "termin.physics": "termin-physics",
    "termin.physics_components": "termin-components-physics",
    "termin.visualization.core": "termin-scene",
    "termin.visualization.components": "termin-components-mesh",
    "termin.entity": "termin-scene",
    "termin.scene": "termin-scene",
    "termin.editor.inspect_field": "termin-inspect",
    "termin.inspect": "termin-inspect",
    "termin.render_components": "termin-components-render",
    "termin.render_framework": "termin-render",
    "termin.lighting": "termin-render",
    "termin.viewport": "termin-render",
    "termin.engine": "termin-engine",
    "termin.input": "termin-input",
    "termin.display": "termin-display",
    "termin.skeleton": "termin-skeleton",
    "termin.animation": "termin-animation",
    "termin.animation_components": "termin-components-animation",
    "termin.skeleton_components": "termin-components-skeleton",
    "termin.kinematic": "termin-components-kinematic",
    "termin.modules": "termin-modules",
    # Fallback: termin.* → termin (editor, assets, etc.)
    "termin": "termin",
}

# Directories to scan for CMakeLists.txt
CMAKE_DIRS = []
for name in os.listdir(ROOT):
    path = os.path.join(ROOT, name)
    if not os.path.isdir(path):
        continue
    if name.startswith("termin-") and name != "termin-nanobind-sdk":
        cmake = os.path.join(path, "CMakeLists.txt")
        if os.path.exists(cmake):
            CMAKE_DIRS.append((name, cmake))
    # termin-components subdirectories
    if name == "termin-components":
        for sub in os.listdir(path):
            subpath = os.path.join(path, sub)
            cmake = os.path.join(subpath, "CMakeLists.txt")
            if os.path.isdir(subpath) and os.path.exists(cmake):
                CMAKE_DIRS.append((sub, cmake))

# termin/ — scan root and cpp/ CMakeLists.txt
for subpath in ["CMakeLists.txt", "cpp/CMakeLists.txt"]:
    cmake = os.path.join(ROOT, "termin", subpath)
    if os.path.exists(cmake):
        CMAKE_DIRS.append(("termin", cmake))

# Pure-Python packages (no CMakeLists.txt) — will be scanned via import analysis
PYTHON_ONLY_DIRS = {
    "diffusion-editor": os.path.join(ROOT, "diffusion-editor"),
}


def parse_cmake_deps(cmake_path):
    """Extract dependencies from target_link_libraries() and find_package().

    For target_link_libraries: skip _test and _native targets (bindings/tests).
    For find_package: only count those outside TERMIN_BUILD_PYTHON blocks.
    """
    with open(cmake_path) as f:
        content = f.read()

    deps = set()

    # 1. Parse target_link_libraries blocks (skip bindings and tests)
    for match in re.finditer(
        r'target_link_libraries\s*\(\s*(\w+)(.*?)\)',
        content, re.DOTALL
    ):
        target_name = match.group(1)
        body = match.group(2)

        if "_test" in target_name or "_native" in target_name:
            continue

        for dep_match in re.finditer(r'(\w+)::(\w+)', body):
            ns = dep_match.group(1)
            tgt = dep_match.group(2)
            dir_name = CMAKE_TARGET_TO_DIR.get(ns) or CMAKE_TARGET_TO_DIR.get(tgt)
            if dir_name:
                deps.add(dir_name)

    # 2. Parse find_package() only in the non-Python section.
    #    Split content at if(TERMIN_BUILD_PYTHON) — only parse before it.
    python_block_start = re.search(
        r'if\s*\(\s*TERMIN_BUILD_PYTHON\s*\)', content)
    core_content = content[:python_block_start.start()] if python_block_start else content

    for match in re.finditer(r'find_package\s*\(\s*(\w+)', core_content):
        pkg = match.group(1)
        if pkg in ("Python", "nanobind", "GTest", "Threads", "OpenGL",
                    "SDL2", "PkgConfig", "Qt5", "Qt6"):
            continue
        dir_name = CMAKE_TARGET_TO_DIR.get(pkg)
        if dir_name:
            deps.add(dir_name)

    return deps


def parse_python_deps(setup_path):
    """Extract install_requires from setup.py."""
    with open(setup_path) as f:
        content = f.read()

    deps = set()
    # Find install_requires=[...] block
    match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not match:
        return deps

    for pkg_match in re.finditer(r'"([^">=<\[]+)', match.group(1)):
        pkg = pkg_match.group(1).strip()
        if pkg in EXTERNAL_PKGS:
            continue
        dir_name = PYTHON_PKG_TO_DIR.get(pkg)
        if dir_name:
            deps.add(dir_name)

    return deps


def _resolve_import(import_path):
    """Map a Python import path to a library dir using longest prefix match."""
    # Sort keys by length descending for longest-prefix-first matching
    for prefix in sorted(PYTHON_IMPORT_TO_DIR, key=len, reverse=True):
        if import_path == prefix or import_path.startswith(prefix + "."):
            return PYTHON_IMPORT_TO_DIR[prefix]
    return None


def parse_python_imports(python_dir):
    """Scan .py files for imports and map to library dirs."""
    deps = set()
    if not os.path.isdir(python_dir):
        return deps

    for dirpath, _, filenames in os.walk(python_dir):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fname)
            try:
                with open(filepath) as f:
                    for line in f:
                        line = line.strip()
                        m = re.match(r'(?:from|import)\s+([\w.]+)', line)
                        if not m:
                            continue
                        import_path = m.group(1)
                        dir_name = _resolve_import(import_path)
                        if dir_name:
                            deps.add(dir_name)
            except (OSError, UnicodeDecodeError):
                continue

    return deps


def main():
    # Collect all edges: (from_dir, to_dir) meaning to_dir depends on from_dir
    edges = set()
    all_nodes = set()

    for dir_name, cmake_path in CMAKE_DIRS:
        all_nodes.add(dir_name)
        cmake_deps = parse_cmake_deps(cmake_path)
        for dep in cmake_deps:
            if dep != dir_name:  # no self-loops
                edges.add((dep, dir_name))
                all_nodes.add(dep)

    # Python deps from setup.py
    python_dirs = [
        ("termin-base", "termin-base"),
        ("termin-graphics", "termin-graphics"),
        ("termin-mesh", "termin-mesh"),
        ("termin-gui", "termin-gui"),
        ("termin-modules", "termin-modules"),
        ("termin-nodegraph", "termin-nodegraph"),
        ("termin", "termin"),
    ]

    for dir_name, subdir in python_dirs:
        setup_path = os.path.join(ROOT, subdir, "setup.py")
        if not os.path.exists(setup_path):
            continue
        all_nodes.add(dir_name)
        py_deps = parse_python_deps(setup_path)
        for dep in py_deps:
            if dep != dir_name:
                edges.add((dep, dir_name))
                all_nodes.add(dep)

    # Python import scanning for packages that have no CMake/setup.py deps,
    # plus termin/termin/ itself (top-level package depends on everything).
    dirs_with_edges = set()
    for _, dst in edges:
        dirs_with_edges.add(dst)

    scan_targets = []

    # Packages with no edges yet — scan their python/ dirs
    for dir_name, _ in CMAKE_DIRS:
        if dir_name in dirs_with_edges:
            continue
        for candidate in [
            os.path.join(ROOT, dir_name, "python"),
            os.path.join(ROOT, "termin-components", dir_name, "python"),
        ]:
            if os.path.isdir(candidate):
                scan_targets.append((dir_name, candidate))

    # Always scan termin/termin/ for Python-level deps (top package)
    termin_py = os.path.join(ROOT, "termin", "termin")
    if os.path.isdir(termin_py):
        scan_targets.append(("termin", termin_py))

    # Pure-Python packages (no CMake)
    for dir_name, py_dir in PYTHON_ONLY_DIRS.items():
        if os.path.isdir(py_dir):
            scan_targets.append((dir_name, py_dir))

    for dir_name, py_dir in scan_targets:
        all_nodes.add(dir_name)
        import_deps = parse_python_imports(py_dir)
        for dep in import_deps:
            if dep != dir_name:
                edges.add((dep, dir_name))
                all_nodes.add(dep)

    # Transitive reduction: remove edge A→B if there's a path A→...→B of length >= 2
    def reachable_without_direct(src, dst, edges_set):
        """Check if dst is reachable from src without using the direct edge."""
        visited = set()
        stack = []
        # Start from all neighbors of src except dst
        for (a, b) in edges_set:
            if a == src and b != dst:
                stack.append(b)
        while stack:
            node = stack.pop()
            if node == dst:
                return True
            if node in visited:
                continue
            visited.add(node)
            for (a, b) in edges_set:
                if a == node and b not in visited:
                    stack.append(b)
        return False

    reduced_edges = set()
    for edge in edges:
        src, dst = edge
        if not reachable_without_direct(src, dst, edges):
            reduced_edges.add(edge)

    print(f"  Transitive reduction: {len(edges)} -> {len(reduced_edges)} edges")
    edges = reduced_edges

    # Node groups (rendered as subgraph clusters with border)
    GROUPS = {
        "UI": ["termin-gui", "termin-nodegraph"],
    }

    # Build reverse map: node → group name
    node_to_group = {}
    for group_name, members in GROUPS.items():
        for m in members:
            node_to_group[m] = group_name

    # Generate .dot
    lines = []
    lines.append('digraph termin_dependencies {')
    lines.append('\tgraph [bgcolor=white,')
    lines.append('\t\tnodesep=0.45,')
    lines.append('\t\toverlap=false,')
    lines.append('\t\tpad=0.2,')
    lines.append('\t\trankdir=LR,')
    lines.append('\t\tranksep=0.9,')
    lines.append('\t\tsplines=true')
    lines.append('\t];')
    lines.append('\tnode [color="#444444",')
    lines.append('\t\tfillcolor="#f7f7f7",')
    lines.append('\t\tfontname="DejaVu Sans",')
    lines.append('\t\tfontsize=11,')
    lines.append('\t\tmargin="0.10,0.06",')
    lines.append('\t\tshape=box,')
    lines.append('\t\tstyle="rounded,filled"')
    lines.append('\t];')
    lines.append('\tedge [arrowsize=0.7,')
    lines.append('\t\tcolor="#666666",')
    lines.append('\t\tpenwidth=1.1')
    lines.append('\t];')
    lines.append('')

    # Grouped nodes (inside subgraph clusters)
    for group_name, members in sorted(GROUPS.items()):
        lines.append(f'\tsubgraph cluster_{group_name.lower().replace(" ", "_")} {{')
        lines.append(f'\t\tlabel="{group_name}";')
        lines.append('\t\tstyle=dashed;')
        lines.append('\t\tcolor="#999999";')
        lines.append('\t\tfontname="DejaVu Sans";')
        lines.append('\t\tfontsize=12;')
        for node in sorted(members):
            if node in all_nodes:
                lines.append(f'\t\t"{node}";')
        lines.append('\t}')
        lines.append('')

    # Ungrouped nodes
    for node in sorted(all_nodes):
        if node not in node_to_group:
            lines.append(f'\t"{node}";')

    lines.append('')

    # Edges
    for src, dst in sorted(edges):
        lines.append(f'\t"{src}" -> "{dst}";')

    lines.append('}')

    dot_path = os.path.join(ROOT, "docs", "library-dependencies.dot")
    with open(dot_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Written {dot_path}")
    print(f"  {len(all_nodes)} nodes, {len(edges)} edges")

    # Render if dot is available
    try:
        png_path = dot_path.replace(".dot", ".png")
        svg_path = dot_path.replace(".dot", ".svg")
        subprocess.run(["dot", "-Tpng", dot_path, "-o", png_path], check=True)
        subprocess.run(["dot", "-Tsvg", dot_path, "-o", svg_path], check=True)
        print(f"  Rendered {png_path}")
        print(f"  Rendered {svg_path}")
    except FileNotFoundError:
        print("  Warning: 'dot' not found, skipping PNG/SVG render")
        print("  Install graphviz: sudo apt install graphviz")


if __name__ == "__main__":
    main()
