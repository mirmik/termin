# Remove ABI Name-Based Scope Assignment From termin_shaderc

Status: implemented 2026-07-09
Created: 2026-07-02
Area: shaderc, shader ABI, resource layout

Implemented by making `termin_shaderc` reject ABI-known resources that arrive
without explicit/imported scope metadata. Active regression coverage lives in
`termin-graphics/tests/python/test_termin_shaderc_cli.py`.

## Context

During the D3D11 `shadow_maps` scope investigation, the immediate bug was fixed by preserving Slang-declared resource metadata through the D3D11 HLSL augmentation path. The fix does not rely on ABI names to infer scopes.

However, `termin_shaderc` still has an older fallback in `canonicalize_shader_abi_resources()` that assigns a documented ABI scope when a known ABI resource name is present with an empty, `unknown`, or `unscoped` scope.

Current location:

- `termin-graphics/tools/termin_shaderc.cpp`: `canonicalize_shader_abi_resources()`

This conflicts with the current policy direction: resource scope authored in Slang should be the source of truth and should survive compiler conversion steps. Well-known ABI names may be validated centrally, but they should not be used to invent missing scope metadata.

## Problem

The compiler currently mixes two responsibilities:

1. Validate well-known engine ABI resources such as `per_frame`, `lighting`, `shadow_block`, and `shadow_maps`.
2. Repair missing scope metadata for those resources based on their names.

The second behavior hides metadata propagation bugs. If a shader explicitly declares `[[TerminScope("pass")]]` and a backend path loses that metadata, `termin_shaderc` should expose the loss with a diagnostic or preserve the metadata through a real source/reflection/catalog path. It should not silently recover by recognizing `shadow_maps` as a magic name.

## Desired Behavior

- `TerminScope` / `Scope` authored in shader source remains the authoritative semantic scope.
- Slang reflection, source/import metadata, and any intermediate sidecar/catalog files preserve that scope explicitly.
- ABI-known resource names are used for validation only:
  - matching kind/scope is accepted;
  - mismatched explicit kind/scope is rejected;
  - missing scope is reported unless an explicit migration/default-scope mode is selected.
- No compiler path should assign `frame`, `pass`, `material`, `draw`, or `transient` solely because the resource name is ABI-known.

## Suggested Work

1. Audit all callers and tests that depend on `canonicalize_shader_abi_resources()` assigning missing scopes.
2. Split ABI validation from scope assignment.
3. Remove or gate the fallback that turns `unscoped` ABI-known resources into their expected scopes.
4. Update tests that currently expect implicit ABI scope assignment.
5. Add regression tests proving that known ABI names without explicit/imported scope produce a clear diagnostic.
6. Keep any temporary migration option explicit, documented, and noisy if legacy shaders still need it.

## Acceptance Criteria

- A shader resource named `shadow_maps` without explicit/imported scope is not silently assigned `pass`.
- A shader resource named `per_frame` without explicit/imported scope is not silently assigned `frame`.
- Valid scoped ABI resources still pass validation.
- Wrong explicit ABI scope still produces an ABI contract diagnostic.
- The D3D11 imported `shadow_maps` case remains fixed through metadata preservation, not through name inference.
