# AI Mid Platform

A full-stack AI mid-platform skeleton with React, Vite, Refine, FastAPI, LiteLLM as a core model module, OpenKB as the RAG adapter, Celery, PostgreSQL, Redis, and MinIO.

## Local Development

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

Demo users:

- `admin` / `admin123`
- `operator` / `operator123`

## File Tree

```text
.
|-- backend
|   |-- Dockerfile
|   |-- alembic
|   |   |-- env.py
|   |   `-- versions
|   |-- alembic.ini
|   |-- app
|   |   |-- api
|   |   |   `-- v1
|   |   |       |-- auth.py
|   |   |       |-- knowledge.py
|   |   |       |-- models.py
|   |   |       `-- tasks.py
|   |   |-- adapters
|   |   |   |-- base_adapter.py
|   |   |   `-- openkb_adapter.py
|   |   |-- core
|   |   |   |-- __init__.py
|   |   |   `-- litellm_client.py
|   |   |-- db
|   |   |   |-- base.py
|   |   |   |-- models.py
|   |   |   `-- session.py
|   |   |-- main.py
|   |   |-- services
|   |   |   |-- knowledge_service.py
|   |   |   |-- model_service.py
|   |   |   `-- task_service.py
|   |   |-- utils
|   |   |   |-- exceptions.py
|   |   |   |-- jwt.py
|   |   |   |-- langfuse.py
|   |   |   `-- logging.py
|   |   `-- workers
|   |       `-- celery_worker.py
|   |-- configs
|   |   |-- adapters.yaml
|   |   |-- litellm.yaml
|   |   `-- settings.py
|   `-- requirements.txt
|-- docker-compose.yml
|-- frontend
|   |-- Dockerfile
|   |-- index.html
|   |-- package.json
|   |-- src
|   |   |-- auth
|   |   |   `-- authProvider.ts
|   |   |-- components
|   |   |   |-- AppHeader.tsx
|   |   |   `-- StatusTag.tsx
|   |   |-- main.tsx
|   |   |-- pages
|   |   |   |-- Dashboard.tsx
|   |   |   |-- ModelCall.tsx
|   |   |   `-- TaskList.tsx
|   |   |-- services
|   |   |   |-- apiClient.ts
|   |   |   |-- modelService.ts
|   |   |   `-- taskService.ts
|   |   |-- styles.css
|   |   |-- types
|   |   |   `-- platform.ts
|   |   `-- vite-env.d.ts
|   |-- tsconfig.json
|   |-- tsconfig.node.json
|   `-- vite.config.ts
`-- README.md
```

## Notes

- LiteLLM is a core backend module at `backend/app/core/litellm_client.py`.
- LiteLLM core configuration is stored in `backend/configs/litellm.yaml`.
- OpenKB is integrated through `backend/app/adapters/openkb_adapter.py` using `openkb==0.1.3` Python APIs.
- OpenKB API endpoints are `POST /api/v1/knowledge/query`, `POST /api/v1/knowledge/chat`, `POST /api/v1/knowledge/add`, `GET /api/v1/knowledge/list`, and `GET /api/v1/knowledge/status`.
- OpenKB KB data is persisted under `storage/openkb` in local backend runs and `openkb_data` in Docker Compose.
- The configured default KB is initialized automatically when the FastAPI backend starts.
- Langfuse Cloud tracing is optional. Fill `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env`; OpenKB query/chat calls are recorded with user, KB, session, model, input, and output metadata. Use `LANGFUSE_BASE_URL=https://us.cloud.langfuse.com` if your Langfuse project is in the US region.
- Refine JWT auth is implemented in `frontend/src/auth/authProvider.ts`.
- Backend RBAC is enforced through `require_permission` in `backend/app/utils/jwt.py`.
- Celery task endpoints are in `backend/app/api/v1/tasks.py`.
- Set `LLM_API_KEY` in `.env` before calling OpenKB query/chat APIs.
