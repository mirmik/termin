# Termin test projects

This directory contains complete, editor-openable projects used for manual
product and platform verification. Unlike `tests/fixtures`, these projects are
intended to exercise the normal project workflow: authored scenes, project
settings, build profiles, packaged applications, and device runs.

Each project owns its build and run instructions in its local `README.md`.

- `android-render-showcase`: Android/Vulkan rendering, packaging, and Surface
  lifecycle coverage.
- `desktop-physics-showcase`: desktop runtime packaging with falling rigid
  bodies, collisions, lighting, and shadows.
- `fem-double-pendulum`: native desktop QP multibody simulation with two rigid
  links, a fixed anchor, and an axial inter-body revolute joint.
- `world-controller-scene-cycle`: Editor Play, source-player, and packaged
  desktop acceptance for identity-based `WorldController` navigation across
  three retained runtime scenes.
