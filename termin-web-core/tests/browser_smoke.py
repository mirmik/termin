#!/usr/bin/env python3
import argparse
import functools
import http.server
import os
import shutil
import subprocess
import threading


SUCCESS_MARKER = "TERMIN_WEB_CORE_SMOKE_PASSED"


def find_browser() -> str:
    configured = os.environ.get("TERMIN_WEB_BROWSER")
    if configured:
        if not os.path.isfile(configured):
            raise RuntimeError(f"TERMIN_WEB_BROWSER does not exist: {configured}")
        return configured
    for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("No Chromium browser found; set TERMIN_WEB_BROWSER to its executable")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Termin Web core browser smoke test")
    parser.add_argument("output_directory")
    args = parser.parse_args()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=args.output_directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/smoke.html"
        completed = subprocess.run(
            [
                find_browser(),
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--dump-dom",
                "--virtual-time-budget=10000",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    if completed.returncode != 0 or SUCCESS_MARKER not in completed.stdout:
        raise RuntimeError(
            "Browser smoke failed\n"
            f"exit code: {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    print(SUCCESS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
