"""Запуск редактора через ``python -m termin.editor``."""

import warnings

# Suppress SDL2 informational warning about using pysdl2-dll binaries (Windows)
warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")

from .run_editor import run_editor


def main():
    run_editor()


if __name__ == "__main__":
    main()
