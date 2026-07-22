# Python Package Naming

Этот документ фиксирует текущий контракт именования Python-части SDK: путь в
монорепозитории, имя Python distribution и публичные import namespaces. Он
закрывает повторяющийся класс ошибок, где `install_requires` ссылался на
repo-directory вроде `termin-graphics`, хотя устанавливаемая distribution
называется `tgfx`.

## Policy

- `build-system/packages.json` является source of truth для порядка установки и
  имен internal distributions.
- `setup.py` / `pyproject.toml` должны публиковать distribution name, совпадающий
  с manifest после нормализации PEP 503 (`-`, `_`, `.` считаются одинаковыми).
- `install_requires` внутри репозитория должен ссылаться на distribution name,
  а не на repo path и не на import namespace.
- Новый пакет по умолчанию использует одинаковые repo path и distribution name
  в стиле `termin-*`; исключения требуют явного обоснования в таблице ниже.
- Public import namespace выбирается по domain API. Он не обязан совпадать с
  distribution name: короткие legacy API (`tcbase`, `tmesh`, `tgfx`, `tcgui`,
  `tcplot`) остаются допустимыми исключениями.
- Component spec packages (`*_component_specs`, `*_render_specs`) являются частью
  owning distribution и не должны становиться отдельными internal dependencies.
- `termin-app` не является distribution. Его editor/launcher-модули входят в
  SDK как application-owned payload по
  `build-system/application-python-payloads.json` и не участвуют в этой
  таблице library packages.

## Validation

Текущий automated gate:

- `python -m termin_build.package_manifest --repo-root . --check` проверяет
  manifest, порядок пакетов и native extension declarations.
- `termin-base/tests/python/test_python_package_install_order.py` проверяет
  topological install order, совпадение manifest distribution names с metadata и
  отсутствие неизвестных internal distribution names в `install_requires`.
- тот же тест проверяет, что таблица ниже содержит все manifest
  `source path / distribution` пары в актуальном порядке.

## Inventory

| Source path | Distribution | Public import namespaces | Notes |
|-------------|--------------|--------------------------|-------|
| `termin-build-tools` | `termin-build-tools` | `termin_build` | Build-time helpers. |
| `termin-nanobind-sdk` | `termin-nanobind` | `termin_nanobind` | Distribution keeps historical short SDK name. |
| `termin-base` | `tcbase` | `tcbase`, `termin.geombase` | Legacy short distribution/import name. |
| `termin-image` | `termin-image` | `termin.image` | Native image codecs for texture/tooling paths. |
| `termin-assets` | `termin-assets` | `termin_assets` | Asset runtime contracts. |
| `termin-tween` | `termin-tween` | `termin.tween` | Core tween runtime. |
| `termin-audio` | `termin-audio` | `termin.audio`, `termin.audio.components`, `termin_audio_component_specs` | Audio runtime and component specs. |
| `termin-mesh` | `tmesh` | `tmesh` | Legacy short distribution/import name. |
| `termin-graphics` | `tgfx` | `tgfx` | Legacy short distribution/import name. |
| `termin-voxels` | `termin-voxels` | `termin.voxels` | Voxel core API. |
| `termin-materials` | `termin-materials` | `termin.materials` | Material runtime API. |
| `termin-shader-runtime` | `termin-shader-runtime` | `termin.shader_tools`, `termin.shader_runtime` | Shared shader tool resolution and source-project shader runtime helpers. |
| `termin-gui` | `tcgui` | `tcgui` | Legacy short distribution/import name. |
| `termin-gui-native` | `termin-gui-native` | `termin.gui_native` | Native retained UI document prototype. |
| `termin-inspect` | `termin-inspect` | `termin.inspect` | Inspection metadata API. |
| `termin-scene` | `termin-scene` | `termin.scene` | Scene/ECS API. |
| `termin-mcp` | `termin-mcp` | `termin.mcp` | Shared MCP transport/executor helpers. |
| `termin-prefab` | `termin-prefab` | `termin.prefab` | Namespace package. |
| `termin-display` | `termin-display` | `termin.display`, `termin.viewport` | Display/windowing API. |
| `termin-csg` | `termin-csg` | `termin.csg` | CSG API. |
| `termin-modules` | `termin-modules` | `termin_modules` | Module runtime API. |
| `termin-components/termin-components-kinematic` | `termin-components-kinematic` | `termin.kinematic`, `termin_kinematic_component_specs` | Kinematic components. |
| `termin-lighting` | `termin-lighting` | `termin.lighting` | Lighting API. |
| `termin-components/termin-components-mesh` | `termin-components-mesh` | `termin.mesh`, `termin_mesh_component_specs` | Scene mesh components. |
| `termin-components/termin-components-tween` | `termin-components-tween` | `termin_tween_component_specs` | Tween component specs. |
| `termin-input` | `termin-input` | `termin.input` | Input API. |
| `termin-collision` | `termin-collision` | `termin.colliders`, `termin.collision`, `termin_collision_component_specs` | Collision runtime and components. |
| `termin-render` | `termin-render` | `termin.render`, `termin.render_framework`, `termin_render_framework_specs` | Render framework. |
| `termin-components/termin-components-render` | `termin-components-render` | `termin.render_components`, `termin_render_component_specs` | Render components. |
| `termin-navmesh` | `termin-navmesh` | `termin.navmesh`, `termin_navmesh_component_specs` | Navmesh runtime and components. |
| `termin-components/termin-components-voxels` | `termin-components-voxels` | `termin_voxel_components`, `termin_voxel_component_specs` | Voxel components. |
| `termin-components/termin-components-foliage` | `termin-components-foliage` | `termin.foliage` | Foliage components. |
| `termin-components/termin-components-ui` | `termin-components-ui` | `termin.ui_components`, `termin_ui_component_specs` | UI components. |
| `termin-render-passes` | `termin-render-passes` | `termin.render_passes`, `termin_render_pass_specs` | Concrete render passes. |
| `termin-qopt` | `termin-qopt` | `termin.fem`, `termin.linalg`, `termin.robot` | Optimization/FEM Python APIs. |
| `termin-physics-fem` | `termin-physics-fem` | `termin.physics_fem` | Experimental FEM scene API. |
| `termin-pga` | `termin-pga` | `termin.ga201`, `termin.geomalgo` | Geometric algebra APIs. |
| `termin-physics` | `termin-physics` | `termin.physics` | Rigid-body physics API. |
| `termin-components/termin-components-physics` | `termin-components-physics` | `termin_physics_component_specs` | Physics component specs. |
| `termin-default-assets` | `termin-default-assets` | `termin.default_assets` | Default asset adapters. |
| `termin-stdlib` | `termin-stdlib` | `termin.stdlib` | Standard library resources and sync helpers. |
| `termin-engine` | `termin-engine` | `termin.engine` | Engine integration API. |
| `termin-skeleton` | `termin-skeleton` | `termin.skeleton`, `termin.skeleton_components`, `termin_skeleton_component_specs` | Skeleton runtime and components. |
| `termin-animation` | `termin-animation` | `termin.animation`, `termin.animation_components`, `termin_animation_component_specs` | Animation runtime and components. |
| `termin-bootstrap` | `termin-bootstrap` | `termin.bootstrap` | Bootstrap/runtime startup helpers. |
| `termin-glb` | `termin-glb` | `termin.glb` | GLB importer. |
| `termin-project` | `termin-project` | `termin.project` | Project settings and creation helpers. |
| `termin-project-modules` | `termin-project-modules` | `termin.project_modules` | Source project module runtime and warmup helpers. |
| `termin-project-build` | `termin-project-build` | `termin.project_build` | Project build and runtime package export pipeline. |
| `termin-player` | `termin-player` | `termin.player` | Standalone/source/headless player runtime. |
| `termin-nodegraph` | `termin-nodegraph` | `tcnodegraph` | Public import keeps historical short namespace. |
| `tcplot` | `tcplot` | `tcplot` | Legacy short distribution/import name. |
