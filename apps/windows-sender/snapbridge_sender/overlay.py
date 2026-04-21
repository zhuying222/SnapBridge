from __future__ import annotations

import ctypes
import io
import sys
import tkinter as tk
from dataclasses import dataclass

from PIL import ImageGrab


_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79


def _enable_high_dpi_mode() -> None:
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.windll.user32
    except AttributeError:
        return

    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


_enable_high_dpi_mode()


@dataclass
class CaptureResult:
    image_bytes: bytes
    width: int
    height: int


class ScreenCaptureOverlay:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.overlay: tk.Toplevel | None = None
        self.canvas: tk.Canvas | None = None
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self._start_canvas_x = 0
        self._start_canvas_y = 0
        self._end_canvas_x = 0
        self._end_canvas_y = 0
        self.rect_id: int | None = None
        self.result: CaptureResult | None = None

    def capture(self) -> CaptureResult | None:
        self.result = None
        left, top, width, height = self._get_virtual_screen_bounds()
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.28)
        self.overlay.configure(bg="black")
        self.overlay.overrideredirect(True)
        self.overlay.geometry(self._format_geometry(left, top, width, height))
        self.overlay.focus_force()

        self.canvas = tk.Canvas(self.overlay, cursor="crosshair", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Escape>", self._cancel)
        self.overlay.bind("<Escape>", self._cancel)
        self.canvas.focus_set()

        self.root.wait_window(self.overlay)
        return self.result

    def _get_virtual_screen_bounds(self) -> tuple[int, int, int, int]:
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                return (
                    int(user32.GetSystemMetrics(_SM_XVIRTUALSCREEN)),
                    int(user32.GetSystemMetrics(_SM_YVIRTUALSCREEN)),
                    int(user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN)),
                    int(user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN)),
                )
            except AttributeError:
                pass

        return 0, 0, int(self.root.winfo_screenwidth()), int(self.root.winfo_screenheight())

    @staticmethod
    def _format_geometry(left: int, top: int, width: int, height: int) -> str:
        return f"{width}x{height}{left:+d}{top:+d}"

    def _event_to_canvas_coords(self, event: tk.Event) -> tuple[int, int]:
        if self.canvas is None:
            return int(round(event.x)), int(round(event.y))

        return (
            int(round(self.canvas.canvasx(event.x))),
            int(round(self.canvas.canvasy(event.y))),
        )

    def _canvas_to_screen_coords(self, canvas_x: int, canvas_y: int) -> tuple[int, int]:
        if self.canvas is None:
            return canvas_x, canvas_y

        return (
            int(round(self.canvas.winfo_rootx() + canvas_x)),
            int(round(self.canvas.winfo_rooty() + canvas_y)),
        )

    def _on_press(self, event: tk.Event) -> None:
        self._start_canvas_x, self._start_canvas_y = self._event_to_canvas_coords(event)
        self._end_canvas_x = self._start_canvas_x
        self._end_canvas_y = self._start_canvas_y
        self.start_x, self.start_y = self._canvas_to_screen_coords(self._start_canvas_x, self._start_canvas_y)
        self.end_x = self.start_x
        self.end_y = self.start_y
        if self.canvas is not None:
            self.rect_id = self.canvas.create_rectangle(
                self._start_canvas_x,
                self._start_canvas_y,
                self._start_canvas_x,
                self._start_canvas_y,
                outline="#4da3ff",
                width=2,
            )

    def _on_drag(self, event: tk.Event) -> None:
        self._end_canvas_x, self._end_canvas_y = self._event_to_canvas_coords(event)
        self.end_x, self.end_y = self._canvas_to_screen_coords(self._end_canvas_x, self._end_canvas_y)
        if self.canvas is not None and self.rect_id is not None:
            self.canvas.coords(
                self.rect_id,
                self._start_canvas_x,
                self._start_canvas_y,
                self._end_canvas_x,
                self._end_canvas_y,
            )

    def _on_release(self, event: tk.Event) -> None:
        self._end_canvas_x, self._end_canvas_y = self._event_to_canvas_coords(event)
        self.end_x, self.end_y = self._canvas_to_screen_coords(self._end_canvas_x, self._end_canvas_y)
        left = min(self.start_x, self.end_x)
        top = min(self.start_y, self.end_y)
        right = max(self.start_x, self.end_x)
        bottom = max(self.start_y, self.end_y)

        if right - left < 5 or bottom - top < 5:
            self._cancel()
            return

        assert self.overlay is not None
        self.overlay.withdraw()
        try:
            image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
            with io.BytesIO() as buffer:
                image.save(buffer, format="PNG")
                self.result = CaptureResult(
                    image_bytes=buffer.getvalue(),
                    width=image.width,
                    height=image.height,
                )
        finally:
            self.overlay.destroy()

    def _cancel(self, _event: tk.Event | None = None) -> None:
        if self.overlay is not None:
            self.overlay.destroy()
