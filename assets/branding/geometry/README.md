# Angular TERMIN — Blender prototype

The approved `../wordmarks/12-termin-angular.png` is the silhouette reference. This is a
hand-traced interpretation with authored depth, not an exact reconstruction of
the generated image. Six closed letter meshes have flat triangular faces,
raised creases and rear walls. The current bodies total 256 triangles. Separate
editable curve objects supply thin illumination on outlines and major folds.

## Rebuild

Requires Blender 5.2 (the triangulation API returns indices) and FFmpeg for video.
From the repository root:

```sh
task branding:logo
task branding:logo -- --animate
```

Outputs go to `build/branding/termin-wordmark/` by default; `--output PATH`
overrides the directory. The task logs and fails on invalid mesh topology or
render/export errors.

- `termin-angular.blend`: editable geometry, packed reference, camera, lights
  and procedural materials. Open the camera view and use Rendered mode to see
  the complete lighting. Play frames 1–96 at 24 fps for the four-second loop.
- `termin-angular.glb`: six letter meshes with static standard PBR material.
  Procedural shaders and separate light curves are **not** included in GLB.
- `preview.png`, `preview-oblique.png`: actual Cycles renders.
- `shimmer.mp4`: four-second preview at 12 fps, generated with `--animate`.
- `mesh-report.json`: per-letter vertex/triangle counts and manifold validation.
- `frames/`: intermediate PNG frames for the video.

## Material

The material is opaque cyan with metalness 0.55 and roughness 0.32. Individual
face normals create the faceting; no normal-map illusion or logo image texture
is used. The travelling illumination is deliberately smooth:

```text
phase = 2*pi*(frame - 1)/96
crest = max(sin(0.60 * world_position.x - phase), 0)^8
body_emission_strength = 0.045 + 0.95 * crest
edge_emission_strength = 1.8 + 2.4 * crest
```

The shader repeats exactly at frame 97; frames 1–96 contain one loop without
duplicating its endpoint. The video samples every second frame.

## Launcher integration boundary

This prototype does not change launcher rendering. Currently
`editor/termin-app/termin/launcher/native_app.py` installs a static `back.png`
image and renders on demand. A live version needs a mesh rendering path, a
Termin shader implementing the effect, and time-driven redraws. The Blender
node graph does not automatically transfer through glTF. The static GLB is the
geometry handoff, and the formula above documents the effect to port.
