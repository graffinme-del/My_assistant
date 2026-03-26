# My_assistant

Web-first MVP for a personal legal process assistant.

## Current project structure

- `apps/api` - FastAPI backend with MVP endpoints
- `apps/web` - web placeholder page
- `apps/worker` - background worker placeholder
- `infra` - deployment and backup scripts
- `packages/shared` - shared utilities/types placeholder
- `.github/workflows` - CI and deploy pipelines

## Implemented MVP backend endpoints

- Health: `GET /health`
- Cases: `POST /cases`, `GET /cases`, `GET /cases/{id}`
- Timeline events: `POST /cases/{id}/events`, `GET /cases/{id}/events`
- Tasks: `POST /cases/{id}/tasks`, `GET /cases/{id}/tasks`
- Documents metadata: `POST /cases/{id}/documents`, `GET /cases/{id}/documents`
- Hearing note parser: `POST /cases/{id}/hearing-note`
- AI summary by case: `GET /cases/{id}/summary`

## Quick start (local)

1. Create env file:
   - PowerShell: `copy .env.example .env`
2. Start stack:
   - `docker compose up --build`
3. Open:
   - Web: `http://localhost:8080`
   - API docs: `http://localhost:8000/docs`
   - API health: `http://localhost:8000/health`

## Hetzner deployment model

- One separate folder on server for this project.
- One separate Docker Compose stack to avoid conflicts with other services.
- Deploy by GitHub Actions over SSH.
- Backup script at `infra/backup.sh`.

## GitHub Actions setup (required secrets)

For deploy workflow, set:

- `HETZNER_HOST`
- `HETZNER_USER`
- `HETZNER_SSH_KEY`
- `DEPLOY_PATH` (example: `/opt/my_assistant`)

## Notes

- If `OPENAI_API_KEY` is empty, summary endpoint still works with local fallback text.
- OCR and semantic indexing are prepared at architecture level and will be expanded in next steps.
