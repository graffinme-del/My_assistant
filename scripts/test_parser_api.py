#!/usr/bin/env python3
"""
Локальный тест Parser-API без поднятого Docker (из корня репозитория):

  cd путь/к/My_assistant
  set PARSER_API_KEY=ваш_ключ
  python scripts/test_parser_api.py A40-97353/2020

Или положите PARSER_API_KEY в .env в корне репо — скрипт перейдёт в корень и подхватит настройки.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    sys.path.insert(0, str(root / "apps" / "api"))

    case_number = sys.argv[1] if len(sys.argv) > 1 else "А40-97353/2020"

    from app.parser_api_client import (
        extract_kad_pdf_urls_from_details,
        parser_details_by_number,
        parser_pdf_download,
    )

    print(f"Номер дела: {case_number}")
    print("Запрос details_by_number...")
    data = parser_details_by_number(case_number)
    print(f"Success: {data.get('Success')}")
    cases = data.get("Cases") or []
    print(f"Cases: {len(cases)}")
    urls = extract_kad_pdf_urls_from_details(data)
    print(f"URL на PDF (kad.arbitr.ru): {len(urls)}")
    if urls:
        print(f"Первый: {urls[0][:100]}...")
        print("Пробуем pdf_download первого файла...")
        try:
            raw = parser_pdf_download(urls[0])
            print(f"Скачано байт: {len(raw)}, это PDF: {raw[:4] == b'%PDF'}")
        except Exception as e:
            print(f"Ошибка pdf_download: {e}")
    else:
        print("В ответе нет прямых ссылок PdfDocument — для этого дела список может быть пуст.")


if __name__ == "__main__":
    main()
