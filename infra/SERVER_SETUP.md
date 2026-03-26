# Hetzner server setup (simple)

## 1) Prepare folder

```bash
sudo mkdir -p /opt/my_assistant
sudo chown -R $USER:$USER /opt/my_assistant
cd /opt/my_assistant
```

## 2) Install Docker + Compose plugin

Use official Docker instructions for your Ubuntu version.

## 3) Create `.env`

Copy `.env.example` to `.env` and fill values.

## 4) First run

```bash
docker compose up -d --build
docker compose ps
```

## 5) Backup cron (daily)

```bash
chmod +x infra/backup.sh
crontab -e
```

Add:

```bash
0 3 * * * cd /opt/my_assistant && set -a && . ./.env && set +a && ./infra/backup.sh >> /opt/my_assistant/backup.log 2>&1
```
