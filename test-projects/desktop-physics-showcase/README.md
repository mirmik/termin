# Desktop Physics Showcase

This complete Termin project verifies the normal desktop project workflow with
Python physics components. The scene contains a static arena, falling boxes and
spheres, PBR materials, directional shadows, point lighting, and the default
RenderingManager topology.

## Open in the editor

```bash
./sdk/bin/termin_editor \
  test-projects/desktop-physics-showcase/DesktopPhysicsShowcase.terminproj
```

Enter game mode to restart the simulation from the authored poses.

## Inspect and build the profile

```bash
./sdk/bin/termin_builder profile linux-dev \
  --project test-projects/desktop-physics-showcase

./sdk/bin/termin_builder build linux-dev \
  --dry-run \
  --project test-projects/desktop-physics-showcase

./sdk/bin/termin_builder build linux-dev \
  --project test-projects/desktop-physics-showcase
```

The portable desktop bundle is written to `dist/linux`.

## Run the packaged application

```bash
test-projects/desktop-physics-showcase/dist/linux/DesktopPhysicsShowcase
```

The first bodies should reach the arena after roughly one second. Keep the
application running for at least 120 frames and check the log for physics,
component, shader, and render errors.
