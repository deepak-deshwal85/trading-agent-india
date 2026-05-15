#!/usr/bin/env python3
"""Send a file to a Telegram chat via Bot API (for CI or local use)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def send_document(
    file_path: str | Path,
    *,
    token: str,
    chat_id: str,
    caption: str = "",
    timeout: int = 120,
) -> None:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    url = TELEGRAM_API.format(token=token, method="sendDocument")
    data: dict[str, str] = {"chat_id": chat_id}
    if caption.strip():
        data["caption"] = caption.strip()[:1024]

    with path.open("rb") as fh:
        resp = requests.post(
            url,
            data=data,
            files={"document": (path.name, fh, "application/pdf")},
            timeout=timeout,
        )

    body = resp.json() if resp.content else {}
    if not resp.ok or not body.get("ok"):
        desc = body.get("description", resp.text[:500])
        raise RuntimeError(f"Telegram sendDocument failed ({resp.status_code}): {desc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a file to Telegram")
    parser.add_argument("--file", required=True, help="Path to file to send (e.g. PDF report)")
    parser.add_argument("--caption", default="", help="Optional message caption")
    parser.add_argument(
        "--token",
        default=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        help="Bot token (or TELEGRAM_BOT_TOKEN env)",
    )
    parser.add_argument(
        "--chat-id",
        default=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        help="Chat ID (or TELEGRAM_CHAT_ID env)",
    )
    args = parser.parse_args()

    if not args.token or not args.chat_id:
        print(
            "Telegram skipped: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
            "(GitHub Actions secrets or env vars).",
            file=sys.stderr,
        )
        return 0

    try:
        send_document(
            args.file,
            token=args.token,
            chat_id=args.chat_id,
            caption=args.caption
            or os.getenv("TELEGRAM_CAPTION", "Indian Market Advisory — daily report"),
        )
    except Exception as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return 1

    print(f"Sent to Telegram: {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
