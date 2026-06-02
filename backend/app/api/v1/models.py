from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.chapter_profile.service import PROFILE_EXTRACTION_PROMPT
from app.db.models import ModelPromptTestRecord
from app.db.session import get_db
from app.review_checkpoints.service import CHECKPOINT_PROMPT
from app.services.model_service import ModelService, get_model_service
from app.utils.jwt import CurrentUser, require_permission
from app.utils.langfuse import langfuse_observation, update_langfuse_observation

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


class PromptTestRequest(BaseModel):
    prompt_type: Literal["profile_extraction", "checkpoint"]
    text: str = Field(min_length=1)
    model: str | None = None
    temperature: float = 0.1
    max_tokens: int | None = None
    title: str | None = None
    standard_name: str | None = None
    clause_no: str | None = None
    clause_title: str | None = None


class PromptTestResponse(BaseModel):
    record_id: int
    prompt_type: Literal["profile_extraction", "checkpoint"]
    prompt: str
    provider: str
    model: str
    output: Any


class PromptTestRecordRead(BaseModel):
    id: int
    prompt_type: str
    model: str
    provider: str | None
    temperature: float
    max_tokens: int | None
    input_text: str
    rendered_prompt: str
    output: Any
    status: str
    error_message: str | None
    created_by: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PromptTestRecordList(BaseModel):
    items: list[PromptTestRecordRead]
    total: int
    page: int
    page_size: int


@router.post("/call", response_model=ModelCallResponse)
async def call_model(
    payload: ModelCallRequest,
    _: Annotated[CurrentUser, Depends(require_permission("models:call"))],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelCallResponse:
    result = await service.call_model(payload.model_dump())
    return ModelCallResponse(**result)


@router.post("/prompt-test", response_model=PromptTestResponse)
async def test_prompt(
    payload: PromptTestRequest,
    user: Annotated[CurrentUser, Depends(require_permission("models:call"))],
    service: Annotated[ModelService, Depends(get_model_service)],
    db: Annotated[Session, Depends(get_db)],
) -> PromptTestResponse:
    text = payload.text.strip()
    if payload.prompt_type == "profile_extraction":
        prompt = PROFILE_EXTRACTION_PROMPT.replace("{title}", payload.title or "测试章节").replace(
            "{content}",
            text[:4000],
        )
        max_tokens = payload.max_tokens or 1200
    else:
        clause_title = payload.clause_title or payload.title or "测试条文"
        prompt = (
            CHECKPOINT_PROMPT.replace("{standard_name}", payload.standard_name or "测试规范")
            .replace("{clause_no}", payload.clause_no or "")
            .replace("{clause_title}", clause_title)
            .replace("{clause_content}", text)
        )
        max_tokens = payload.max_tokens or 1800

    requested_model = payload.model or service.default_model
    record = ModelPromptTestRecord(
        prompt_type=payload.prompt_type,
        model=requested_model,
        temperature=payload.temperature,
        max_tokens=max_tokens,
        input_text=text,
        rendered_prompt=prompt,
        status="running",
        created_by=user.username,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    call_payload = {
        "model": requested_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": payload.temperature,
        "max_tokens": max_tokens,
    }
    metadata = {
        "operation": "model.prompt_test",
        "record_id": record.id,
        "prompt_type": payload.prompt_type,
        "requested_model": requested_model,
        "temperature": payload.temperature,
        "max_tokens": max_tokens,
        "input_chars": len(text),
        "prompt_chars": len(prompt),
        "created_by": user.username,
    }
    try:
        with langfuse_observation(
            name="model.prompt_test",
            input_data={"messages": call_payload["messages"]},
            metadata=metadata,
            user_id=user.username,
            session_id=f"prompt-test:{user.username}",
            tags=["prompt_test", payload.prompt_type, "llm"],
            as_type="generation",
            model=requested_model,
        ) as observation:
            try:
                result = await service.call_model(call_payload)
            except Exception as exc:
                update_langfuse_observation(
                    observation,
                    output={"error": str(exc)},
                    metadata=metadata | {"status": "failed", "error_message": str(exc)},
                )
                raise
            output_content = ((result.get("output") or {}).get("content") or "").strip()
            update_langfuse_observation(
                observation,
                output={"content": output_content, "raw": result.get("output")},
                metadata=metadata
                | {
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "output_chars": len(output_content),
                    "status": "success",
                },
            )
    except Exception as exc:
        record.status = "failed"
        record.error_message = str(exc)
        record.completed_at = datetime.utcnow()
        db.commit()
        raise

    record.provider = result.get("provider")
    record.model = result.get("model") or record.model
    record.output = result.get("output")
    record.status = "success"
    record.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(record)

    return PromptTestResponse(
        record_id=record.id,
        prompt_type=payload.prompt_type,
        prompt=prompt,
        **result,
    )


@router.get("/prompt-test-records", response_model=PromptTestRecordList)
async def list_prompt_test_records(
    _: Annotated[CurrentUser, Depends(require_permission("models:call"))],
    db: Annotated[Session, Depends(get_db)],
    prompt_type: Literal["profile_extraction", "checkpoint"] | None = None,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> PromptTestRecordList:
    query = db.query(ModelPromptTestRecord)
    if prompt_type:
        query = query.filter(ModelPromptTestRecord.prompt_type == prompt_type)
    if status:
        query = query.filter(ModelPromptTestRecord.status == status)
    total = query.count()
    items = (
        query.order_by(ModelPromptTestRecord.created_at.desc(), ModelPromptTestRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PromptTestRecordList(items=items, total=total, page=page, page_size=page_size)
