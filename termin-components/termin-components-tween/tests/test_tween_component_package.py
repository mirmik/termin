from __future__ import annotations

from importlib.util import find_spec

from termin.tween import TweenManagerComponent
from termin.tween_components import TweenManagerComponent as CanonicalComponent
from termin_tween_component_specs import COMPONENT_SPECS


def test_tween_component_uses_its_own_package_boundary() -> None:
    assert TweenManagerComponent is CanonicalComponent
    assert COMPONENT_SPECS == (
        ("termin.tween_components.component", "TweenManagerComponent"),
    )
    assert find_spec("termin.tween.component") is None
