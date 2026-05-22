from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import PlanDocument, PlanSection, ReviewIssue, ReviewTask, RuleExecutionLog
from app.rule_engine.schemas import ReviewIssueCreate
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

        issues: list[ReviewIssueCreate] = []
        issues.extend(run_template_framework_review(task, db))
        task.progress = 50
        db.flush()

        issues.extend(run_standard_rule_review(task, db))
        task.progress = 80
        db.flush()

        saved_issues = _save_deduped_issues(task, db, issues)
        _update_issue_counts(task, saved_issues)
        task.status = "pending_confirm" if saved_issues else "completed"
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
    section_count = db.query(PlanSection).filter(PlanSection.document_id == task.plan_document_id).count()
    if section_count == 0:
        raise PlatformError("The selected plan document has no parsed sections.", status_code=400)
    return document


def _has_previous_run(task: ReviewTask, db: Session) -> bool:
    if task.started_at is not None:
        return True
    issue_exists = db.query(ReviewIssue.id).filter(ReviewIssue.task_id == task.id).first() is not None
    if issue_exists:
        return True
    return db.query(RuleExecutionLog.id).filter(RuleExecutionLog.task_id == task.id).first() is not None


def _load_template(task: ReviewTask, db: Session) -> None:
    from app.db.models import ReviewTemplate

    template = db.query(ReviewTemplate).filter(ReviewTemplate.id == task.template_id).first()
    if not template or template.status == "archived":
        raise PlatformError(f"Review template id={task.template_id} not found", status_code=404)


def _save_deduped_issues(
    task: ReviewTask,
    db: Session,
    issues: list[ReviewIssueCreate],
) -> list[ReviewIssue]:
    seen: set[tuple] = set()
    saved: list[ReviewIssue] = []
    for issue in issues:
        key = (
            issue.issue_type,
            issue.source_type,
            issue.source_rule_id,
            issue.source_template_rule_id,
            issue.plan_section_id,
            issue.issue_title,
        )
        if key in seen:
            continue
        seen.add(key)
        row = ReviewIssue(task_id=task.id, version=task.version, status="pending_confirm", **issue.__dict__)
        db.add(row)
        saved.append(row)
    db.flush()
    return saved


def _update_issue_counts(task: ReviewTask, issues: list[ReviewIssue]) -> None:
    task.total_issue_count = len(issues)
    task.critical_issue_count = sum(1 for issue in issues if issue.risk_level == "critical")
    task.major_issue_count = sum(1 for issue in issues if issue.risk_level == "major")
    task.minor_issue_count = sum(1 for issue in issues if issue.risk_level == "minor")
