from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import PlanDocument, PlanParseResult, PlanSection, ReviewTask, RuleExecutionLog
from app.rule_engine.standard_rule_checker import run_standard_rule_review
from app.rule_engine.template_checker import run_template_framework_review
from app.utils.exceptions import PlatformError


def run_review_task(task_id: int, db: Session) -> dict:
    task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
    if not task:
        raise PlatformError(f"Review task id={task_id} not found", status_code=404)

    try:
        if _has_previous_run(task, db):
            task.version = (task.version or 1) + 1
        else:
            task.version = task.version or 1

        task.status = "running"
        task.progress = 5
        task.started_at = datetime.utcnow()
        task.finished_at = None
        task.error_message = None
        task.total_issue_count = 0
        task.critical_issue_count = 0
        task.major_issue_count = 0
        task.minor_issue_count = 0

        _load_plan_document(task, db)
        if task.template_id:
            _load_template(task, db)

        _run_template_review(task, db)
        task.progress = 50
        db.flush()

        _run_standard_review(task, db)
        task.progress = 80
        db.flush()

        task.status = "completed"
        task.progress = 100
        task.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        return {
            "task_id": task.id,
            "status": task.status,
            "version": task.version,
            "total_issue_count": task.total_issue_count,
            "critical_issue_count": task.critical_issue_count,
            "major_issue_count": task.major_issue_count,
            "minor_issue_count": task.minor_issue_count,
        }
    except Exception as exc:
        db.rollback()
        failed_task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
        if failed_task:
            failed_task.status = "failed"
            failed_task.error_message = str(exc)
            failed_task.finished_at = datetime.utcnow()
            db.commit()
        if isinstance(exc, PlatformError):
            raise
        raise


def _load_plan_document(task: ReviewTask, db: Session) -> PlanDocument:
    document = db.query(PlanDocument).filter(PlanDocument.id == task.plan_document_id).first()
    if not document:
        raise PlatformError(f"Plan document id={task.plan_document_id} not found", status_code=404)
    section_count = (
        db.query(PlanSection)
        .join(PlanParseResult, PlanParseResult.id == PlanSection.parse_result_id)
        .filter(
            PlanSection.document_id == task.plan_document_id,
            PlanParseResult.section_parse_mode == document.section_parse_mode,
            PlanParseResult.parse_status == "parsed",
        )
        .count()
    )
    if section_count == 0:
        raise PlatformError("The selected plan document has no parsed sections.", status_code=400)
    return document


def _has_previous_run(task: ReviewTask, db: Session) -> bool:
    if task.started_at is not None:
        return True
    return db.query(RuleExecutionLog.id).filter(RuleExecutionLog.task_id == task.id).first() is not None


def _load_template(task: ReviewTask, db: Session) -> None:
    from app.db.models import ReviewTemplate

    template = db.query(ReviewTemplate).filter(ReviewTemplate.id == task.template_id).first()
    if not template or template.status == "archived":
        raise PlatformError(f"Review template id={task.template_id} not found", status_code=404)


def _run_template_review(task: ReviewTask, db: Session) -> None:
    from app.rule_engine.template_checker import run_template_framework_review
    run_template_framework_review(task, db)


def _run_standard_review(task: ReviewTask, db: Session) -> None:
    run_standard_rule_review(task, db)
