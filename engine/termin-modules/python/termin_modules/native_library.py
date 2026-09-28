"""Typed C calls into a runtime-owned native module, without another dlopen.

Bindings belong to one generation and become unusable on unload. Dependents
are reimported by ModuleRuntime and bind again after their dependency loads.
An active call prevents native unload, including on free-threaded Python.
"""
from __future__ import annotations

import ctypes


class NativeFunction:
    def __init__(self, symbols, name: str):
        self._symbols = symbols
        self._name = name
        self.argtypes = None
        self.restype = ctypes.c_int

    def __call__(self, *args):
        if self.argtypes is None:
            raise TypeError(f"Set argtypes before calling {self._name}")
        call = self._symbols.acquire(self._name)
        try:
            function = ctypes.PYFUNCTYPE(self.restype, *self.argtypes)(call.address)
            return function(*args)
        finally:
            call.release()


class NativeLibrary:
    def __init__(self, symbols):
        self._symbols = symbols
        self._functions: dict[str, NativeFunction] = {}

    @property
    def valid(self) -> bool:
        return self._symbols.valid

    def __getattr__(self, name: str) -> NativeFunction:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._functions:
            self._symbols.resolve(name)
            self._functions[name] = NativeFunction(self._symbols, name)
        return self._functions[name]
