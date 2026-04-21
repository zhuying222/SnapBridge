# Repo Status

Last updated: 2026-04-21

## Snapshot

| Component | Current Reality | Validation Status | Notes |
| --- | --- | --- | --- |
| `apps/windows-sender` | Runnable Python MVP | Locally exercised | Supports pairing, region capture, encrypted upload, and acknowledgement verification |
| `apps/android-receiver` | Source scaffold only | Not built here | Intended receiver app structure exists, but there is no device-verified flow yet |
| `tools/mock-receiver` | Runnable local test double | Locally exercised | Used for current protocol and transfer validation |

## What Is Actually Working

Verified today:

- the Windows sender can talk to the mock receiver
- the pairing flow works in local development
- image payloads can be encrypted, transferred, acknowledged, and written to disk through the mock receiver

Not verified today:

- Windows sender to Huawei tablet over the real Android receiver
- Android gallery insertion on a real device
- background service stability on Huawei hardware
- discovery, retry, and polished desktop tray behavior

## Current Verification Path

The repo's honest verification path is:

```text
apps/windows-sender -> tools/mock-receiver
```

Contributors should use that path for local validation unless they are explicitly working on Android device testing.

## Main Gaps

- Android receiver still needs a real build environment and device validation.
- The mock receiver proves the protocol, but not Android service lifecycle or `MediaStore` behavior.
- The sender is functional, but still in MVP UX form rather than production desktop packaging.

## Next Milestones

1. Build the Android receiver in Android Studio.
2. Validate pairing and save-to-gallery on the Huawei tablet.
3. Compare real-device behavior against the mock receiver contract and close any gaps.
4. Add receiver discovery and improve sender UX once the device path is stable.
