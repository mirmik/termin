# Project Build Manifest

## Problem

Standalone player currently runs directly from a project directory. It scans files at runtime, uses editor file processors, and reconstructs resources from the source tree. This is enough for "Run Standalone" during development, but it is not a real project build:

- player depends on editor-side resource scanning code;
- project content is not collected into a dedicated build layout;
- there is no explicit manifest of resources included in the build;
- startup has to discover project files instead of loading a known asset set;
- `.terminproj` does not describe build targets, entry scene, app metadata, or included resources.

The build pipeline needs a resource compilation step that gathers project content into one output directory and produces a manifest that the player can load deterministically.

## Ownership

`ProjectBuildManifest` should be produced by a dedicated build step, not by the editor watcher and not by the player.

Recommended split:

- Editor: invokes the build step from UI actions such as "Build" or "Run Build".
- CLI/build tool: scans the project, collects resources, writes the build layout and manifest.
- Player: reads the build manifest and loads the already-collected layout.
- ResourceManager: remains the runtime registry and loader for resources listed by the manifest.

## Proposed Modules

Create a runtime-safe build module, for example `termin.project_builder`.

Suggested components:

- `ProjectScanner`: reads the project root, `.terminproj`, project settings, and project modules.
- `AssetCollector`: uses shared file preloaders that are moved out of `termin.editor.file_processors` into a runtime-safe package.
- `DependencyCollector`: follows scene, prefab, material, shader include, pipeline, and handle references by UUID.
- `ProjectBuildManifestWriter`: writes `assets/manifest.json` and top-level `build.json`.
- CLI entrypoint: `python -m termin.project_builder build <project> --scene Scenes/Main.scene --out dist/MyGame`.

## First Implementation Stage

Start with a broad build. Include all supported project resource files instead of trying to minimize the graph immediately.

Include:

- selected entry scene and all `.scene` files, or at least all scenes under the project root;
- all recognized assets and their `.meta` files;
- project modules;
- project settings;
- `stdlib`, initially copied as a whole;
- optional app metadata from `.terminproj` once fields are added.

This creates a working build pipeline before dependency pruning exists.

## Later Stages

After the broad build works, add reachable-resource collection from the selected entry scene:

- traverse scene components and serialized handles by UUID;
- include referenced prefabs;
- include material dependencies;
- include shader and GLSL include dependencies;
- include pipelines and scene pipelines;
- include GLB child assets through their parent GLB source;
- report unresolved UUIDs as build errors.

At this stage the player should stop recursively scanning arbitrary project directories. It should load resources from the manifest.

## Build Layout Sketch

```text
dist/MyGame/
  build.json
  assets/
    manifest.json
    ...
  modules/
    ...
  stdlib/
    ...
  scenes/
    Main.scene
```

`build.json` describes the app and entrypoint:

```json
{
  "format_version": 1,
  "project_name": "MyGame",
  "entry_scene": "scenes/Main.scene",
  "asset_manifest": "assets/manifest.json"
}
```

`assets/manifest.json` describes the included resources:

```json
{
  "format_version": 1,
  "resources": [
    {
      "uuid": "00000000-0000-0000-0000-000000000000",
      "type": "texture",
      "name": "Albedo",
      "path": "assets/Textures/Albedo.png",
      "meta": "assets/Textures/Albedo.png.meta"
    }
  ]
}
```

## Player Contract

Player should support two modes during migration:

- development mode: current `python -m termin.player <project> --scene ...` behavior;
- build mode: `python -m termin.player --build dist/MyGame/build.json`.

Once build mode is stable, standalone distribution should use build mode exclusively.

