# Original relief T with a volumetric back

This version follows the accepted direction after the separate twisted-tube
sculpture was rejected: keep the previous relief T's front and extend it behind.

`build_t_volume.py` imports `GLYPHS['T']` and `make_glyph` from `build_logo.py`.
All ten front vertices and all nine front triangles are preserved exactly.
Only the rear and side geometry is replaced. A rigid coordinate transform
centres the letter and makes the vertical axis Z; it does not change the form.

The rear contour contracts to 86% around the front fold junction, remaining
inside the frontal silhouette. Its large triangular planes converge to a rear
ridge 1.6 units behind the original front coordinate plane. Total depth is
2.08 units, width 4.24, height 3.80. The closed, connected mesh has 36 triangles.

## Build and inspect

Requires Blender 5.2; animation export also requires FFmpeg.

```sh
task branding:t-volume
task branding:t-volume -- --animate
```

Files are saved to `build/branding/t-volume/` (or `--output PATH`):

- `t-volume.blend`: editable model, grey studio material and turntable. The
  hidden `Reference | original relief T` object preserves the old thin model.
- `t-volume.glb`: the static mesh and standard material, without the studio.
- `viewer.html`: offline WebGL viewer; drag to rotate, wheel to zoom.
- `original-front.png` and `front.png`: the thin and thick models under the
  same camera and lighting, for direct comparison.
- `quarter.png`, `side.png`, `rear.png`: oblique and rear geometry studies.
- `turntable.mp4`: one 360-degree turn in six seconds, 72 frames at 12 fps.
- `mesh-report.json`: manifold/connectivity checks and the measured maximum
  front vertex displacement, which must be exactly zero.

The neutral material makes geometry visible without emission or texture. The
previous wordmark and rejected sculpture outputs are kept separately.
