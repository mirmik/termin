"""Запуск редактора через ``python -m termin.editor``."""

import argparse
import warnings
import faulthandler

faulthandler.enable()

# Suppress SDL2 informational warning about using pysdl2-dll binaries (Windows)
warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")

from .run_editor import run_editor


def main():
    parser = argparse.ArgumentParser(description="Run termin editor")
    parser.add_argument(
        "--debug-resource",
        type=str,
        default=None,
        help="Open framegraph debugger with this resource (e.g., shadow_maps, color)"
    )
    args = parser.parse_args()
    run_editor(debug_resource=args.debug_resource)


if __name__ == "__main__":
    main()
