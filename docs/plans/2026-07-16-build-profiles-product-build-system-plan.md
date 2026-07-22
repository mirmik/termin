# Build Profiles And Product Build System Plan

Date: 2026-07-16

Canonical architecture:

- [Build Profiles And Product Composition](../architecture/2026-07-16-build-profiles-and-product-composition.md)

Related existing work:

- #128 Build Profiles editor umbrella;
- #446 typed profile schema (scope must be updated to remove v1 migration);
- #447 toolkit-neutral profile collection/controller;
- #448 native Build Profiles window;
- #449 unified profile actions;
- #32 strict runtime package resource graph;
- #39 dynamic resource include policy.

## Goal

Replace the current schema-v1 property bag and target wrappers with one typed
product-profile path used by CLI and editor. Profiles explicitly select product
content roots and target artifact variants; the build resolves their dependency
closure, validates local capabilities without mutating intent, and emits
authoritative manifests.

The work also removes the known implementation defects discovered during the
profile architecture review:

- desktop output platform is implicit in host/SDK selection;
- `BuildProfile.data` leaves most of the contract untyped;
- a single `shader_targets` field is named after only half of its coupled
  runtime/backend meaning;
- only one scene is packaged;
- every discovered `.pymodule` is packaged instead of a selected module
  closure;
- Android and Quest wrappers duplicate most APK pipeline stages;
- Android and Quest always consume `app-debug.apk` even when the profile
  requests another configuration;
- Android derives application ID while Quest hard-codes `org.termin.openxr`;
- local tool paths and portable profile intent are not cleanly separated;
- editor build actions still bypass one canonical selected-profile workflow.

## Non-goals

- Preserve or migrate schema v1 at runtime.
- Design remote/cross-build orchestration before a real executor exists.
- Generalize Quest into hypothetical Pico/generic Android OpenXR combinations.
- Infer product root modules from every file/import in arbitrary gameplay code.
- Treat deployment/device state as project profile data.
- Rewrite the runtime package/resource graph independently of existing #32/#39
  ownership.

## Stage 0: freeze the contract and inventory real profiles

1. Treat the architecture document above as the schema source of truth.
2. Locate the small set of real `build_profiles.json` files used by engine/game
   development and record their intended targets, scenes and modules.
3. Convert those files directly to v2 examples before enabling the v2 reader.
4. Remove v1 migration requirements from #446 and dependent documentation.
5. Add canonical Linux desktop, Windows desktop, Android and Quest fixtures.

Exit criteria:

- every real profile has an agreed v2 representation;
- no unresolved schema/product decision is hidden in the implementation card;
- v1 compatibility is explicitly out of scope.

## Stage 1: introduce the typed schema-v2 model

Replace the current common `BuildProfile` plus `data: Mapping[str, Any]` with
closed dataclasses/enums owned by `termin.project_build.profiles`:

- common profile identity/configuration/content types;
- `DesktopTarget`, `AndroidTarget` and `QuestOpenXRTarget` variants;
- ordered desktop backend list;
- typed scene/module/Python/resource roots;
- deterministic v2 document serialization.

The store must:

- accept exactly document version 2;
- reject v1 and unknown versions with a clear diagnostic;
- reject unknown keys and fields belonging to another target variant;
- preserve no opaque compatibility property bags;
- expose create/update/delete/duplicate operations over typed profiles;
- use project-relative paths in JSON and immutable/copy-safe model values;
- keep atomic deterministic save from #445.

Move pure structural and cross-field validation into the model layer. Keep host
and tool probing out of load/save.

Tests:

- round-trip every target variant;
- malformed/unknown/duplicate field diagnostics;
- v1 rejection;
- deterministic save;
- entry scene membership and backend-list invariants;
- target-specific field rejection.

Exit criteria:

- CLI/editor-safe imports expose only the typed v2 model;
- no production profile reader accepts schema v1;
- `BuildProfile.data` and backend-side JSON parsing are gone.

## Stage 2: compile profiles into normalized build requests

Introduce a pure request compiler between profile storage and target dispatch.
It combines:

- typed profile intent;
- project application/settings data;
- resolved project content roots;
- an explicit `ToolchainContext` supplied by the caller.

The resulting `BuildRequest` contains resolved absolute paths, target variant,
content closure, configuration, backend order, concrete toolchain selection,
output/log locations and target adapter input. It must be inspectable by dry-run
and editor UI without running the build.

Split validation output into stable structured diagnostics:

- schema/semantic profile diagnostics;
- project resolution diagnostics;
- local capability/toolchain diagnostics.

Refactor `profile_build.py` into a thin CLI/dispatch layer. Direct desktop
argument mode may remain as a low-level smoke/debug entry point, but normal
project builds consume a compiled named profile.

Exit criteria:

- CLI and future editor controller call the same request compiler;
- a valid foreign-platform profile can be loaded and inspected on any host;
- inability to build locally is a capability diagnostic, not schema failure;
- dry-run exposes the exact resolved request without writing the profile.

## Stage 3: make product content selection explicit

### Scene roots

Status: implemented by #489. Runtime package schema v2 owns the explicit scene
table and entry identity; exporter, validator, native loader and player consume
the same stable project-relative identities.

1. Replace the single-scene exporter contract with entry scene plus an explicit
   scene-root set.
2. Require the entry scene to be present in that set.
3. Package every selected scene under a stable project-relative identity rather
   than rewriting one input to an anonymous `scene.json` contract.
4. Extend runtime package/app manifests with entry-scene identity and the full
   packaged scene table.
5. Teach runtime loading to resolve packaged scene transitions without reading
   source project files.
6. Add dependency discovery across all selected scenes.

### Module roots

1. Add a canonical module descriptor index keyed by stable module name/ID.
2. Let profiles name root modules explicitly.
3. Extend descriptors with explicit module dependencies where missing.
4. Resolve a deterministic transitive closure and reject missing/duplicate
   identities and cycles with contextual diagnostics.
5. Change `python_module_packager` from project-wide `.pymodule` discovery to
   packaging only the selected closure.
6. Include native/project-module artifacts owned by the same resolved modules.

### Python and resources

1. Merge selected module requirements with profile-specific extra Python
   requirements.
2. Resolve/install only the declared distributions through the existing locked
   runtime packaging policy; never copy the active environment implicitly.
3. Feed all selected scenes/modules into the strict resource graph.
4. Integrate explicit dynamic resource roots with #39 rather than inventing a
   second include mechanism.
5. Record selected roots and resolved closure in artifact manifests.

Exit criteria:

- a two-scene product runs from outside the source tree and can transition to
  its second packaged scene;
- excluding an unrelated project module excludes its packages/files;
- transitive selected-module requirements are packaged;
- missing dynamic/static dependencies fail strict builds with stable paths;
- output manifests prove the exact scene/module/Python/resource closure.

## Stage 4: make desktop targets reproducible

1. Require desktop OS and architecture in the typed target.
2. Make SDK/toolchain discovery return explicit target metadata.
3. Reject an SDK whose OS/architecture does not match the profile.
4. Rename the current ordered shader target concept to the single canonical
   runtime backend order.
5. Generate shader artifacts for exactly that backend list and write the same
   order into runtime target requirements.
6. Make normal startup try backends in order only during initial backend
   creation; log every failure.
7. Make an explicit backend override select exactly one packaged backend and
   fail without fallback when unavailable.
8. Add relocatable Linux and Windows manifest/request fixtures even where the
   current host can execute only one of them.

Exit criteria:

- the declared target platform, selected SDK and emitted manifest agree;
- no host-default logic changes the profile backend order;
- backend list and packaged shader artifact families cannot diverge;
- Linux/Vulkan+OpenGL and Windows/D3D11 profile requests are deterministic.

## Stage 5: consolidate Android-family implementation and fix variants

Keep `android` and `quest_openxr` as separate product variants, but extract a
shared internal APK pipeline for:

- output/log preparation;
- Android SDK/NDK/Gradle/tool preflight;
- native ABI/API arguments;
- process execution and log streaming;
- APK discovery/copy/publication;
- ADB install/launch primitives where applicable.

Target adapters remain responsible for their actual differences:

- standard Android uses `TerminActivity` and the standard launcher manifest;
- Quest uses NativeActivity, OpenXR/Oculus manifest policy and Quest runtime
  assets;
- each adapter supplies its Gradle template and application metadata.

Fix configuration handling:

- map `dev`, `debug` and `release` to documented real Gradle variants;
- do not always copy `app-debug.apk`;
- verify artifact name/path from Gradle output rather than duplicating a fragile
  hard-coded path;
- ensure release signing policy is explicit and fails when unavailable.

Fix application identity:

- add base application ID, label and version fields to canonical project
  settings;
- consume the same identity in Android and Quest pipelines;
- remove hard-coded `org.termin.openxr` as the identity of every Quest product;
- add an explicit per-profile suffix only if real dev/release coexistence needs
  it.

Exit criteria:

- Android and Quest share common mechanics without sharing product-specific
  manifests;
- configuration changes the actual Gradle variant;
- two Quest projects cannot overwrite each other through one package ID;
- build/install/launch results report the exact application ID and activity;
- focused Android/Quest request and command-construction tests cover all
  variants without requiring a connected device.

## Stage 6: separate portable intent from local capabilities

1. Remove project-profile fields for SDK root, shader compiler, Gradle, build
   script, ADB and speculative `toolchain.execution`.
2. Define `ToolchainContext` providers for SDK installation defaults,
   environment overrides and editor-local settings.
3. Produce a capability report with stable codes for missing/mismatched tools.
4. Ensure capability checks never save defaults or corrected values into the
   project profile.
5. Keep future remote/cross execution behind a new provider interface only when
   a real executor is implemented.

Exit criteria:

- profiles remain portable between developer machines;
- local overrides do not dirty project files;
- editor and CLI show the same capability diagnostics;
- foreign-platform profiles remain editable even when not locally buildable.

## Stage 7: build-profile editor and canonical actions

Implement #447/#448/#449 on top of the completed typed model and request
compiler:

- collection controller for create/duplicate/delete/select/edit/revert/save;
- target-specific native editor fields generated from typed variants;
- content-root selectors for scenes and modules;
- resolved request/content preview and structured diagnostics;
- selected-profile persistence in editor-local/project UI state as appropriate;
- canonical Build, Run, Install and Launch actions;
- action availability derived from target, artifact and live capabilities;
- removal of one-off Android/Quest menu paths after parity gates pass.

The UI must not implement another schema projection with independent defaults.
It edits the same typed objects used by CLI tests.

Exit criteria:

- CLI and editor produce equal normalized requests for the same profile;
- editor can construct every supported target variant without invalid hidden
  combinations;
- target actions route only through the selected profile;
- legacy dialogs/routes are deleted after documented live verification.

## Stage 8: remove stale contracts and close the migration

1. Delete schema-v1 fixtures, docs and compatibility language.
2. Update `docs/build-system.md`, CLI docs and target-specific build docs to the
   v2 contract.
3. Mark the 2026-06-26 editor-window schema sketch as historical/superseded.
4. Delete duplicated profile parsing, implicit all-module discovery and
   single-scene package assumptions.
5. Audit source/build/runtime manifests so their version fields and meanings
   are not confused with build-profile schema versions.
6. Run repository-wide searches for old field names such as top-level
   `shader_targets`, `default_shader_language`, `android.platform` and profile
   tool paths.

Exit criteria:

- one profile schema and one profile-to-request path remain;
- no production compatibility branch accepts v1;
- architecture, user docs, examples, tests and editor UI agree;
- old build paths fail explicitly rather than falling back silently.

## Verification matrix

Automated coverage must include at least:

| Profile | Required verification |
| --- | --- |
| Linux desktop, Vulkan/OpenGL | typed round-trip, request compile, shader closure, relocatable bundle smoke |
| Windows desktop, D3D11 | typed round-trip and request/capability validation on Linux; real build/smoke on Windows |
| Standard Android arm64 | request/Gradle command construction, debug/release artifact selection, APK/package validation |
| Quest/OpenXR arm64 | request/Gradle command construction, Quest manifest validation, application identity, APK validation |
| Multi-scene product | entry + secondary scene packaging and runtime transition outside source tree |
| Selective modules | selected transitive closure included; unrelated module and Python packages absent |

Repository gates:

- focused profile/store/request tests;
- runtime package exporter/validator tests;
- desktop/Android/Quest wrapper tests;
- editor controller/native UI tests;
- `./build-sdk.sh --no-wheels` when SDK/runtime bindings or bundled code change;
- `./run-tests.sh` before completing implementation cards;
- platform/manual smokes recorded explicitly where the current host cannot
  provide them.

## Recommended card decomposition

Keep #128 as the umbrella. Rewrite #446 around Stages 1-2 with no v1 migration.
Do not make #446 absorb the content graph or target-wrapper cleanup. Create or
reuse focused children for:

1. schema-v2 typed target/content model;
2. profile-to-request compiler and structured diagnostics;
3. multi-scene package/runtime contract;
4. selected module dependency closure;
5. profile-specific Python requirements;
6. explicit resource roots integrated with #39;
7. desktop platform/backend enforcement;
8. shared Android APK pipeline and real build variants;
9. project application identity for Android/Quest;
10. local `ToolchainContext` and capability providers.

Only independently executable children with settled acceptance should move to
Ready. The editor cards remain dependent on the typed model/request compiler,
not on completion of every future package-policy extension.
