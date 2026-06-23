import termin._native.assets as native_assets


def test_app_native_assets_does_not_export_texture_handle() -> None:
    assert "TextureHandle" not in dir(native_assets)
    assert "get_white_texture_handle" not in dir(native_assets)
