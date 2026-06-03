from __future__ import annotations

import json
import re
from collections.abc import Generator
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    CheckpointMatchResult,
    PlanSection,
    ReviewCheckpoint,
    ReviewTask,
    RuleExecutionLog,
)
from app.services.model_service import ModelService
from app.utils.exceptions import PlatformError
from app.utils.langfuse import langfuse_observation, update_langfuse_observation


CHECKPOINT_REVIEW_PROMPT = """你是一名施工方案规范审查专家。

请基于“审查点/规范依据”和“施工方案章节内容”，判断该章节是否满足审查点要求。

只输出单行紧凑 JSON，不要输出 Markdown，不要添加解释性文字，不要使用代码块。

判断要求：
1. 只审查给定审查点，不要扩展到其他规范要求。
2. 如果章节内容明确满足审查点，result 输出 pass。
3. 如果章节内容明确缺失、冲突或不满足审查点，result 输出 fail。
4. 如果审查点明显不适用于该章节，result 输出 not_applicable。
5. 如果证据不足且无法判断，result 输出 uncertain。
6. evidence 必须引用施工方案中的关键证据；没有证据时为空字符串。
7. suggestion 只在 fail 或 uncertain 时输出简短整改/补充建议。
8. risk_level 只能是 critical、major、minor 之一；pass/not_applicable 默认 minor。
9. confidence 为 0-1 小数。

审查点：
{checkpoint_text}

对象词：
{object_terms}

规范条文号：
{clause_no}

规范条文原文：
{clause_text}

施工方案章节：
{section_title}

施工方案内容：
{section_content}

输出格式：
{{"result":"pass","risk_level":"minor","confidence":0.0,"summary":"","evidence":"","suggestion":""}}
"""


class CheckpointExecutorService:
    async def run_checkpoint_review(self, db: Session, task_id: int) -> dict[str, Any]:
        task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
        if not task:
            raise PlatformError(f"Review task id={task_id} not found", status_code=404)

        matches = (
            db.query(CheckpointMatchResult)
            .join(PlanSection, PlanSection.id == CheckpointMatchResult.section_id)
            .filter(
                CheckpointMatchResult.task_id == task.id,
                CheckpointMatchResult.status.in_(("selected", "executed")),
                PlanSection.level >= 3,
            )
            .order_by(CheckpointMatchResult.match_score.desc(), CheckpointMatchResult.id.asc())
            .all()
        )
        if not matches:
            raise PlatformError("No selected checkpoint matches found. Run checkpoint matching first.", status_code=400)

        if _has_previous_checkpoint_run(task, db):
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
        db.flush()

        executed_count = 0
        skipped_count = 0
        failed: list[dict[str, Any]] = []
        issue_counts = {"critical": 0, "major": 0, "minor": 0}

        for match in matches:
            checkpoint = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.id == match.checkpoint_id).first()
            section = db.query(PlanSection).filter(PlanSection.id == match.section_id).first()
            if not checkpoint or not section:
                match.status = "skipped"
                skipped_count += 1
                continue
            try:
                review = await self._execute_checkpoint(task, match, checkpoint, section)
                status = _execution_status(review)
                match.status = "executed"
                executed_count += 1
                if status == "failed":
                    issue_counts[_risk_level(review)] += 1
                _add_log(db, task, checkpoint, section, status, match.match_reason, review)
            except Exception as exc:
                match.status = "error"
                failed.append({"match_result_id": match.id, "checkpoint_id": checkpoint.id, "reason": str(exc)})
                _add_log(db, task, checkpoint, section, "error", str(exc))

        task.status = "completed"
        task.progress = 100
        task.finished_at = datetime.utcnow()
        task.critical_issue_count = issue_counts["critical"]
        task.major_issue_count = issue_counts["major"]
        task.minor_issue_count = issue_counts["minor"]
        task.total_issue_count = sum(issue_counts.values())
        db.commit()
        return {
            "task_id": task.id,
            "executed_count": executed_count,
            "skipped_count": skipped_count,
            "failed": failed,
        }

    async def _execute_checkpoint(
        self,
        task: ReviewTask,
        match: CheckpointMatchResult,
        checkpoint: ReviewCheckpoint,
        section: PlanSection,
    ) -> dict[str, Any]:
        model_service = ModelService()
        prompt = CHECKPOINT_REVIEW_PROMPT.replace("{checkpoint_text}", _truncate(checkpoint.rule_text or "", 2500))
        prompt = prompt.replace(
            "{object_terms}",
            json.dumps(_checkpoint_keywords(checkpoint.object_terms), ensure_ascii=False),
        )
        prompt = prompt.replace("{clause_no}", checkpoint.clause_no or "")
        prompt = prompt.replace("{clause_text}", _truncate(checkpoint.clause_text or "", 3000))
        prompt = prompt.replace("{section_title}", section.title or "")
        prompt = prompt.replace("{section_content}", _truncate(section.content or "", 7000))
        payload = {
            "model": model_service.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1200,
        }
        metadata = {
            "operation": "checkpoint_review.execute",
            "task_id": task.id,
            "version": task.version or 1,
            "match_result_id": match.id,
            "checkpoint_id": checkpoint.id,
            "section_id": section.id,
            "section_title": section.title,
            "match_score": float(match.match_score or 0),
            "prompt_chars": len(prompt),
        }
        with langfuse_observation(
            name="checkpoint_review.execute",
            input_data={"messages": payload["messages"]},
            metadata=metadata,
            session_id=f"review-task:{task.id}:v{task.version or 1}",
            tags=["checkpoint_review", "llm"],
            as_type="generation",
            model=model_service.default_model,
        ) as observation:
            result = await model_service.call_model(payload)
            content = ((result.get("output") or {}).get("content") or "").strip()
            parsed = _parse_json_object(content)
            normalized = _normalize_review(parsed)
            update_langfuse_observation(
                observation,
                output={"content": content},
                metadata=metadata
                | {
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "output_chars": len(content),
                    "review_result": normalized["result"],
                    "risk_level": normalized["risk_level"],
                    "confidence": normalized["confidence"],
                },
            )
        return normalized


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


def _has_previous_checkpoint_run(task: ReviewTask, db: Session) -> bool:
    return (
        db.query(RuleExecutionLog.id)
        .filter(
            RuleExecutionLog.task_id == task.id,
            RuleExecutionLog.rule_type == "checkpoint",
        )
        .first()
        is not None
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    if not content:
        raise PlatformError("LLM returned empty content.", status_code=502)
    cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise PlatformError("LLM output is not a JSON object.", status_code=502)
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise PlatformError("LLM output JSON must be an object.", status_code=502)
    return parsed


def _normalize_review(data: dict[str, Any]) -> dict[str, Any]:
    result = str(data.get("result") or "uncertain").strip().lower()
    aliases = {
        "passed": "pass",
        "compliant": "pass",
        "符合": "pass",
        "failed": "fail",
        "non_compliant": "fail",
        "不符合": "fail",
        "not applicable": "not_applicable",
        "不适用": "not_applicable",
        "无法判断": "uncertain",
    }
    result = aliases.get(result, result)
    if result not in {"pass", "fail", "not_applicable", "uncertain"}:
        result = "uncertain"
    risk_level = str(data.get("risk_level") or "minor").strip().lower()
    if risk_level not in {"critical", "major", "minor"}:
        risk_level = "minor"
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "result": result,
        "risk_level": risk_level,
        "confidence": confidence,
        "summary": str(data.get("summary") or "").strip(),
        "evidence": str(data.get("evidence") or "").strip(),
        "suggestion": str(data.get("suggestion") or "").strip(),
    }


def _execution_status(review: dict[str, Any]) -> str:
    if review.get("result") == "fail":
        return "failed"
    if review.get("result") == "uncertain":
        return "uncertain"
    return "passed"


def _risk_level(review: dict[str, Any]) -> str:
    risk_level = str(review.get("risk_level") or "minor").lower()
    return risk_level if risk_level in {"critical", "major", "minor"} else "minor"


def _truncate(text: str, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[内容已截断]"


def _add_log(
    db: Session,
    task: ReviewTask,
    checkpoint: ReviewCheckpoint,
    section: PlanSection,
    status: str,
    message: str | None,
    review: dict[str, Any] | None = None,
) -> None:
    log_message = message
    if review:
        log_message = json.dumps(review, ensure_ascii=False, separators=(",", ":"))
    db.add(
        RuleExecutionLog(
            task_id=task.id,
            version=task.version or 1,
            rule_type="checkpoint",
            rule_id=checkpoint.id,
            plan_section_id=section.id,
            status=status,
            message=log_message,
            matched_text=review.get("evidence") if review else None,
            expected_value=checkpoint.rule_text,
            actual_value=review.get("summary") if review else section.title,
        )
    )


def get_checkpoint_executor_service() -> Generator[CheckpointExecutorService, None, None]:
    yield CheckpointExecutorService()
