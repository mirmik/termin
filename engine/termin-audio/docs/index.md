# termin-audio

`termin-audio` owns canonical native audio resources, playback voices, and
audio scene components:

- `termin.audio.AudioEngine`
- `termin.audio.TcAudioClip`
- `termin.audio.TcAudioVoice`
- `termin.audio.components.AudioSource`
- `termin.audio.components.AudioListener`

`tc_audio_clip_handle` is the serializable resource identity. The native clip
registry owns decoded PCM and validates index/generation pairs. A
`tc_audio_voice_handle` is a transient playback instance referencing a clip;
voices own their independent cursor, looping, gain, pitch, and spatial state.

miniaudio is compiled privately as the device, decoding, mixing, resampling,
and spatialization backend. Its resource manager is disabled: UUIDs, names,
lifetime, and serialization remain owned by Termin.

The built-in decoder contract covers WAV, MP3, FLAC, and Ogg/Vorbis. Vorbis is
decoded by the bundled Xiph libogg/libvorbis backend through miniaudio's private
decoder-vtable boundary. Decoded PCM is copied into the canonical
`tc_audio_clip` registry; no backend object participates in resource identity or
lifetime.

Audio asset adapters live in `termin-default-assets` under
`termin.default_assets.audio`: `AudioClipAsset` declares and loads the canonical
native clip, while import/runtime plugins connect project assets to the registry.
No Python resource handle or process-global resource-manager lookup participates
in audio resolution.
