#!/usr/bin/env python3
"""Make the pinned Slang binary usable with manylinux_2_28 libstdc++."""

from __future__ import annotations

import platform
from pathlib import Path
import subprocess
import sys


GCC_NONSHARED = Path(
    "/opt/rh/gcc-toolset-14/root/usr/lib/gcc/"
    "x86_64-redhat-linux/14/libstdc++_nonshared.a"
)
SYSTEM_LIBSTDCXX = Path("/usr/lib64/libstdc++.so.6")
ORIGINAL_SONAME = "libstdc++.so.6"
COMPAT_SONAME = "libstdc++-slang-compat.so.6"
VERSION_SCRIPT = Path(__file__).with_name("slang-libstdcxx.map")


def run(command: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"command failed with exit code {result.returncode}: "
            f"{' '.join(command)}{': ' + detail if detail else ''}"
        )
    return result.stdout.strip() if capture else ""


def is_elf(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as stream:
        return stream.read(4) == b"\x7fELF"


def patch_toolchain(root: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        raise RuntimeError("Slang manylinux compatibility patch requires Linux x86_64")
    required = (GCC_NONSHARED, SYSTEM_LIBSTDCXX, VERSION_SCRIPT, root / "bin" / "slangc")
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Slang compatibility inputs are missing: " + ", ".join(missing))

    compatibility_library = root / "lib" / COMPAT_SONAME
    compatibility_library.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "gcc",
            "-shared",
            f"-Wl,-soname,{COMPAT_SONAME}",
            f"-Wl,--version-script,{VERSION_SCRIPT}",
            "-Wl,--whole-archive",
            str(GCC_NONSHARED),
            "-Wl,--no-whole-archive",
            "-Wl,--no-as-needed",
            str(SYSTEM_LIBSTDCXX),
            "-o",
            str(compatibility_library),
        ]
    )

    patched = 0
    compatible = 0
    for candidate in sorted(root.rglob("*")):
        if candidate == compatibility_library or not is_elf(candidate):
            continue
        needed = run(["patchelf", "--print-needed", str(candidate)], capture=True).splitlines()
        if ORIGINAL_SONAME in needed:
            run(
                [
                    "patchelf",
                    "--replace-needed",
                    ORIGINAL_SONAME,
                    COMPAT_SONAME,
                    str(candidate),
                ]
            )
            patched += 1
        elif COMPAT_SONAME in needed:
            compatible += 1

    if patched + compatible == 0:
        raise RuntimeError("Slang toolchain contains no libstdc++ consumers to patch")
    compiler_needed = run(
        ["patchelf", "--print-needed", str(root / "bin" / "slangc")],
        capture=True,
    ).splitlines()
    if COMPAT_SONAME not in compiler_needed:
        raise RuntimeError("patched slangc does not use the compatibility library")
    print(
        f"Slang manylinux compatibility ready: {patched} patched, "
        f"{compatible} already compatible",
        file=sys.stderr,
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} INSTALL_ROOT", file=sys.stderr)
        return 2
    try:
        patch_toolchain(Path(sys.argv[1]).resolve())
    except (OSError, RuntimeError) as error:
        print(f"ERROR: failed to patch Slang for manylinux: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
