from __future__ import annotations

from termin_assets import AssetCatalog, AssetContext, PreLoadResult
from termin.foliage import TcFoliageData
from termin.foliage.asset_plugin import FoliageDataRuntimePlugin


class _ResourceManager:
    def __init__(self) -> None:
        self.external_assets = AssetCatalog()


def test_runtime_plugin_declares_native_foliage_data() -> None:
    TcFoliageData.clear_registry_for_tests()
    uuid = "00000000-0005-0000-0003-000000000001"
    path = "/tmp/foliage_data.tfoliage"
    rm = _ResourceManager()
    context = AssetContext(resource_manager=rm, name="foliage_data")
    result = PreLoadResult(
        resource_type="foliage_data",
        path=path,
        content=None,
        uuid=uuid,
        spec_data={"uuid": uuid},
    )

    FoliageDataRuntimePlugin().register(context, result)

    record = rm.external_assets.get_by_uuid("foliage_data", uuid)
    assert record is not None
    assert record.path == path

    handle = TcFoliageData.from_uuid(uuid)
    assert handle.is_valid
    assert handle.name == "foliage_data"
    assert handle.source_path == path
    TcFoliageData.clear_registry_for_tests()
