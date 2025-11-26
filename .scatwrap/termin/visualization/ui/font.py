<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/ui/font.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# termin/visualization/ui/font.py<br>
from PIL import Image, ImageDraw, ImageFont<br>
import numpy as np<br>
<br>
import os<br>
from ..backends.base import GraphicsBackend, TextureHandle<br>
<br>
class FontTextureAtlas:<br>
    def __init__(self, path: str, size: int = 32):<br>
        if not os.path.exists(path):<br>
            raise FileNotFoundError(f&quot;Font file not found: {path}&quot;)<br>
        self.font = ImageFont.truetype(path, size)<br>
        self.size = size<br>
        self.glyphs = {}<br>
        self._handles: dict[int | None, TextureHandle] = {}<br>
        self._atlas_data = None<br>
        self.tex_w = 0<br>
        self.tex_h = 0<br>
        self._build_atlas()<br>
<br>
    @property<br>
    def texture(self) -&gt; TextureHandle | None:<br>
        &quot;&quot;&quot;Backend texture handle (uploaded lazily once a context exists).&quot;&quot;&quot;<br>
        return self._handles.get(None)<br>
<br>
    def ensure_texture(self, graphics: GraphicsBackend, context_key: int | None = None) -&gt; TextureHandle:<br>
        &quot;&quot;&quot;Uploads atlas into the current graphics backend if not done yet.&quot;&quot;&quot;<br>
        handle = self._handles.get(context_key)<br>
        if handle is None:<br>
            handle = self._upload_texture(graphics)<br>
            self._handles[context_key] = handle<br>
        return handle<br>
<br>
    def _build_atlas(self):<br>
        chars = [chr(i) for i in range(32, 127)]<br>
        padding = 2<br>
<br>
        ascent, descent = self.font.getmetrics()<br>
        line_height = ascent + descent<br>
<br>
        max_w = 0<br>
        max_h = 0<br>
<br>
        glyph_images = []<br>
        for ch in chars:<br>
            try:<br>
                bbox = self.font.getbbox(ch)<br>
                w = bbox[2] - bbox[0]<br>
                h = bbox[3] - bbox[1]<br>
            except:<br>
                continue<br>
<br>
            # создаём глиф высотой всей строки<br>
            img = Image.new(&quot;L&quot;, (w, line_height))<br>
            draw = ImageDraw.Draw(img)<br>
<br>
            # вертикальное смещение так, чтобы bbox правильно лег на baseline<br>
            offset_x = -bbox[0]<br>
            offset_y = ascent - bbox[3]<br>
<br>
            draw.text((offset_x, offset_y), ch, fill=255, font=self.font)<br>
            glyph_images.append((ch, img))<br>
            max_w = max(max_w, w)<br>
            max_h = max(max_h, h)<br>
<br>
        cols = 16<br>
        rows = (len(chars) + cols - 1) // cols<br>
        atlas_w = cols * (max_w + padding)<br>
        atlas_h = rows * (max_h + padding)<br>
        self.tex_w = atlas_w<br>
        self.tex_h = atlas_h<br>
<br>
        atlas = Image.new(&quot;L&quot;, (atlas_w, atlas_h))<br>
        draw = ImageDraw.Draw(atlas)<br>
<br>
        x = y = 0<br>
        for i, (ch, img) in enumerate(glyph_images):<br>
            atlas.paste(img, (x, y))<br>
            w, h = img.size<br>
            self.glyphs[ch] = {<br>
                &quot;uv&quot;: (<br>
                    x / atlas_w,<br>
                    y / atlas_h,<br>
                    (x + w) / atlas_w,<br>
                    (y + h) / atlas_h<br>
                ),<br>
                &quot;size&quot;: (w, h)<br>
            }<br>
            x += max_w + padding<br>
            if (i + 1) % cols == 0:<br>
                x = 0<br>
                y += max_h + padding<br>
<br>
        # Keep CPU-side atlas; upload to GPU later when a graphics context is guaranteed.<br>
        self._atlas_data = np.array(atlas, dtype=np.uint8)<br>
<br>
    def _upload_texture(self, graphics: GraphicsBackend) -&gt; TextureHandle:<br>
        if self._atlas_data is None:<br>
            raise RuntimeError(&quot;Font atlas data is missing; cannot upload texture.&quot;)<br>
        return graphics.create_texture(self._atlas_data, (self.tex_w, self.tex_h), channels=1, mipmap=False, clamp=True)<br>
<!-- END SCAT CODE -->
</body>
</html>
