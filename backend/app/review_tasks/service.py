from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.models import PlanDocument, ReviewIssue, ReviewTask, ReviewTemplate
from app.review_tasks.schemas import ReviewTaskCreate, ReviewTaskUpdate
from app.rule_engine.engine import run_review_task
from app.utils.exceptions import PlatformError

TASK_STATUSES = {"created", "running", "pending_confirm", "completed", "failed", "cancelled"}
REVIEW_MODES = {"quick", "standard", "deep"}


class ReviewTaskService:
    def list_tasks(
        self,
        db: Session,
        *,
        status: str | None = None,
        plan_document_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReviewTask], int]:
        query = db.query(ReviewTask)
        if status:
            query = query.filter(ReviewTask.status == status)
        if plan_document_id:
            query = query.filter(ReviewTask.plan_document_id == plan_document_id)
        total = query.count()
        items = (
            query.order_by(ReviewTask.created_at.desc(), ReviewTask.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_task(self, db: Session, task_id: int) -> ReviewTask:
        task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
        if not task:
            raise PlatformError(f"Review task id={task_id} not found", status_code=404)
        return task

    def create_task(
        self,
        db: Session,
        data: ReviewTaskCreate,
        created_by: int | None = None,
    ) -> ReviewTask:
        self._validate_review_mode(data.review_mode)
        self._ensure_plan_document(db, data.plan_document_id)
        if data.template_id:
            self._ensure_template(db, data.template_id)

        task = ReviewTask(**data.model_dump(), created_by=created_by)
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def update_task(self, db: Session, task_id: int, data: ReviewTaskUpdate) -> ReviewTask:
        task = self.get_task(db, task_id)
        values = data.model_dump(exclude_unset=True)
        if "review_mode" in values:
            self._validate_review_mode(values["review_mode"])
        if "status" in values:
            self._validate_status(values["status"])
        if values.get("template_id"):
            self._ensure_template(db, values["template_id"])
        for key, value in values.items():
            setattr(task, key, value)
        db.commit()
        db.refresh(task)
        return task

    def start_task(self, db: Session, task_id: int) -> dict:
        task = self.get_task(db, task_id)
        if task.status == "running":
            raise PlatformError("Review task is already running.", status_code=409)
        result = run_review_task(task_id, db)
        return {
            "id": result["task_id"],
            "status": result["status"],
            "version": result.get("version"),
            "total_issue_count": result.get("total_issue_count"),
            "critical_issue_count": result.get("critical_issue_count"),
            "major_issue_count": result.get("major_issue_count"),
            "minor_issue_count": result.get("minor_issue_count"),
        }

    def list_issues(
        self,
        db: Session,
        task_id: int,
        *,
        version: int | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        issue_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReviewIssue], int]:
        task = self.get_task(db, task_id)
        query = db.query(ReviewIssue).filter(ReviewIssue.task_id == task_id)
        query = query.filter(ReviewIssue.version == (version or task.version))
        if status:
            query = query.filter(ReviewIssue.status == status)
        if risk_level:
            query = query.filter(ReviewIssue.risk_level == risk_level)
        if issue_type:
            query = query.filter(ReviewIssue.issue_type == issue_type)
        total = query.count()
        items = (
            query.order_by(ReviewIssue.created_at.desc(), ReviewIssue.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def _ensure_plan_document(self, db: Session, document_id: int) -> PlanDocument:
        document = db.query(PlanDocument).filter(PlanDocument.id == document_id).first()
        if not document:
            raise PlatformError(f"Plan document id={document_id} not found", status_code=404)
        return document

    def _ensure_template(self, db: Session, template_id: int) -> ReviewTemplate:
        template = db.query(ReviewTemplate).filter(ReviewTemplate.id == template_id).first()
        if not template or template.status == "archived":
            raise PlatformError(f"Review template id={template_id} not found", status_code=404)
        return template

    def _validate_review_mode(self, review_mode: str | None) -> None:
        if review_mode and review_mode not in REVIEW_MODES:
            raise PlatformError(f"Invalid review_mode: {review_mode}", status_code=400)

    def _validate_status(self, status: str | None) -> None:
        if status and status not in TASK_STATUSES:
            raise PlatformError(f"Invalid review task status: {status}", status_code=400)


def get_review_task_service() -> Generator[ReviewTaskService, None, None]:
    yield ReviewTaskService()
