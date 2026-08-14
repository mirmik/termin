from __future__ import annotations

import json

import numpy as np
import pytest

from termin.inspect import KindRegistry
from termin.prefab import PrefabOverrideValue


@pytest.mark.parametrize(
    ("value", "tag"),
    [
        (None, "none"),
        (True, "bool"),
        (-(2**63), "int64"),
        (2**64 - 1, "uint64"),
        (1.25, "float64"),
        ("hello", "string"),
        ([1, 2.0, "three"], "list"),
        ((1, 2, 3), "tuple"),
        ({"nested": [None, False]}, "dict"),
    ],
)
def test_python_value_round_trip_preserves_explicit_type(value, tag):
    encoded = PrefabOverrideValue.from_python(value)

    assert encoded.tag == tag
    assert encoded.to_python() == value
    assert PrefabOverrideValue.from_json(encoded.to_json()).to_data() == encoded.to_data()


def test_numeric_list_is_not_inferred_as_dense_array():
    numeric_list = PrefabOverrideValue.from_python([1.0, 2.0, 3.0])
    dense_array = PrefabOverrideValue.from_python(
        np.asarray([1.0, 2.0, 3.0], dtype=np.float32)
    )

    assert numeric_list.tag == "list"
    assert dense_array.tag == "array"
    decoded = dense_array.to_python()
    assert isinstance(decoded, np.ndarray)
    assert decoded.dtype == np.float32
    np.testing.assert_array_equal(decoded, np.asarray([1.0, 2.0, 3.0], dtype=np.float32))


def test_dense_array_round_trip_preserves_shape_and_dtype():
    source = np.asarray([[1, 2, 3], [4, 5, 6]], dtype=np.uint16)

    encoded = PrefabOverrideValue.from_python(source)
    decoded = encoded.to_python()

    assert encoded.to_data()["value"]["shape"] == [2, 3]
    assert decoded.shape == (2, 3)
    assert decoded.dtype == np.uint16
    np.testing.assert_array_equal(decoded, source)


def test_numpy_scalar_uses_primitive_tag():
    encoded = PrefabOverrideValue.from_python(np.float32(2.5))

    assert encoded.tag == "float64"
    assert encoded.to_python() == 2.5


def test_registered_kind_round_trip_preserves_semantic_kind():
    class VectorProbe:
        def __init__(self, values):
            self.values = tuple(values)

    registry = KindRegistry.instance()
    registry.register_python(
        "prefab_test_vector",
        lambda value: list(value.values),
        lambda data: VectorProbe(data),
    )
    registry.register_type(VectorProbe, "prefab_test_vector")
    try:
        encoded = PrefabOverrideValue.from_python(VectorProbe((1.0, 2.0, 3.0)))
        decoded = encoded.to_python()

        assert encoded.tag == "kind"
        assert encoded.to_data()["value"]["kind"] == "prefab_test_vector"
        assert isinstance(decoded, VectorProbe)
        assert decoded.values == (1.0, 2.0, 3.0)
    finally:
        registry.unregister_python("prefab_test_vector")


def test_native_scalar_kind_can_wrap_plain_python_payload():
    encoded = PrefabOverrideValue.from_python(3.5, kind="double")

    assert encoded.tag == "kind"
    assert encoded.to_data()["value"]["kind"] == "double"
    assert encoded.to_python() == 3.5


def test_resource_round_trip_requires_explicit_type_kind_and_uuid():
    class ResourceProbe:
        def __init__(self, uuid: str, name: str = ""):
            self.uuid = uuid
            self.name = name

    registry = KindRegistry.instance()
    registry.register_python(
        "prefab_test_resource",
        lambda value: {"uuid": value.uuid, "name": value.name},
        lambda data: ResourceProbe(data["uuid"], data.get("name", "")),
    )
    registry.register_type(ResourceProbe, "prefab_test_resource")
    try:
        encoded = PrefabOverrideValue.from_python(
            ResourceProbe("resource-uuid", "Probe"),
            kind="prefab_test_resource",
            resource_type="test-resource",
        )
        decoded = encoded.to_python()

        assert encoded.tag == "resource"
        assert encoded.to_data()["value"] == {
            "tag": "resource",
            "resource_type": "test-resource",
            "kind": "prefab_test_resource",
            "uuid": "resource-uuid",
            "name": "Probe",
        }
        assert isinstance(decoded, ResourceProbe)
        assert decoded.uuid == "resource-uuid"
    finally:
        registry.unregister_python("prefab_test_resource")


@pytest.mark.parametrize(
    "value",
    [
        2**64,
        float("nan"),
        float("inf"),
        {1: "non-string-key"},
        np.asarray([1 + 2j], dtype=np.complex64),
        object(),
    ],
)
def test_unsupported_python_values_fail_without_partial_fallback(value):
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        PrefabOverrideValue.from_python(value)


def test_malformed_tagged_data_is_rejected_with_context():
    malformed = {
        "schema": "termin.prefab.override-value",
        "version": 1,
        "value": {
            "tag": "dict",
            "entries": [
                {"key": "same", "value": {"tag": "none"}},
                {"key": "same", "value": {"tag": "bool", "value": True}},
            ],
        },
    }

    with pytest.raises(ValueError, match="duplicate dictionary key"):
        PrefabOverrideValue.from_json(json.dumps(malformed))
