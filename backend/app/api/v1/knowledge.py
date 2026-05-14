from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel

from app.utils.jwt import CurrentUser, require_permission

router = APIRouter()


class KnowledgeQueryRequest(BaseModel):
    collection: str
    query: str
    top_k: int = 5


class KnowledgeQueryResponse(BaseModel):
    collection: str
    matches: list[dict]


@router.post("/documents")
async def upload_document(
    collection: str,
    file: UploadFile,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
) -> dict[str, str]:
    return {
        "collection": collection,
        "filename": file.filename or "document",
        "status": "queued_for_indexing",
    }


@router.post("/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(
    payload: KnowledgeQueryRequest,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
) -> KnowledgeQueryResponse:
    return KnowledgeQueryResponse(collection=payload.collection, matches=[])
