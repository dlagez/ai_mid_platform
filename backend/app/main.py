from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, knowledge, models, tasks
from app.utils.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="AI Mid Platform API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://frontend:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(models.router, prefix="/api/v1/models", tags=["models"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
    app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])

    register_exception_handlers(app)
    return app


app = create_app()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
