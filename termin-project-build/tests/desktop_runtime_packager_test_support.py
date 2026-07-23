from pathlib import Path


def write_fake_distribution(
    site_packages: Path,
    distribution: str,
    files: dict[str, str],
    requires: list[str] | None = None,
    version: str = "1.0",
) -> None:
    normalized = distribution.replace("-", "_")
    dist_info = site_packages / f"{normalized}-{version}.dist-info"
    dist_info.mkdir(parents=True)
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {distribution}",
        f"Version: {version}",
    ]
    for requirement in requires or []:
        metadata_lines.append(f"Requires-Dist: {requirement}")
    (dist_info / "METADATA").write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

    record_paths: list[str] = []
    for rel_path, text in files.items():
        path = site_packages / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        record_paths.append(rel_path)
    record_paths.append(f"{dist_info.name}/METADATA")
    record_paths.append(f"{dist_info.name}/RECORD")
    (dist_info / "RECORD").write_text(
        "".join(f"{path},,\n" for path in record_paths),
        encoding="utf-8",
    )


def write_fake_player_runtime_distributions(site_packages: Path) -> None:
    distributions: dict[str, tuple[dict[str, str], list[str]]] = {
        "termin-player": ({"termin/player/__init__.py": "VALUE = 'player seed'\n"}, ["termin-mcp"]),
        "termin-mcp": ({"termin/mcp/__init__.py": "VALUE = 'mcp seed'\n"}, []),
        "termin-nanobind": ({"termin_nanobind/__init__.py": "VALUE = 'nanobind seed'\n"}, []),
        "tcbase": ({"tcbase/__init__.py": "VALUE = 'runtime seed'\n"}, []),
        "termin-assets": ({"termin_assets_seed/__init__.py": "VALUE = 'assets seed'\n"}, []),
        "termin-default-assets": ({"termin/default_assets/__init__.py": "VALUE = 'default assets seed'\n"}, []),
        "termin-stdlib": (
            {
                "termin/stdlib/__init__.py": "VALUE = 'stdlib seed'\n",
                "termin/stdlib/resources/materials/BlinnPhong.material": "{}\n",
            },
            [],
        ),
        "termin-prefab": ({"termin/prefab_seed/__init__.py": "VALUE = 'prefab seed'\n"}, []),
        "termin-glb": ({"termin/glb/__init__.py": "VALUE = 'glb seed'\n"}, ["termin-skeleton", "termin-animation"]),
        "termin-tween": ({"termin/tween/__init__.py": "VALUE = 'tween seed'\n"}, []),
        "termin-components-tween": ({"termin/tween_components/__init__.py": "VALUE = 'tween components seed'\n"}, []),
        "termin-components-kinematic": (
            {
                "termin/kinematic/__init__.py": "VALUE = 'kinematic seed'\n",
                "termin/kinematic/kinematic_components.py": "VALUE = 'kinematic components seed'\n",
                "termin_kinematic_component_specs/__init__.py": "COMPONENT_SPECS = ()\n",
            },
            [],
        ),
        "termin-audio": ({"termin/audio/__init__.py": "VALUE = 'audio seed'\n"}, []),
        "termin-voxels": ({"termin/voxels/__init__.py": "VALUE = 'voxels seed'\n"}, []),
        "termin-components-voxels": ({"termin/voxel_components/__init__.py": "VALUE = 'voxel components seed'\n"}, []),
        "termin-components-physics": ({"termin/physics_components/__init__.py": "VALUE = 'physics components seed'\n"}, []),
        "termin-components-ui": ({"termin/ui_components/__init__.py": "VALUE = 'ui components seed'\n"}, []),
        "termin-materials": ({"termin/materials/__init__.py": "VALUE = 'materials seed'\n"}, []),
        "termin-shader-runtime": (
            {
                "termin/shader_tools.py": "VALUE = 'shader tools seed'\n",
                "termin/shader_runtime.py": "VALUE = 'shader runtime seed'\n",
            },
            [],
        ),
        "termin-render-passes": ({"termin/render_passes/__init__.py": "VALUE = 'render passes seed'\n"}, []),
        "termin-modules": ({"termin_modules/__init__.py": "VALUE = 'modules seed'\n"}, []),
        "termin-project": ({"termin/project/__init__.py": "VALUE = 'project seed'\n"}, []),
        "termin-project-modules": (
            {"termin/project_modules/__init__.py": "VALUE = 'project modules seed'\n"},
            ["termin-engine", "termin-project", "termin-modules"],
        ),
        "termin-scene": ({"termin/scene/__init__.py": "VALUE = 'scene seed'\n"}, []),
        "termin-display": (
            {
                "termin/display/__init__.py": "VALUE = 'display seed'\n",
                "termin/viewport/__init__.py": "VALUE = 'viewport seed'\n",
            },
            ["termin-image", "optional-extra; extra == 'debug'"],
        ),
        "termin-engine": ({"termin/engine/__init__.py": "VALUE = 'engine seed'\n"}, []),
        "termin-render": ({"termin/render/__init__.py": "VALUE = 'render seed'\n"}, []),
        "termin-components-render": ({"termin/render_components/__init__.py": "VALUE = 'render components seed'\n"}, []),
        "termin-input": ({"termin/input/__init__.py": "VALUE = 'input seed'\n"}, []),
        "termin-inspect": ({"termin/inspect/__init__.py": "VALUE = 'inspect seed'\n"}, []),
        "termin-collision": ({"termin/collision/__init__.py": "VALUE = 'collision seed'\n"}, []),
        "termin-physics": ({"termin/physics/__init__.py": "VALUE = 'physics seed'\n"}, []),
        "termin-physics-fem": ({"termin/physics_fem/__init__.py": "VALUE = 'physics fem seed'\n"}, ["termin-qopt"]),
        "termin-navmesh": ({"termin/navmesh/__init__.py": "VALUE = 'navmesh seed'\n"}, []),
        "termin-lighting": ({"termin/lighting/__init__.py": "VALUE = 'lighting seed'\n"}, []),
        "tmesh": ({"tmesh/__init__.py": "VALUE = 'tmesh seed'\n"}, []),
        "tgfx": ({"tgfx/__init__.py": "VALUE = 'tgfx seed'\n"}, []),
        "tcgui": ({"tcgui/__init__.py": "VALUE = 'tcgui seed'\n"}, []),
        "numpy": ({"numpy/__init__.py": "VALUE = 'numpy seed'\n"}, []),
        "termin-image": ({"termin/image/__init__.py": "VALUE = 'image seed'\n"}, []),
        "scipy": ({"scipy/__init__.py": "VALUE = 'scipy dependency'\n"}, []),
        "termin-qopt": ({"termin/fem/__init__.py": "VALUE = 'qopt fem seed'\n"}, ["scipy"]),
        "termin-skeleton": ({"termin/skeleton/__init__.py": "VALUE = 'skeleton seed'\n"}, []),
        "termin-animation": ({"termin/animation/__init__.py": "VALUE = 'animation seed'\n"}, []),
        "optional-extra": ({"optional_extra/__init__.py": "VALUE = 'optional extra'\n"}, []),
        "termin-build-tools": ({"termin_build/__init__.py": "VALUE = 'build tools'\n"}, ["setuptools"]),
    }
    for distribution, (files, requires) in distributions.items():
        write_fake_distribution(site_packages, distribution, files, requires=requires)
