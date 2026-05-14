from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.task_service import TaskService, get_task_service
from app.utils.jwt import CurrentUser, require_permission

router = APIRouter()


class TaskCreateRequest(BaseModel):
    task_type: str
    payload: dict[str, Any] = {}


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Any | None = None


@router.post("", response_model=TaskCreateResponse)
async def create_task(
    payload: TaskCreateRequest,
    _: Annotated[CurrentUser, Depends(require_permission("tasks:write"))],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskCreateResponse:
    task = service.enqueue(payload.task_type, payload.payload)
    return TaskCreateResponse(task_id=task.id, status=task.status)


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    _: Annotated[CurrentUser, Depends(require_permission("tasks:read"))],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskStatusResponse:
    return TaskStatusResponse(**service.get_status(task_id))
