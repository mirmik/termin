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
&#9;def __init__(self, path: str, size: int = 32):<br>
&#9;&#9;if not os.path.exists(path):<br>
&#9;&#9;&#9;raise FileNotFoundError(f&quot;Font file not found: {path}&quot;)<br>
&#9;&#9;self.font = ImageFont.truetype(path, size)<br>
&#9;&#9;self.size = size<br>
&#9;&#9;self.glyphs = {}<br>
&#9;&#9;self._handles: dict[int | None, TextureHandle] = {}<br>
&#9;&#9;self._atlas_data = None<br>
&#9;&#9;self.tex_w = 0<br>
&#9;&#9;self.tex_h = 0<br>
&#9;&#9;self._build_atlas()<br>
<br>
&#9;@property<br>
&#9;def texture(self) -&gt; TextureHandle | None:<br>
&#9;&#9;&quot;&quot;&quot;Backend texture handle (uploaded lazily once a context exists).&quot;&quot;&quot;<br>
&#9;&#9;return self._handles.get(None)<br>
<br>
&#9;def ensure_texture(self, graphics: GraphicsBackend, context_key: int | None = None) -&gt; TextureHandle:<br>
&#9;&#9;&quot;&quot;&quot;Uploads atlas into the current graphics backend if not done yet.&quot;&quot;&quot;<br>
&#9;&#9;handle = self._handles.get(context_key)<br>
&#9;&#9;if handle is None:<br>
&#9;&#9;&#9;handle = self._upload_texture(graphics)<br>
&#9;&#9;&#9;self._handles[context_key] = handle<br>
&#9;&#9;return handle<br>
<br>
&#9;def _build_atlas(self):<br>
&#9;&#9;chars = [chr(i) for i in range(32, 127)]<br>
&#9;&#9;padding = 2<br>
<br>
&#9;&#9;ascent, descent = self.font.getmetrics()<br>
&#9;&#9;line_height = ascent + descent<br>
<br>
&#9;&#9;max_w = 0<br>
&#9;&#9;max_h = 0<br>
<br>
&#9;&#9;glyph_images = []<br>
&#9;&#9;for ch in chars:<br>
&#9;&#9;&#9;try:<br>
&#9;&#9;&#9;&#9;bbox = self.font.getbbox(ch)<br>
&#9;&#9;&#9;&#9;w = bbox[2] - bbox[0]<br>
&#9;&#9;&#9;&#9;h = bbox[3] - bbox[1]<br>
&#9;&#9;&#9;except:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;# создаём глиф высотой всей строки<br>
&#9;&#9;&#9;img = Image.new(&quot;L&quot;, (w, line_height))<br>
&#9;&#9;&#9;draw = ImageDraw.Draw(img)<br>
<br>
&#9;&#9;&#9;# вертикальное смещение так, чтобы bbox правильно лег на baseline<br>
&#9;&#9;&#9;offset_x = -bbox[0]<br>
&#9;&#9;&#9;offset_y = ascent - bbox[3]<br>
<br>
&#9;&#9;&#9;draw.text((offset_x, offset_y), ch, fill=255, font=self.font)<br>
&#9;&#9;&#9;glyph_images.append((ch, img))<br>
&#9;&#9;&#9;max_w = max(max_w, w)<br>
&#9;&#9;&#9;max_h = max(max_h, h)<br>
<br>
&#9;&#9;cols = 16<br>
&#9;&#9;rows = (len(chars) + cols - 1) // cols<br>
&#9;&#9;atlas_w = cols * (max_w + padding)<br>
&#9;&#9;atlas_h = rows * (max_h + padding)<br>
&#9;&#9;self.tex_w = atlas_w<br>
&#9;&#9;self.tex_h = atlas_h<br>
<br>
&#9;&#9;atlas = Image.new(&quot;L&quot;, (atlas_w, atlas_h))<br>
&#9;&#9;draw = ImageDraw.Draw(atlas)<br>
<br>
&#9;&#9;x = y = 0<br>
&#9;&#9;for i, (ch, img) in enumerate(glyph_images):<br>
&#9;&#9;&#9;atlas.paste(img, (x, y))<br>
&#9;&#9;&#9;w, h = img.size<br>
&#9;&#9;&#9;self.glyphs[ch] = {<br>
&#9;&#9;&#9;&#9;&quot;uv&quot;: (<br>
&#9;&#9;&#9;&#9;&#9;x / atlas_w,<br>
&#9;&#9;&#9;&#9;&#9;y / atlas_h,<br>
&#9;&#9;&#9;&#9;&#9;(x + w) / atlas_w,<br>
&#9;&#9;&#9;&#9;&#9;(y + h) / atlas_h<br>
&#9;&#9;&#9;&#9;),<br>
&#9;&#9;&#9;&#9;&quot;size&quot;: (w, h)<br>
&#9;&#9;&#9;}<br>
&#9;&#9;&#9;x += max_w + padding<br>
&#9;&#9;&#9;if (i + 1) % cols == 0:<br>
&#9;&#9;&#9;&#9;x = 0<br>
&#9;&#9;&#9;&#9;y += max_h + padding<br>
<br>
&#9;&#9;# Keep CPU-side atlas; upload to GPU later when a graphics context is guaranteed.<br>
&#9;&#9;self._atlas_data = np.array(atlas, dtype=np.uint8)<br>
<br>
&#9;def _upload_texture(self, graphics: GraphicsBackend) -&gt; TextureHandle:<br>
&#9;&#9;if self._atlas_data is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;Font atlas data is missing; cannot upload texture.&quot;)<br>
&#9;&#9;return graphics.create_texture(self._atlas_data, (self.tex_w, self.tex_h), channels=1, mipmap=False, clamp=True)<br>
<!-- END SCAT CODE -->
</body>
</html>
