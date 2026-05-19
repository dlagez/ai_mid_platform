from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.knowledge_service import KnowledgeService, get_knowledge_service
from app.utils.exceptions import PlatformError
from app.utils.jwt import CurrentUser, require_permission

router = APIRouter()


class KnowledgeQueryRequest(BaseModel):
    kb_name: str | None = None
    question: str
    save: bool = False


class KnowledgeQueryResponse(BaseModel):
    kb_name: str
    question: str
    answer: str
    saved_path: str | None = None


class KnowledgeChatRequest(BaseModel):
    kb_name: str | None = None
    message: str
    session_id: str | None = None


class KnowledgeChatResponse(BaseModel):
    kb_name: str
    session_id: str
    message: str
    answer: str
    turn_count: int


class KnowledgeAddResponse(BaseModel):
    kb_name: str
    added: list[str]
    skipped: list[str]


class KnowledgeListResponse(BaseModel):
    kb_name: str
    documents: list[dict[str, Any]]
    summaries: list[str]
    concepts: list[str]
    reports: list[str]


class KnowledgeRawFilesResponse(BaseModel):
    kb_name: str
    raw_dir: str
    files: list[dict[str, Any]]


class KnowledgeUploadResponse(BaseModel):
    kb_name: str
    filename: str
    path: str
    status: str


class KnowledgeStatusResponse(BaseModel):
    kb_name: str
    kb_dir: str
    model: str
    language: str
    directories: dict[str, int]
    total_indexed: int
    last_compile: str | None = None
    last_lint: str | None = None


class KnowledgeCommandHelpResponse(BaseModel):
    commands: list[dict[str, str]]


class KnowledgeClearRequest(BaseModel):
    kb_name: str | None = None
    previous_session_id: str | None = None


class KnowledgeClearResponse(BaseModel):
    kb_name: str
    previous_session_id: str | None = None
    session_id: str
    message: str


class KnowledgeSaveRequest(BaseModel):
    kb_name: str | None = None
    session_id: str
    name: str | None = None


class KnowledgeSaveResponse(BaseModel):
    kb_name: str
    session_id: str
    saved_path: str
    message: str


class KnowledgeLintRequest(BaseModel):
    kb_name: str | None = None


class KnowledgeLintResponse(BaseModel):
    kb_name: str
    report_path: str | None = None
    message: str


class KnowledgeExitRequest(BaseModel):
    kb_name: str | None = None
    session_id: str | None = None


class KnowledgeExitResponse(BaseModel):
    kb_name: str
    session_id: str | None = None
    closed: bool
    message: str


@router.get("/help", response_model=KnowledgeCommandHelpResponse)
async def help_knowledge(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeCommandHelpResponse:
    return KnowledgeCommandHelpResponse(**service.help())


@router.post("/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(
    payload: KnowledgeQueryRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeQueryResponse:
    data = payload.model_dump()
    data["user_id"] = current_user.username
    data["user_role"] = current_user.role
    return KnowledgeQueryResponse(**await service.query(data))


@router.post("/chat", response_model=KnowledgeChatResponse)
async def chat_knowledge(
    payload: KnowledgeChatRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeChatResponse:
    data = payload.model_dump()
    data["user_id"] = current_user.username
    data["user_role"] = current_user.role
    return KnowledgeChatResponse(**await service.chat(data))


@router.post("/add", response_model=KnowledgeAddResponse)
async def add_knowledge(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    kb_name: Annotated[str | None, Form()] = None,
    path: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> KnowledgeAddResponse:
    if file is not None:
        destination = service.save_upload(
            filename=file.filename or "document",
            content=await file.read(),
            kb_name=kb_name,
        )
        return KnowledgeAddResponse(**await service.add(path=str(destination), kb_name=kb_name))

    if path:
        return KnowledgeAddResponse(**await service.add(path=path, kb_name=kb_name))

    raise PlatformError("Provide either multipart file or form path for OpenKB add", status_code=400)


@router.post("/upload", response_model=KnowledgeUploadResponse)
async def upload_knowledge_file(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    file: Annotated[UploadFile, File()],
    kb_name: Annotated[str | None, Form()] = None,
) -> KnowledgeUploadResponse:
    destination = service.save_upload(
        filename=file.filename or "document",
        content=await file.read(),
        kb_name=kb_name,
    )
    return KnowledgeUploadResponse(
        kb_name=destination.parent.parent.name,
        filename=destination.name,
        path=str(destination),
        status="uploaded",
    )


@router.get("/list", response_model=KnowledgeListResponse)
async def list_knowledge(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    kb_name: str | None = None,
) -> KnowledgeListResponse:
    return KnowledgeListResponse(**service.list(kb_name=kb_name))


@router.get("/files", response_model=KnowledgeRawFilesResponse)
async def list_knowledge_raw_files(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    kb_name: str | None = None,
) -> KnowledgeRawFilesResponse:
    return KnowledgeRawFilesResponse(**service.raw_files(kb_name=kb_name))


@router.get("/files/preview")
async def preview_knowledge_raw_pdf(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    kb_name: str | None = None,
    relative_path: str | None = None,
) -> Response:
    if not relative_path:
        raise PlatformError("relative_path is required.", status_code=400)
    try:
        file_path, content = service.get_raw_pdf(kb_name, relative_path)
    except FileNotFoundError as exc:
        raise PlatformError(str(exc), status_code=404) from exc
    encoded_name = quote(file_path.name)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}"},
    )


@router.get("/status", response_model=KnowledgeStatusResponse)
async def status_knowledge(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    kb_name: str | None = None,
) -> KnowledgeStatusResponse:
    return KnowledgeStatusResponse(**service.status(kb_name=kb_name))


@router.post("/clear", response_model=KnowledgeClearResponse)
async def clear_knowledge_chat(
    payload: KnowledgeClearRequest,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeClearResponse:
    return KnowledgeClearResponse(
        **service.clear_session(
            kb_name=payload.kb_name,
            previous_session_id=payload.previous_session_id,
        )
    )


@router.post("/save", response_model=KnowledgeSaveResponse)
async def save_knowledge_chat(
    payload: KnowledgeSaveRequest,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeSaveResponse:
    return KnowledgeSaveResponse(**service.save_transcript(**payload.model_dump()))


@router.post("/lint", response_model=KnowledgeLintResponse)
async def lint_knowledge(
    payload: KnowledgeLintRequest,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeLintResponse:
    return KnowledgeLintResponse(**await service.lint(kb_name=payload.kb_name))


@router.post("/exit", response_model=KnowledgeExitResponse)
async def exit_knowledge_chat(
    payload: KnowledgeExitRequest,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeExitResponse:
    return KnowledgeExitResponse(**service.exit_session(**payload.model_dump()))
