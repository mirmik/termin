import json
from pathlib import Path

import pytest

from termin.project_build import android_apk_pipeline
from termin.project_build.android_apk_pipeline import AndroidApkProduct, build_android_apk


ANDROID_PRODUCT = AndroidApkProduct(
    display_name="Android",
    gradle_build_dir="android-gradle",
    artifact_qualifier="",
    log_filename="android-build.log",
)
QUEST_PRODUCT = AndroidApkProduct(
    display_name="Quest/OpenXR",
    gradle_build_dir="android-gradle-openxr",
    artifact_qualifier="quest-openxr",
    log_filename="quest-openxr-build.log",
)


@pytest.mark.parametrize(
    ("product", "application_id", "configuration", "variant", "artifact_name"),
    [
        (ANDROID_PRODUCT, "org.example.game", "dev", "debug", "Game-debug.apk"),
        (ANDROID_PRODUCT, "org.example.game", "debug", "debug", "Game-debug.apk"),
        (ANDROID_PRODUCT, "org.example.game", "release", "release", "Game-release.apk"),
        (
            QUEST_PRODUCT,
            "org.termin.openxr",
            "dev",
            "debug",
            "Game-quest-openxr-debug.apk",
        ),
        (
            QUEST_PRODUCT,
            "org.termin.openxr",
            "debug",
            "debug",
            "Game-quest-openxr-debug.apk",
        ),
        (
            QUEST_PRODUCT,
            "org.termin.openxr",
            "release",
            "release",
            "Game-quest-openxr-release.apk",
        ),
    ],
)
def test_build_android_apk_maps_configuration_and_uses_gradle_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    product: AndroidApkProduct,
    application_id: str,
    configuration: str,
    variant: str,
    artifact_name: str,
) -> None:
    termin_root = tmp_path / "termin"
    dist_dir = tmp_path / "dist"
    logs_dir = dist_dir / "logs"
    (dist_dir / "apk").mkdir(parents=True)
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    keystore = tmp_path / "release.keystore"
    keystore.write_bytes(b"keystore")
    for name, value in {
        "TERMIN_ANDROID_SIGNING_KEYSTORE": str(keystore),
        "TERMIN_ANDROID_SIGNING_KEY_ALIAS": "termin",
        "TERMIN_ANDROID_SIGNING_STORE_PASSWORD": "store-secret",
        "TERMIN_ANDROID_SIGNING_KEY_PASSWORD": "key-secret",
    }.items():
        monkeypatch.setenv(name, value)

    commands: list[list[str]] = []

    def fake_run_logged_process(**kwargs) -> None:
        cmd = kwargs["cmd"]
        commands.append(cmd)
        selected_variant = cmd[cmd.index("--variant") + 1]
        output_dir = (
            termin_root
            / "build"
            / product.gradle_build_dir
            / "app"
            / "outputs"
            / "apk"
            / selected_variant
        )
        output_dir.mkdir(parents=True)
        produced_apk = output_dir / f"product-{selected_variant}-from-gradle.apk"
        produced_apk.write_bytes(selected_variant.encode("ascii"))
        (output_dir / "output-metadata.json").write_text(
            json.dumps(
                {
                    "applicationId": application_id,
                    "elements": [{"outputFile": produced_apk.name}],
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(android_apk_pipeline, "_run_logged_process", fake_run_logged_process)

    result = build_android_apk(
        product=product,
        configuration=configuration,
        project_name="Game",
        application_id=application_id,
        termin_root=termin_root,
        build_script=tmp_path / "build-apk",
        package_dir=package_dir,
        dist_dir=dist_dir,
        logs_dir=logs_dir,
        gradle=tmp_path / "gradle",
        android_sdk_root=tmp_path / "sdk/android",
        abi="arm64-v8a",
        platform="android-26",
    )

    assert commands[0][commands[0].index("--variant") + 1] == variant
    assert result.variant.task == ("assembleDebug" if variant == "debug" else "assembleRelease")
    assert result.apk_path == dist_dir / "apk" / artifact_name
    assert result.apk_path.read_bytes() == variant.encode("ascii")


def test_release_build_fails_before_launch_when_signing_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in android_apk_pipeline.ANDROID_RELEASE_SIGNING_ENV:
        monkeypatch.delenv(name, raising=False)
    launched = False

    def fake_run_logged_process(**kwargs) -> None:
        nonlocal launched
        launched = True

    monkeypatch.setattr(android_apk_pipeline, "_run_logged_process", fake_run_logged_process)

    with pytest.raises(RuntimeError, match="release builds require signing configuration"):
        build_android_apk(
            product=ANDROID_PRODUCT,
            configuration="release",
            project_name="Game",
            application_id="org.example.game",
            termin_root=tmp_path,
            build_script=tmp_path / "build-apk",
            package_dir=tmp_path / "package",
            dist_dir=tmp_path / "dist",
            logs_dir=tmp_path / "dist/logs",
            gradle=None,
            android_sdk_root=tmp_path / "sdk/android",
            abi="arm64-v8a",
            platform="android-26",
        )

    assert not launched


def test_gradle_metadata_rejects_wrong_application_id(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "build/android-gradle/app/outputs/apk/debug"
    output_dir.mkdir(parents=True)
    (output_dir / "game.apk").write_bytes(b"apk")
    (output_dir / "output-metadata.json").write_text(
        json.dumps(
            {
                "applicationId": "org.example.wrong",
                "elements": [{"outputFile": "game.apk"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="applicationId mismatch"):
        android_apk_pipeline.discover_gradle_apk(
            termin_root=tmp_path,
            product=ANDROID_PRODUCT,
            variant=android_apk_pipeline.resolve_android_gradle_variant("debug"),
            expected_application_id="org.example.game",
        )
