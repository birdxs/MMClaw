import base64
import json
import time
import urllib.request
import urllib.error
import tempfile
from pathlib import Path
import traceback

CONFIG_FILE = Path.home() / ".mmclaw" / "skill-config" / "clawmeets.json"
TMP_DIR     = Path(tempfile.gettempdir()) / "mmclaw-clawmeets"
SERVER      = "https://testapi.clawmeets.com"
INTERVAL    = 2  # seconds between checks


def notify(msg):
    print(f"[NOTIFY] {msg}", flush=True)


def fetch(path, headers):
    req = urllib.request.Request(f"{SERVER}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())


def save_files(message_id, files) -> list[str]:
    """Decode base64 files to system temp dir, return abs paths."""
    msg_dir = TMP_DIR / message_id
    msg_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in files:
        dest = msg_dir / f["filename"]
        dest.write_bytes(base64.b64decode(f["data"]))
        paths.append(str(dest))
    return paths


while True:

    # Pass silently if not configured yet
    if not CONFIG_FILE.exists():
        time.sleep(INTERVAL)
        continue

    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except Exception:
        time.sleep(INTERVAL)
        continue

    address = cfg.get("address", "").strip()
    token   = cfg.get("token", "").strip()

    if not address or not token:
        time.sleep(INTERVAL)
        continue

    try:
        headers = {"X-Address": address, "X-Token": token, "User-Agent": "MMClaw"}
        # Only fetch unread messages.
        # Note: get_message (<id>) on the server automatically marks as read.
        messages = fetch("/messages?unread=1&limit=20", headers)

        if messages:
            for m in messages:
                # Fetch full message content (this also marks it as read on the server)
                full = fetch(f"/messages/{m['id']}", headers)

                lines = [
                    f"New message from '{m['from']}'",
                    f"Subject: {m['subject']}",
                    f"Body:\n---\n{full.get('body', '')}\n---",
                    f"Message ID: {m['id']}"
                ]

                if full.get("files"):
                    paths = save_files(m["id"], full.get("files", []))
                    lines.append("Attached files:")
                    for p in paths:
                        lines.append(f"  {p}")

                notify("\n".join(lines))

    except Exception as e:
        print(f"[clawmeets watcher error] {e}", flush=True)
        # traceback.print_exc() # Keep output clean unless needed

    time.sleep(INTERVAL)
