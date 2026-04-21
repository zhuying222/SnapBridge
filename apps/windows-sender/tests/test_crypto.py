import unittest

from snapbridge_sender.crypto import (
    compute_ack_signature,
    compute_sas_code,
    decrypt_payload,
    derive_transfer_key,
    encrypt_payload,
    generate_private_key_b64,
    public_key_from_private_b64,
    verify_ack_signature,
)


class CryptoTests(unittest.TestCase):
    def test_sas_code_is_symmetric(self) -> None:
        private_a = generate_private_key_b64()
        private_b = generate_private_key_b64()
        public_a = public_key_from_private_b64(private_a)
        public_b = public_key_from_private_b64(private_b)

        sas_ab = compute_sas_code(public_a, public_b, "challenge-123")
        sas_ba = compute_sas_code(public_b, public_a, "challenge-123")

        self.assertEqual(sas_ab, sas_ba)
        self.assertEqual(len(sas_ab), 6)

    def test_encrypt_roundtrip_and_ack_signature(self) -> None:
        private_a = generate_private_key_b64()
        private_b = generate_private_key_b64()
        public_b = public_key_from_private_b64(private_b)
        public_a = public_key_from_private_b64(private_a)

        key_a = derive_transfer_key(private_a, public_b, "pair-1")
        key_b = derive_transfer_key(private_b, public_a, "pair-1")
        self.assertEqual(key_a, key_b)

        metadata = {
            "pair_id": "pair-1",
            "sender_id": "sender-1",
            "receiver_id": "receiver-1",
            "message_id": "message-1",
            "captured_at": "2026-04-21T15:30:00Z",
            "mime_type": "image/png",
            "file_name": "capture.png",
            "width": 100,
            "height": 50,
            "sha256": "placeholder",
        }
        plaintext = b"example-image-bytes"
        nonce, ciphertext = encrypt_payload(key_a, metadata, plaintext)
        decrypted = decrypt_payload(key_b, metadata, nonce, ciphertext)
        self.assertEqual(decrypted, plaintext)

        ack_payload = {
            "message_id": "message-1",
            "status": "saved",
            "received_sha256": "abc123",
            "saved_uri": "content://images/1",
        }
        signature = compute_ack_signature(key_a, ack_payload)
        self.assertTrue(verify_ack_signature(key_b, ack_payload, signature))


if __name__ == "__main__":
    unittest.main()
