#!/usr/bin/env python3
"""Portable long-running process used by process-smoke timeout tests."""

from __future__ import annotations

import time


print("PROCESS_TIMEOUT_READY", flush=True)
time.sleep(60)
