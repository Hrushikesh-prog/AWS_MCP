#!/usr/bin/env python3
"""Backward-compatible entry-point shim — delegates to main.py."""
import pathlib
import runpy

runpy.run_path(
    str(pathlib.Path(__file__).parent / "main.py"),
    run_name="__main__",
)
