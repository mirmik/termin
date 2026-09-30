import uuid

import pytest

from termin.base import clear_resource_loader, set_resource_loader
from termin.voxels import TcVoxelGrid, tc_voxel_grid_get_all_info


@pytest.mark.parametrize("success", [False, True])
def test_lazy_voxel_grid_loading_survives_registry_growth(success):
    resource_uuid = str(uuid.uuid4())
    resource = TcVoxelGrid.declare(resource_uuid, "deferred voxel grid")
    # Registry capacity doubles; declarations remain registered after Python
    # wrappers go away. Exceed the next capacity boundary from the current count.
    allocation_count = max(64, 2 * len(tc_voxel_grid_get_all_info()))
    declared = []
    calls = []

    def load(loaded_uuid):
        calls.append(loaded_uuid)
        for _ in range(allocation_count):
            declared.append(TcVoxelGrid.declare(str(uuid.uuid4()), "grow pool"))
        return success

    set_resource_loader(load)
    try:
        assert not resource.is_loaded
        assert resource.ensure_loaded() is success
        assert calls == [resource_uuid]
        assert resource.is_valid
        assert resource.uuid == resource_uuid
        assert resource.name == "deferred voxel grid"
        assert resource.is_loaded is success
        if success:
            assert resource.ensure_loaded()
            assert calls == [resource_uuid]
        assert all(entry.is_valid and not entry.is_loaded for entry in declared)
    finally:
        clear_resource_loader()
