from termin.animation import TcAnimationClip
from termin.default_assets.animation.asset import AnimationClipAsset


def test_animation_clip_asset_wraps_clip():
    clip = TcAnimationClip.create("walk")
    asset = AnimationClipAsset.from_clip(clip, source_path="/tmp/walk.anim")

    assert asset.clip is clip
    assert asset.name == "walk"
    assert asset.source_path.name == "walk.anim"


def test_animation_clip_asset_package_reexports_canonical_class():
    from termin.default_assets.animation import AnimationClipAsset as PackageAnimationClipAsset

    assert PackageAnimationClipAsset is AnimationClipAsset
