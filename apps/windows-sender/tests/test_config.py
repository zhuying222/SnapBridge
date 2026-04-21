import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from snapbridge_sender.app import SnapBridgeApp
from snapbridge_sender.config import load_settings, save_settings
from snapbridge_sender.models import ReceiverProfile, SenderSettings


class ConfigTests(unittest.TestCase):
    def test_save_and_load_settings_preserve_preferred_receiver_url(self) -> None:
        receiver = ReceiverProfile(
            pair_id="pair-123",
            receiver_id="receiver-123",
            receiver_name="Huawei MatePad",
            receiver_url="http://192.168.1.25:8765",
            receiver_public_key="public-key",
            paired_at="2026-04-21T15:30:00+00:00",
        )
        settings = SenderSettings(
            device_id="device-123",
            device_name="Lenovo-Yoga",
            private_key="private-key",
            floating_button_x=120,
            floating_button_y=240,
            preferred_receiver_url="http://192.168.1.25:8765",
            receiver=receiver,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_path = config_dir / "sender-config.json"
            with patch("snapbridge_sender.config.CONFIG_DIR", config_dir), patch("snapbridge_sender.config.CONFIG_PATH", config_path):
                save_settings(settings)
                loaded = load_settings()

        self.assertEqual(loaded.device_name, settings.device_name)
        self.assertEqual(loaded.preferred_receiver_url, settings.preferred_receiver_url)
        self.assertIsNotNone(loaded.receiver)
        assert loaded.receiver is not None
        self.assertEqual(loaded.receiver.receiver_url, receiver.receiver_url)
        self.assertEqual(loaded.receiver.pair_id, receiver.pair_id)

    def test_normalize_receiver_url_adds_scheme_and_strips_trailing_slash(self) -> None:
        normalized = SnapBridgeApp._normalize_receiver_url("192.168.1.25:8765/")
        self.assertEqual(normalized, "http://192.168.1.25:8765")

    def test_normalize_receiver_url_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            SnapBridgeApp._normalize_receiver_url("http:///missing-host")


if __name__ == "__main__":
    unittest.main()
