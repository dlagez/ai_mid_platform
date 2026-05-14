from typing import Any

from celery.result import AsyncResult

from app.workers.celery_worker import celery_app, run_platform_task


class TaskService:
    def enqueue(self, task_type: str, payload: dict[str, Any]) -> Any:
        return run_platform_task.delay(task_type, payload)

    def get_status(self, task_id: str) -> dict[str, Any]:
        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        }


def get_task_service() -> TaskService:
    return TaskService()
