# Выгрузка документов из Telegram (Telethon)

## Что делает скрипт

1. Подключается к вашему Telegram.
2. Скачивает документы из указанного чата в папку на ПК.
3. Автоматически отправляет каждый файл в API помощника (`/documents/ingest`).

## Шаги запуска

1. Откройте папку:

```bash
cd c:\Users\job\Desktop\My_assistant\tools\telegram_dump
```

2. Создайте `.env` из шаблона и заполните:

```bash
copy .env.example .env
```

Заполните в `.env`:
- `TG_API_ID`
- `TG_API_HASH`
- `TG_PHONE`
- `TG_CHAT` (username/ссылка/ID чата)
- `ASSISTANT_API_BASE`
- `ASSISTANT_API_TOKEN`

3. Установите зависимости:

```bash
pip install -r requirements.txt
```

4. Запустите:

```bash
python dump_telegram_docs.py
```

При первом запуске Telegram попросит код подтверждения.

## Важно

- Если документов очень много, начните с малого лимита:
  - `TG_LIMIT=200`
- Потом увеличивайте или ставьте `0` (все сообщения).
