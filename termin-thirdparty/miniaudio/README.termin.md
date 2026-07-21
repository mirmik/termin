# miniaudio vendor drop

Termin vendors miniaudio v0.11.25 at commit
`9634bedb5b5a2ca38c1ee7108a9358a4e233f14d` from
<https://github.com/mackron/miniaudio>.

Tracked files and SHA-256 checksums:

- `miniaudio.h`: `ac7af4de748b7e26b777f37e01cee313a308a7296a3eb080e2906b320cc55c89`
- `miniaudio.c`: `ab1984bb9804ffd7b0303813595d0b345a8a86c34da1daffc353a14b34102a65`
- `LICENSE`: `457f1b500e0adf6bc059edddfa78a2f62012e7c3bb43476c20e0bd23b25ba0eb`
- `extras/decoders/libvorbis/miniaudio_libvorbis.h`: upstream v0.11.25
  libvorbis decoder adapter, SHA-256
  `ffbfdfa05994aa46330c0223f55114c9f3af88ebeb7a5fa6e18d0623b0b36aeb`.
- `extras/decoders/libvorbis/miniaudio_libvorbis.c`: upstream v0.11.25
  libvorbis decoder adapter, SHA-256
  `06fd2349b8c01e0d41f88ded1125f4c4bca4cc8ec7fbc9e4e224ee33b4289b78`.

`termin-audio` compiles this source privately with resource management,
encoding, and waveform generation disabled. No `ma_*` type is part of the
public Termin API. Ogg/Vorbis support uses the matching upstream adapter and
the pinned Xiph libogg/libvorbis submodules.
