from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ReceiverProfile:
    pair_id: str
    receiver_id: str
    receiver_name: str
    receiver_url: str
    receiver_public_key: str
    paired_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SenderSettings:
    device_id: str
    device_name: str
    private_key: str
    floating_button_x: int = 40
    floating_button_y: int = 140
    preferred_receiver_url: str = "http://192.168.1.10:8765"
    receiver: ReceiverProfile | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.receiver is not None:
            data["receiver"] = self.receiver.to_dict()
        return data


@dataclass
class ChallengeInfo:
    receiver_id: str
    receiver_name: str
    receiver_public_key: str
    challenge_id: str
    expires_at: str


@dataclass
class PairingStatus:
    request_id: str
    status: str
    pair_id: str | None = None
    receiver_id: str | None = None
    receiver_name: str | None = None
    receiver_public_key: str | None = None
    reason: str | None = None
