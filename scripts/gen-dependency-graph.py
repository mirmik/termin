#!/usr/bin/env python3
"""Generate the repository library dependency graph.

Parses:
- C/C++ deps from termin_require_package(), find_package(), and
  target_link_libraries() in CMakeLists.txt
- Python deps from install_requires in setup.py
- Python deps from imports for selected namespace packages

Outputs docs/library-dependencies.dot, .png, .svg, and standalone .html
"""

import argparse
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_TEMPLATE = os.path.join(ROOT, "scripts", "dependency-graph-template.html")

# Map CMake target namespaces to directory names
CMAKE_TARGET_TO_DIR = {
    "tcbase": "termin-base",
    "termin_base": "termin-base",
    "tgfx": "termin-graphics",
    "termin_graphics": "termin-graphics",
    "termin_mesh": "termin-mesh",
    "termin_scene": "termin-scene",
    "termin_lighting": "termin-lighting",
    "termin_render": "termin-render",
    "termin_render_passes": "termin-render-passes",
    "termin_display": "termin-display",
    "termin_window": "termin-window",
    "termin_input": "termin-input",
    "termin_inspect": "termin-inspect",
    "termin_collision": "termin-collision",
    "termin_engine": "termin-engine",
    "termin_physics": "termin-physics",
    "termin_skeleton": "termin-skeleton",
    "termin_animation": "termin-animation",
    "termin_modules": "termin-modules",
    "termin_components_render": "termin-components-render",
    "termin_components_ui": "termin-components-ui",
    "termin_components_mesh": "termin-components-mesh",
    "termin_components_collision": "termin-components-collision",
    "termin_components_kinematic": "termin-components-kinematic",
    "termin_components_physics": "termin-components-physics",
    "termin_components_skeleton": "termin-components-skeleton",
    "termin_components_animation": "termin-components-animation",
    "tcplot": "tcplot",
    # The installed CMake package `termin` is produced from termin-app/cpp.
    # On the high-level diagram route those native bundle dependencies to
    # termin-app; the `termin` node itself is only the Python namespace root.
    "termin": "termin-app",
}

# Map Python package names to directory names
PYTHON_PKG_TO_DIR = {
    "termin-mesh": "termin-mesh",
    "termin-graphics": "termin-graphics",
    "termin-nodegraph": "termin-nodegraph",
    "termin_modules": "termin-modules",
    "termin-plot": "tcplot",
    "termin": "termin",
    "termin-app": "termin-app",
    "termin-player": "termin-player",
    "termin-project": "termin-project",
    "termin-project-build": "termin-project-build",
    "termin-project-modules": "termin-project-modules",
    "termin-stdlib": "termin-stdlib",
    "termin-mcp": "termin-mcp",
    "termin-shader-runtime": "termin-shader-runtime",
    "termin-base": "termin-base",
    "termin-assets": "termin-assets",
    "termin-tween": "termin-tween",
    "termin-voxels": "termin-voxels",
    "termin-components-tween": "termin-components-tween",
    "termin-components-voxels": "termin-components-voxels",
    "termin-components-physics": "termin-components-physics",
    "termin-physics-fem": "termin-physics-fem",
    "termin-components-ui": "termin-components-ui",
    "termin-inspect": "termin-inspect",
    "termin-qopt": "termin-qopt",
    "termin-scene": "termin-scene",
    "termin-nanobind": "termin-nanobind-sdk",
    "termin-csg": "termin-csg",
    "termin-lighting": "termin-lighting",
    "termin-render-passes": "termin-render-passes",
    # "termin-entity": "termin-entity",  # удалён, мигрирован в termin-app
    "termin-navmesh": "termin-navmesh",
}

# External deps to skip
EXTERNAL_PKGS = {
    "numpy", "scipy", "glfw", "pyassimp",
    "PyYAML",
}

# Map Python import paths to directory names.
# Longer prefixes are matched first (most specific wins).
PYTHON_IMPORT_TO_DIR = {
    # Standalone packages
    "termin.base": "termin-base",
    "termin.graphics": "termin-graphics",
    "termin.mesh": "termin-mesh",
    "termin.nodegraph": "termin-nodegraph",
    "termin_modules": "termin-modules",
    "termin_nanobind": "termin-nanobind-sdk",
    "termin_assets": "termin-assets",
    "termin.plot": "tcplot",
    # termin.* submodules → actual library
    "termin.editor_core": "termin-app",
    "termin.project_build": "termin-project-build",
    "termin.project_modules": "termin-project-modules",
    "termin.project": "termin-project",
    "termin.stdlib": "termin-stdlib",
    "termin.glb.native": "termin-glb-native",
    "termin.glb._glb_native": "termin-glb-native",
    "termin.glb": "termin-glb",
    "termin.player": "termin-player",
    "termin.mcp": "termin-mcp",
    "termin.shader_runtime": "termin-shader-runtime",
    "termin.shader_tools": "termin-shader-runtime",
    "termin.csg": "termin-csg",
    "termin.geombase": "termin-base",
    "termin.collision": "termin-collision",
    "termin.colliders": "termin-components-collision",
    "termin.fem": "termin-qopt",
    "termin.linalg": "termin-qopt",
    "termin.physics_fem": "termin-physics-fem",
    "termin.physics": "termin-physics",
    "termin.physics_components": "termin-components-physics",
    # "termin.entity" был удалён — ECS API мигрирован в termin.scene
    "termin.scene": "termin-scene",
    "termin.inspect": "termin-inspect",
    "termin.render_components": "termin-components-render",
    "termin.ui_components": "termin-components-ui",
    "termin.render_framework": "termin-render",
    "termin.render_passes": "termin-render-passes",
    "termin.lighting": "termin-lighting",
    "termin.viewport": "termin-render",
    "termin.engine": "termin-engine",
    "termin.input": "termin-input",
    "termin.display": "termin-display",
    "termin.skeleton": "termin-skeleton",
    "termin.animation": "termin-animation",
    "termin.animation_components": "termin-components-animation",
    "termin.skeleton_components": "termin-components-skeleton",
    "termin.kinematic": "termin-components-kinematic",
    "termin.robot": "termin-qopt",
    "termin.navmesh": "termin-navmesh",
    "termin.tween_components": "termin-components-tween",
    "termin.tween": "termin-tween",
    "termin.voxels.component": "termin-components-voxels",
    "termin.voxels.display_component": "termin-components-voxels",
    "termin.voxels.visualization": "termin-components-voxels",
    "termin.voxels.voxelizer_component": "termin-components-voxels",
    "termin.voxels": "termin-voxels",
    # Fallback: bare `import termin` touches only the namespace root.
    "termin": "termin",
}

# Repository packages are owned by districts, while the root CMake graph owns
# orchestration.  Keep this discovery list explicit so generated architecture
# documentation cannot silently regress to the retired flat layout.
DISTRICTS = ("core", "graphics", "engine", "editor", "physics")
PACKAGE_DIRS = {}
for district in DISTRICTS:
    district_path = os.path.join(ROOT, district)
    if not os.path.isdir(district_path):
        continue
    for current_root, directory_names, _file_names in os.walk(district_path):
        directory_names[:] = [
            name for name in directory_names
            if name not in {"build", "install", "sdk", ".git", "__pycache__"}
        ]
        package_name = os.path.basename(current_root)
        if package_name.startswith("termin-") or package_name.startswith("tcplot"):
            PACKAGE_DIRS.setdefault(package_name, current_root)

CMAKE_DIRS = []
for package_name, package_path in sorted(PACKAGE_DIRS.items()):
    cmake = os.path.join(package_path, "CMakeLists.txt")
    if os.path.exists(cmake) and package_name != "termin-nanobind-sdk":
        CMAKE_DIRS.append((package_name, cmake))

# Main native/core bundle exported as the CMake package `termin`.
# It is an implementation detail of termin-app on this high-level diagram.
termin_native_cmake = os.path.join(ROOT, "editor", "termin-app", "cpp", "CMakeLists.txt")
if os.path.exists(termin_native_cmake):
    CMAKE_DIRS.append(("termin-app", termin_native_cmake))

# Pure-Python packages (no CMakeLists.txt) — will be scanned via import analysis.
PYTHON_ONLY_DIRS = {
    "termin-shader-runtime": os.path.join(
        ROOT, "graphics", "termin-shader-runtime", "termin"
    ),
    "termin-stdlib": os.path.join(ROOT, "engine", "termin-stdlib", "python", "termin"),
}

# Dependencies that are structural but not reliably visible from setup.py or
# CMake parsing. `termin` is the namespace root; packages extending termin.*
# conceptually sit on top of it, but it does not depend on engine libraries.
MANUAL_DEPS = {
    "termin-app": {"termin"},
    "termin-player": {"termin"},
    "termin-shader-runtime": {"termin"},
    "termin-stdlib": {"termin"},
    # "termin-entity": {"termin"},  # удалён, мигрирован в termin-app
    "termin-navmesh": {"termin"},
    "termin-tween": {"termin"},
    "termin-components-tween": {"termin-tween"},
    "termin-voxels": {"termin"},
    "termin-components-voxels": {"termin-voxels"},
}


def resolve_cmake_dependency(name):
    """Resolve a CMake package/target name to a repository module.

    Most package names follow the mechanical ``termin_foo`` -> ``termin-foo``
    convention.  CMAKE_TARGET_TO_DIR only contains the historical aliases that
    cannot be inferred that way (tcbase, tgfx, tmesh, ...).
    """
    explicit = CMAKE_TARGET_TO_DIR.get(name)
    if explicit:
        return explicit

    candidate = name.replace("_", "-")
    if candidate in PACKAGE_DIRS:
        return candidate
    return None


def strip_cmake_comments(content):
    """Remove line comments without treating ``#`` inside strings as syntax."""
    result = []
    index = 0
    quote = None
    while index < len(content):
        char = content[index]
        if quote:
            result.append(char)
            if char == "\\" and index + 1 < len(content):
                index += 1
                result.append(content[index])
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
            result.append(char)
        elif char == "#":
            newline = content.find("\n", index)
            if newline == -1:
                break
            result.append("\n")
            index = newline
        else:
            result.append(char)
        index += 1
    return "".join(result)


def iter_cmake_commands(content, command_names):
    """Yield ``(command_name, body)`` for balanced CMake command calls.

    A non-greedy regular expression stops at the first parenthesis and breaks
    on generator expressions and nested conditions.  This small scanner is not
    a complete CMake parser, but it does preserve balanced calls and quoted
    text while ignoring comments.
    """
    content = strip_cmake_comments(content)
    names = set(command_names)
    command_re = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    position = 0

    while True:
        match = command_re.search(content, position)
        if match is None:
            return
        position = match.end()
        command = match.group(1)
        depth = 1
        index = position
        quote = None

        while index < len(content) and depth:
            char = content[index]
            if quote:
                if char == "\\":
                    index += 2
                    continue
                if char == quote:
                    quote = None
                index += 1
                continue
            if char in ('"', "'"):
                quote = char
                index += 1
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1

        if depth:
            return
        if command in names:
            yield command, content[position:index - 1]
            position = index
        else:
            # Search inside control-flow commands such as if()/foreach().
            position = match.end()


def first_cmake_argument(body):
    """Return the first plain argument from a CMake command body."""
    match = re.search(r'[^\s"\']+|"([^"]*)"|\'([^\']*)\'', body)
    if match is None:
        return None
    return next((group for group in match.groups() if group is not None), match.group(0))


def parse_cmake_deps(cmake_path):
    """Extract declared module dependencies from a CMakeLists.txt.

    Package declarations are authoritative even when a dependency is selected
    only by one build profile.  Link declarations complement them for local or
    otherwise implicit dependencies.  Test and binding targets are omitted
    because this is a graph of repository modules, not build-only targets.
    """
    with open(cmake_path, encoding="utf-8") as f:
        content = f.read()

    deps = set()

    package_commands = {"termin_require_package", "termin_csharp_require_package"}
    for _, body in iter_cmake_commands(content, package_commands):
        package = first_cmake_argument(body)
        if package:
            dir_name = resolve_cmake_dependency(package)
            if dir_name:
                deps.add(dir_name)

    for _, body in iter_cmake_commands(content, {"target_link_libraries"}):
        target_name = first_cmake_argument(body) or ""
        build_only_markers = (
            "_test", "_smoke", "_example", "_benchmark", "_bench", "_validator",
        )
        if "_native" in target_name or any(
            marker in target_name for marker in build_only_markers
        ):
            continue

        for dep_match in re.finditer(r'(\w+)::(\w+)', body):
            ns = dep_match.group(1)
            tgt = dep_match.group(2)
            dir_name = resolve_cmake_dependency(ns) or resolve_cmake_dependency(tgt)
            if dir_name:
                deps.add(dir_name)

    for _, body in iter_cmake_commands(content, {"find_package"}):
        pkg = first_cmake_argument(body)
        if pkg in ("Python", "nanobind", "GTest", "Threads", "OpenGL",
                    "SDL2", "PkgConfig", "Qt5", "Qt6"):
            continue
        dir_name = resolve_cmake_dependency(pkg) if pkg else None
        if dir_name:
            deps.add(dir_name)

    return deps


def parse_python_deps(setup_path):
    """Extract install_requires from setup.py."""
    with open(setup_path, encoding="utf-8") as f:
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
                with open(filepath, encoding="utf-8") as f:
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


def render_interactive_html(all_nodes, direct_edges, node_to_group):
    """Render a standalone focused-graph document with embedded direct edges."""
    html_data = {
        "nodes": [
            {"id": node, "group": node_to_group.get(node, "Other")}
            for node in sorted(all_nodes)
        ],
        "edges": [
            {"source": source, "target": dependency}
            for source, dependency in sorted(direct_edges)
        ],
    }
    with open(HTML_TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    encoded_data = json.dumps(html_data, ensure_ascii=False, separators=(",", ":"))
    return html.replace(
        "__DEPENDENCY_GRAPH_DATA__",
        encoded_data.replace("<", "\\u003c"),
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-namespace",
        action="store_true",
        help="include the structural 'termin' Python namespace node",
    )
    parser.add_argument(
        "--all-direct",
        action="store_true",
        help="show every declared direct edge instead of the reduced overview",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="skip Graphviz PNG/SVG rendering (DOT and HTML are still written)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    # Collect edges as (consumer, dependency), matching the rendered arrow.
    edges = set()
    all_nodes = set()

    for dir_name, cmake_path in CMAKE_DIRS:
        all_nodes.add(dir_name)
        cmake_deps = parse_cmake_deps(cmake_path)
        for dep in cmake_deps:
            if dep != dir_name:  # no self-loops
                edges.add((dir_name, dep))
                all_nodes.add(dep)

    # Python deps from setup.py — auto-discover all directories with setup.py
    python_dirs = []
    for name in os.listdir(ROOT):
        path = os.path.join(ROOT, name)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "setup.py")):
            python_dirs.append((name, name))
        if name == "termin-components":
            for sub in os.listdir(path):
                subpath = os.path.join(path, sub)
                setup_path = os.path.join(subpath, "setup.py")
                if os.path.isdir(subpath) and os.path.exists(setup_path):
                    python_dirs.append((sub, os.path.join(name, sub)))

    for dir_name, subdir in python_dirs:
        setup_path = os.path.join(ROOT, subdir, "setup.py")
        if not os.path.exists(setup_path):
            continue
        all_nodes.add(dir_name)
        py_deps = parse_python_deps(setup_path)
        for dep in py_deps:
            if dep != dir_name:
                edges.add((dir_name, dep))
                all_nodes.add(dep)

    # Python import scanning for packages that have no CMake/setup.py deps,
    # plus termin/termin/ itself (top-level package depends on everything).
    dirs_with_edges = set()
    for consumer, _ in edges:
        dirs_with_edges.add(consumer)

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

    # Always scan termin-app/termin/ for Python-level deps. termin-app owns the
    # root `termin` namespace and composes editor/player/runtime packages.
    termin_app_py = os.path.join(ROOT, "termin-app", "termin")
    if os.path.isdir(termin_app_py):
        scan_targets.append(("termin-app", termin_app_py))

    # Pure-Python packages (no CMake)
    for dir_name, py_dir in PYTHON_ONLY_DIRS.items():
        if os.path.isdir(py_dir):
            scan_targets.append((dir_name, py_dir))

    for dir_name, py_dir in scan_targets:
        all_nodes.add(dir_name)
        import_deps = parse_python_imports(py_dir)
        for dep in import_deps:
            if dep != dir_name:
                edges.add((dir_name, dep))
                all_nodes.add(dep)

    manual_edges = set()
    for dst, deps in MANUAL_DEPS.items():
        all_nodes.add(dst)
        for dep in deps:
            if dep != dst:
                edge = (dst, dep)
                edges.add(edge)
                manual_edges.add(edge)
                all_nodes.add(dep)

    if not args.show_namespace:
        all_nodes.discard("termin")
        edges = {edge for edge in edges if "termin" not in edge}

    # The interactive document always needs the truthful direct graph.  Its UI
    # applies depth and direction filters without regenerating the artifact.
    direct_edges = set(edges)

    # Default presentation-only transitive reduction.  --all-direct retains
    # every declaration in the static overview for architectural audits.
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

    if not args.all_direct:
        reduced_edges = set()
        for edge in edges:
            src, dst = edge
            if edge in manual_edges or not reachable_without_direct(src, dst, edges):
                reduced_edges.add(edge)

        print(f"  Transitive reduction: {len(edges)} -> {len(reduced_edges)} edges")
        edges = reduced_edges

    # Node groups (rendered as subgraph clusters with border)
    GROUPS = {
        "UI": ["termin-gui-native", "termin-nodegraph", "tcplot-gui-native"],
        "Application": ["termin-app"],
        "Namespace": ["termin"],
        "Native Interop": ["termin-csharp"],
        "Python Support": ["termin-assets", "termin-nanobind-sdk"],
        "Render Stack": [
            "termin-graphics", "termin-lighting", "termin-render",
            "termin-display", "termin-components-render",
        ],
        "Runtime": ["termin-engine"],
        "Foundation": [
            "termin-base", "termin-mesh", "termin-inspect", "termin-modules",
            "termin-scene", "termin-skeleton", "termin-collision", "termin-input",
            "termin-animation", "termin-physics", "termin-qopt", "termin-csg",
            "termin-navmesh", "termin-tween", "termin-voxels",
        ],
        "Other Components": [
            "termin-components-skeleton", "termin-components-animation",
            "termin-components-collision", "termin-components-physics",
            "termin-physics-fem",
            "termin-components-kinematic", "termin-components-mesh",
            "termin-components-tween", "termin-components-voxels",
            "termin-components-ui",
        ],
        "Thin Facades": [],  # termin-entity удалён
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
    lines.append('\t\tconcentrate=true,')
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
        visible_members = sorted(node for node in members if node in all_nodes)
        if not visible_members:
            continue
        lines.append(f'\tsubgraph cluster_{group_name.lower().replace(" ", "_")} {{')
        lines.append(f'\t\tlabel="{group_name}";')
        lines.append('\t\tstyle=dashed;')
        lines.append('\t\tcolor="#999999";')
        lines.append('\t\tfontname="DejaVu Sans";')
        lines.append('\t\tfontsize=12;')
        for node in visible_members:
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

    html_path = os.path.join(ROOT, "docs", "library-dependencies.html")
    with open(html_path, "w") as f:
        f.write(render_interactive_html(all_nodes, direct_edges, node_to_group))
    print(f"Written {html_path}")

    if args.no_render:
        return

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
