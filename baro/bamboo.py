"""ctypes binding for BARO's bamboo-core engine.

The Vietnamese transformations come from the Rust shared library built from
``fcitx5/rust`` (which vendors bamboo-core, the MIT engine used by Ngó Sen).
This module keeps the FFI details in one place; ``engine.py`` only talks to
:class:`BambooEngine`.
"""

from __future__ import annotations

import ctypes
import os

_LIB_NAME = "libbaro_bamboo.so"


def _candidates():
    override = os.environ.get("BARO_BAMBOO_LIB")
    if override:
        yield override
    here = os.path.dirname(os.path.abspath(__file__))
    # Installed layout: ~/.local/lib/baro/baro/bamboo.py + ../libbaro_bamboo.so
    yield os.path.join(os.path.dirname(here), _LIB_NAME)
    yield os.path.join(here, _LIB_NAME)
    yield os.path.expanduser(os.path.join("~", ".local", "lib", "baro", _LIB_NAME))
    # Source tree after `cargo build --release`.
    yield os.path.join(os.path.dirname(here), "fcitx5", "rust", "target", "release", _LIB_NAME)


def _load():
    errors = []
    for path in _candidates():
        if not path or not os.path.exists(path):
            continue
        try:
            return ctypes.CDLL(path)
        except OSError as error:
            errors.append(f"{path}: {error}")
    detail = "; ".join(errors) if errors else "shared library not found"
    raise OSError(f"BARO bamboo core is unavailable ({detail})")


try:
    _lib = _load()
except OSError as _error:  # pragma: no cover - depends on the machine
    _lib = None
    _load_error = _error
else:
    _load_error = None


def available() -> bool:
    return _lib is not None


def load_error() -> str:
    return "" if _load_error is None else str(_load_error)


if _lib is not None:
    _lib.baro_engine_new.argtypes = [ctypes.c_char_p]
    _lib.baro_engine_new.restype = ctypes.c_size_t
    _lib.baro_engine_free.argtypes = [ctypes.c_size_t]
    _lib.baro_engine_free.restype = None
    _lib.baro_engine_set_options.argtypes = [
        ctypes.c_size_t,
        ctypes.c_bool,
        ctypes.c_bool,
        ctypes.c_bool,
    ]
    _lib.baro_engine_set_options.restype = None
    _lib.baro_engine_set_method.argtypes = [ctypes.c_size_t, ctypes.c_char_p]
    _lib.baro_engine_set_method.restype = None
    _lib.baro_engine_process_key.argtypes = [ctypes.c_size_t, ctypes.c_uint32]
    _lib.baro_engine_process_key.restype = ctypes.c_bool
    _lib.baro_engine_backspace.argtypes = [ctypes.c_size_t]
    _lib.baro_engine_backspace.restype = ctypes.c_bool
    _lib.baro_engine_pull_preedit.argtypes = [ctypes.c_size_t]
    _lib.baro_engine_pull_preedit.restype = ctypes.c_void_p
    _lib.baro_engine_reset.argtypes = [ctypes.c_size_t]
    _lib.baro_engine_reset.restype = None
    _lib.baro_engine_string_free.argtypes = [ctypes.c_void_p]
    _lib.baro_engine_string_free.restype = None


class BambooEngine:
    """Stateful word buffer backed by the Rust bamboo-core engine."""

    def __init__(
        self,
        method: str = "telex",
        modern_style: bool = True,
        free_marking: bool = True,
        auto_restore: bool = True,
    ):
        if _lib is None:
            raise OSError(load_error())
        self._lib = _lib
        self._handle = _lib.baro_engine_new(method.encode("ascii", "ignore"))
        if not self._handle:
            raise OSError("cannot create BARO bamboo engine")
        self._method = "vni" if method.lower() == "vni" else "telex"
        self._modern_style = bool(modern_style)
        self._free_marking = bool(free_marking)
        self._auto_restore = bool(auto_restore)
        self._apply_options()

    def _apply_options(self) -> None:
        self._lib.baro_engine_set_options(
            self._handle,
            self._modern_style,
            self._free_marking,
            self._auto_restore,
        )

    def configure(
        self,
        method: str = "telex",
        modern_style: bool = True,
        free_marking: bool = True,
        auto_restore: bool = True,
    ) -> None:
        method = "vni" if method.lower() == "vni" else "telex"
        if method != self._method:
            self._lib.baro_engine_set_method(self._handle, method.encode("ascii"))
            self._method = method
        modern_style = bool(modern_style)
        free_marking = bool(free_marking)
        auto_restore = bool(auto_restore)
        if (
            modern_style != self._modern_style
            or free_marking != self._free_marking
            or auto_restore != self._auto_restore
        ):
            self._modern_style = modern_style
            self._free_marking = free_marking
            self._auto_restore = auto_restore
            self._apply_options()

    def process_key(self, char: str) -> bool:
        if not char:
            return False
        return bool(self._lib.baro_engine_process_key(self._handle, ord(char[0])))

    def backspace(self) -> bool:
        return bool(self._lib.baro_engine_backspace(self._handle))

    def preedit(self) -> str:
        pointer = self._lib.baro_engine_pull_preedit(self._handle)
        if not pointer:
            return ""
        try:
            return ctypes.string_at(pointer).decode("utf-8", "replace")
        finally:
            self._lib.baro_engine_string_free(pointer)

    def has_text(self) -> bool:
        return bool(self.preedit())

    def reset(self) -> None:
        if self._handle:
            self._lib.baro_engine_reset(self._handle)

    def close(self) -> None:
        if self._handle:
            self._lib.baro_engine_free(self._handle)
            self._handle = 0

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
