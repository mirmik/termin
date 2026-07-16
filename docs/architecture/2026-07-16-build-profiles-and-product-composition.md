# Build Profiles And Product Composition

## Status and decision

`project_settings/build_profiles.json` is the project-owned description of
named, portable and reproducible product recipes. A profile describes the
artifact the project intends to produce and the roots of the content that
belongs to that artifact.

A build profile is not:

- a snapshot of the current workstation;
- a resolved command line or execution graph;
- an artifact or runtime-package manifest;
- a device/deployment status record;
- a compatibility envelope for obsolete profile schemas.

The canonical profile format is schema version 2. Version 1 is development
history and is rejected. There is no v1 loader, in-process migration result,
silent upgrade or save-time rewrite. With the current number of real project
profiles, updating those files directly is cheaper and safer than maintaining
two interpretations of the build contract.

The implementation plan is
[Build Profiles And Product Build System Plan](../plans/2026-07-16-build-profiles-product-build-system-plan.md).

## Responsibility boundary

The build path has four distinct representations:

```text
project-owned BuildProfileDocument
    -> validated typed BuildProfile
    + project settings
    + local ToolchainContext
    -> resolved BuildRequest
    -> target pipeline
    -> artifact manifests and deployable output
```

### `BuildProfileDocument`

The JSON document stores user decisions that may vary between named products:

- target product kind and exact target platform;
- entry scene and packaged scene roots;
- packaged project-module roots;
- additional Python distributions required by this product;
- configuration and resource/package policy;
- runtime backend order where the target permits a choice;
- optional output location override.

The document uses project-relative paths and stable module identities. It does
not contain absolute workstation paths.

### Typed `BuildProfile`

Loading produces a closed discriminated union, not a common dataclass plus an
untyped `Mapping[str, Any]` property bag. Target-specific fields exist only on
the target variant that owns them. Structurally impossible combinations cannot
be represented after validation.

Loading and schema validation are pure and do not probe the host filesystem
beyond reading project-owned inputs. A Windows/D3D11 profile remains a valid
profile when inspected on a Linux machine that cannot build it.

### `ToolchainContext`

Local SDK roots, FXC/Slang executables, Android SDK/NDK, Gradle, ADB, environment
overrides and future remote executors belong to a separate local context. They
may come from the SDK installation, environment variables or editor-local
settings, but not from the portable project profile.

Toolchain discovery reports capabilities. It never mutates a profile or
silently substitutes a different target/backend.

### `BuildRequest`

The request compiler combines a typed profile, project settings and a
toolchain context. Its output contains absolute paths, resolved module and
scene closure, concrete target adapter, compiler locations, output/log paths
and an ordered execution plan.

This request is inspectable and serializable for diagnostics, dry-run and UI
preview, but it is derived state and is not written back into
`build_profiles.json`.

### Artifact manifests

Runtime package, desktop bundle, Python module and APK manifests describe what
was actually produced. They contain exact files, resolved dependency closure,
target requirements and tool/build provenance. A profile is intent; a manifest
is evidence. Neither substitutes for the other.

## Target product kinds

`target.kind` selects a closed product/build pipeline. The variants do not need
to be an orthogonal matrix of OS, runtime and device flags. Each variant owns
its invariants and target-specific settings.

### Desktop

Desktop profiles name the target OS and architecture explicitly:

```json
{
  "kind": "desktop",
  "os": "linux",
  "arch": "x86_64"
}
```

`desktop` without OS/architecture is insufficient: it makes the artifact depend
on whichever SDK and host happen to execute the build. The resolved SDK must
match the declared target platform or preflight fails.

Desktop runtime backend order is explicit:

```json
{
  "backends": ["vulkan", "opengl"]
}
```

This single ordered list has two deliberately coupled meanings:

1. generate/package shader artifacts for every listed backend;
2. try runtime backends in the listed priority order.

There is no separate `shaders.artifact_targets` field while these sets are
identical in real products. Duplicates and an empty list are errors. An
explicit command-line/environment backend override must name a backend packaged
by the profile and disables automatic fallback.

Fallback is limited to initial backend creation before product state is
started. Every failed candidate is logged. Runtime failure after successful
initialization is not hidden by switching backend.

### Android

The `android` target means the standard Termin Android application pipeline:
the Java `TerminActivity`, launcher intent and non-XR presentation contract.
It is not a generic bag of Android/OpenXR/device flags.

```json
{
  "kind": "android",
  "abi": "arm64-v8a",
  "ndk_api": 26
}
```

`ndk_api` names the native toolchain API level. Gradle `minSdk` and `targetSdk`
are separate application-platform policy and must not be conflated with it.
While this target supports only Vulkan, no configurable backend list is stored.

### Quest/OpenXR

The `quest_openxr` target means the current Quest-specific Android OpenXR
pipeline: NativeActivity, the OpenXR immersive intent, Oculus permissions and
metadata, supported Quest device declarations and Vulkan runtime.

```json
{
  "kind": "quest_openxr",
  "abi": "arm64-v8a",
  "ndk_api": 26
}
```

Android, OpenXR and Vulkan are invariants of this target and are not repeated as
independently editable fields. If a real generic Android OpenXR or another
device-family product appears, it receives a new target variant or motivates a
new shared abstraction then. The current schema does not speculate about it.

The Android and Quest target pipelines may share internal APK build machinery.
Their product contracts remain separate even when their implementation reuses
the same stages.

## Product content roots

A profile explicitly names roots; the build system computes and validates the
transitive closure.

```json
{
  "content": {
    "entry_scene": "Scenes/Main.scene",
    "scenes": [
      "Scenes/Main.scene",
      "Scenes/Menu.scene"
    ],
    "modules": [
      "gameplay",
      "game_ui"
    ],
    "python": {
      "requirements": [
        "some-distribution==1.2.3"
      ]
    },
    "resources": {
      "policy": "strict",
      "include": []
    }
  }
}
```

### Scenes

- `entry_scene` is the scene loaded at application start;
- `scenes` is the complete explicit root set that the product may load;
- `entry_scene` must occur in `scenes`;
- every scene is validated and packaged under a stable project-relative path;
- scene references and declared dynamic scene dependencies extend the closure;
- the runtime package manifest records all packaged scenes and the entry scene.

The build must not assume that a product contains only one scene.

### Project modules

`modules` names explicit root modules by stable descriptor identity. The module
registry resolves descriptors and transitive module dependencies. The build
packages only the resolved closure, not every `.pymodule` or loadable module
found anywhere under the project root.

Module descriptors remain responsible for their owned Python packages, native
artifacts and declared Python distribution requirements. Missing, duplicate or
ambiguous module identity is a build error.

### Python distributions

`content.python.requirements` adds product-specific distributions to the
requirements contributed by selected module descriptors. It does not replace
the module requirements and does not copy arbitrary active-environment
site-packages.

The exact resolved distribution set and versions belong to the artifact
manifest/lock, not to an implicit scan of the build host. Profile policy may
later grow a reference to a project-owned lock or requirements group when a
real second policy is needed.

### Resources

Static resource dependencies are discovered from all selected scenes and
modules. `resources.include` supplies explicit roots for resources selected
dynamically by name/UUID or gameplay code. The exporter computes a single
deduplicated graph and diagnoses missing identities, ambiguous names and
unresolved UUIDs.

`resources.policy` controls strictness, not graph meaning. A dev/smoke policy
may permit explicitly documented placeholders with warnings; release/strict
output never silently invents missing product content.

## Common profile policy

The common profile fields are intentionally small:

- `configuration`: `dev`, `debug` or `release` and must reach the real target
  build variant;
- `content`: product composition roots described above;
- optional `output_dir`, defaulting to `dist/<profile-name>`;
- target-specific `runtime` settings only where the target exposes a real
  choice.

Application identity is project data, not usually profile data. Base application
ID, label, semantic version and version code belong to project settings. A
profile may eventually carry an explicit suffix/variant override such as
`.dev`, but target wrappers must not synthesize incompatible identities or use
one hard-coded package ID for every project.

Deploy actions are derived capabilities. `installable`, `launchable`, attached
device state, ADB path and last deployment result are not persisted in the
profile. The editor derives action availability from the target, built
artifacts and current toolchain/device context.

## Canonical schema shape

An illustrative schema-v2 document is:

```json
{
  "version": 2,
  "profiles": {
    "linux-dev": {
      "target": {
        "kind": "desktop",
        "os": "linux",
        "arch": "x86_64"
      },
      "configuration": "dev",
      "content": {
        "entry_scene": "Scenes/Main.scene",
        "scenes": ["Scenes/Main.scene", "Scenes/Menu.scene"],
        "modules": ["gameplay", "game_ui"],
        "python": {
          "requirements": []
        },
        "resources": {
          "policy": "strict",
          "include": []
        }
      },
      "runtime": {
        "backends": ["vulkan", "opengl"],
        "python_package_policy": "minimal_strict"
      }
    },
    "quest-debug": {
      "target": {
        "kind": "quest_openxr",
        "abi": "arm64-v8a",
        "ndk_api": 26
      },
      "configuration": "debug",
      "content": {
        "entry_scene": "Scenes/XR.scene",
        "scenes": ["Scenes/XR.scene"],
        "modules": ["xr_gameplay"],
        "python": {
          "requirements": []
        },
        "resources": {
          "policy": "strict",
          "include": []
        }
      }
    }
  }
}
```

The example is a contract illustration, not permission to accept unknown
fields. Readers reject unknown keys, wrong target-specific fields, duplicate
list entries and inconsistent content roots with path-specific diagnostics.

## Validation phases

Validation remains layered so the editor can distinguish a broken profile from
a valid profile that cannot be built on this workstation:

1. **Schema validation** checks version, types, required/unknown fields and
   target-variant shape.
2. **Semantic validation** checks backend/platform compatibility, entry-scene
   membership, duplicate roots, application identity and cross-field rules.
3. **Project resolution** resolves scenes, modules, resources and project-owned
   paths without choosing tools.
4. **Capability validation** compares the resolved request with installed SDKs,
   compilers, Gradle/ADB and host/cross-build support.
5. **Artifact validation** proves that emitted manifests and files satisfy the
   request.

Diagnostics have stable codes, severity, profile name and field/project path.
No validation phase repairs input silently.

## Failure and compatibility policy

- Schema v1 fails explicitly and names version 2 as the supported format.
- Missing module, scene, resource, tool or target SDK produces a contextual
  diagnostic and prevents the affected build.
- Unknown target kinds and fields are rejected rather than preserved as inert
  data.
- A failed build does not rewrite its profile.
- Host capability gaps do not change backend order or target platform.
- Partial output is not published as a successful artifact; manifests are
  written from the completed resolved closure.

## Consequences

This contract deliberately trades speculative generic configuration for
closed, typed product variants. Adding a target or policy requires an explicit
schema/model change, target adapter and validation coverage. In return, the
editor and CLI cannot create combinations that no build pipeline understands,
and project profiles remain small enough to review as product definitions.
