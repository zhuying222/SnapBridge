# Mock Receiver

This is a local desktop receiver that implements the current SnapBridge protocol closely enough for development.

Its job is narrow:

- validate the Windows sender end-to-end on a machine without the Android toolchain
- keep the transport and crypto contract executable while the tablet app is still scaffold-only

This is not the shipping receiver. It saves files to disk and auto-approves pairing so contributors can iterate quickly.

## What It Verifies

- pairing challenge retrieval
- pairing request submission and status polling
- encrypted image upload
- acknowledgement signature generation
- filesystem persistence of received images

It does not verify:

- Android service behavior
- Android `MediaStore` insertion
- Huawei-specific background execution behavior

## Run

```powershell
cd D:\111\SnapBridge\tools\mock-receiver
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_mock_receiver.py
```

Optional arguments:

```powershell
python run_mock_receiver.py --host 127.0.0.1 --port 8765
```

The server prints:

- receiver URL
- current pairing code
- output folder for received images

## Quick Verification

With the mock receiver running:

```powershell
python smoke_test_mock_receiver.py
```

That script performs a local pairing flow, uploads a tiny PNG, verifies the acknowledgement signature, and confirms the file was written.

## Reset Mock State

To clear the mock receiver's saved state and received files:

```powershell
python reset_mock_receiver.py
```

Useful flags:

```powershell
python reset_mock_receiver.py --keep-received
python reset_mock_receiver.py --keep-state
```

## Files Written By This Tool

- State directory: `tools/mock-receiver/.snapbridge-mock/`
- Received files: `tools/mock-receiver/received/`
