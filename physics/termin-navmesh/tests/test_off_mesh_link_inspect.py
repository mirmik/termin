from __future__ import annotations

import gc

import pytest

from termin.bootstrap import bootstrap_player, shutdown_player


@pytest.fixture(scope="module", autouse=True)
def _runtime():
    bootstrap_player()
    yield
    gc.collect()
    shutdown_player()


def test_off_mesh_link_stable_user_id_roundtrips_above_signed_int_range():
    from termin.navmesh import OffMeshLinkComponent

    component = OffMeshLinkComponent()
    component.stable_user_id = 4_000_000_000

    data = component.serialize_data()

    assert data["stable_user_id"] == 4_000_000_000
    component.stable_user_id = 0
    component.deserialize_data(data)
    assert component.stable_user_id == 4_000_000_000
