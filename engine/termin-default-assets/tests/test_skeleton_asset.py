from termin.default_assets.skeleton.asset import SkeletonAsset
from termin.skeleton import TcSkeleton


def test_skeleton_asset_wraps_tc_skeleton():
    skeleton = TcSkeleton.create("test-skeleton")
    asset = SkeletonAsset.from_tc_skeleton(
        skeleton,
        name="rig",
        source_path="/tmp/rig.glb",
    )

    assert asset.skeleton_data is skeleton
    assert asset.name == "rig"
    assert asset.source_path.name == "rig.glb"


def test_skeleton_asset_package_reexports_canonical_class():
    from termin.default_assets.skeleton import SkeletonAsset as PackageSkeletonAsset

    assert PackageSkeletonAsset is SkeletonAsset
