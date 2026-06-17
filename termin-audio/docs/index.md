# termin-audio

`termin-audio` owns the runtime audio primitives and audio asset integration:

- `termin.audio.AudioEngine`
- `termin.audio.AudioClip`
- `termin.audio.asset.AudioClipAsset`
- `termin.audio.handle.AudioClipHandle`
- `termin.audio.asset_plugin.AudioClipImportPlugin`
- `termin.audio.asset_plugin.AudioClipRuntimePlugin`
- `termin.audio.components.AudioSource`
- `termin.audio.components.AudioListener`

The package intentionally owns the whole `termin.audio` namespace so `termin-app`
does not need to provide audio runtime or component modules.
