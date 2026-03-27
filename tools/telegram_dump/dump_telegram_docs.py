from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
from telethon import TelegramClient


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


async def main() -> None:
    api_id = int(env("TG_API_ID"))
    api_hash = env("TG_API_HASH")
    phone = env("TG_PHONE")
    chat = env("TG_CHAT")  # username/chat link/id

    assistant_base = env("ASSISTANT_API_BASE")  # e.g. http://49.12.235.166:8000
    assistant_token = env("ASSISTANT_API_TOKEN")
    preferred_case_number = os.getenv("PREFERRED_CASE_NUMBER", "").strip()

    out_dir = Path(os.getenv("TG_DOWNLOAD_DIR", "./downloads/telegram")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    session_dir = Path(os.getenv("TG_SESSION_DIR", "./sessions")).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = str(session_dir / "telegram_dump")

    limit = int(os.getenv("TG_LIMIT", "0"))  # 0 means all messages

    print("Connecting to Telegram...")
    client = TelegramClient(session_path, api_id, api_hash)
    await client.start(phone=phone)
    entity = await client.get_entity(chat)

    print("Downloading documents from chat...")
    downloaded: list[Path] = []
    async for msg in client.iter_messages(entity, limit=limit or None):
        if not msg.file:
            continue
        filename = msg.file.name or f"file_{msg.id}"
        target = out_dir / filename
        # Avoid overwrite collisions
        i = 1
        while target.exists():
            target = out_dir / f"{target.stem}_{i}{target.suffix}"
            i += 1
        await msg.download_media(file=str(target))
        downloaded.append(target)
        print(f"Downloaded: {target.name}")

    await client.disconnect()
    print(f"Downloaded total: {len(downloaded)}")
    if not downloaded:
        return

    print("Sending files to assistant API...")
    headers = {"X-API-Token": assistant_token}
    async with httpx.AsyncClient(timeout=120) as http:
        ok = 0
        failed = 0
        for p in downloaded:
            form_data: dict[str, str] = {}
            if preferred_case_number:
                # optional hint for easier routing
                form_data["preferred_case_number"] = preferred_case_number
            with p.open("rb") as f:
                files = {"file": (p.name, f)}
                try:
                    resp = await http.post(
                        f"{assistant_base}/documents/ingest",
                        headers=headers,
                        data=form_data,
                        files=files,
                    )
                    if resp.status_code < 300:
                        ok += 1
                        print(f"Uploaded: {p.name}")
                    else:
                        failed += 1
                        print(f"Failed: {p.name} -> {resp.status_code} {resp.text[:200]}")
                except Exception as e:
                    failed += 1
                    print(f"Failed: {p.name} -> {e}")
        print(f"Upload done. OK={ok}, failed={failed}")


if __name__ == "__main__":
    asyncio.run(main())
