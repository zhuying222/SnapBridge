import unittest
from types import SimpleNamespace
from unittest.mock import patch

from snapbridge_sender.overlay import ScreenCaptureOverlay


class FakeRoot:
    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080


class FakeCanvas:
    def __init__(self, rootx: int = 0, rooty: int = 0) -> None:
        self._rootx = rootx
        self._rooty = rooty
        self.created_rectangle: tuple[tuple[int, ...], dict[str, object]] | None = None
        self.updated_coords: tuple[int, tuple[int, ...]] | None = None

    def canvasx(self, value: int) -> int:
        return value

    def canvasy(self, value: int) -> int:
        return value

    def winfo_rootx(self) -> int:
        return self._rootx

    def winfo_rooty(self) -> int:
        return self._rooty

    def create_rectangle(self, *coords: int, **kwargs: object) -> int:
        self.created_rectangle = (coords, kwargs)
        return 99

    def coords(self, rect_id: int, *coords: int) -> None:
        self.updated_coords = (rect_id, coords)


class FakeOverlay:
    def __init__(self) -> None:
        self.withdrawn = False
        self.destroy_calls = 0

    def withdraw(self) -> None:
        self.withdrawn = True

    def destroy(self) -> None:
        self.destroy_calls += 1


class FakeImage:
    def __init__(self, width: int, height: int, payload: bytes = b"fake-png") -> None:
        self.width = width
        self.height = height
        self.payload = payload

    def save(self, buffer, format: str) -> None:
        buffer.write(self.payload)


class OverlayTests(unittest.TestCase):
    def test_release_uses_canvas_coordinates_for_rectangle_and_screen_coordinates_for_capture(self) -> None:
        overlay = ScreenCaptureOverlay(FakeRoot())
        overlay.canvas = FakeCanvas(rootx=-1280, rooty=120)
        overlay.overlay = FakeOverlay()

        overlay._on_press(SimpleNamespace(x=20, y=30, x_root=9999, y_root=9999))
        self.assertEqual(overlay.canvas.created_rectangle[0], (20, 30, 20, 30))

        overlay._on_drag(SimpleNamespace(x=220, y=180, x_root=1, y_root=2))
        self.assertEqual(overlay.canvas.updated_coords, (99, (20, 30, 220, 180)))

        with patch("snapbridge_sender.overlay.ImageGrab.grab", return_value=FakeImage(200, 150)) as grab:
            overlay._on_release(SimpleNamespace(x=220, y=180, x_root=4000, y_root=5000))

        grab.assert_called_once_with(bbox=(-1260, 150, -1060, 300), all_screens=True)
        self.assertTrue(overlay.overlay.withdrawn)
        self.assertEqual(overlay.overlay.destroy_calls, 1)
        self.assertIsNotNone(overlay.result)
        assert overlay.result is not None
        self.assertEqual(overlay.result.width, 200)
        self.assertEqual(overlay.result.height, 150)
        self.assertEqual(overlay.result.image_bytes, b"fake-png")

    def test_release_cancels_small_selection_without_grab(self) -> None:
        overlay = ScreenCaptureOverlay(FakeRoot())
        overlay.canvas = FakeCanvas(rootx=100, rooty=200)
        overlay.overlay = FakeOverlay()

        overlay._on_press(SimpleNamespace(x=10, y=15, x_root=500, y_root=500))

        with patch("snapbridge_sender.overlay.ImageGrab.grab") as grab:
            overlay._on_release(SimpleNamespace(x=13, y=18, x_root=800, y_root=900))

        grab.assert_not_called()
        self.assertFalse(overlay.overlay.withdrawn)
        self.assertEqual(overlay.overlay.destroy_calls, 1)
        self.assertIsNone(overlay.result)

    def test_format_geometry_preserves_negative_virtual_screen_origin(self) -> None:
        self.assertEqual(
            ScreenCaptureOverlay._format_geometry(left=-1280, top=0, width=3200, height=1800),
            "3200x1800-1280+0",
        )


if __name__ == "__main__":
    unittest.main()
