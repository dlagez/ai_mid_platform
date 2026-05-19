from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, documents, knowledge, models, tasks, utils
from app.services.knowledge_service import KnowledgeService
from app.utils.exceptions import register_exception_handlers
from app.utils.langfuse import configure_langfuse_env, flush_langfuse
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    configure_langfuse_env()
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
    app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
    app.include_router(utils.router, prefix="/api/v1/utils", tags=["utils"])

    register_exception_handlers(app)

    @app.on_event("startup")
    async def initialize_default_openkb() -> None:
        KnowledgeService().initialize_default_kb()

    @app.on_event("shutdown")
    async def shutdown_langfuse() -> None:
        flush_langfuse()

    return app


app = create_app()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
