"""Запуск редактора через ``python -m termin.editor``."""

import warnings
import faulthandler

faulthandler.enable()

# Suppress SDL2 informational warning about using pysdl2-dll binaries (Windows)
warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")

from .run_editor import run_editor


def main():
    # Args parsed inside init_editor/_parse_editor_args
    run_editor()


if __name__ == "__main__":
    main()
