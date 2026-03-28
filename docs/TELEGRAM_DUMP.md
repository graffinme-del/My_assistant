# Выгрузка документов из Telegram (Telethon)

## Что делает скрипт

1. Подключается к вашему Telegram (сессия сохраняется в `TG_SESSION_DIR`).
2. Обходит сообщения в указанном чате и **скачивает файлы-документы** (PDF, DOCX и т.д.).
3. По желанию — **фото** (`TG_INCLUDE_PHOTOS=1`).
4. Отправляет каждый файл в API помощника: `POST /documents/ingest` (тот же пайплайн, что загрузка через веб).

## Шаги запуска

1. Папка:

```bash
cd c:\Users\job\Desktop\My_assistant\tools\telegram_dump
```

2. Скопируйте `.env` и заполните:

```bash
copy .env.example .env
```

Обязательно: `TG_API_ID`, `TG_API_HASH`, `TG_PHONE`, `TG_CHAT`, `ASSISTANT_API_BASE`, `ASSISTANT_API_TOKEN`.

**URL API с вашего ПК:** если с сервера открыт только порт **8080**, используйте прокси веба:

```env
ASSISTANT_API_BASE=http://ВАШ_IP:8080/api
```

Токен — тот же, что в `.env` сервера (`OWNER_TOKEN`), либо `MEMBER_TOKEN`.

3. Зависимости:

```bash
pip install -r requirements.txt
```

4. Запуск:

```bash
python dump_telegram_docs.py
```

Только скачать файлы, без отправки в API:

```bash
python dump_telegram_docs.py --download-only
```

При первом запуске Telegram запросит код из SMS/Telegram. При 2FA задайте `TG_PASSWORD_2FA` в `.env`.

## Переменные (фрагмент)

| Переменная | Смысл |
|------------|--------|
| `TG_LIMIT` | `0` — все сообщения; для пробы `100` |
| `TG_FROM_OLDEST` | `1` — от старых к новым |
| `TG_INCLUDE_PHOTOS` | `1` — ещё и фото как файлы |
| `TG_UPLOAD` | `0` — не вызывать API (как `--download-only`) |
| `TG_UPLOAD_DELAY_SEC` | пауза между запросами к API |
| `PREFERRED_CASE_NUMBER` | подсказка для маршрутизации в ingest |

## Важно

- Не коммитьте `.env` и папку `sessions` — там сессия Telegram.
- Большие чаты: сначала `TG_LIMIT=50`, потом без лимита.
