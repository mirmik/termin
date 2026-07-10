from termin.audio.components.audio_source import AudioSource
from termin.default_assets.audio.handle import AudioClipHandle


class _Asset:
    uuid = "audio-uuid"
    name = "impact"


class _Clip:
    is_asset = True

    def get_asset(self):
        return _Asset()


def test_audio_source_inspector_uses_serialized_handle_values():
    source = AudioSource()
    source.clip = _Clip()
    field = source.inspect_fields["clip"]

    assert field.kind == "audio_clip_handle"
    assert field.get_value(source) == {"uuid": "audio-uuid", "name": "impact"}

    field.set_value(source, {"uuid": "audio-uuid", "name": "impact"})
    assert isinstance(source.clip, AudioClipHandle)

    field.set_value(source, None)
    assert source.clip is None
