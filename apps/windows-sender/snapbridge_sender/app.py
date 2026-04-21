from __future__ import annotations

import logging
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox
from urllib.parse import urlparse

import requests

from .config import CONFIG_DIR, load_settings, save_settings
from .models import ReceiverProfile, SenderSettings
from .overlay import CaptureResult, ScreenCaptureOverlay
from .pairing import PairingClient, PairingError
from .settings_dialog import PairingFormData, SettingsDialog
from .transfer import TransferClient, TransferError


LOG_PATH = CONFIG_DIR / "sender.log"


@dataclass
class CachedCapture:
    image_bytes: bytes
    width: int
    height: int
    captured_at: str


class SnapBridgeApp:
    WINDOW_SIZE = 112
    DRAG_THRESHOLD = 6
    STATUS_HIDE_DELAY_MS = 3600
    TRANSPARENT_COLOR = "#010203"

    STATUS_COLORS = {
        "info": "#cbd5e1",
        "success": "#bbf7d0",
        "busy": "#fde68a",
        "error": "#fecaca",
    }

    STATUS_ACCENTS = {
        "info": "#3b82f6",
        "success": "#22c55e",
        "busy": "#f59e0b",
        "error": "#ef4444",
    }

    ORB_STYLES = {
        "ready": {
            "shadow": "#09121c",
            "outer": "#11253d",
            "middle": "#1c3b63",
            "inner": "#2563eb",
            "ring": "#dbeafe",
            "label": "#f8fafc",
            "secondary": "#bfdbfe",
            "dot": "#86efac",
        },
        "unpaired": {
            "shadow": "#191309",
            "outer": "#342812",
            "middle": "#664518",
            "inner": "#d97706",
            "ring": "#ffedd5",
            "label": "#fff7ed",
            "secondary": "#fed7aa",
            "dot": "#fbbf24",
        },
        "busy": {
            "shadow": "#1e1209",
            "outer": "#4a2b0b",
            "middle": "#8a4b12",
            "inner": "#ea580c",
            "ring": "#ffedd5",
            "label": "#fff7ed",
            "secondary": "#fed7aa",
            "dot": "#fde68a",
        },
    }

    @staticmethod
    def _asset_path(name: str) -> Path:
        base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        return base_dir / "assets" / name

    def __init__(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=LOG_PATH,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )

        self.settings = load_settings()
        self.root = tk.Tk()
        self.root.title("SnapBridge")
        self.root.overrideredirect(True)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.TRANSPARENT_COLOR)
        self._apply_window_icon()
        self.root.geometry(
            f"{self.WINDOW_SIZE}x{self.WINDOW_SIZE}+"
            f"{self.settings.floating_button_x}+{self.settings.floating_button_y}"
        )
        try:
            self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_COLOR)
        except tk.TclError:
            pass

        self.pairing_client = PairingClient()
        self.transfer_client = TransferClient()

        self.status_var = tk.StringVar(value=self._default_status())
        self._status_tone = "info"
        self._drag_origin_pointer = (0, 0)
        self._drag_origin_window = (0, 0)
        self._is_dragging = False
        self._hovered = False
        self._floating_hidden = False
        self._status_hide_job: str | None = None
        self.is_busy = False
        self.last_capture: CachedCapture | None = None
        self.settings_dialog: SettingsDialog | None = None

        self.orb_canvas: tk.Canvas | None = None
        self.menu: tk.Menu | None = None
        self.status_window: tk.Toplevel | None = None
        self.status_frame: tk.Frame | None = None
        self.status_label: tk.Label | None = None

        self._build_ui()
        self._refresh_action_state()
        self.root.after(180, lambda: self._show_status_bubble(persist_ms=2400))

    def _apply_window_icon(self) -> None:
        icon_path = self._asset_path("snapbridge.ico")
        if not icon_path.exists():
            return
        try:
            self.root.iconbitmap(default=str(icon_path))
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        self.orb_canvas = tk.Canvas(
            self.root,
            width=self.WINDOW_SIZE,
            height=self.WINDOW_SIZE,
            bg=self.TRANSPARENT_COLOR,
            bd=0,
            highlightthickness=0,
            relief="flat",
            cursor="hand2",
        )
        self.orb_canvas.pack(fill="both", expand=True)

        self.orb_canvas.bind("<ButtonPress-1>", self._on_left_press)
        self.orb_canvas.bind("<B1-Motion>", self._on_left_drag)
        self.orb_canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.orb_canvas.bind("<Button-3>", self.show_menu)
        self.orb_canvas.bind("<Enter>", self._on_hover_enter)
        self.orb_canvas.bind("<Leave>", self._on_hover_leave)

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Capture and Send", command=self.capture_and_send)
        self.menu.add_command(label="Resend Last Capture", command=self.resend_last_capture)
        self.menu.add_separator()
        self.menu.add_command(label="Settings", command=self.open_settings_dialog)
        self.menu.add_command(label="Clear Pairing", command=self.clear_pairing)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.quit)

        self.status_window = tk.Toplevel(self.root)
        self.status_window.overrideredirect(True)
        self.status_window.attributes("-topmost", True)
        self.status_window.configure(bg="#08111d")
        self.status_window.withdraw()

        self.status_frame = tk.Frame(
            self.status_window,
            bg="#08111d",
            padx=12,
            pady=9,
            highlightthickness=1,
            highlightbackground=self.STATUS_ACCENTS["info"],
        )
        self.status_frame.pack(fill="both", expand=True)

        self.status_label = tk.Label(
            self.status_frame,
            textvariable=self.status_var,
            bg="#08111d",
            fg=self.STATUS_COLORS["info"],
            justify="left",
            anchor="w",
            wraplength=240,
            font=("Segoe UI", 9),
        )
        self.status_label.pack(fill="both", expand=True)

        self.root.bind("<Configure>", lambda _event: self._position_status_bubble())

    def _default_status(self) -> str:
        if self.settings.receiver is None:
            return "Not paired. Left-click to open settings, or right-click for more actions."
        return (
            f"Ready for {self.settings.receiver.receiver_name}. "
            "Left-click captures and sends immediately."
        )

    def _current_orb_state(self) -> str:
        if self.is_busy:
            return "busy"
        if self.settings.receiver is None:
            return "unpaired"
        return "ready"

    def _orb_copy(self) -> tuple[str, str]:
        if self.is_busy:
            return ("Wait", "sending")
        if self.settings.receiver is None:
            return ("Pair", "setup")
        return ("Snap", "send")

    def _render_orb(self) -> None:
        if self.orb_canvas is None:
            return

        style = self.ORB_STYLES[self._current_orb_state()]
        headline, subline = self._orb_copy()
        canvas = self.orb_canvas
        canvas.delete("all")

        hover_outline = style["ring"] if self._hovered else style["secondary"]
        size = self.WINDOW_SIZE
        center = size // 2

        canvas.create_oval(18, 20, 102, 104, fill=style["shadow"], outline="")
        canvas.create_oval(10, 10, 102, 102, fill=style["outer"], outline="")
        canvas.create_oval(15, 15, 97, 97, fill=style["middle"], outline="")
        canvas.create_oval(21, 21, 91, 91, fill=style["inner"], outline="")
        canvas.create_oval(18, 18, 96, 96, outline=hover_outline, width=2)
        canvas.create_arc(26, 18, 84, 52, start=12, extent=124, style="arc", outline=style["ring"], width=2)

        canvas.create_text(
            center,
            50,
            text=headline,
            fill=style["label"],
            font=("Segoe UI", 16, "bold"),
        )
        canvas.create_text(
            center,
            70,
            text=subline,
            fill=style["secondary"],
            font=("Segoe UI", 8, "bold"),
        )
        canvas.create_oval(80, 21, 90, 31, fill=style["dot"], outline="")

        if self.last_capture is not None and self.settings.receiver is not None:
            canvas.create_oval(79, 77, 92, 90, fill="#0f766e", outline="")
            canvas.create_text(85, 84, text="R", fill="white", font=("Segoe UI", 7, "bold"))

    def _update_menu_state(self) -> None:
        if self.menu is None:
            return
        can_resend = self.last_capture is not None and self.settings.receiver is not None and not self.is_busy
        action_state = "disabled" if self.is_busy else "normal"
        clear_state = "normal" if self.settings.receiver is not None and not self.is_busy else "disabled"

        self.menu.entryconfigure(0, state=action_state)
        self.menu.entryconfigure(1, state="normal" if can_resend else "disabled")
        self.menu.entryconfigure(3, state=action_state)
        self.menu.entryconfigure(4, state=clear_state)

    def _refresh_action_state(self) -> None:
        self._render_orb()
        self._update_menu_state()

    def _set_busy(self, is_busy: bool) -> None:
        self.is_busy = is_busy
        self._refresh_action_state()
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.set_busy(is_busy)

    def _get_settings_dialog(self) -> SettingsDialog | None:
        if self.settings_dialog is None:
            return None
        if not self.settings_dialog.window.winfo_exists():
            self.settings_dialog = None
            return None
        return self.settings_dialog

    def _on_left_press(self, event: tk.Event) -> None:
        self._cancel_status_hide()
        self._drag_origin_pointer = (event.x_root, event.y_root)
        self._drag_origin_window = (self.root.winfo_x(), self.root.winfo_y())
        self._is_dragging = False

    def _on_left_drag(self, event: tk.Event) -> None:
        delta_x = event.x_root - self._drag_origin_pointer[0]
        delta_y = event.y_root - self._drag_origin_pointer[1]
        if not self._is_dragging and (
            abs(delta_x) >= self.DRAG_THRESHOLD or abs(delta_y) >= self.DRAG_THRESHOLD
        ):
            self._is_dragging = True
        if not self._is_dragging:
            return

        x = self._drag_origin_window[0] + delta_x
        y = self._drag_origin_window[1] + delta_y
        self.root.geometry(f"+{x}+{y}")
        self._position_status_bubble()

    def _on_left_release(self, _event: tk.Event) -> None:
        if self._is_dragging:
            self.settings.floating_button_x = self.root.winfo_x()
            self.settings.floating_button_y = self.root.winfo_y()
            save_settings(self.settings)
            if not self.is_busy:
                self._schedule_status_hide(700)
            return
        self.on_main_action()

    def _on_hover_enter(self, _event: tk.Event) -> None:
        self._hovered = True
        self._refresh_action_state()
        self._show_status_bubble()

    def _on_hover_leave(self, _event: tk.Event) -> None:
        self._hovered = False
        self._refresh_action_state()
        if not self.is_busy:
            self._schedule_status_hide(650)

    def _position_status_bubble(self) -> None:
        if self.status_window is None or not self.status_window.winfo_exists():
            return
        if not self.status_window.winfo_viewable():
            return

        self.status_window.update_idletasks()
        bubble_width = self.status_window.winfo_reqwidth()
        bubble_height = self.status_window.winfo_reqheight()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = self.root.winfo_x() + self.WINDOW_SIZE + 12
        if x + bubble_width > screen_width - 12:
            x = max(12, self.root.winfo_x() - bubble_width - 12)

        y = self.root.winfo_y() + (self.WINDOW_SIZE - bubble_height) // 2
        y = max(12, min(screen_height - bubble_height - 12, y))

        self.status_window.geometry(f"+{x}+{y}")

    def _cancel_status_hide(self) -> None:
        if self._status_hide_job is not None:
            self.root.after_cancel(self._status_hide_job)
            self._status_hide_job = None

    def _schedule_status_hide(self, delay_ms: int) -> None:
        if self.status_window is None or not self.status_window.winfo_exists():
            return
        self._cancel_status_hide()
        self._status_hide_job = self.root.after(delay_ms, self._hide_status_bubble)

    def _show_status_bubble(self, persist_ms: int | None = None) -> None:
        if self._floating_hidden:
            return
        if self.status_window is None or not self.status_window.winfo_exists():
            return
        self._cancel_status_hide()
        self.status_window.deiconify()
        self.status_window.lift()
        self._position_status_bubble()
        if persist_ms is not None:
            self._status_hide_job = self.root.after(persist_ms, self._hide_status_bubble)

    def _hide_status_bubble(self) -> None:
        self._status_hide_job = None
        if self.status_window is not None and self.status_window.winfo_exists():
            self.status_window.withdraw()

    def show_menu(self, event: tk.Event) -> None:
        if self.menu is None:
            return
        self._cancel_status_hide()
        self._refresh_action_state()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
        if not self.is_busy and not self._hovered:
            self._schedule_status_hide(900)

    def set_status(self, message: str, tone: str = "info") -> None:
        self._status_tone = tone
        timestamped_message = f"{datetime.now().strftime('%H:%M:%S')}  {message}"
        self.status_var.set(timestamped_message)
        if self.status_label is not None:
            self.status_label.configure(fg=self.STATUS_COLORS.get(tone, self.STATUS_COLORS["info"]))
        if self.status_frame is not None:
            self.status_frame.configure(
                highlightbackground=self.STATUS_ACCENTS.get(tone, self.STATUS_ACCENTS["info"])
            )

        persist_ms = None if tone == "busy" else self.STATUS_HIDE_DELAY_MS
        self._show_status_bubble(persist_ms=persist_ms)
        self.root.update_idletasks()

    def on_main_action(self) -> None:
        if self.is_busy:
            return
        if self.settings.receiver is None:
            self.open_settings_dialog()
            return
        self.capture_and_send()

    def open_settings_dialog(self) -> None:
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.show()
            return

        self.settings_dialog = SettingsDialog(
            parent=self.root,
            settings=self.settings,
            on_save=self.save_settings_from_form,
            on_pair=self.start_pairing_flow,
            on_clear_pairing=self.clear_pairing,
            on_close=self._on_settings_dialog_closed,
        )
        self.settings_dialog.show()

    def _on_settings_dialog_closed(self) -> None:
        self.settings_dialog = None

    def save_settings_from_form(self, form_data: PairingFormData) -> None:
        try:
            device_name, receiver_url = self._validate_settings_form(form_data, require_pairing_code=False)
        except ValueError as exc:
            self._report_validation_error(str(exc))
            return

        self.settings.device_name = device_name
        self.settings.preferred_receiver_url = receiver_url
        if self.settings.receiver is not None:
            self.settings.receiver.receiver_url = receiver_url
        save_settings(self.settings)

        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.update_receiver(self.settings.receiver)
            dialog.set_status("Saved local sender settings.", tone="success")
        self.set_status("Saved sender settings.", tone="success")
        self._refresh_action_state()

    def start_pairing_flow(self, form_data: PairingFormData | None = None) -> None:
        if self.is_busy:
            return
        if form_data is None:
            self.open_settings_dialog()
            return

        try:
            device_name, receiver_url = self._validate_settings_form(form_data, require_pairing_code=True)
        except ValueError as exc:
            self._report_validation_error(str(exc))
            return

        self.settings.device_name = device_name
        self.settings.preferred_receiver_url = receiver_url
        save_settings(self.settings)

        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.set_verification_code("Fetching challenge...")
            dialog.set_status("Fetching pairing challenge from the receiver...", tone="busy")

        self._set_busy(True)
        self.set_status("Fetching pairing challenge...", tone="busy")

        pairing_code = form_data.pairing_code.strip()

        def worker() -> None:
            try:
                challenge = self.pairing_client.get_challenge(receiver_url)
                sas_code = self.pairing_client.compute_sas(self.settings.private_key, challenge)
                self.root.after(0, lambda: self._on_pairing_challenge(sas_code, challenge.receiver_name))
                request_id = self.pairing_client.request_pairing(
                    receiver_url=receiver_url,
                    sender_id=self.settings.device_id,
                    sender_name=self.settings.device_name,
                    sender_private_key=self.settings.private_key,
                    challenge=challenge,
                    pairing_code=pairing_code,
                )
                self.root.after(0, self._on_pairing_request_pending)
                status = self.pairing_client.poll_pairing_status(receiver_url, request_id)
                if status.status != "approved":
                    raise PairingError(status.reason or "Pairing was rejected by the receiver.")
                receiver = ReceiverProfile(
                    pair_id=status.pair_id or "",
                    receiver_id=status.receiver_id or challenge.receiver_id,
                    receiver_name=status.receiver_name or challenge.receiver_name,
                    receiver_url=receiver_url.rstrip("/"),
                    receiver_public_key=status.receiver_public_key or challenge.receiver_public_key,
                    paired_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )
                self.settings.receiver = receiver
                self.settings.preferred_receiver_url = receiver.receiver_url
                save_settings(self.settings)
                self.root.after(0, lambda: self._on_pairing_success(receiver))
            except Exception as exc:
                logging.exception("Pairing failed")
                self.root.after(0, lambda exc=exc: self._on_pairing_error(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_pairing_challenge(self, sas_code: str, receiver_name: str) -> None:
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.set_verification_code(sas_code)
            dialog.set_status(
                f"Compare code {sas_code} on both devices, then approve the request on {receiver_name}.",
                tone="busy",
            )
        self.set_status(f"Verify code {sas_code} on both devices.", tone="busy")

    def _on_pairing_request_pending(self) -> None:
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.set_status("Pairing request sent. Waiting for tablet approval...", tone="busy")
        self.set_status("Waiting for tablet approval...", tone="busy")

    def _on_pairing_success(self, receiver: ReceiverProfile) -> None:
        self._set_busy(False)
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.update_receiver(receiver)
            dialog.clear_pairing_code()
            dialog.set_verification_code("Verified")
            dialog.set_status(f"Paired with {receiver.receiver_name}.", tone="success")
        self.set_status(f"Paired with {receiver.receiver_name}. Ready to capture.", tone="success")

    def _on_pairing_error(self, exc: Exception) -> None:
        self._set_busy(False)
        message = self._format_exception(exc)
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.set_status(message, tone="error")
        self.set_status("Pairing failed.", tone="error")
        messagebox.showerror("Pairing failed", message, parent=self.root)

    def clear_pairing(self) -> None:
        if self.settings.receiver is None:
            dialog = self._get_settings_dialog()
            if dialog is not None:
                dialog.set_status("No paired receiver to forget.", tone="info")
            self.set_status("No paired receiver to forget.", tone="info")
            return
        if not messagebox.askyesno("Clear Pairing", "Forget the current receiver?", parent=self.root):
            return
        self.settings.receiver = None
        save_settings(self.settings)
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.update_receiver(None)
            dialog.set_verification_code("Not requested yet")
            dialog.clear_pairing_code()
            dialog.set_status("Current receiver forgotten.", tone="success")
        self.set_status("Pairing cleared. Left-click to pair again.", tone="info")
        self._refresh_action_state()

    def _hide_for_capture(self) -> None:
        self._floating_hidden = True
        self._hide_status_bubble()
        try:
            self.root.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self.root.update_idletasks()

    def _restore_after_capture(self) -> None:
        self._floating_hidden = False
        try:
            self.root.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        self.root.lift()
        self.root.attributes("-topmost", True)
        if self._hovered or self.is_busy:
            self._show_status_bubble()

    def capture_and_send(self) -> None:
        if self.is_busy:
            return
        if self.settings.receiver is None:
            self.open_settings_dialog()
            return

        self._hide_for_capture()
        try:
            overlay = ScreenCaptureOverlay(self.root)
            capture = overlay.capture()
        finally:
            self._restore_after_capture()

        if capture is None:
            self.set_status(self._default_status(), tone="info")
            return
        self.last_capture = self._cache_capture(capture)
        self._refresh_action_state()
        self._send_cached_capture(self.last_capture, is_retry=False)

    def resend_last_capture(self) -> None:
        if self.is_busy:
            return
        if self.last_capture is None:
            self.set_status("No capture available to resend yet.", tone="info")
            return
        if self.settings.receiver is None:
            self.open_settings_dialog()
            return
        self._send_cached_capture(self.last_capture, is_retry=True)

    def _cache_capture(self, capture: CaptureResult) -> CachedCapture:
        return CachedCapture(
            image_bytes=capture.image_bytes,
            width=capture.width,
            height=capture.height,
            captured_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )

    def _send_cached_capture(self, capture: CachedCapture, is_retry: bool) -> None:
        action_label = "Resending last capture..." if is_retry else "Sending capture..."
        self._set_busy(True)
        self.set_status(action_label, tone="busy")

        def worker() -> None:
            try:
                ack = self.transfer_client.send_capture(
                    settings=self.settings,
                    image_bytes=capture.image_bytes,
                    width=capture.width,
                    height=capture.height,
                )
                self.root.after(0, lambda: self._on_transfer_success(ack, capture, is_retry))
            except Exception as exc:
                logging.exception("Transfer failed")
                self.root.after(0, lambda exc=exc: self._on_transfer_error(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_transfer_success(self, ack: dict[str, str], capture: CachedCapture, is_retry: bool) -> None:
        self._set_busy(False)
        receiver_name = self.settings.receiver.receiver_name if self.settings.receiver is not None else "tablet"
        action = "Resent" if is_retry else "Sent"
        logging.info(
            "%s capture %sx%s to %s at %s",
            action,
            capture.width,
            capture.height,
            receiver_name,
            ack.get("saved_uri", "gallery"),
        )
        self.set_status(f"{action} {capture.width}x{capture.height} image to {receiver_name}.", tone="success")

    def _on_transfer_error(self, exc: Exception) -> None:
        self._set_busy(False)
        message = self._format_exception(exc)
        self.set_status("Send failed. Use 'Resend Last Capture' to retry.", tone="error")
        messagebox.showerror("Transfer failed", message, parent=self.root)

    def _validate_settings_form(
        self,
        form_data: PairingFormData,
        require_pairing_code: bool,
    ) -> tuple[str, str]:
        device_name = form_data.device_name.strip()
        if not device_name:
            raise ValueError("Device name is required.")

        receiver_url = self._normalize_receiver_url(form_data.receiver_url)
        if require_pairing_code and not form_data.pairing_code.strip():
            raise ValueError("Enter the pairing code shown on the tablet.")

        return device_name, receiver_url

    def _report_validation_error(self, message: str) -> None:
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.set_status(message, tone="error")
        self.set_status(message, tone="error")
        messagebox.showerror("Settings", message, parent=self.root)

    @staticmethod
    def _normalize_receiver_url(receiver_url: str) -> str:
        value = receiver_url.strip()
        if not value:
            raise ValueError("Receiver URL is required.")
        if "://" not in value:
            value = f"http://{value}"

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Receiver URL must look like http://host:port or https://host:port.")
        return value.rstrip("/")

    @staticmethod
    def _format_exception(exc: Exception) -> str:
        if isinstance(exc, (TransferError, PairingError)):
            return str(exc)
        if isinstance(exc, requests.Timeout):
            return "The receiver did not respond before the timeout."
        if isinstance(exc, requests.RequestException):
            return f"Network error while contacting the receiver: {exc}"
        return f"Unexpected error: {exc}"

    def quit(self) -> None:
        save_settings(self.settings)
        self._cancel_status_hide()
        if self.status_window is not None and self.status_window.winfo_exists():
            self.status_window.destroy()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = SnapBridgeApp()
    app.run()
