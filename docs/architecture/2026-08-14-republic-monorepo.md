# Republic monorepo

Status: accepted target architecture.

Termin is one source repository split into root-level product republics. A
republic is a package-ownership namespace, not a nested project or separate Git
repository.

```text
core/
graphics/
physics/
engine/
editor/
platform/
docs/
build-system/
termin-thirdparty/
```

There is deliberately no `packages/` wrapper. Package paths include their
republic (`graphics/termin-graphics`, `core/termin-base`) and therefore carry
ownership in the filesystem. CMake project policy, build recipes, tests, SDK
orchestration and third-party checkouts remain shared at repository root. A
mature republic may have a local `CMakeLists.txt` that only composes its owned
packages into the root graph; it is not a standalone project or public build
entry point.

## Dependency direction

The allowed product direction is:

```text
core <- graphics <- engine <- editor
  ^         ^          ^
  +------ physics -----+
             ^
          platform
```

- Core is domain-neutral and depends on no other republic.
- Graphics and Physics may depend on Core, but not on Engine or Editor.
- Graphics and Physics do not depend on each other unless a later explicit
  adapter package is owned by Engine.
- Engine composes domain packages and owns scenes, assets, components and
  runtime integration.
- Editor owns projects, applications, player/editor bootstrap and developer
  workflows.
- Platform owns Android, OpenXR and Web hosts; it consumes lower products and
  does not become a dependency of them.

These rules are enforced by the ownership manifest, build profiles, dependency
checks and CI. Source visibility in the monorepo is not permission to create an
undeclared dependency.

## SDK products

One root build system produces several SDK profiles from the same source tree:

- `core`: the standalone base SDK;
- `graphics`: a complete Core + Graphics SDK;
- `full`: the editor SDK and desktop applications.

Physics and runtime profiles may be added when their package closures are
ready. A profile is a root build selection, not a build system owned by a
republic. If publishing thin delta artifacts later proves useful, they remain
an output mode of the root orchestrator rather than making a republic
self-building.

## Command surface

The root `Taskfile.yml` is the only public entry point. Republics do not have
Taskfiles and do not build themselves. Root tasks select package closures and
SDK profiles through the shared build frontend. Scripts below `scripts/` are
private implementation details of those tasks; the former root wrapper scripts
are removed rather than retained as a second command surface.

The root CMake graph owns repository-wide capabilities and profile selection.
Each mature republic may own the package composition and ordering of its
closed layer, while each package translates root capabilities into its own
local options and targets. In particular, the root must not maintain a growing
table of `PACKAGE_BUILD_TESTS`, backend aliases, or application switches;
those defaults belong beside the targets that consume them. Republics whose
boundaries are not yet closed remain explicitly composed by the root until
their cross-domain integration is separated.

The root adds Graphics only through `add_subdirectory(graphics)`. Graphics
owns the complete ordering of its packages and the interpretation of platform
capabilities for that layer, including Web/Android backend selection and
example availability. `graphics/termin-render-core` is the authoritative
scene-neutral renderer package; `engine/termin-render` is a higher-level
adapter that consumes its installed CMake target and must not contain a second
copy of render-core sources or package metadata.

## Migration policy

The short-lived `termin-core` and `termin-graphics` extraction experiment is
not part of the canonical repository history. The monorepo history records a
direct move from root-level packages into republic-owned paths. Only package
sources and reusable product contracts survived the experiment; duplicated
Taskfiles, scripts, build systems, CI and third-party roots did not.

`termin-thirdparty/` is the sole vendor root shared by all republics. Old
root-level package copies are removed as soon as their authoritative republic
copy is in place. Compatibility symlinks and source-path fallbacks are
intentionally not introduced. A broken undeclared path should fail during
migration instead of becoming permanent ambiguity.

The former repositories are historical experiments, not release inputs. CI
must build every profile from this checkout and must not fetch either repository.
