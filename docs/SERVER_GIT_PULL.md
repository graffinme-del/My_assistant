# Git pull на сервере без конфликтов с шаблоном env

## В чём была проблема

Файл **`.env.example`** (с точкой) был **в репозитории**. Любая правка на сервере в этом файле давала:

`error: Your local changes to the following files would be overwritten by merge: .env.example`

## Как исправлено навсегда

- В git отслеживается только **`env.example`** (без точки в начале имени).
- Локальный файл **`.env.example`** попадает под правило `.env.*` в `.gitignore` и **не отслеживается** — можете копировать туда что угодно как шпаргалку; **`git pull` это не трогает**.
- Секреты по-прежнему только в **`.env`** и при необходимости **`.env.local`**.

## Что сделать один раз на сервере (если pull ещё с ошибкой)

```bash
cd /opt/my_assistant
# если мешает старая локальная правка в отслеживаемом .env.example:
git checkout -- .env.example 2>/dev/null || true
git pull origin main
```

Если всё ещё конфликт — сохраните копию и сбросьте:

```bash
cp .env.example .env.example.manual.bak 2>/dev/null || true
git checkout -- .env.example
git pull origin main
```

После обновления шаблон — **`env.example`**. Обновить справочник вручную:

```bash
cp env.example .env.example
# или только подсмотреть diff: diff -u .env.manual.bak env.example
```

## Удобная команда

Из корня репозитория:

```bash
bash scripts/git_pull_safe.sh
```

Она делает безопасный pull (см. скрипт).
