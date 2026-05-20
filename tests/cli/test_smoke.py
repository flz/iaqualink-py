from __future__ import annotations

import importlib


def test_i2d_system_module_importable() -> None:
    importlib.import_module("iaqualink.systems.i2d.system")
