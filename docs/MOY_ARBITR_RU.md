# «Мой Арбитр»: самостоятельный парсинг через ваш доступ

Ассистент умеет ставить фоновые задачи поиска/загрузки из `https://my.arbitr.ru` без внешнего Parser-API.
Используется Playwright-сессия браузера: пароль Госуслуг и ключи УКЭП в проект не записываются.

## 1. Настройки

В `.env`:

```env
MOY_ARBITR_ENABLED=true
MOY_ARBITR_BASE_URL=https://my.arbitr.ru
MOY_ARBITR_STATE_PATH=/app/moy_arbitr/state.json
MOY_ARBITR_HEADLESS=true
MOY_ARBITR_MAX_CASES=25
MOY_ARBITR_MAX_DOCS_PER_CASE=80
```

`state.json` хранится в docker volume `moy_arbitr_state`.

## 2. Первый вход

Нужно один раз сохранить авторизованную браузерную сессию.

В среде, где можно открыть headed Chromium:

```bash
cd /opt/my_assistant
docker compose -f runtime.compose.yml exec worker python /app/save_moy_arbitr_state.py
```

Откроется `my.arbitr.ru`: войдите через Госуслуги/КЭП, затем вернитесь в терминал и нажмите Enter.
Сессия сохранится в `/app/moy_arbitr/state.json`.

Если сервер без графического окружения, выполните этот скрипт на машине с браузером в таком же worker-образе
и перенесите `state.json` в docker volume/путь `MOY_ARBITR_STATE_PATH` на сервере.

## 3. Команды ассистенту

Примеры:

- `Найди в Мой Арбитр дело А40-12345/2025`
- `Скачай из Мой Арбитр материалы дела А40-12345/2025`
- `Поищи в Мой Арбитр по участнику «Иванов Иван Иванович»`
- `Найди в Мой Арбитр по ИНН 7701234567`
- `Скачай из Мой Арбитр документы по организации «Ромашка»`
- `Поищи в Мой Арбитр новые документы по всем делам`

Команда «по всем делам» берёт только папки, где номер похож на арбитражный (`А40-...`).
Папки без номера, `UNSORTED` и технические `TAG-*` пропускаются.

Поиск создаёт фоновую задачу. Статус можно смотреть теми же фразами, что для КАД:

- `статус загрузки`
- `отчёт по задаче #123`

Если сессия истекла, задача завершится статусом `needs_manual_step` с инструкцией повторить вход.

## 4. Диагностика, если поиск ничего не нашёл

Если задача вернула `results=0`, воркер сохраняет то, что реально увидел Playwright:

- HTML: `/app/moy_arbitr/debug/moy-arbitr-job-...html`
- скриншот: `/app/moy_arbitr/debug/moy-arbitr-job-...png`
- console/network log: `/app/moy_arbitr/debug/moy-arbitr-job-...log`

Скачать с сервера:

```bash
cd /opt/my_assistant
docker compose -f runtime.compose.yml cp worker:/app/moy_arbitr/debug ./moy_arbitr_debug
```

## 5. Снятие Network-трассы для прямого API-клиента

Если headless-браузер на сервере видит пустую страницу, нужно снять реальные запросы сайта на компьютере,
где вы можете войти в «Мой Арбитр» вручную. Скрипт работает на macOS/Linux/Windows, не сохраняет cookies
и вырезает чувствительные заголовки (`cookie`, `authorization`, `set-cookie`).

macOS/Linux:

```bash
mkdir moy_arbitr_trace
cd moy_arbitr_trace
curl -o trace_moy_arbitr_network.py https://raw.githubusercontent.com/graffinme-del/My_assistant/main/apps/worker/trace_moy_arbitr_network.py

python3 -m venv .venv
source .venv/bin/activate
pip install playwright
python -m playwright install chromium

python trace_moy_arbitr_network.py --out moy_arbitr_trace.json
```

Windows PowerShell:

```powershell
mkdir moy_arbitr_trace
cd moy_arbitr_trace
curl.exe -o trace_moy_arbitr_network.py https://raw.githubusercontent.com/graffinme-del/My_assistant/main/apps/worker/trace_moy_arbitr_network.py

py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install playwright
python -m playwright install chromium

python trace_moy_arbitr_network.py --out moy_arbitr_trace.json
```

После запуска:

1. В открывшемся браузере войдите в «Мой Арбитр».
2. Вручную откройте «Мои дела» / выполните поиск по номеру дела.
3. Дождитесь результатов.
4. Вернитесь в терминал и нажмите Enter.
5. Передайте файл `moy_arbitr_trace.json` разработчику/агенту для добавления прямого API-клиента.
