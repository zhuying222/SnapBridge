from __future__ import annotations

import json
import random
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .crypto import generate_private_key_b64, public_key_from_private_b64


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / ".snapbridge-mock"
STATE_PATH = STATE_DIR / "state.json"
OUTPUT_DIR = BASE_DIR / "received"


@dataclass
class PendingPairRequest:
    request_id: str
    challenge_id: str
    sender_id: str
    sender_name: str
    sender_public_key: str
    status: str
    pair_id: str | None = None
    reason: str | None = None


@dataclass
class MockState:
    receiver_id: str
    receiver_name: str
    private_key: str
    current_pairing_code: str
    challenge_id: str
    challenge_expires_at: str
    paired_senders: dict[str, dict[str, Any]]
    pending_requests: dict[str, dict[str, Any]]

    @property
    def receiver_public_key(self) -> str:
        return public_key_from_private_b64(self.private_key)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_pairing_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _new_challenge() -> tuple[str, str]:
    expires_at = (utc_now() + timedelta(minutes=5)).replace(microsecond=0).isoformat()
    return str(uuid.uuid4()), expires_at


def load_state() -> MockState:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        challenge_id, expires_at = _new_challenge()
        state = MockState(
            receiver_id=str(uuid.uuid4()),
            receiver_name="SnapBridge Mock Receiver",
            private_key=generate_private_key_b64(),
            current_pairing_code=_new_pairing_code(),
            challenge_id=challenge_id,
            challenge_expires_at=expires_at,
            paired_senders={},
            pending_requests={},
        )
        save_state(state)
        return state

    raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state = MockState(**raw)
    expires_at = datetime.fromisoformat(state.challenge_expires_at)
    if expires_at <= utc_now():
        refresh_challenge(state)
        save_state(state)
    return state


def save_state(state: MockState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def refresh_challenge(state: MockState) -> None:
    state.challenge_id, state.challenge_expires_at = _new_challenge()
    state.current_pairing_code = _new_pairing_code()

