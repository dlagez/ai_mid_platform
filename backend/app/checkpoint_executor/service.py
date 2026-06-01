from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    CheckpointMatchResult,
    PlanSection,
    ReviewCheckpoint,
    ReviewTask,
    RuleExecutionLog,
)
from app.rule_engine.matchers import contains_any
from app.utils.exceptions import PlatformError


class CheckpointExecutorService:
    def run_checkpoint_review(self, db: Session, task_id: int) -> dict[str, Any]:
        task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
        if not task:
            raise PlatformError(f"Review task id={task_id} not found", status_code=404)

        matches = (
            db.query(CheckpointMatchResult)
            .filter(CheckpointMatchResult.task_id == task.id, CheckpointMatchResult.status == "selected")
            .order_by(CheckpointMatchResult.match_score.desc(), CheckpointMatchResult.id.asc())
            .all()
        )
        if not matches:
            raise PlatformError("No selected checkpoint matches found. Run checkpoint matching first.", status_code=400)

        executed_count = 0
        skipped_count = 0
        failed: list[dict[str, Any]] = []

        for match in matches:
            checkpoint = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.id == match.checkpoint_id).first()
            section = db.query(PlanSection).filter(PlanSection.id == match.section_id).first()
            if not checkpoint or not section:
                match.status = "skipped"
                skipped_count += 1
                continue
            try:
                has_issue = self._execute_checkpoint(task, match, checkpoint, section)
                match.status = "executed"
                executed_count += 1
                _add_log(db, task, checkpoint, section, "failed" if has_issue else "passed", match.match_reason)
            except Exception as exc:
                match.status = "error"
                failed.append({"match_result_id": match.id, "checkpoint_id": checkpoint.id, "reason": str(exc)})
                _add_log(db, task, checkpoint, section, "error", str(exc))

        task.status = "completed"
        task.finished_at = None  # Will be set by engine
        db.commit()
        return {
            "task_id": task.id,
            "executed_count": executed_count,
            "skipped_count": skipped_count,
            "failed": failed,
        }

    def _execute_checkpoint(
        self,
        task: ReviewTask,
        match: CheckpointMatchResult,
        checkpoint: ReviewCheckpoint,
        section: PlanSection,
    ) -> bool:
        content = f"{section.title}\n{section.content or ''}"
        terms = _checkpoint_keywords(checkpoint.object_terms, checkpoint.rule_text)
        return bool(terms and not any(contains_any(content, [term]) for term in terms))


def _checkpoint_keywords(*values: Any) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []
    for value in values:
        if not value:
            continue
        iterable = value if isinstance(value, list) else [value]
        for item in iterable:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            keywords.append(text)
    return keywords


def _add_log(
    db: Session,
    task: ReviewTask,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
    status: str,
    message: str | None,
) -> None:
    db.add(
        RuleExecutionLog(
            task_id=task.id,
            version=task.version or 1,
            rule_type="checkpoint",
            rule_id=checkpoint.id,
            plan_section_id=section.id,
            status=status,
            message=message,
            expected_value=checkpoint.rule_text,
            actual_value=section.title,
        )
    )


def get_checkpoint_executor_service() -> Generator[CheckpointExecutorService, None, None]:
    yield CheckpointExecutorService()
