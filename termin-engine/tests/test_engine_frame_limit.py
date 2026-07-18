import math

import pytest

from termin.engine import EngineCore


def test_engine_core_accepts_zero_as_unlimited_frame_rate():
    engine = EngineCore()

    engine.target_fps = 0

    assert engine.target_fps == 0


@pytest.mark.parametrize("value", [-1.0, math.inf, math.nan])
def test_engine_core_rejects_invalid_frame_rate_limits(value):
    engine = EngineCore()

    with pytest.raises(ValueError, match="target FPS"):
        engine.target_fps = value
