from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.services.model_service import ModelService, get_model_service
from app.utils.jwt import CurrentUser, get_current_user, require_permission

router = APIRouter()


class ModelCallRequest(BaseModel):
    model: str = Field(default="gpt-4o-mini")
    messages: list[dict[str, str]]
    temperature: float = 0.2
    max_tokens: int | None = 1024


class ModelCallResponse(BaseModel):
    provider: str
    model: str
    output: Any


@router.post("/call", response_model=ModelCallResponse)
async def call_model(
    payload: ModelCallRequest,
    _: Annotated[CurrentUser, Depends(require_permission("models:call"))],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelCallResponse:
    result = await service.call_model(payload.model_dump())
    return ModelCallResponse(**result)
