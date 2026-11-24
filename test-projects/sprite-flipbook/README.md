# Sprite Flipbook

Open the project from the engine checkout and enter Play mode.

```bash
./sdk/bin/termin_editor test-projects/sprite-flipbook/SpriteFlipbook.terminproj
```

The slime crouches, stretches, jumps and lands on the spot. The Slime entity
has a SpriteRenderer2D and a SpriteAnimator2D. Its Hop clip plays six frames
in 0.94 seconds using five regions of one texture atlas. The crouching sprite
is reused on landing. The clip places the `takeoff` and `land` events on entry
to their corresponding frames.

Edit the timing and order in `Assets/Hop.spriteclip`. Each `.sprite` file
defines a 48 × 48 pixel region of `Assets/Slime.png`. The atlas uses nearest
sampling to keep the pixel artwork sharp.

To build and run the Linux desktop package:

```bash
./sdk/bin/termin_builder build linux-dev --project test-projects/sprite-flipbook
test-projects/sprite-flipbook/dist/linux/SpriteFlipbook
```

To export the same scene to a single HTML file, build the SDK with `task build`
and the browser runtime with `task build:web`. From the checkout root, run

```bash
task package:web:project -- --project test-projects/sprite-flipbook \
  --entry-scene Scenes/Main.scene build/web-core/bin/Termin-SpriteFlipbook.html
```

Open `build/web-core/bin/Termin-SpriteFlipbook.html` directly in a browser.
The file embeds the runtime, the clip, its atlas and shaders for WebGPU and
WebGL2. Repeat the export after editing the clip or its sprites.
