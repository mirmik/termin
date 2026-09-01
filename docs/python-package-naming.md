# Python Package Naming

Этот документ фиксирует текущий контракт именования Python-части SDK: путь в
монорепозитории, имя Python distribution и публичные import namespaces. Он
закрывает повторяющийся класс ошибок, где distribution и import namespace
расходились без явной причины.

## Policy

- `build-system/packages.json` является source of truth для порядка установки и
  имен internal distributions.
- `setup.py` / `pyproject.toml` должны публиковать distribution name, совпадающий
  с manifest после нормализации PEP 503 (`-`, `_`, `.` считаются одинаковыми).
- `install_requires` внутри репозитория должен ссылаться на distribution name,
  а не на repo path и не на import namespace.
- Новый пакет по умолчанию использует одинаковые repo path и distribution name
  в стиле `termin-*`; исключения требуют явного обоснования в таблице ниже.
- Public import namespace выбирается по domain API. Для migrated base,
  graphics и nodegraph packages используются canonical namespaces
  `termin.base`, `termin.graphics` и `termin.nodegraph`.
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
- Package order, distribution metadata and district ownership are verified in
  this repository. Product profiles select closures from the same canonical
  manifest; no external Core repository participates in validation.
- documentation inventory checks that the table below contains every manifest
  `package identity / distribution` pair in current order.

## Inventory

| Source path | Distribution | Public import namespaces | Notes |
|-------------|--------------|--------------------------|-------|
| `core/termin-build-tools` | `termin-build-tools` | `termin_build` | Build-time helpers. |
| `core/termin-nanobind-sdk` | `termin-nanobind` | `termin_nanobind` | Distribution keeps historical short SDK name. |
| `core/termin-base` | `termin-base` | `termin.base`, `termin.geombase` | Canonical base distribution and namespace. |
| `core/termin-dispatch` | `termin-dispatch` | `termin.dispatch` | Caller-driven language-neutral deferred dispatcher. |
| `graphics/termin-image` | `termin-image` | `termin.image` | Native image codecs for texture/tooling paths. |
| `engine/termin-assets` | `termin-assets` | `termin_assets` | Asset runtime contracts. |
| `graphics/termin-tween` | `termin-tween` | `termin.tween` | Core tween runtime. |
| `engine/termin-audio` | `termin-audio` | `termin.audio`, `termin.audio.components`, `termin_audio_component_specs` | Audio runtime and component specs. |
| `graphics/termin-mesh` | `termin-mesh` | `termin.mesh` | Canonical mesh distribution and namespace. |
| `graphics/termin-graphics` | `termin-graphics` | `termin.graphics` | Canonical graphics distribution and namespace; owns `termin/graphics/__init__.py`. |
| `graphics/termin-visual-scene` | `termin-visual-scene` | `termin.visual_scene` | Retained 2D visual identity and interaction. |
| `engine/termin-voxels` | `termin-voxels` | `termin.voxels` | Voxel core API. |
| `core/termin-inspect` | `termin-inspect` | `termin.inspect` | Inspection metadata API. |
| `graphics/termin-materials` | `termin-materials` | `termin.materials` | Material runtime API. |
| `graphics/termin-shader-runtime` | `termin-shader-runtime` | `termin.shader_tools`, `termin.shader_runtime` | Shared shader tool resolution and source-project shader runtime helpers. |
| `graphics/termin-window` | `termin-window` | `termin.window` | Framework-neutral native window infrastructure. |
| `graphics/termin-gui-native` | `termin-gui-native` | `termin.gui_native` | Canonical native retained UI toolkit. |
| `engine/termin-scene` | `termin-scene` | `termin.scene` | Scene/ECS API. |
| `core/termin-mcp` | `termin-mcp` | `termin.mcp` | Shared MCP transport/executor helpers. |
| `graphics/termin-graphics-mcp` | `termin-graphics-mcp` | `termin.graphics.mcp` | Graphics-owned MCP adapters; owns only the child namespace. |
| `engine/termin-prefab` | `termin-prefab` | `termin.prefab` | Namespace package. |
| `engine/termin-display` | `termin-display` | `termin.display`, `termin.viewport` | Display/windowing API. |
| `engine/termin-csg` | `termin-csg` | `termin.csg` | CSG API. |
| `engine/termin-modules` | `termin-modules` | `termin_modules` | Module runtime API. |
| `physics/termin-robotics` | `termin-robotics` | `termin.robotics` | Articulation models and control algorithms. |
| `engine/termin-components/termin-components-kinematic` | `termin-components-kinematic` | `termin.kinematic`, `termin_kinematic_component_specs` | Kinematic components. |
| `engine/termin-lighting` | `termin-lighting` | `termin.lighting` | Lighting API. |
| `engine/termin-components/termin-components-mesh` | `termin-components-mesh` | `termin.mesh`, `termin_mesh_component_specs` | Scene mesh components. |
| `engine/termin-components/termin-components-tween` | `termin-components-tween` | `termin.tween_components`, `termin_tween_component_specs` | Tween scene component and specs. |
| `engine/termin-input` | `termin-input` | `termin.input` | Input API. |
| `physics/termin-collision` | `termin-collision` | `termin.colliders`, `termin.collision`, `termin_collision_component_specs` | Collision runtime and components. |
| `engine/termin-render` | `termin-render` | `termin.render`, `termin.render_framework`, `termin_render_framework_specs` | Render framework. |
| `engine/termin-components/termin-components-render` | `termin-components-render` | `termin.render_components`, `termin_render_component_specs` | Render components. |
| `physics/termin-navmesh` | `termin-navmesh` | `termin.navmesh`, `termin_navmesh_component_specs` | Navmesh runtime and components. |
| `engine/termin-components/termin-components-voxels` | `termin-components-voxels` | `termin_voxel_components`, `termin_voxel_component_specs` | Voxel components. |
| `engine/termin-components/termin-components-foliage` | `termin-components-foliage` | `termin.foliage` | Foliage components. |
| `engine/termin-components/termin-components-ui` | `termin-components-ui` | `termin.ui_components`, `termin_ui_component_specs` | UI components. |
| `engine/termin-render-passes` | `termin-render-passes` | `termin.render_passes`, `termin_render_pass_specs` | Concrete render passes. |
| `physics/termin-qopt` | `termin-qopt` | `termin.fem`, `termin.linalg`, `termin.robot` | Reference/research Python APIs; current solver and 3D runtime are native C++. |
| `physics/termin-physics-fem` | `termin-physics-fem` | `termin.physics_fem` | Reference-only Python projection; current scene integration is native C++. |
| `physics/termin-pga` | `termin-pga` | `termin.ga201`, `termin.geomalgo` | Geometric algebra APIs. |
| `physics/termin-physics` | `termin-physics` | `termin.physics` | Rigid-body physics API. |
| `engine/termin-components/termin-components-physics` | `termin-components-physics` | `termin_physics_component_specs` | Physics component specs. |
| `engine/termin-default-assets` | `termin-default-assets` | `termin.default_assets` | Default asset adapters. |
| `engine/termin-stdlib` | `termin-stdlib` | `termin.stdlib` | Standard library resources and sync helpers. |
| `engine/termin-engine` | `termin-engine` | `termin.engine` | Engine integration API. |
| `graphics/termin-skeleton` | `termin-skeleton` | `termin.skeleton`, `termin.skeleton_components`, `termin_skeleton_component_specs` | Skeleton runtime and components. |
| `graphics/termin-animation` | `termin-animation` | `termin.animation`, `termin.animation_components`, `termin_animation_component_specs` | Animation runtime and components. |
| `engine/termin-bootstrap` | `termin-bootstrap` | `termin.bootstrap` | Bootstrap/runtime startup helpers. |
| `graphics/termin-glb-native` | `termin-glb-native` | `termin.glb.native` | Minimal native cgltf document and mesh importer. |
| `graphics/termin-glb` | `termin-glb` | `termin.glb` | High-level GLB asset, plugin, and scene importer layer. |
| `editor/termin-project` | `termin-project` | `termin.project` | Project settings and creation helpers. |
| `editor/termin-project-modules` | `termin-project-modules` | `termin.project_modules` | Source project module runtime and warmup helpers. |
| `editor/termin-project-build` | `termin-project-build` | `termin.project_build` | Project build and runtime package export pipeline. |
| `editor/termin-player` | `termin-player` | `termin.player` | Standalone/source/headless player runtime. |
| `graphics/termin-nodegraph` | `termin-nodegraph` | `termin.nodegraph` | Canonical nodegraph import; distribution remains unchanged. |
| `graphics/tcplot` | `termin-plot` | `termin.plot` | Canonical plotting distribution and namespace. |
| `graphics/tcplot-gui-native` | `termin-plot-gui-native` | `termin.plot.gui_native` | Optional native UI adapters for plot widgets. |
