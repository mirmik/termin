# AGENTS.md

These instructions apply to packages under `core/` and supplement the
repository-level `AGENTS.md`.

## Ownership boundary

`core/` is a package-ownership namespace inside the Termin monorepo, not an
independently built repository. Core packages must remain domain-neutral and
must not depend on graphics, assets, scenes, physics, editor, player, or engine
packages.

Builds, SDK profiles, tests, CI, global CMake infrastructure, documentation
tooling, and third-party dependencies are owned by the repository root. Use
the root `Taskfile.yml` and root build/test scripts. `core/CMakeLists.txt` may
compose Core-owned packages for the root build, but must not declare a
standalone CMake project or duplicate root build policy. Do not add nested
SDKs or a private `termin-thirdparty` tree under `core/`.

Use `apply_patch` for edits, preserve unrelated work, log failures, avoid
non-reflective `getattr`/`setattr`/`hasattr`, and do not introduce C/C++
`thread_local` state.
