"""Compatibility package exposing the historical `Cell2Fire` import path."""

from importlib import import_module
import sys

_pkg = import_module("cell2fire")

# Re-export symbols and share package search path so submodules resolve:
# e.g. `from Cell2Fire.utils.ParseInputs import ParseInputs`.
globals().update(_pkg.__dict__)
__path__ = _pkg.__path__

# Ensure both names reference the same loaded package instance.
sys.modules[__name__] = _pkg
