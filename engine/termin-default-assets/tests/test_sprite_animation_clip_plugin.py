import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from termin.default_assets.render.sprite_animation_plugin import SpriteAnimationClipImportPlugin, SpriteAnimationClipRuntimePlugin
from termin.render_components import TcSpriteAnimationClip, parse_sprite_animation_clip
from termin_assets import AssetCatalog, AssetContext, AssetIdentityPolicy


def descriptor(frames):
    return json.dumps({"format": "termin.sprite-animation", "version": 1, "frames": frames})


def test_clip_load_reload_unload(tmp_path: Path):
    path = tmp_path / "run.spriteclip"
    path.write_text(descriptor([{"sprite": "a", "duration": 0.1}, {"sprite": "b", "duration": 0.25, "event": "step"}]))
    uuid = str(uuid4())
    result = SpriteAnimationClipImportPlugin().preload(str(path))
    assert result.identity_policy is AssetIdentityPolicy.GENERATE_SIDECAR
    assert result.resource_type == "sprite_animation_clip"
    catalog = AssetCatalog()
    context = AssetContext(resource_manager=SimpleNamespace(external_assets=catalog), name="run", uuid=uuid)
    plugin = SpriteAnimationClipRuntimePlugin()
    plugin.register(context, result)
    clip = TcSpriteAnimationClip.from_uuid(uuid)
    assert clip.is_loaded and clip.uuid == uuid
    assert [(f.sprite_uuid, f.duration, f.event) for f in clip.frames] == [("a", 0.1, ""), ("b", 0.25, "step")]
    assert catalog.get_by_uuid(result.resource_type, uuid).path == str(path)

    first_version = clip.version
    path.write_text(descriptor([{"sprite": "b", "duration": 0.5}]))
    assert plugin.reload(context, result)
    assert clip.version == first_version + 1
    assert clip.frames[0].duration == 0.5
    path.write_text(descriptor([{"sprite": "b", "duration": -1}]))
    with pytest.raises(ValueError, match="duration"):
        plugin.reload(context, result)
    assert clip.frames[0].duration == 0.5 and clip.version == first_version + 1

    plugin.unregister(context, result)
    assert clip.is_valid and not clip.is_loaded and not clip.frames
    assert catalog.get_by_uuid(result.resource_type, uuid) is None


@pytest.mark.parametrize("frames", [
    [], None, [{"duration": 0.1}], [{"sprite": "", "duration": 0.1}],
    [{"sprite": "a", "duration": 0}], [{"sprite": "a", "duration": True}],
    [{"sprite": "a", "duration": 0.1, "event": None}],
])
def test_invalid_frames(frames):
    with pytest.raises(ValueError):
        parse_sprite_animation_clip(descriptor(frames))


def test_rejects_unknown_clip_version():
    with pytest.raises(ValueError, match="version"):
        parse_sprite_animation_clip('{"format":"termin.sprite-animation","version":2,"frames":[]}')
