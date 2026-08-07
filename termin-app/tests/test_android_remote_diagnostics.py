import os
from pathlib import Path
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ACTIVITY = (
    REPO_ROOT
    / "termin-android/platform/app/src/main/java/org/termin/android/TerminActivity.java"
)
BOOTSTRAP = REPO_ROOT / "termin-android/src/bootstrap.cpp"
MANIFEST = REPO_ROOT / "termin-android/platform/app/src/main/AndroidManifest.xml"


def test_remote_framegraph_is_debuggable_gated_and_does_not_log_token() -> None:
    activity = ACTIVITY.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")

    assert "debuggable && remoteFramegraphRequested" in activity
    assert 'getBooleanExtra("termin.framegraph.remote", false)' in activity
    assert 'getIntExtra("termin.framegraph.port", 46052)' in activity
    assert 'getStringExtra("termin.framegraph.token")' in activity
    assert 'android:debuggable="true"' not in manifest

    assert 'target.platform = "Android"' in bootstrap
    assert "RemoteFrameGraphTarget" in bootstrap
    assert "attach_debugger" in bootstrap
    assert "detach_debugger" in bootstrap
    assert "remote_framegraph_token" not in "\n".join(
        line
        for line in bootstrap.splitlines()
        if "android_log_" in line or "tc_log_" in line
    )
    assert '" + remoteFramegraphToken' not in activity


@pytest.mark.parametrize(
    ("helper", "port", "prefix"),
    [
        ("android-profiler-forward", "46051", "termin.profiler"),
        ("android-framegraph-forward", "46052", "termin.framegraph"),
    ],
)
def test_android_diagnostics_forward_helpers_launch_expected_service(
    tmp_path: Path,
    helper: str,
    port: str,
    prefix: str,
) -> None:
    calls = tmp_path / "adb-calls"
    fake_adb = tmp_path / "adb"
    fake_adb.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$TERMIN_TEST_ADB_CALLS\"\n",
        encoding="utf-8",
    )
    fake_adb.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["TERMIN_TEST_ADB_CALLS"] = str(calls)

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / helper),
            "--serial",
            "device-1",
            "--token",
            "launch-secret",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    recorded = calls.read_text(encoding="utf-8")
    assert f"forward tcp:{port} tcp:{port}" in recorded
    assert f"--ez {prefix}.remote true" in recorded
    assert f"--ei {prefix}.port {port}" in recorded
    assert f"--es {prefix}.token launch-secret" in recorded
    assert "127.0.0.1" in result.stdout
    assert f"editor port:   {port}" in result.stdout
