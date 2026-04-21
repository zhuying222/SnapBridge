from __future__ import annotations

import logging
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime, timezone
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
    STATUS_COLORS = {
        "info": "#d1d5db",
        "success": "#86efac",
        "busy": "#fde68a",
        "error": "#fca5a5",
    }

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
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#111827")
        self.root.geometry(f"240x154+{self.settings.floating_button_x}+{self.settings.floating_button_y}")

        self.pairing_client = PairingClient()
        self.transfer_client = TransferClient()

        self.status_var = tk.StringVar(value=self._default_status())
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self.is_busy = False
        self.last_capture: CachedCapture | None = None
        self.settings_dialog: SettingsDialog | None = None

        self.capture_button: tk.Button | None = None
        self.resend_button: tk.Button | None = None
        self.setup_button: tk.Button | None = None
        self.status_label: tk.Label | None = None

        self._build_ui()
        self._refresh_action_state()

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, bg="#111827", bd=1, relief="solid")
        frame.pack(fill="both", expand=True)

        header = tk.Frame(frame, bg="#111827")
        header.pack(fill="x", padx=8, pady=(8, 6))

        title = tk.Label(
            header,
            text="SnapBridge",
            bg="#111827",
            fg="white",
            font=("Segoe UI", 9, "bold"),
        )
        title.pack(side="left")

        self.setup_button = tk.Button(
            header,
            text="Setup",
            command=self.open_settings_dialog,
            bg="#334155",
            fg="white",
            activebackground="#475569",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=4,
        )
        self.setup_button.pack(side="right")

        self.capture_button = tk.Button(
            frame,
            command=self.on_main_action,
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            bd=0,
            padx=16,
            pady=8,
        )
        self.capture_button.pack(fill="x", padx=8, pady=(0, 6))

        self.resend_button = tk.Button(
            frame,
            text="Send Last Capture Again",
            command=self.resend_last_capture,
            bg="#1f2937",
            fg="white",
            activebackground="#374151",
            activeforeground="white",
            bd=0,
            padx=16,
            pady=7,
        )
        self.resend_button.pack(fill="x", padx=8, pady=(0, 6))

        self.status_label = tk.Label(
            frame,
            textvariable=self.status_var,
            bg="#111827",
            fg="#d1d5db",
            font=("Segoe UI", 8),
            justify="left",
            anchor="w",
            wraplength=214,
        )
        self.status_label.pack(fill="x", padx=8, pady=(0, 10))

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Capture Now", command=self.capture_and_send)
        self.menu.add_command(label="Send Last Capture Again", command=self.resend_last_capture)
        self.menu.add_separator()
        self.menu.add_command(label="Open Settings", command=self.open_settings_dialog)
        self.menu.add_command(label="Clear Pairing", command=self.clear_pairing)
        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self.quit)

        for widget in (self.root, frame, header, title, self.capture_button, self.resend_button, self.setup_button, self.status_label):
            widget.bind("<Button-3>", self.show_menu)

        for drag_handle in (frame, header, title, self.status_label):
            self._bind_drag_handle(drag_handle)

    def _bind_drag_handle(self, widget: tk.Misc) -> None:
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._on_drag)
        widget.bind("<ButtonRelease-1>", self._end_drag)

    def _default_status(self) -> str:
        if self.settings.receiver is None:
            return "Not paired. Open Setup to pair a tablet."
        return f"Ready for {self.settings.receiver.receiver_name}."

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_offset_x = event.x_root - self.root.winfo_x()
        self._drag_offset_y = event.y_root - self.root.winfo_y()

    def _on_drag(self, event: tk.Event) -> None:
        x = self.root.winfo_pointerx() - self._drag_offset_x
        y = self.root.winfo_pointery() - self._drag_offset_y
        self.root.geometry(f"+{x}+{y}")

    def _end_drag(self, _event: tk.Event) -> None:
        self.settings.floating_button_x = self.root.winfo_x()
        self.settings.floating_button_y = self.root.winfo_y()
        save_settings(self.settings)

    def show_menu(self, event: tk.Event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def set_status(self, message: str, tone: str = "info") -> None:
        timestamped_message = f"{datetime.now().strftime('%H:%M:%S')}  {message}"
        self.status_var.set(timestamped_message)
        if self.status_label is not None:
            self.status_label.configure(fg=self.STATUS_COLORS.get(tone, self.STATUS_COLORS["info"]))
        self.root.update_idletasks()

    def _refresh_action_state(self) -> None:
        main_text = "Capture" if self.settings.receiver else "Pair Receiver"
        button_state = "disabled" if self.is_busy else "normal"
        can_resend = self.last_capture is not None and self.settings.receiver is not None and not self.is_busy

        if self.capture_button is not None:
            self.capture_button.configure(text=main_text, state=button_state)
        if self.setup_button is not None:
            self.setup_button.configure(state=button_state)
        if self.resend_button is not None:
            self.resend_button.configure(state="normal" if can_resend else "disabled")

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

    def on_main_action(self) -> None:
        if self.is_busy:
            return
        if self.settings.receiver is None:
            self.open_settings_dialog()
        else:
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
                self.root.after(0, lambda: self._on_pairing_error(exc))

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
        messagebox.showerror("Pairing failed", message)

    def clear_pairing(self) -> None:
        if self.settings.receiver is None:
            dialog = self._get_settings_dialog()
            if dialog is not None:
                dialog.set_status("No paired receiver to forget.", tone="info")
            return
        if not messagebox.askyesno("Clear Pairing", "Forget the current receiver?"):
            return
        self.settings.receiver = None
        save_settings(self.settings)
        dialog = self._get_settings_dialog()
        if dialog is not None:
            dialog.update_receiver(None)
            dialog.set_verification_code("Not requested yet")
            dialog.clear_pairing_code()
            dialog.set_status("Current receiver forgotten.", tone="success")
        self.set_status("Pairing cleared. Open Setup to pair again.", tone="info")
        self._refresh_action_state()

    def capture_and_send(self) -> None:
        if self.is_busy:
            return
        if self.settings.receiver is None:
            self.open_settings_dialog()
            return
        overlay = ScreenCaptureOverlay(self.root)
        capture = overlay.capture()
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
                self.root.after(0, lambda: self._on_transfer_error(exc))

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
        self.set_status("Send failed. Use 'Send Last Capture Again' to retry.", tone="error")
        messagebox.showerror("Transfer failed", message)

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
        messagebox.showerror("Settings", message)

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
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = SnapBridgeApp()
    app.run()
