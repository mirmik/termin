# termin-thirdparty

Third-party sources used by Termin modules. Large dependencies should be git
submodules. Small generated/vendor drops are allowed when the exact vendored
files are intentionally tracked in-tree.

Current contents:

- `manifold`: Manifold v3.4.1, commit `31afd71d17c7a94cfaeada83f657d7b42628ead6`, Apache-2.0.
- `clipper2`: Clipper2 commit `f9c5eb6e14a59f6f5d65fbfb3564519a561cf4fd`, Boost Software License 1.0.
- `guard`: lightweight C/C++ test framework used by Termin native tests, commit `082b3d9c7eb26e27d95f8c5e9a2ef79d371813e5`.
- `glad`: vendored OpenGL loader generated for `termin-graphics`.
- `stb`: vendored single-header subset used by `termin-graphics` font atlas
  code.
- `recastnavigation`: Recast/Detour submodule used by app-level navmesh
  builder and pathfinding integration, commit `1078bfe346d9bb560faa748c8fde2e7aae73a3ab`.
- `openxr-sdk`: Khronos OpenXR SDK submodule used by `termin-openxr` for
  header-level integration smoke.

`termin-csg` builds Manifold and Clipper2 statically into `libtermin_csg.so`; it
does not build Manifold Python, C, JS bindings or tests.
