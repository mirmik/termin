# Termin application icon

The selected icon is the folded letter T, source `assets/branding/icons/05-folded-t.png`
(relative to the repository root). The master and design history live in
`assets/branding/`; only application exports are packaged here.

Rebuild from the repository root with `task branding:icon` (Python 3 + FFmpeg),
then `task build` to install into the SDK.

- PNG: opaque RGB, 256 × 256, installed for Linux desktop launchers.
- BMP: 24-bit RGB, 256 × 256, loaded by SDL editor and launcher windows.
- ICO: RGB PNG frames at 16, 20, 24, 32, 40, 48, 64, 96, 128 and 256 pixels.

Exports discard the generated alpha channel and retain its RGB artwork and
midnight background, matching the approved opaque preview. This avoids the
unwanted translucent halo. No mask, crop or regenerated artwork is applied.
The obsolete tesseract SVG is retired; historical concepts remain in `docs/ui`.
