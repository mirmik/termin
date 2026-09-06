import numpy as np
import pytest
from termin.graphics import TcTexture


@pytest.mark.parametrize("channels", [1, 2, 3, 4])
def test_texture_payload_round_trip(channels):
    pixels = np.arange(6 * channels, dtype=np.uint8).reshape(2, 3, channels)
    texture = TcTexture.from_data(pixels, 3, 2, channels, flip_y=False)
    assert texture.is_valid
    assert texture.channels == channels
    assert texture.data_size == pixels.nbytes
    np.testing.assert_array_equal(texture.data, pixels)
    uploaded, extent = texture.get_upload_data()
    assert extent == (3, 2)
    np.testing.assert_array_equal(uploaded, pixels)


@pytest.mark.parametrize(
    "size,width,height,channels",
    [(2, 1, 1, 3), (4, 1, 1, 3), (0, 0, 1, 3), (0, 1, 0, 3),
     (3, 1, 1, 0), (5, 1, 1, 5), (3, 2**32 - 1, 2**32 - 1, 4)],
)
def test_invalid_texture_payload_is_rejected(size, width, height, channels):
    with pytest.raises(ValueError, match="buffer size"):
        TcTexture.from_data(np.zeros(size, dtype=np.uint8), width, height, channels)


def test_short_update_does_not_damage_existing_texture():
    pixels = np.array([[[10, 20, 30]]], dtype=np.uint8)
    texture = TcTexture.from_data(pixels, 1, 1, 3, uuid="payload-update-test")
    version = texture.version
    with pytest.raises(ValueError, match="buffer size"):
        TcTexture.from_data(np.zeros(2, dtype=np.uint8), 1, 1, 3, uuid=texture.uuid)
    assert texture.version == version
    np.testing.assert_array_equal(texture.data, pixels)
