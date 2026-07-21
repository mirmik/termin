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
- `miniaudio`: vendored miniaudio v0.11.25 used privately by `termin-audio`
  for decoding, device I/O, mixing, and spatial playback. Termin owns resource
  identity and lifetime; miniaudio's resource manager is disabled.
- `libogg`: Xiph libogg v1.3.6, commit
  `be05b13e98b048f0b5a0f5fa8ce514d56db5f822`, BSD-3-Clause; bundled privately
  by `termin-audio` for Ogg container parsing.
- `libvorbis`: Xiph libvorbis v1.3.7, commit
  `0657aee69dec8508a0011f47f3b69d7538e9d262`, BSD-3-Clause; bundled privately
  by `termin-audio` for Vorbis decoding.
- `recastnavigation`: Recast/Detour submodule used by app-level navmesh
  builder and pathfinding integration, commit `1078bfe346d9bb560faa748c8fde2e7aae73a3ab`.
- `openxr-sdk`: Khronos OpenXR SDK submodule used by `termin-openxr` for
  header-level integration smoke.
- `sdl2`: SDL2 source submodule used as the default Windows SDL provider for
  editor/window/input builds; Linux builds continue to prefer system SDL2.
- `zlib`: zlib v1.3.2, commit `da607da739fa6047df13e66a2af6b8bec7c2a498`,
  used by bundled libpng for `termin-image`, Zlib license.
- `libpng`: libpng v1.6.58, commit `3061454d980de7d53608f594194cfac722721d2a`,
  used by `termin-image` PNG decoding, libpng license.
- `libjpeg-turbo`: libjpeg-turbo 3.2.0, commit
  `c85e6b905bf237038faa936dab160ebfc5da0344`, used by `termin-image`
  JPEG decoding, BSD-style/IJG/zlib licenses.
- `libwebp`: libwebp v1.6.0, commit `4fa21912338357f89e4fd51cf2368325b59e9bd9`,
  used by `termin-image` WebP decoding, BSD-style license.

`termin-csg` builds Manifold and Clipper2 statically into `libtermin_csg.so`; it
does not build Manifold Python, C, JS bindings or tests.

`termin-image` links PNG/JPEG/WebP codecs privately. Linux builds prefer system
packages by default; Windows builds prefer the bundled static codec submodules
so SDK users do not need a separate codec SDK next to Termin.
