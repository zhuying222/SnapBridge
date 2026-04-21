from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from typing import Callable

from .models import ReceiverProfile, SenderSettings


@dataclass
class PairingFormData:
    device_name: str
    receiver_url: str
    pairing_code: str


class SettingsDialog:
    STATUS_COLORS = {
        "info": "#cbd5e1",
        "success": "#86efac",
        "busy": "#fde68a",
        "error": "#fca5a5",
    }

    def __init__(
        self,
        parent: tk.Misc,
        settings: SenderSettings,
        on_save: Callable[[PairingFormData], None],
        on_pair: Callable[[PairingFormData], None],
        on_clear_pairing: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self.on_save = on_save
        self.on_pair = on_pair
        self.on_clear_pairing = on_clear_pairing
        self.on_close = on_close

        self.window = tk.Toplevel(parent)
        self.window.title("SnapBridge Settings")
        self.window.transient(parent)
        self.window.resizable(False, False)
        self.window.configure(bg="#0f172a")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.device_name_var = tk.StringVar()
        self.receiver_url_var = tk.StringVar()
        self.pairing_code_var = tk.StringVar()
        self.current_receiver_var = tk.StringVar()
        self.verification_code_var = tk.StringVar(value="Not requested yet")
        self.status_var = tk.StringVar(value="Update the receiver URL, then pair when ready.")

        self.device_name_entry: tk.Entry | None = None
        self.receiver_url_entry: tk.Entry | None = None
        self.pairing_code_entry: tk.Entry | None = None
        self.status_label: tk.Label | None = None
        self.save_button: tk.Button | None = None
        self.pair_button: tk.Button | None = None
        self.clear_button: tk.Button | None = None

        self._build_ui()
        self.refresh(settings)

    def _build_ui(self) -> None:
        frame = tk.Frame(self.window, bg="#0f172a", padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="Device Name",
            anchor="w",
            bg="#0f172a",
            fg="#e2e8f0",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.device_name_entry = tk.Entry(
            frame,
            textvariable=self.device_name_var,
            width=42,
            bg="#111827",
            fg="white",
            insertbackground="white",
            relief="flat",
        )
        self.device_name_entry.grid(row=1, column=0, sticky="ew", pady=(4, 10))

        tk.Label(
            frame,
            text="Receiver URL",
            anchor="w",
            bg="#0f172a",
            fg="#e2e8f0",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="w")
        self.receiver_url_entry = tk.Entry(
            frame,
            textvariable=self.receiver_url_var,
            width=42,
            bg="#111827",
            fg="white",
            insertbackground="white",
            relief="flat",
        )
        self.receiver_url_entry.grid(row=3, column=0, sticky="ew", pady=(4, 10))

        tk.Label(
            frame,
            text="Tablet Pairing Code",
            anchor="w",
            bg="#0f172a",
            fg="#e2e8f0",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=4, column=0, sticky="w")
        self.pairing_code_entry = tk.Entry(
            frame,
            textvariable=self.pairing_code_var,
            width=42,
            bg="#111827",
            fg="white",
            insertbackground="white",
            relief="flat",
        )
        self.pairing_code_entry.grid(row=5, column=0, sticky="ew", pady=(4, 10))

        tk.Label(
            frame,
            text="Current Receiver",
            anchor="w",
            bg="#0f172a",
            fg="#e2e8f0",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=6, column=0, sticky="w")
        tk.Label(
            frame,
            textvariable=self.current_receiver_var,
            anchor="w",
            justify="left",
            bg="#111827",
            fg="#cbd5e1",
            padx=10,
            pady=8,
            wraplength=320,
        ).grid(row=7, column=0, sticky="ew", pady=(4, 10))

        tk.Label(
            frame,
            text="Verification Code",
            anchor="w",
            bg="#0f172a",
            fg="#e2e8f0",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=8, column=0, sticky="w")
        tk.Label(
            frame,
            textvariable=self.verification_code_var,
            anchor="w",
            justify="left",
            bg="#111827",
            fg="#f8fafc",
            padx=10,
            pady=8,
            wraplength=320,
        ).grid(row=9, column=0, sticky="ew", pady=(4, 12))

        button_row = tk.Frame(frame, bg="#0f172a")
        button_row.grid(row=10, column=0, sticky="ew")
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)
        button_row.columnconfigure(2, weight=1)
        button_row.columnconfigure(3, weight=1)

        self.save_button = tk.Button(
            button_row,
            text="Save",
            command=self._handle_save,
            bg="#334155",
            fg="white",
            activebackground="#475569",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=6,
        )
        self.save_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.pair_button = tk.Button(
            button_row,
            text="Pair",
            command=self._handle_pair,
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=6,
        )
        self.pair_button.grid(row=0, column=1, sticky="ew", padx=6)

        self.clear_button = tk.Button(
            button_row,
            text="Forget",
            command=self.on_clear_pairing,
            bg="#7f1d1d",
            fg="white",
            activebackground="#991b1b",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=6,
        )
        self.clear_button.grid(row=0, column=2, sticky="ew", padx=6)

        tk.Button(
            button_row,
            text="Close",
            command=self.close,
            bg="#1f2937",
            fg="white",
            activebackground="#374151",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=6,
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        self.status_label = tk.Label(
            frame,
            textvariable=self.status_var,
            anchor="w",
            justify="left",
            bg="#0f172a",
            fg=self.STATUS_COLORS["info"],
            wraplength=320,
            pady=10,
        )
        self.status_label.grid(row=11, column=0, sticky="ew")

        frame.columnconfigure(0, weight=1)

    def _handle_save(self) -> None:
        self.on_save(self.form_data())

    def _handle_pair(self) -> None:
        self.on_pair(self.form_data())

    def form_data(self) -> PairingFormData:
        return PairingFormData(
            device_name=self.device_name_var.get().strip(),
            receiver_url=self.receiver_url_var.get().strip(),
            pairing_code=self.pairing_code_var.get().strip(),
        )

    def refresh(self, settings: SenderSettings) -> None:
        self.device_name_var.set(settings.device_name)
        self.receiver_url_var.set(settings.receiver.receiver_url if settings.receiver else settings.preferred_receiver_url)
        self.current_receiver_var.set(self._receiver_summary(settings.receiver))
        if settings.receiver is None:
            self.verification_code_var.set("Not requested yet")

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self.window.grab_set()

    def close(self) -> None:
        if not self.window.winfo_exists():
            return
        try:
            current_grab = self.window.grab_current()
            if current_grab == self.window:
                self.window.grab_release()
        except tk.TclError:
            pass
        self.window.destroy()
        self.on_close()

    def set_status(self, message: str, tone: str = "info") -> None:
        self.status_var.set(message)
        if self.status_label is not None:
            self.status_label.configure(fg=self.STATUS_COLORS.get(tone, self.STATUS_COLORS["info"]))

    def set_verification_code(self, code: str) -> None:
        self.verification_code_var.set(code)

    def clear_pairing_code(self) -> None:
        self.pairing_code_var.set("")

    def set_busy(self, is_busy: bool) -> None:
        entry_state = "disabled" if is_busy else "normal"
        button_state = "disabled" if is_busy else "normal"
        if self.device_name_entry is not None:
            self.device_name_entry.configure(state=entry_state)
        if self.receiver_url_entry is not None:
            self.receiver_url_entry.configure(state=entry_state)
        if self.pairing_code_entry is not None:
            self.pairing_code_entry.configure(state=entry_state)
        if self.save_button is not None:
            self.save_button.configure(state=button_state)
        if self.pair_button is not None:
            self.pair_button.configure(state=button_state)
        if self.clear_button is not None:
            self.clear_button.configure(state=button_state)

    def update_receiver(self, receiver: ReceiverProfile | None) -> None:
        self.current_receiver_var.set(self._receiver_summary(receiver))

    @staticmethod
    def _receiver_summary(receiver: ReceiverProfile | None) -> str:
        if receiver is None:
            return "No receiver paired yet."
        return (
            f"{receiver.receiver_name}\n"
            f"URL: {receiver.receiver_url}\n"
            f"Pair ID: {receiver.pair_id}"
        )
