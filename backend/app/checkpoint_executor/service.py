from __future__ import annotations

import re
from collections.abc import Generator
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    CheckpointMatchResult,
    PlanSection,
    ReviewCheckpoint,
    ReviewIssue,
    ReviewIssueEvidence,
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
        issue_count = 0
        failed: list[dict[str, Any]] = []
        seen = _existing_issue_keys(db, task)

        for match in matches:
            checkpoint = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.id == match.checkpoint_id).first()
            section = db.query(PlanSection).filter(PlanSection.id == match.section_id).first()
            if not checkpoint or not section:
                match.status = "skipped"
                skipped_count += 1
                continue
            try:
                issues = self._execute_checkpoint(task, match, checkpoint, section)
                for issue_payload in issues:
                    key = _issue_key(issue_payload)
                    if key in seen:
                        continue
                    seen.add(key)
                    issue = ReviewIssue(version=task.version or 1, status="pending_confirm", **issue_payload)
                    db.add(issue)
                    db.flush()
                    db.add(_build_evidence(issue, match, checkpoint, section))
                    issue_count += 1
                match.status = "executed"
                executed_count += 1
                _add_log(db, task, checkpoint, section, "failed" if issues else "passed", match.match_reason)
            except Exception as exc:
                match.status = "error"
                failed.append({"match_result_id": match.id, "checkpoint_id": checkpoint.id, "reason": str(exc)})
                _add_log(db, task, checkpoint, section, "error", str(exc))

        _refresh_task_counts(db, task)
        db.commit()
        return {
            "task_id": task.id,
            "executed_count": executed_count,
            "issue_count": issue_count,
            "skipped_count": skipped_count,
            "failed": failed,
        }

    def _execute_checkpoint(
        self,
        task: ReviewTask,
        match: CheckpointMatchResult,
        checkpoint: ReviewCheckpoint,
        section: PlanSection,
    ) -> list[dict[str, Any]]:
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
        return []


def _execute_required_content(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> list[dict[str, Any]]:
    content = f"{section.title}\n{section.content or ''}"
    expected = _checkpoint_keywords(checkpoint.expected_items, checkpoint.keywords, checkpoint.target_objects)
    missing = [item for item in expected if not contains_any(content, [item])]
    if not missing:
        return []
    return [
        _issue_payload(
            task,
            match,
            checkpoint,
            section,
            issue_type="checkpoint_required_content_missing",
            title=f"审查点必要内容缺失：{checkpoint.checkpoint_name}",
            description=f"章节“{section.title}”缺少审查点要求的内容：{', '.join(missing)}。",
            original_text=(section.content or "")[:500],
            suggestion="补充审查点对应的规范要求、构造措施或控制参数。",
        )
    ]


def _execute_forbidden_content(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> list[dict[str, Any]]:
    content = f"{section.title}\n{section.content or ''}"
    forbidden = _checkpoint_keywords(checkpoint.forbidden_items, checkpoint.keywords)
    issues: list[dict[str, Any]] = []
    for keyword in forbidden:
        if not contains_any(content, [keyword]):
            continue
        issues.append(
            _issue_payload(
                task,
                match,
                checkpoint,
                section,
                issue_type="checkpoint_forbidden_content_found",
                title=f"发现审查点禁止内容：{keyword}",
                description=f"章节“{section.title}”命中审查点“{checkpoint.checkpoint_name}”的禁止内容。",
                original_text=extract_text_snippet(content, keyword),
                suggestion="删除或调整与规范禁止性要求冲突的表述。",
            )
        )
    return issues


def _execute_parameter_threshold(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> list[dict[str, Any]]:
    parameter = checkpoint.parameters or {}
    check_object = parameter.get("check_object") or parameter.get("target_parameter") or _first(checkpoint.target_parameters)
    threshold = _parse_threshold(parameter)
    if not check_object or not threshold:
        return []

    issues: list[dict[str, Any]] = []
    actual_values = extract_parameter_values(section.content, str(check_object))
    for actual in actual_values:
        passed = compare_value(actual["value_mm"], threshold["operator"], threshold["threshold_mm"])
        if passed:
            continue
        issues.append(
            _issue_payload(
                task,
                match,
                checkpoint,
                section,
                issue_type="checkpoint_parameter_violation",
                title=f"审查点参数不满足：{checkpoint.checkpoint_name}",
                description=(
                    f"“{check_object}”实际值 {actual['value']}{actual['unit']} "
                    f"不满足 {threshold['operator']}{threshold['threshold_value']}{threshold['unit']}。"
                ),
                original_text=actual["snippet"],
                suggestion="按审查点对应规范阈值调整参数或补充计算论证。",
            )
        )
    return issues


def _execute_procedure_required(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> list[dict[str, Any]]:
    content = section.content or ""
    expected = _checkpoint_keywords(checkpoint.expected_items, checkpoint.keywords, checkpoint.applicable_condition.get("procedures") if checkpoint.applicable_condition else [])
    missing = [item for item in expected if not contains_any(content, [item])]
    if not missing:
        return []
    return [
        _issue_payload(
            task,
            match,
            checkpoint,
            section,
            issue_type="checkpoint_procedure_missing",
            title=f"施工流程缺少必要步骤：{checkpoint.checkpoint_name}",
            description=f"章节“{section.title}”缺少必要流程或工序：{', '.join(missing)}。",
            original_text=content[:500],
            suggestion="补充施工步骤、顺序及控制要求。",
        )
    ]


def _execute_semantic_check(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> list[dict[str, Any]]:
    # MVP does not call LLM here. It only falls back to keyword coverage, so AI output is not treated as final conclusion.
    return _execute_required_content(task, match, checkpoint, section)


def _execute_cross_section_consistency(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> list[dict[str, Any]]:
    # Cross-section consistency needs broader domain rules. MVP records execution without generating hard issues.
    return []


def _issue_payload(
    task: ReviewTask,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
    *,
    issue_type: str,
    title: str,
    description: str,
    original_text: str,
    suggestion: str,
) -> dict[str, Any]:
    confidence = min(0.95, max(0.45, float(match.match_score or 0)))
    return {
        "task_id": task.id,
        "issue_type": issue_type,
        "risk_level": checkpoint.risk_level or "major",
        "issue_title": title[:255],
        "issue_description": description,
        "plan_section_id": section.id,
        "plan_section_title": section.title,
        "plan_original_text": original_text,
        "source_type": "checkpoint",
        "source_rule_id": None,
        "source_template_rule_id": None,
        "standard_clause_id": checkpoint.clause_id,
        "checkpoint_id": checkpoint.id,
        "match_result_id": match.id,
        "confidence": round(confidence, 2),
        "confidence_reason": match.match_reason,
        "ai_reason": None,
        "suggestion": suggestion,
    }


def _build_evidence(
    issue: ReviewIssue,
    match: CheckpointMatchResult,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
) -> ReviewIssueEvidence:
    return ReviewIssueEvidence(
        issue_id=issue.id,
        evidence_type="checkpoint_match",
        standard_id=checkpoint.standard_id,
        clause_id=checkpoint.clause_id,
        clause_no=checkpoint.clause_no,
        clause_text=checkpoint.clause_text,
        plan_section_id=section.id,
        plan_text=issue.plan_original_text,
        checkpoint_id=checkpoint.id,
        match_reason=match.match_reason,
        score=match.match_score,
    )


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


def _issue_key(payload: dict[str, Any]) -> tuple:
    return (
        payload.get("task_id"),
        payload.get("issue_type"),
        payload.get("checkpoint_id"),
        payload.get("match_result_id"),
        payload.get("plan_section_id"),
        payload.get("issue_title"),
    )


def _existing_issue_keys(db: Session, task: ReviewTask) -> set[tuple]:
    keys: set[tuple] = set()
    rows = db.query(ReviewIssue).filter(ReviewIssue.task_id == task.id, ReviewIssue.version == task.version).all()
    for issue in rows:
        keys.add(
            (
                issue.task_id,
                issue.issue_type,
                issue.checkpoint_id,
                issue.match_result_id,
                issue.plan_section_id,
                issue.issue_title,
            )
        )
    return keys


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


def _refresh_task_counts(db: Session, task: ReviewTask) -> None:
    issues = db.query(ReviewIssue).filter(ReviewIssue.task_id == task.id, ReviewIssue.version == task.version).all()
    task.total_issue_count = len(issues)
    task.critical_issue_count = sum(1 for issue in issues if issue.risk_level == "critical")
    task.major_issue_count = sum(1 for issue in issues if issue.risk_level == "major")
    task.minor_issue_count = sum(1 for issue in issues if issue.risk_level == "minor")
    if issues:
        task.status = "pending_confirm"
    elif task.status not in {"failed", "cancelled"}:
        task.status = "completed"
    task.finished_at = datetime.utcnow()


def get_checkpoint_executor_service() -> Generator[CheckpointExecutorService, None, None]:
    yield CheckpointExecutorService()
