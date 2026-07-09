"""Запуск редактора через ``python -m termin.editor``."""

import faulthandler

faulthandler.enable()

from .run_editor import run_editor


def main():
    # Args parsed inside init_editor/_parse_editor_args
    run_editor()


if __name__ == "__main__":
    main()
