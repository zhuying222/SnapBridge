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

    PANEL_BG = "#0f1d31"
    PANEL_BORDER = "#1d3b5c"
    WINDOW_BG = "#091523"
    ENTRY_BG = "#13243a"

    def __init__(
        self,
        parent: tk.Misc,
        settings: SenderSettings,
        on_save: Callable[[PairingFormData], None],
        on_pair: Callable[[PairingFormData], None],
        on_clear_pairing: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self.parent = parent
        self.on_save = on_save
        self.on_pair = on_pair
        self.on_clear_pairing = on_clear_pairing
        self.on_close = on_close

        self.window = tk.Toplevel(parent)
        self.window.title("SnapBridge Settings")
        self.window.transient(parent)
        self.window.resizable(False, False)
        self.window.configure(bg=self.WINDOW_BG)
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
        self.status_frame: tk.Frame | None = None
        self.save_button: tk.Button | None = None
        self.pair_button: tk.Button | None = None
        self.clear_button: tk.Button | None = None

        self._build_ui()
        self.refresh(settings)

    def _build_ui(self) -> None:
        shell = tk.Frame(self.window, bg=self.WINDOW_BG, padx=20, pady=20)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=self.WINDOW_BG)
        header.pack(fill="x")

        tk.Label(
            header,
            text="SnapBridge Sender",
            bg=self.WINDOW_BG,
            fg="#f8fafc",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Configure the receiver once, then use the floating orb for left-click capture and right-click actions.",
            bg=self.WINDOW_BG,
            fg="#94a3b8",
            justify="left",
            wraplength=430,
            font=("Segoe UI", 9),
            pady=6,
        ).pack(anchor="w")

        form_card = self._card(shell)
        form_card.pack(fill="x", pady=(14, 12))

        self.device_name_entry = self._create_field(
            form_card,
            label="Device Name",
            hint="Shown on the tablet when it receives a pairing request.",
            textvariable=self.device_name_var,
        )
        self.receiver_url_entry = self._create_field(
            form_card,
            label="Receiver URL",
            hint="Example: http://192.168.1.25:8765",
            textvariable=self.receiver_url_var,
        )
        self.pairing_code_entry = self._create_field(
            form_card,
            label="Tablet Pairing Code",
            hint="Enter the short code currently shown on the Android receiver.",
            textvariable=self.pairing_code_var,
        )

        info_row = tk.Frame(shell, bg=self.WINDOW_BG)
        info_row.pack(fill="x")
        info_row.columnconfigure(0, weight=1)
        info_row.columnconfigure(1, weight=1)

        receiver_card = self._card(info_row)
        receiver_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        verification_card = self._card(info_row)
        verification_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._create_info_block(
            receiver_card,
            title="Current Receiver",
            value_var=self.current_receiver_var,
        )
        self._create_info_block(
            verification_card,
            title="Verification Code",
            value_var=self.verification_code_var,
            code_style=True,
        )

        button_row = tk.Frame(shell, bg=self.WINDOW_BG, pady=14)
        button_row.pack(fill="x")
        for column in range(4):
            button_row.columnconfigure(column, weight=1)

        self.save_button = tk.Button(
            button_row,
            text="Save",
            command=self._handle_save,
            bg="#1d4ed8",
            fg="white",
            activebackground="#1e40af",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=8,
        )
        self.save_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.pair_button = tk.Button(
            button_row,
            text="Pair",
            command=self._handle_pair,
            bg="#0f766e",
            fg="white",
            activebackground="#115e59",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=8,
        )
        self.pair_button.grid(row=0, column=1, sticky="ew", padx=6)

        self.clear_button = tk.Button(
            button_row,
            text="Clear Pairing",
            command=self.on_clear_pairing,
            bg="#9a3412",
            fg="white",
            activebackground="#7c2d12",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=8,
        )
        self.clear_button.grid(row=0, column=2, sticky="ew", padx=6)

        tk.Button(
            button_row,
            text="Close",
            command=self.close,
            bg="#334155",
            fg="white",
            activebackground="#475569",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=8,
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        self.status_frame = tk.Frame(
            shell,
            bg=self.PANEL_BG,
            padx=12,
            pady=10,
            highlightthickness=1,
            highlightbackground=self.STATUS_ACCENTS["info"],
        )
        self.status_frame.pack(fill="x")

        self.status_label = tk.Label(
            self.status_frame,
            textvariable=self.status_var,
            anchor="w",
            justify="left",
            bg=self.PANEL_BG,
            fg=self.STATUS_COLORS["info"],
            wraplength=430,
            font=("Segoe UI", 9),
        )
        self.status_label.pack(fill="x")

    def _card(self, parent: tk.Misc) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=self.PANEL_BG,
            padx=14,
            pady=14,
            highlightthickness=1,
            highlightbackground=self.PANEL_BORDER,
        )

    def _create_field(
        self,
        parent: tk.Misc,
        label: str,
        hint: str,
        textvariable: tk.StringVar,
    ) -> tk.Entry:
        block = tk.Frame(parent, bg=self.PANEL_BG)
        block.pack(fill="x", pady=(0, 12))

        tk.Label(
            block,
            text=label,
            anchor="w",
            bg=self.PANEL_BG,
            fg="#e2e8f0",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")

        tk.Label(
            block,
            text=hint,
            anchor="w",
            justify="left",
            bg=self.PANEL_BG,
            fg="#94a3b8",
            wraplength=400,
            font=("Segoe UI", 8),
            pady=4,
        ).pack(anchor="w")

        entry = tk.Entry(
            block,
            textvariable=textvariable,
            width=48,
            bg=self.ENTRY_BG,
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#32506f",
            highlightcolor="#60a5fa",
        )
        entry.pack(fill="x", ipady=6)
        return entry

    def _create_info_block(
        self,
        parent: tk.Misc,
        title: str,
        value_var: tk.StringVar,
        code_style: bool = False,
    ) -> None:
        tk.Label(
            parent,
            text=title,
            anchor="w",
            bg=self.PANEL_BG,
            fg="#e2e8f0",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")

        value_font = ("Consolas", 14, "bold") if code_style else ("Segoe UI", 9)
        value_color = "#f8fafc" if code_style else "#cbd5e1"

        tk.Label(
            parent,
            textvariable=value_var,
            anchor="w",
            justify="left",
            bg=self.ENTRY_BG,
            fg=value_color,
            padx=10,
            pady=12,
            wraplength=180,
            font=value_font,
        ).pack(fill="x", pady=(6, 0))

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

    def _center_over_parent(self) -> None:
        self.window.update_idletasks()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        window_width = self.window.winfo_reqwidth()
        window_height = self.window.winfo_reqheight()

        x = max(24, parent_x + (parent_width - window_width) // 2)
        y = max(24, parent_y + (parent_height - window_height) // 2)
        self.window.geometry(f"+{x}+{y}")

    def show(self) -> None:
        self.window.deiconify()
        self._center_over_parent()
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
        if self.status_frame is not None:
            self.status_frame.configure(
                highlightbackground=self.STATUS_ACCENTS.get(tone, self.STATUS_ACCENTS["info"])
            )

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
