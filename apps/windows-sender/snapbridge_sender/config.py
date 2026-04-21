from __future__ import annotations

import json
import platform
import uuid
from pathlib import Path

from .crypto import generate_private_key_b64
from .models import ReceiverProfile, SenderSettings


CONFIG_DIR = Path.home() / "AppData" / "Roaming" / "SnapBridge"
CONFIG_PATH = CONFIG_DIR / "sender-config.json"


def load_settings() -> SenderSettings:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        settings = SenderSettings(
            device_id=str(uuid.uuid4()),
            device_name=platform.node() or "Windows PC",
            private_key=generate_private_key_b64(),
        )
        save_settings(settings)
        return settings

    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    receiver = None
    if raw.get("receiver"):
        receiver = ReceiverProfile(**raw["receiver"])

    return SenderSettings(
        device_id=raw["device_id"],
        device_name=raw["device_name"],
        private_key=raw["private_key"],
        floating_button_x=raw.get("floating_button_x", 40),
        floating_button_y=raw.get("floating_button_y", 140),
        preferred_receiver_url=raw.get("preferred_receiver_url", "http://192.168.1.10:8765"),
        receiver=receiver,
    )


def save_settings(settings: SenderSettings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(settings.to_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
