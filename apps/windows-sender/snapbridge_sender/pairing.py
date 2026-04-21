from __future__ import annotations

import time

import requests

from .crypto import compute_sas_code, public_key_from_private_b64
from .models import ChallengeInfo, PairingStatus


class PairingError(RuntimeError):
    pass


class PairingClient:
    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get_challenge(self, receiver_url: str) -> ChallengeInfo:
        response = requests.get(
            f"{receiver_url.rstrip('/')}/api/v1/pairing/challenge",
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            self._raise_pairing_error(response, "Receiver rejected the pairing challenge request")
        payload = response.json()
        return ChallengeInfo(**payload)

    def compute_sas(self, sender_private_key: str, challenge: ChallengeInfo) -> str:
        sender_public_key = public_key_from_private_b64(sender_private_key)
        return compute_sas_code(
            local_public_key_b64=sender_public_key,
            remote_public_key_b64=challenge.receiver_public_key,
            challenge_id=challenge.challenge_id,
        )

    def request_pairing(
        self,
        receiver_url: str,
        sender_id: str,
        sender_name: str,
        sender_private_key: str,
        challenge: ChallengeInfo,
        pairing_code: str,
    ) -> str:
        payload = {
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_public_key": public_key_from_private_b64(sender_private_key),
            "challenge_id": challenge.challenge_id,
            "pairing_code": pairing_code,
        }
        response = requests.post(
            f"{receiver_url.rstrip('/')}/api/v1/pairing/requests",
            json=payload,
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            self._raise_pairing_error(response, "Receiver rejected the pairing request")
        body = response.json()
        request_id = body.get("request_id")
        if not request_id:
            raise PairingError("Receiver did not return a pairing request id.")
        return request_id

    def poll_pairing_status(
        self,
        receiver_url: str,
        request_id: str,
        max_wait_seconds: int = 90,
    ) -> PairingStatus:
        deadline = time.time() + max_wait_seconds
        endpoint = f"{receiver_url.rstrip('/')}/api/v1/pairing/requests/{request_id}"

        while time.time() < deadline:
            response = requests.get(endpoint, timeout=self.timeout_seconds)
            if not response.ok:
                self._raise_pairing_error(response, "Receiver rejected the pairing status check")
            payload = response.json()
            status = PairingStatus(**payload)
            if status.status in {"approved", "rejected"}:
                return status
            time.sleep(1.0)

        raise PairingError("Timed out waiting for pairing approval on the receiver.")

    @staticmethod
    def _raise_pairing_error(response: requests.Response, prefix: str) -> None:
        detail = PairingClient._error_detail(response)
        if detail:
            raise PairingError(f"{prefix} ({response.status_code}): {detail}")
        raise PairingError(f"{prefix} ({response.status_code}).")

    @staticmethod
    def _error_detail(response: requests.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text[:200] if text else None

        if isinstance(payload, dict):
            for key in ("reason", "error", "message", "detail"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None
