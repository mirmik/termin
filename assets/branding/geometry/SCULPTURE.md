# Volumetric T sculpture

This second prototype studies an all-sided object rather than the relief
lettering in `build_logo.py`. It deliberately uses neutral grey with no
emission, textures, or image planes.

The crossbar is a hollow triangular beam with 120 degrees of axial twist and
open ends. The tapering stem has a triangular cross-section rotating 95 degrees
over its height. A fork connects them, leaving an opening below the beam.
Exact boolean unions join the parts into one closed, connected mesh; the source
parts remain editable in the hidden Construction collection in the blend.

The prototype has 228 triangles. Its bounding box is approximately 5.0 wide,
1.72 deep and 4.55 high. It is not a literal reconstruction of the flat angular
wordmark; it explores a related shape in three dimensions.

## Reproduce

Requires Blender 5.2 and FFmpeg for video. Run from the repository root:

```sh
task branding:sculpture
task branding:sculpture -- --animate
```

Outputs: `build/branding/t-sculpture/` (override with `--output PATH`).

- `t-sculpture.blend`: scene, grey material, camera, studio and a full turntable.
  Select `T | volumetric sculpture` and orbit freely; the turntable parent
  rotates 360 degrees over frames 1–144 at 24 fps.
- `t-sculpture.glb`: static geometry and standard PBR material, no studio.
- `viewer.html`: embedded triangle geometry, an offline WebGL viewer with drag
  rotation, wheel zoom and a spin button. No network dependencies. Lighting is
  a simple preview approximation, not the Blender studio renderer.
- `front.png`, `quarter.png`, `side.png`, `rear.png`: four Cycles renders.
- `turntable.mp4`: six seconds, full rotation, 72 frames at 12 fps.
- `mesh-report.json`: manifold, connectivity, volume and size checks.

The render loop excludes the repeated endpoint at frame 145. Playback therefore
wraps from 355 to 360/0 degrees at a constant angular speed.
