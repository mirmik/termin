<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/ui/font.py</title>
</head>
<body>
<pre><code>
# termin/visualization/ui/font.py
from PIL import Image, ImageDraw, ImageFont
import numpy as np

import os
from ..backends.base import GraphicsBackend, TextureHandle

class FontTextureAtlas:
    def __init__(self, path: str, size: int = 32):
        if not os.path.exists(path):
            raise FileNotFoundError(f&quot;Font file not found: {path}&quot;)
        self.font = ImageFont.truetype(path, size)
        self.size = size
        self.glyphs = {}
        self._handles: dict[int | None, TextureHandle] = {}
        self._atlas_data = None
        self.tex_w = 0
        self.tex_h = 0
        self._build_atlas()

    @property
    def texture(self) -&gt; TextureHandle | None:
        &quot;&quot;&quot;Backend texture handle (uploaded lazily once a context exists).&quot;&quot;&quot;
        return self._handles.get(None)

    def ensure_texture(self, graphics: GraphicsBackend, context_key: int | None = None) -&gt; TextureHandle:
        &quot;&quot;&quot;Uploads atlas into the current graphics backend if not done yet.&quot;&quot;&quot;
        handle = self._handles.get(context_key)
        if handle is None:
            handle = self._upload_texture(graphics)
            self._handles[context_key] = handle
        return handle

    def _build_atlas(self):
        chars = [chr(i) for i in range(32, 127)]
        padding = 2

        ascent, descent = self.font.getmetrics()
        line_height = ascent + descent

        max_w = 0
        max_h = 0

        glyph_images = []
        for ch in chars:
            try:
                bbox = self.font.getbbox(ch)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            except:
                continue

            # создаём глиф высотой всей строки
            img = Image.new(&quot;L&quot;, (w, line_height))
            draw = ImageDraw.Draw(img)

            # вертикальное смещение так, чтобы bbox правильно лег на baseline
            offset_x = -bbox[0]
            offset_y = ascent - bbox[3]

            draw.text((offset_x, offset_y), ch, fill=255, font=self.font)
            glyph_images.append((ch, img))
            max_w = max(max_w, w)
            max_h = max(max_h, h)

        cols = 16
        rows = (len(chars) + cols - 1) // cols
        atlas_w = cols * (max_w + padding)
        atlas_h = rows * (max_h + padding)
        self.tex_w = atlas_w
        self.tex_h = atlas_h

        atlas = Image.new(&quot;L&quot;, (atlas_w, atlas_h))
        draw = ImageDraw.Draw(atlas)

        x = y = 0
        for i, (ch, img) in enumerate(glyph_images):
            atlas.paste(img, (x, y))
            w, h = img.size
            self.glyphs[ch] = {
                &quot;uv&quot;: (
                    x / atlas_w,
                    y / atlas_h,
                    (x + w) / atlas_w,
                    (y + h) / atlas_h
                ),
                &quot;size&quot;: (w, h)
            }
            x += max_w + padding
            if (i + 1) % cols == 0:
                x = 0
                y += max_h + padding

        # Keep CPU-side atlas; upload to GPU later when a graphics context is guaranteed.
        self._atlas_data = np.array(atlas, dtype=np.uint8)

    def _upload_texture(self, graphics: GraphicsBackend) -&gt; TextureHandle:
        if self._atlas_data is None:
            raise RuntimeError(&quot;Font atlas data is missing; cannot upload texture.&quot;)
        return graphics.create_texture(self._atlas_data, (self.tex_w, self.tex_h), channels=1, mipmap=False, clamp=True)

</code></pre>
</body>
</html>
