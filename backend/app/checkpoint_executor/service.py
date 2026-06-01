from __future__ import annotations

import re
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
from app.rule_engine.matchers import (
    compare_value,
    contains_any,
    extract_parameter_values,
    extract_text_snippet,
    normalize_unit_to_mm,
)
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
        """Execute a checkpoint against a section. Returns True if any issue would have been raised."""
        checkpoint_type = checkpoint.checkpoint_type
        if checkpoint_type == "required_content":
            return _execute_required_content(task, match, checkpoint, section)
        if checkpoint_type == "forbidden_content":
            return _execute_forbidden_content(task, match, checkpoint, section)
        if checkpoint_type == "parameter_threshold":
            return _execute_parameter_threshold(task, match, checkpoint, section)
        if checkpoint_type == "procedure_required":
            return _execute_procedure_required(task, match, checkpoint, section)
        if checkpoint_type == "semantic_check":
            return _execute_semantic_check(task, match, checkpoint, section)
        if checkpoint_type == "cross_section_consistency":
            return _execute_cross_section_consistency(task, match, checkpoint, section)
        return False


def _execute_required_content(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> bool:
    content = f"{section.title}\n{section.content or ''}"
    expected = _checkpoint_keywords(checkpoint.expected_items, checkpoint.keywords, checkpoint.target_objects)
    missing = [item for item in expected if not contains_any(content, [item])]
    if not missing:
        return False
    return True


def _execute_forbidden_content(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> bool:
    content = f"{section.title}\n{section.content or ''}"
    forbidden = _checkpoint_keywords(checkpoint.forbidden_items, checkpoint.keywords)
    for keyword in forbidden:
        if contains_any(content, [keyword]):
            return True
    return False


def _execute_parameter_threshold(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> bool:
    parameter = checkpoint.parameters or {}
    check_object = parameter.get("check_object") or parameter.get("target_parameter") or _first(checkpoint.target_parameters)
    threshold = _parse_threshold(parameter)
    if not check_object or not threshold:
        return False

    actual_values = extract_parameter_values(section.content, str(check_object))
    for actual in actual_values:
        passed = compare_value(actual["value_mm"], threshold["operator"], threshold["threshold_mm"])
        if not passed:
            return True
    return False


def _execute_procedure_required(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> bool:
    content = section.content or ""
    expected = _checkpoint_keywords(
        checkpoint.expected_items,
        checkpoint.keywords,
        checkpoint.applicable_condition.get("procedures") if checkpoint.applicable_condition else [],
    )
    missing = [item for item in expected if not contains_any(content, [item])]
    return bool(missing)


def _execute_semantic_check(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> bool:
    # MVP does not call LLM here. It only falls back to keyword coverage.
    return _execute_required_content(task, match, checkpoint, section)


def _execute_cross_section_consistency(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> bool:
    # Cross-section consistency needs broader domain rules. MVP records execution without generating hard issues.
    return False


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


def _parse_threshold(parameter: dict[str, Any]) -> dict[str, Any] | None:
    value = parameter.get("threshold_value") or parameter.get("value") or parameter.get("threshold")
    unit = parameter.get("unit") or "mm"
    operator = parameter.get("operator") or parameter.get("compare") or "<="
    if value is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    numeric_value = float(match.group(0))
    return {
        "operator": str(operator),
        "threshold_value": numeric_value,
        "unit": unit,
        "threshold_mm": normalize_unit_to_mm(numeric_value, unit),
    }


def _first(values: list | None) -> str | None:
    if not values:
        return None
    return str(values[0])


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
            rule_type=f"checkpoint:{checkpoint.checkpoint_type}",
            rule_id=checkpoint.id,
            plan_section_id=section.id,
            status=status,
            message=message,
            expected_value=checkpoint.check_goal,
            actual_value=section.title,
        )
    )


def get_checkpoint_executor_service() -> Generator[CheckpointExecutorService, None, None]:
    yield CheckpointExecutorService()
