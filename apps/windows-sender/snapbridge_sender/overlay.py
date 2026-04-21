from __future__ import annotations

import io
import tkinter as tk
from dataclasses import dataclass

from PIL import ImageGrab


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
        self.rect_id: int | None = None
        self.result: CaptureResult | None = None

    def capture(self) -> CaptureResult | None:
        self.result = None
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.28)
        self.overlay.configure(bg="black")
        self.overlay.overrideredirect(True)
        self.overlay.focus_force()

        self.canvas = tk.Canvas(self.overlay, cursor="crosshair", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Escape>", self._cancel)
        self.overlay.bind("<Escape>", self._cancel)

        self.root.wait_window(self.overlay)
        return self.result

    def _on_press(self, event: tk.Event) -> None:
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.end_x = event.x_root
        self.end_y = event.y_root
        if self.canvas is not None:
            self.rect_id = self.canvas.create_rectangle(
                event.x,
                event.y,
                event.x,
                event.y,
                outline="#4da3ff",
                width=2,
            )

    def _on_drag(self, event: tk.Event) -> None:
        self.end_x = event.x_root
        self.end_y = event.y_root
        if self.canvas is not None and self.rect_id is not None:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, self.end_x, self.end_y)

    def _on_release(self, event: tk.Event) -> None:
        self.end_x = event.x_root
        self.end_y = event.y_root
        left = min(self.start_x, self.end_x)
        top = min(self.start_y, self.end_y)
        right = max(self.start_x, self.end_x)
        bottom = max(self.start_y, self.end_y)

        if right - left < 5 or bottom - top < 5:
            self._cancel()
            return

        assert self.overlay is not None
        self.overlay.withdraw()
        image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        with io.BytesIO() as buffer:
            image.save(buffer, format="PNG")
            self.result = CaptureResult(
                image_bytes=buffer.getvalue(),
                width=image.width,
                height=image.height,
            )
        self.overlay.destroy()

    def _cancel(self, _event: tk.Event | None = None) -> None:
        if self.overlay is not None:
            self.overlay.destroy()
