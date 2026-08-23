"""
gui.py — thin OOP wrapper around pyautogui

Each pyautogui function is exposed as a method on the GUI class plus a
module-level convenience instance (``gui``). Lazy imports so the module
loads even when pyautogui is not installed (e.g. on CI / headless).

Usage (Python):
    from gui import GUI
    g = GUI()
    g.moveTo(100, 100, duration=0.5)
    g.click()
    g.typewrite("hello")

Usage from Origin (via py{}):
    py {
        from gui import GUI
        g = GUI()
        g.moveTo(100, 100)
        g.click()
    }

All methods forward *args/**kwargs to the underlying pyautogui call
and re-raise a RuntimeError with a clear message if pyautogui is missing.
"""

from __future__ import annotations
import importlib
import functools
from typing import Any, Tuple, Optional

def _load_pyautogui():
    try:
        return importlib.import_module("pyautogui")
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "pyautogui is not installed. Run `pip install pyautogui pillow opencv-python` "
            "and on Linux `pip install python3-xlib` or `apt install xdotool`."
        ) from e

def _forward(name: str):
    """Create a method that forwards to pyautogui.<name>."""
    def method(self, *args, **kwargs):
        pg = _load_pyautogui()
        fn = getattr(pg, name)
        return fn(*args, **kwargs)
    method.__name__ = name
    method.__doc__ = f"Wrapper for pyautogui.{name}(*args, **kwargs)."
    return method

class GUI:
    """OOP facade over every public pyautogui function."""

    # --- properties / constants -------------------------------------------------
    @property
    def FAILSAFE(self) -> bool:
        return _load_pyautogui().FAILSAFE
    @FAILSAFE.setter
    def FAILSAFE(self, v: bool):
        _load_pyautogui().FAILSAFE = v

    @property
    def PAUSE(self) -> float:
        return _load_pyautogui().PAUSE
    @PAUSE.setter
    def PAUSE(self, v: float):
        _load_pyautogui().PAUSE = v

    @property
    def MINIMUM_DURATION(self) -> float:
        return _load_pyautogui().MINIMUM_DURATION
    @MINIMUM_DURATION.setter
    def MINIMUM_DURATION(self, v: float):
        _load_pyautogui().MINIMUM_DURATION = v

    # --- mouse control ---------------------------------------------------------
    moveTo = _forward("moveTo")
    moveRel = _forward("moveRel")
    move = _forward("move")  # alias for moveRel
    dragTo = _forward("dragTo")
    dragRel = _forward("dragRel")
    drag = _forward("drag")
    click = _forward("click")
    leftClick = _forward("leftClick")
    rightClick = _forward("rightClick")
    middleClick = _forward("middleClick")
    doubleClick = _forward("doubleClick")
    tripleClick = _forward("tripleClick")
    mouseDown = _forward("mouseDown")
    mouseUp = _forward("mouseUp")
    scroll = _forward("scroll")
    hscroll = _forward("hscroll")
    vscroll = _forward("vscroll")
    position = _forward("position")
    size = _forward("size")
    onScreen = _forward("onScreen")

    # --- keyboard control ------------------------------------------------------
    typewrite = _forward("typewrite")
    write = _forward("write")  # alias
    press = _forward("press")
    keyDown = _forward("keyDown")
    keyUp = _forward("keyUp")
    hotkey = _forward("hotkey")
    hold = _forward("hold")  # context manager in newer versions, if present

    # --- screenshot / image ----------------------------------------------------
    screenshot = _forward("screenshot")
    grab = _forward("grab")
    pixel = _forward("pixel")
    pixelMatchesColor = _forward("pixelMatchesColor")
    locateOnScreen = _forward("locateOnScreen")
    locateCenterOnScreen = _forward("locateCenterOnScreen")
    locateAllOnScreen = _forward("locateAllOnScreen")
    locate = _forward("locate")
    locateAll = _forward("locateAll")
    locateAllWindows = _forward("locateAllWindows") if hasattr(importlib, "import_module") else _forward("locateAllWindows")

    # window management (pygetwindow via pyautogui)
    getActiveWindow = _forward("getActiveWindow")
    getActiveWindowTitle = _forward("getActiveWindowTitle")
    getAllWindows = _forward("getAllWindows")
    getWindowsWithTitle = _forward("getWindowsWithTitle")
    getWindow = _forward("getWindow")

    # --- message boxes ---------------------------------------------------------
    alert = _forward("alert")
    confirm = _forward("confirm")
    prompt = _forward("prompt")
    password = _forward("password")
    countDown = _forward("countDown")

    # --- utility ---------------------------------------------------------------
    sleep = _forward("sleep")

    # --- generic fallback ------------------------------------------------------
    def __getattr__(self, name: str):
        """Forward any other pyautogui attribute (e.g. new functions) dynamically."""
        pg = _load_pyautogui()
        if hasattr(pg, name):
            attr = getattr(pg, name)
            if callable(attr):
                @functools.wraps(attr)
                def wrapper(*args, **kwargs):
                    return attr(*args, **kwargs)
                return wrapper
            return attr
        raise AttributeError(f"GUI has no attribute {name!r} and pyautogui has no {name!r}")

    def __repr__(self):
        return f"<GUI wrapping pyautogui>"


# module-level singleton for `import gui; gui.click()` style
gui = GUI()

# re-export common names at module level for `from gui import click` compat
try:
    _pg = importlib.import_module("pyautogui")
    __all__ = [x for x in dir(_pg) if not x.startswith("_")]
except Exception:
    __all__ = ["GUI", "gui"]
