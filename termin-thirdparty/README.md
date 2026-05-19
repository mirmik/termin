# termin-thirdparty

Third-party sources used by Termin modules. Each dependency here should be a
git submodule, not an ordinary copied checkout.

Current contents:

- `manifold`: Manifold v3.4.1, commit `31afd71d17c7a94cfaeada83f657d7b42628ead6`, Apache-2.0.
- `clipper2`: Clipper2 commit `f9c5eb6e14a59f6f5d65fbfb3564519a561cf4fd`, Boost Software License 1.0.
- `openxr-sdk`: Khronos OpenXR SDK submodule used by `termin-openxr` for
  header-level integration smoke.

`termin-csg` builds Manifold and Clipper2 statically into `libtermin_csg.so`; it
does not build Manifold Python, C, JS bindings or tests.
