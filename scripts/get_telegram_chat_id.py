#!/usr/bin/env python3
"""Print Telegram chat id(s) from recent messages to your bot (read .env for token)."""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in .env first.", file=sys.stderr)
        return 1

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    resp = requests.get(url, timeout=30)
    data = resp.json()
    if not data.get("ok"):
        print(f"getUpdates failed: {data}", file=sys.stderr)
        return 1

    results = data.get("result") or []
    if not results:
        print(
            "No messages yet.\n"
            "1. Open Telegram and find your bot\n"
            "2. Tap Start or send any message (e.g. hi)\n"
            "3. Run this script again",
            file=sys.stderr,
        )
        return 1

    seen: set[int] = set()
    print("Chat ID(s) found — copy one into .env as TELEGRAM_CHAT_ID:\n")
    for upd in reversed(results):
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None or cid in seen:
            continue
        seen.add(cid)
        title = chat.get("title") or chat.get("username") or chat.get("first_name") or "?"
        ctype = chat.get("type", "?")
        print(f"  TELEGRAM_CHAT_ID={cid}   ({ctype}: {title})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
