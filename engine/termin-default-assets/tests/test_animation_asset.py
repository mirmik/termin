import json
import uuid

import pytest

from termin.animation import TcAnimationClip, save_animation_clip
from termin.default_assets.animation.asset import AnimationClipAsset


def test_animation_clip_asset_wraps_clip():
    clip = TcAnimationClip.create("walk")
    asset = AnimationClipAsset.from_clip(clip, source_path="/tmp/walk.anim")

    assert asset.clip is clip
    assert asset.uuid == clip.uuid
    assert asset.name == "walk"
    assert asset.source_path.name == "walk.anim"


def test_animation_clip_asset_package_reexports_canonical_class():
    from termin.default_assets.animation import AnimationClipAsset as PackageAnimationClipAsset

    assert PackageAnimationClipAsset is AnimationClipAsset


def _translation_clip(name="walk", distance=1.0):
    clip = TcAnimationClip.create(name, str(uuid.uuid4()))
    clip.set_tps(1.0)
    clip.set_loop(False)
    clip.set_tracks([
        {
            "target_node_index": 0,
            "path": "translation",
            "interpolation": "linear",
            "components": 3,
            "times": [0.0, 1.0],
            "values": [0.0, 0.0, 0.0, distance, 0.0, 0.0],
        }
    ])
    return clip


def test_animation_asset_constructor_preserves_clip_identity():
    clip = _translation_clip()

    assert AnimationClipAsset(clip=clip).uuid == clip.uuid
    assert AnimationClipAsset(clip=clip, uuid=clip.uuid).uuid == clip.uuid
    with pytest.raises(ValueError, match="UUIDs must match"):
        AnimationClipAsset(clip=clip, uuid=str(uuid.uuid4()))


def test_animation_asset_load_uses_asset_uuid(tmp_path):
    path = tmp_path / "walk.tanim"
    source = _translation_clip(distance=2.0)
    save_animation_clip(source, path)
    asset_uuid = str(uuid.uuid4())
    asset = AnimationClipAsset(source_path=path, uuid=asset_uuid)

    assert asset.ensure_loaded()
    assert asset.clip.uuid == asset_uuid
    assert asset.clip.uuid != source.uuid
    assert tuple(asset.clip.sample_track(0, 0.5)) == pytest.approx((1.0, 0.0, 0.0))
    assert TcAnimationClip.from_uuid(asset_uuid).is_valid
    assert source.name == "walk"


def test_animation_asset_reload_updates_retained_clip_in_place(tmp_path):
    path = tmp_path / "walk.tanim"
    source = _translation_clip()
    save_animation_clip(source, path)
    asset = AnimationClipAsset(source_path=path)
    assert asset.ensure_loaded()
    retained = asset.clip
    previous_version = retained.version

    updated = _translation_clip(name="run", distance=4.0)
    save_animation_clip(updated, path)
    assert asset.reload()

    assert retained.is_valid
    assert retained.uuid == asset.uuid == asset.clip.uuid
    assert retained.version > previous_version
    assert retained.name == "run"
    assert tuple(retained.sample_track(0, 0.5)) == pytest.approx((2.0, 0.0, 0.0))


def test_animation_asset_failed_reload_preserves_clip(tmp_path):
    path = tmp_path / "walk.tanim"
    source = _translation_clip(distance=2.0)
    save_animation_clip(source, path)
    asset = AnimationClipAsset(source_path=path)
    assert asset.ensure_loaded()
    retained = asset.clip
    previous_version = retained.version
    previous_asset_version = asset.version
    data = json.loads(path.read_text(encoding="utf-8"))
    data["name"] = "broken"
    data["tps"] = 5.0
    data["loop"] = True
    data["tracks"][0]["values"].pop()
    path.write_text(json.dumps(data), encoding="utf-8")

    assert not asset.reload()

    assert asset.is_loaded
    assert asset.clip is retained
    assert asset.version == previous_asset_version
    assert retained.version == previous_version
    assert retained.name == "walk"
    assert retained.tps == 1.0
    assert not retained.loop
    assert tuple(retained.sample_track(0, 0.5)) == pytest.approx((1.0, 0.0, 0.0))
