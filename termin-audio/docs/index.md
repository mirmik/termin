# termin-audio

`termin-audio` owns the runtime audio primitives and audio scene components:

- `termin.audio.AudioEngine`
- `termin.audio.AudioClip`
- `termin.audio.components.AudioSource`
- `termin.audio.components.AudioListener`

Audio asset adapters live in `termin-default-assets` under
`termin.default_assets.audio`: `AudioClipAsset`, `AudioClipHandle`, and
audio-clip import/runtime plugins. Import asset types and plugin factories from
`termin.default_assets.audio.*` directly; old domain and app compatibility paths
have been removed.
