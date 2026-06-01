from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    auth,
    documents,
    knowledge,
    models,
    review_checkpoints,
    review_tasks,
    review_templates,
    standards,
    tasks,
    utils,
)
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
    app.include_router(review_templates.router, prefix="/api/v1/review-templates", tags=["review-templates"])
    app.include_router(
        review_templates.section_rules_router,
        prefix="/api/v1/template-section-rules",
        tags=["review-templates"],
    )
    app.include_router(standards.router, prefix="/api/v1/standards", tags=["standards"])
    app.include_router(standards.clauses_router, prefix="/api/v1/standard-clauses", tags=["standards"])
    app.include_router(review_checkpoints.router, prefix="/api/v1/review-checkpoints", tags=["review-checkpoints"])
    app.include_router(review_tasks.router, prefix="/api/v1/review-tasks", tags=["review-tasks"])
    app.include_router(
        review_templates.router,
        prefix="/api/review-templates",
        tags=["review-templates"],
        include_in_schema=False,
    )
    app.include_router(
        review_templates.section_rules_router,
        prefix="/api/template-section-rules",
        tags=["review-templates"],
        include_in_schema=False,
    )
    app.include_router(standards.router, prefix="/api/standards", tags=["standards"], include_in_schema=False)
    app.include_router(
        standards.clauses_router,
        prefix="/api/standard-clauses",
        tags=["standards"],
        include_in_schema=False,
    )
    app.include_router(
        review_checkpoints.router,
        prefix="/api/review-checkpoints",
        tags=["review-checkpoints"],
        include_in_schema=False,
    )
    app.include_router(review_tasks.router, prefix="/api/review-tasks", tags=["review-tasks"], include_in_schema=False)

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
