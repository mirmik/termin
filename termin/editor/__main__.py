"""Запуск редактора через ``python -m termin.editor``."""

import argparse
import warnings
import faulthandler
import gc

faulthandler.enable()

# GC debug callback to track what's being collected
# def gc_callback(phase, info):
#     if phase == "start":
#         # Count C++ objects by type
#         cpp_types = {}
#         for obj in gc.get_objects():
#             try:
#                 type_name = type(obj).__name__
#                 module = getattr(type(obj), "__module__", None)
#                 if not isinstance(module, str):
#                     module = ""
#                 if "termin._native" in module or "nanobind" in str(type(obj)):
#                     key = f"{module}.{type_name}"
#                     cpp_types[key] = cpp_types.get(key, 0) + 1
#             except Exception:
#                 pass
#         if cpp_types:
#             print(f"[GC {phase}] gen={info.get('generation', '?')} C++ objects: {dict(sorted(cpp_types.items(), key=lambda x: -x[1])[:10])}")

# gc.callbacks.append(gc_callback)

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
