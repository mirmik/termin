"""A .tanim file must reconstruct its payload without a warm registry."""

import copy
import json
import subprocess
import sys
import uuid

import pytest

from termin.animation import TcAnimationClip, load_animation_clip, save_animation_clip
from termin.animation._animation_native import tc_animation_declare, tc_animation_is_loaded
from termin.animation.clip_io import parse_animation_content
from termin.base import clear_resource_loader, set_resource_loader
from termin.geombase import Quat, Vec3


def _tracks():
    return [
        {
            "target_node_index": 7,
            "path": "translation",
            "interpolation": "step",
            "components": 3,
            "times": [0.0, 2.0],
            "values": [1.0, 2.0, 3.0, 7.0, 8.0, 9.0],
        },
        {
            "target_node_index": 7,
            "path": "scale",
            "interpolation": "linear",
            "components": 3,
            "times": [0.0, 2.0],
            "values": [1.0, 2.0, 3.0, 3.0, 6.0, 9.0],
        },
        {
            "target_node_index": 7,
            "path": "rotation",
            "interpolation": "cubic_spline",
            "components": 4,
            "times": [0.0, 2.0],
            "values": [
                2.0, 3.0, 4.0, 5.0,
                0.0, 0.0, 0.0, 1.0,
                6.0, 7.0, 8.0, 9.0,
                -2.0, -3.0, -4.0, -5.0,
                0.0, 0.0, 1.0, 0.0,
                -6.0, -7.0, -8.0, -9.0,
            ],
        },
        {
            "target_node_index": 7,
            "path": "weights",
            "interpolation": "cubic_spline",
            "components": 2,
            "times": [0.0, 2.0],
            "values": [0.0, 0.0, 0.25, 0.75, 0.1, -0.1, 0.2, -0.2, 0.6, 0.4, 0.0, 0.0],
        },
    ]


def _document(resource_uuid=None):
    return {
        "format": "termin.animation",
        "version": 1,
        "uuid": resource_uuid or str(uuid.uuid4()),
        "name": "Полная анимация",
        "tps": 2.0,
        "loop": False,
        "tracks": _tracks(),
    }


def _fresh_process(path, body):
    script = """
import json
import sys
from termin.animation import TcAnimationClip, load_animation_clip
with open(sys.argv[1], encoding="utf-8") as source:
    document = json.load(source)
assert not TcAnimationClip.from_uuid(document["uuid"]).is_valid
clip = load_animation_clip(sys.argv[1])
""" + body
    result = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


def test_track_file_roundtrip_in_fresh_process_preserves_exact_payload_and_samples(tmp_path):
    document = _document()
    clip = TcAnimationClip.create(document["name"], document["uuid"])
    clip.set_tps(document["tps"])
    clip.set_loop(document["loop"])
    clip.set_tracks(document["tracks"])
    path = tmp_path / "complete.tanim"

    save_animation_clip(clip, path)

    assert json.loads(path.read_text(encoding="utf-8")) == document
    assert dict(clip.serialize()) == {"type": "uuid", "uuid": clip.uuid, "name": clip.name}
    restored = _fresh_process(path, """
print(json.dumps({
    "uuid": clip.uuid, "name": clip.name, "tps": clip.tps, "loop": clip.loop,
    "duration": clip.duration, "tracks": clip.tracks,
    "step": list(clip.sample_track(0, 0.5)),
    "scale": list(clip.sample_track(1, 0.5)),
}))
""")
    assert restored == {
        "uuid": document["uuid"], "name": document["name"], "tps": 2.0, "loop": False,
        "duration": 1.0, "tracks": document["tracks"],
        "step": [1.0, 2.0, 3.0], "scale": [2.0, 4.0, 6.0],
    }


def test_legacy_channel_file_roundtrip_in_fresh_process(tmp_path):
    clip = TcAnimationClip.create("Legacy channels", str(uuid.uuid4()))
    clip.set_tps(2.0)
    clip.set_loop(False)
    clip.set_channels([{
        "target_name": "Root",
        "translation_keys": [(0.0, Vec3(1, 2, 3)), (2.0, Vec3(3, 6, 9))],
        "rotation_keys": [(0.0, Quat(0, 0, 0, 1)), (2.0, Quat(0, 0, 1, 0))],
        "scale_keys": [(0.0, 1.0), (2.0, 3.0)],
    }])
    path = tmp_path / "channels.tanim"
    save_animation_clip(clip, path)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert "tracks" not in document
    assert document["channels"] == [{
        "target_name": "Root",
        "translation_keys": [[0.0, [1.0, 2.0, 3.0]], [2.0, [3.0, 6.0, 9.0]]],
        "rotation_keys": [[0.0, [0.0, 0.0, 0.0, 1.0]], [2.0, [0.0, 0.0, 1.0, 0.0]]],
        "scale_keys": [[0.0, 1.0], [2.0, 3.0]],
    }]
    restored = _fresh_process(path, """
print(json.dumps({"sample": clip.sample(0.5), "duration": clip.duration,
                  "tps": clip.tps, "loop": clip.loop, "count": clip.channel_count}))
""")
    assert restored["count"] == 1
    assert restored["duration"] == pytest.approx(1.0)
    assert restored["tps"] == 2.0
    assert restored["loop"] is False
    assert restored["sample"][0]["target_name"] == "Root"
    assert restored["sample"][0]["translation"] == pytest.approx([2.0, 4.0, 6.0])
    assert restored["sample"][0]["rotation"] == pytest.approx([0.0, 0.0, 2**-0.5, 2**-0.5])
    assert restored["sample"][0]["scale"] == pytest.approx(2.0)


@pytest.mark.parametrize("declared", [False, True])
def test_load_replaces_same_uuid_payload_and_metadata_in_place(tmp_path, declared):
    document = _document()
    if declared:
        existing = tc_animation_declare(document["uuid"], "Declared")
        assert not tc_animation_is_loaded(existing)
    else:
        existing = TcAnimationClip.create("Old name", document["uuid"])
        existing.set_tps(5.0)
        existing.set_loop(True)
        existing.set_tracks([_tracks()[0]])
    version = existing.version
    path = tmp_path / "updated.tanim"
    path.write_text(json.dumps(document), encoding="utf-8")

    loaded = load_animation_clip(path)

    assert loaded.uuid == existing.uuid == document["uuid"]
    assert existing.name == document["name"]
    assert existing.tracks == document["tracks"]
    assert existing.tps == 2.0
    assert existing.loop is False
    assert existing.version > version
    assert tc_animation_is_loaded(existing)


def _set_field(document, path, value):
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


@pytest.mark.parametrize("loaded", [False, True])
@pytest.mark.parametrize("field,value", [
    (("format",), "other.format"),
    (("version",), 2),
    (("version",), True),
    (("uuid",), 123),
    (("name",), None),
    (("tps",), 0.0),
    (("tps",), float("nan")),
    (("tps",), float("inf")),
    (("tps",), True),
    (("loop",), 1),
    (("tracks",), {}),
    (("channels",), []),
    (("tracks", 0, "target_node_index"), -1),
    (("tracks", 0, "target_node_index"), True),
    (("tracks", 0, "path"), "unknown"),
    (("tracks", 0, "interpolation"), "unknown"),
    (("tracks", 0, "components"), 2),
    (("tracks", 0, "times"), [1.0, 0.0]),
    (("tracks", 0, "times"), [0.0, 0.0]),
    (("tracks", 0, "values"), [1.0]),
    (("tracks", 0, "values", 0), float("inf")),
    (("tracks", 0, "values", 0), True),
    (("tracks", 2, "values", 7), 0.0),
])
def test_invalid_file_does_not_publish_or_change_existing_resource(field, value, loaded):
    document = _document()
    _set_field(document, field, value)
    # The asset UUID override must not bypass validation of the original document.
    target_uuid = str(uuid.uuid4())
    with pytest.raises((ValueError, TypeError, RuntimeError)):
        parse_animation_content(json.dumps(document), uuid_hint=target_uuid)
    assert not TcAnimationClip.from_uuid(target_uuid).is_valid

    existing = (
        parse_animation_content(json.dumps(_document(target_uuid)))
        if loaded else tc_animation_declare(target_uuid, "Still declared")
    )
    before = (existing.name, existing.tps, existing.loop, existing.version, existing.tracks)
    with pytest.raises((ValueError, TypeError, RuntimeError)):
        parse_animation_content(json.dumps(document), uuid_hint=target_uuid)
    assert (existing.name, existing.tps, existing.loop, existing.version, existing.tracks) == before
    assert tc_animation_is_loaded(existing) is loaded


@pytest.mark.parametrize("field", ["format", "version", "uuid", "name", "tps", "loop", "tracks"])
def test_incomplete_document_is_rejected_without_publication(field):
    document = _document()
    resource_uuid = document["uuid"]
    del document[field]
    with pytest.raises((ValueError, TypeError, RuntimeError)):
        parse_animation_content(json.dumps(document))
    assert not TcAnimationClip.from_uuid(resource_uuid).is_valid


def test_rejects_reference_only_legacy_file_even_with_live_uuid():
    clip = parse_animation_content(json.dumps(_document()))
    with pytest.raises(ValueError, match="reference|legacy|payload|format"):
        parse_animation_content(json.dumps(dict(clip.serialize())))


def test_asset_uuid_override_publishes_only_under_asset_identity():
    document = _document()
    asset_uuid = str(uuid.uuid4())
    clip = parse_animation_content(json.dumps(document), uuid_hint=asset_uuid)
    assert clip.uuid == asset_uuid
    assert clip.tracks == document["tracks"]
    assert not TcAnimationClip.from_uuid(document["uuid"]).is_valid


def test_saving_declared_clip_loads_payload_before_writing(tmp_path):
    document = _document()
    clip = tc_animation_declare(document["uuid"], document["name"])
    calls = []

    def load(resource_uuid):
        calls.append(resource_uuid)
        parsed = parse_animation_content(json.dumps(document))
        return parsed.is_valid

    set_resource_loader(load)
    try:
        path = tmp_path / "lazy.tanim"
        save_animation_clip(clip, path)
    finally:
        clear_resource_loader()
    assert calls == [document["uuid"]]
    assert json.loads(path.read_text(encoding="utf-8")) == document


def test_failed_lazy_save_preserves_existing_file(tmp_path):
    clip = tc_animation_declare(str(uuid.uuid4()), "Unavailable")
    path = tmp_path / "keep.tanim"
    path.write_text("original contents", encoding="utf-8")
    set_resource_loader(lambda resource_uuid: False)
    try:
        with pytest.raises((ValueError, RuntimeError)):
            save_animation_clip(clip, path)
    finally:
        clear_resource_loader()
    assert path.read_text(encoding="utf-8") == "original contents"


def test_empty_clip_is_explicit_valid_payload(tmp_path):
    document = _document()
    document["tracks"] = []
    clip = parse_animation_content(json.dumps(document))
    path = tmp_path / "empty.tanim"
    save_animation_clip(clip, path)
    assert json.loads(path.read_text(encoding="utf-8")) == document
    assert _fresh_process(path, 'print(json.dumps([clip.track_count, clip.channel_count, clip.duration]))') == [0, 0, 0.0]


@pytest.mark.parametrize("bad_keys", [
    [[0.0, [1.0, 2.0]]],
    [[0.0, [1.0, 2.0, 3.0], "tail"]],
    [[float("nan"), [1.0, 2.0, 3.0]]],
    [[1.0, [1.0, 2.0, 3.0]], [0.0, [4.0, 5.0, 6.0]]],
])
def test_invalid_legacy_channel_payload_is_transactional(bad_keys):
    document = _document()
    existing = parse_animation_content(json.dumps(document))
    before = (existing.version, existing.tracks)
    invalid = copy.deepcopy(document)
    del invalid["tracks"]
    invalid["channels"] = [{
        "target_name": "Root", "translation_keys": bad_keys,
        "rotation_keys": [], "scale_keys": [],
    }]
    with pytest.raises((ValueError, TypeError, RuntimeError)):
        parse_animation_content(json.dumps(invalid))
    assert (existing.version, existing.tracks) == before
