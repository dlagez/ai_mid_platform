# AI Mid Platform

A full-stack AI mid-platform skeleton with React, Vite, Refine, FastAPI, LiteLLM adapter hooks, Celery, PostgreSQL, Redis, and MinIO.

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
|   |   |   `-- litellm_adapter.py
|   |   |-- db
|   |   |   |-- base.py
|   |   |   |-- models.py
|   |   |   `-- session.py
|   |   |-- main.py
|   |   |-- services
|   |   |   |-- model_service.py
|   |   |   `-- task_service.py
|   |   |-- utils
|   |   |   |-- exceptions.py
|   |   |   |-- jwt.py
|   |   |   `-- logging.py
|   |   `-- workers
|   |       `-- celery_worker.py
|   |-- configs
|   |   |-- adapters.yaml
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

- LiteLLM is called through `backend/app/adapters/litellm_adapter.py`.
- Refine JWT auth is implemented in `frontend/src/auth/authProvider.ts`.
- Backend RBAC is enforced through `require_permission` in `backend/app/utils/jwt.py`.
- Celery task endpoints are in `backend/app/api/v1/tasks.py`.
- RAG endpoints are placeholders in `backend/app/api/v1/knowledge.py` for a future vector store/index adapter.
