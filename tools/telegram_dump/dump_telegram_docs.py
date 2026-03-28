from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import httpx
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def _want_message(msg, include_photos: bool) -> bool:
    if not msg.media:
        return False
    if isinstance(msg.media, MessageMediaDocument):
        return True
    if include_photos and isinstance(msg.media, MessageMediaPhoto):
        return True
    return False


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Скачать документы из Telegram-чата (Telethon) и отправить в My Assistant /documents/ingest."
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Только скачать в папку, не вызывать API",
    )
    args = parser.parse_args()

    api_id = int(env("TG_API_ID"))
    api_hash = env("TG_API_HASH")
    phone = env("TG_PHONE")
    chat = env("TG_CHAT")

    upload = not args.download_only and os.getenv("TG_UPLOAD", "1").strip() != "0"
    assistant_base = os.getenv("ASSISTANT_API_BASE", "").strip().rstrip("/")
    assistant_token = os.getenv("ASSISTANT_API_TOKEN", "").strip()
    if upload:
        if not assistant_base:
            raise RuntimeError("Для загрузки в API задайте ASSISTANT_API_BASE")
        if not assistant_token:
            raise RuntimeError("Для загрузки в API задайте ASSISTANT_API_TOKEN")

    preferred_case_number = os.getenv("PREFERRED_CASE_NUMBER", "").strip()
    include_photos = os.getenv("TG_INCLUDE_PHOTOS", "").strip() in ("1", "true", "yes")
    reverse = os.getenv("TG_FROM_OLDEST", "").strip() in ("1", "true", "yes")
    upload_delay = float(os.getenv("TG_UPLOAD_DELAY_SEC", "0.35"))
    max_mb = os.getenv("TG_MAX_FILE_MB", "").strip()
    max_bytes = int(float(max_mb) * 1024 * 1024) if max_mb else 0

    out_dir = Path(os.getenv("TG_DOWNLOAD_DIR", "./downloads/telegram")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    session_dir = Path(os.getenv("TG_SESSION_DIR", "./sessions")).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = str(session_dir / "telegram_dump")

    limit = int(os.getenv("TG_LIMIT", "0"))
    password_2fa = os.getenv("TG_PASSWORD_2FA", "").strip() or None

    print("Connecting to Telegram...")
    client = TelegramClient(session_path, api_id, api_hash)
    await client.start(phone=phone, password=password_2fa)
    entity = await client.get_entity(chat)

    mode = "документы"
    if include_photos:
        mode += " + фото"
    print(f"Сканирую чат ({mode}, сначала {'старые' if reverse else 'новые'})…")

    downloaded: list[Path] = []
    skipped = 0
    async for msg in client.iter_messages(entity, limit=limit or None, reverse=reverse):
        if not _want_message(msg, include_photos):
            continue
        sz = getattr(msg.file, "size", None) if msg.file else None
        if max_bytes and sz and sz > max_bytes:
            skipped += 1
            print(f"Пропуск (>{max_mb} MB): msg {msg.id}")
            continue
        filename = msg.file.name if msg.file and msg.file.name else f"file_{msg.id}"
        if isinstance(msg.media, MessageMediaPhoto) and not filename.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            filename = f"{Path(filename).stem}_photo_{msg.id}.jpg"
        target = out_dir / filename
        i = 1
        while target.exists():
            target = out_dir / f"{target.stem}_{i}{target.suffix}"
            i += 1
        await msg.download_media(file=str(target))
        downloaded.append(target)
        print(f"Скачано: {target.name}")

    await client.disconnect()
    print(f"Итого скачано: {len(downloaded)}, пропущено крупных: {skipped}")
    if not downloaded:
        return

    if not upload:
        print("TG_UPLOAD=0 или --download-only: отправка в API пропущена.")
        return

    print("Отправка в API помощника…")
    headers = {"X-API-Token": assistant_token}
    async with httpx.AsyncClient(timeout=120) as http:
        ok = 0
        failed = 0
        for p in downloaded:
            form_data: dict[str, str] = {}
            if preferred_case_number:
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
                        print(f"Загружено: {p.name}")
                    else:
                        failed += 1
                        print(f"Ошибка: {p.name} -> {resp.status_code} {resp.text[:200]}")
                except Exception as e:
                    failed += 1
                    print(f"Ошибка: {p.name} -> {e}")
            if upload_delay > 0:
                await asyncio.sleep(upload_delay)
        print(f"Готово. OK={ok}, ошибок={failed}")


if __name__ == "__main__":
    asyncio.run(main())
