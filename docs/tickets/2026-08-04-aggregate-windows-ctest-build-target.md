# [build/qa] Aggregate Selected CTest Targets for Windows Builds

Status: ready
Created: 2026-08-04
Area: build system, Windows, CTest, MSBuild
Tags: cleanup, qa, size:M

## Context

During the Windows SDK regression pass, the default C++ test plan selected 182
CTest tests. `run-tests-cpp.ps1` correctly resolved their owning CMake build
targets and passed the full target list to `Invoke-TerminCMakeBuild`, but the
Visual Studio generator processed that selection as a long sequence of
per-target MSBuild invocations.

On the tested incremental Release tree, the C++ build stage took approximately
12 minutes before CTest execution. Most targets were already up to date, so a
material part of that time was orchestration and repeated MSBuild project-graph
startup rather than compilation. This substantially lengthened the Windows
debug loop and made successive linker/compiler failures appear only after long
waits.

Current path:

- `run-tests-cpp.ps1` obtains `--build-targets` from the repository CTest
  planner and passes every returned target to `Invoke-TerminCMakeBuild`.
- `scripts/Invoke-CMakeBuild.ps1` translates the list to
  `cmake --build ... --target <target...>`.
- The Visual Studio generator/MSBuild combination does not build this large
  target set as one efficient aggregate dependency graph.

The test planner and its capability/profile filtering are valuable and must
remain the source of truth. The problem is only how the selected build targets
are materialized and submitted to the native build tool.

## Problem

Windows C++ test turnaround scales poorly with the number of selected tests,
even for an almost entirely up-to-date build. The runner lacks a generated or
stable aggregate CMake target representing the exact selected test-build set,
so MSBuild repeatedly pays scheduling and project-loading overhead.

Simply building every test unconditionally is not an equivalent solution. It
would discard the existing profile, platform, capability, and window-test
selection semantics and could build targets whose dependencies are unavailable
in the active configuration.

## Desired Behavior

- A selected CTest plan is built through one aggregate dependency graph on the
  Visual Studio generator.
- The aggregate contains exactly the targets selected by the repository CTest
  planner, plus explicitly required support tools such as `termin_shaderc`.
- Existing profile, platform, capability, configuration, and window-test
  filtering remains unchanged.
- Ninja and Linux behavior remains correct and does not acquire a
  Windows-specific workaround in generic test-selection logic.
- Incremental Windows runs spend time proportional to actual rebuild work, not
  primarily to the number of selected CTest targets.

## Suggested Work

1. Measure a no-op or near-no-op Release run and record separately the selected
   target build time and CTest execution time.
2. Confirm the number and shape of native build-tool invocations produced by
   CMake for a large `--target` list with the Visual Studio generator.
3. Introduce a simple aggregate-target mechanism. Prefer a CMake-native target
   whose dependencies are the planner-selected targets; if the selection is
   dynamic, generate a small configuration-specific CMake include or helper
   project rather than teaching PowerShell to reconstruct the dependency graph.
4. Incorporate `termin_shaderc` provenance into the aggregate dependency set so
   the existing separate support-tool build is unnecessary.
5. Preserve the planner inventory and execution-manifest validation.
6. Add regression coverage for mapping a representative filtered plan to the
   aggregate dependencies, including configurations with disabled graphics
   capabilities and with window tests off.
7. Compare clean and incremental timings against the baseline and document the
   result in the change or task history.

## Acceptance Criteria

- `run-tests-cpp.ps1` builds the selected Windows CTest set through a single
  aggregate MSBuild dependency graph, without one top-level native build
  invocation per selected target.
- The default Windows plan still executes and reports the same selected test
  inventory; no test is silently omitted or added by the aggregation change.
- `termin_shaderc` used by Python-driven shader tests is produced by the same
  configuration and build graph.
- Plans with Vulkan, OpenGL, SDL, D3D11, and window-test capabilities disabled
  continue to resolve only valid targets.
- A no-op or near-no-op Release build demonstrates a meaningful reduction from
  the approximately 12-minute observed build stage, with before/after timings
  recorded.
- The full Windows C++ test plan passes after the change, and the Linux/Ninja
  central test workflow remains green.

