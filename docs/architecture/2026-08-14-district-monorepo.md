# District monorepo

Status: accepted target architecture.

Implementation status: physical package ownership and the standalone Core and
Graphics profiles are active. The universal cross-district dependency gate and
the intended Physics closure are not complete yet; this document is normative
where current code still carries migration debt.

Termin is one source repository split into root-level product districts. A
district is a package-ownership namespace, not a nested project or separate Git
repository. The terminology is intentionally city-oriented: Termin is the city,
while Core, Graphics, Physics, Engine, Editor and Platform are its districts.

The abridged product layout is:

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

Shared roots also include `cmake/`, `scripts/`, `examples/`, `tests/`,
`test-projects/`, `tools/` and `termin-csharp/`. They are repository-owned
infrastructure or cross-product surfaces, not unnamed districts.

There is deliberately no `packages/` wrapper. Package paths include their
district (`graphics/termin-graphics`, `core/termin-base`) and therefore carry
ownership in the filesystem. CMake project policy, build recipes, tests, SDK
orchestration and third-party checkouts remain shared at repository root. A
mature district may have a local `CMakeLists.txt` that only composes its owned
packages into the root graph; it is not a standalone project or public build
entry point.

## Dependency direction

The allowed product direction is:

```text
core <- graphics <- engine <- editor
  ^                   ^
  +------ physics ----+
```

Platform hosts consume the selected lower product closure. Lower districts do
not depend on Platform.

- Core is domain-neutral and depends on no other district.
- Graphics and Physics may depend on Core, but not on Engine or Editor.
- Graphics and Physics do not depend on each other unless a later explicit
  adapter package is owned by Engine.
- Engine composes domain packages and owns scenes, assets, components and
  runtime integration.
- Editor owns projects, applications, player/editor bootstrap and developer
  workflows.
- Platform owns Android, OpenXR and Web hosts; it consumes lower products and
  does not become a dependency of them.

The ownership manifest currently enforces unique physical package ownership,
and CI builds the closed Core and Graphics profiles. Some cross-district
dependency checks remain incomplete, especially around the Physics migration.
Source visibility in the monorepo is never permission to create an undeclared
dependency; the absence of a universal gate is migration status, not policy.

## SDK products

One root build system produces several SDK profiles from the same source tree:

- `core`: the standalone base SDK;
- `graphics`: a complete Core + Graphics SDK;
- `full`: the editor SDK and desktop applications.

Physics and runtime profiles may be added when their package closures are
ready. A profile is a root build selection, not a build system owned by a
district. If publishing thin delta artifacts later proves useful, they remain
an output mode of the root orchestrator rather than making a district
self-building.

## Command surface

The root `Taskfile.yml` is the only public entry point. Districts do not have
Taskfiles and do not build themselves. Root tasks select package closures and
SDK profiles through the shared build frontend. Scripts below `scripts/` are
private implementation details of those tasks; the former root wrapper scripts
are removed rather than retained as a second command surface.

The root CMake graph owns repository-wide capabilities and profile selection.
Each mature district may own the package composition and ordering of its
closed layer, while each package translates root capabilities into its own
local options and targets. In particular, the root must not maintain a growing
table of `PACKAGE_BUILD_TESTS`, backend aliases, or application switches;
those defaults belong beside the targets that consume them. Districts whose
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
direct move from root-level packages into district-owned paths. Only package
sources and reusable product contracts survived the experiment; duplicated
Taskfiles, scripts, build systems, CI and third-party roots did not.

`termin-thirdparty/` is the sole vendor root shared by all districts. Old
root-level package copies are removed as soon as their authoritative district
copy is in place. Compatibility symlinks and source-path fallbacks are
intentionally not introduced. A broken undeclared path should fail during
migration instead of becoming permanent ambiguity.

The former repositories are historical experiments, not release inputs. CI
must build every profile from this checkout and must not fetch either repository.
