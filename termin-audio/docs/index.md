# termin-audio

`termin-audio` owns the runtime audio primitives and audio scene components:

- `termin.audio.AudioEngine`
- `termin.audio.AudioClip`
- `termin.audio.components.AudioSource`
- `termin.audio.components.AudioListener`

Audio asset adapters live in `termin-default-assets` under
`termin.default_assets.audio`: `AudioClipAsset`, `AudioClipHandle`, and
audio-clip import/runtime plugins. Old `termin.audio.asset`,
`termin.audio.handle`, `termin.audio.asset_plugin`, and
`termin.assets.audio_clip_*` paths remain compatibility re-exports.
