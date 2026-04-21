# Android Receiver

This directory holds the native Android receiver app for Huawei tablets that can run Android applications.

## Implemented

- persistent receiver identity and X25519 key material stored in app preferences
- challenge state that stays stable for its 5-minute TTL instead of changing on every `GET /api/v1/pairing/challenge`
- protocol-aligned pairing flow:
  - `POST /api/v1/pairing/requests` returns `pending`
  - `GET /api/v1/pairing/requests/{request_id}` exposes pending, approved, and rejected status
  - the tablet UI shows the derived 6-digit verification code and lets the user approve or reject
- capture upload path that attempts the full MVP flow in source:
  - derive transfer key from X25519 + HKDF-SHA256
  - decrypt `AES-256-GCM` payloads using canonical JSON metadata as AAD
  - verify the uploaded `sha256`
  - save to `Pictures/SnapBridge` via `MediaStore`
  - return a signed acknowledgement compatible with the current Windows sender
- duplicate `message_id` detection for recent captures
- clearer dashboard and foreground notification state for current receiver status, next action, pending request, and last saved capture

## Still Pending

- actual build and device verification from Android Studio on a machine with Java/Gradle/Android SDK
- end-to-end interop confirmation against the Windows sender on a Huawei tablet
- LAN discovery, TLS transport, and certificate/pin management
- notification permission handling and Huawei-specific background execution tuning
- any boot-start or battery-optimization UX

## Environment Needed To Build

- Java 17+
- Android Studio Hedgehog or newer
- Android SDK Platform 35
- Gradle wrapper

This machine does not currently have Java, Gradle, or the Android SDK installed, so the code here was updated by source inspection and protocol alignment, not by a local Android build.

## Next Steps

1. Open this folder in Android Studio.
2. Let Gradle sync dependencies.
3. Install on the Huawei tablet and verify the foreground service lifecycle.
4. Pair against the Windows sender and confirm the 6-digit verification code matches on both sides.
5. Send a real PNG capture and verify decrypt, save, and ack signature interop.
6. Decide whether pairing approval should remain manual or move to an explicit auto-approve mode for trusted networks.
