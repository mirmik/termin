from termin.audio.components.audio_source import AudioSource
from termin.audio import TcAudioClip


def test_audio_source_inspector_uses_serialized_handle_values():
    source = AudioSource()
    source.clip = TcAudioClip.declare("audio-inspector-uuid", "impact")
    field = source.inspect_fields["clip"]

    assert field.kind == "audio_clip_handle"
    assert field.get_value(source) == {"uuid": "audio-inspector-uuid", "name": "impact"}

    field.set_value(source, {"uuid": "audio-inspector-uuid", "name": "impact"})
    assert isinstance(source.clip, TcAudioClip)
    assert source.clip.uuid == "audio-inspector-uuid"

    field.set_value(source, None)
    assert source.clip is None


def test_audio_source_inspector_rejects_name_only_references():
    source = AudioSource()
    field = source.inspect_fields["clip"]

    field.set_value(source, {"uuid": None, "name": "impact"})

    assert source.clip is None
