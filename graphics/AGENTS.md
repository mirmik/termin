# AGENTS.md

These instructions apply to packages under `graphics/` and supplement the
repository-level `AGENTS.md`.

## Ownership boundary

`graphics/` is a package-ownership namespace inside the Termin monorepo, not
an independently built repository. It owns image, mesh, GPU/backends, shaders,
materials, render core, windowing, visual scene, native GUI, nodegraph,
plotting, graphics MCP, skeleton, animation, and scene-neutral GLB support.
It does not own `termin-assets`, engine scene/ECS/components, physics,
editor/player, project management, or application bootstrap.

Builds, SDK profiles, tests, CI, global CMake infrastructure, documentation
tooling, and third-party dependencies are owned by the repository root. Use
the root `Taskfile.yml` and root build/test scripts. `graphics/CMakeLists.txt`
may compose Graphics-owned packages for the root build, but must not declare a
standalone CMake project or duplicate root build policy. Do not add nested SDKs
or a private `termin-thirdparty` tree under `graphics/`.

Prefer simple, durable architecture over compatibility fallbacks. Use
`apply_patch` for edits, preserve unrelated work, log failures, avoid
non-reflective `getattr`/`setattr`/`hasattr`, and do not introduce C/C++
`thread_local` state.
