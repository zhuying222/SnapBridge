# Windows Sender

This is the first runnable SnapBridge component. It provides:

- a floating always-on-top capture button
- a built-in settings window for receiver URL, device name, and pairing
- region capture with Pillow
- one-click resend of the last captured image in the current session
- encrypted upload and acknowledgement verification

## Run

```powershell
cd D:\111\SnapBridge\apps\windows-sender
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_sender.py
```

## Daily Use

- Click `Setup` to enter the receiver URL, confirm your device name, and pair with the tablet using the code shown on the receiver.
- Once paired, click `Capture` to drag a region and send it immediately.
- If a transfer fails or you want to drop the same screenshot into another note, click `Send Last Capture Again`.
- Right-click the floating window for quick access to capture, resend, settings, clear pairing, or quit.

## Current MVP Notes

- The current UI is `tkinter` so it can run without a heavy framework.
- Pairing still follows the documented `challenge -> request -> pending -> approved/rejected` flow and keeps the existing protocol field names unchanged.
- Successful sends now report through the inline status area instead of interrupting every capture with a modal dialog.
- The sender stores its config in `%APPDATA%\SnapBridge\sender-config.json`.
- The config now remembers a preferred receiver URL separately from the active paired receiver record.
- Tray integration, auto-discovery, and retry queue are planned next.
