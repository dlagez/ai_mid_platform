from __future__ import annotations

import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import PlanSection, ReviewRule, ReviewTask, RuleExecutionLog
from app.rule_engine.matchers import (
    compare_value,
    contains_any,
    extract_parameter_values,
    extract_text_snippet,
    normalize_unit_to_mm,
)
from app.rule_engine.schemas import ReviewIssueCreate, RuleExecutionLogCreate


def run_standard_rule_review(task: ReviewTask, db: Session) -> list[ReviewIssueCreate]:
    query = db.query(ReviewRule).filter(ReviewRule.status == "active")
    if task.work_type:
        query = query.filter(or_(ReviewRule.work_type == task.work_type, ReviewRule.work_type.is_(None), ReviewRule.work_type == ""))
    rules = query.order_by(ReviewRule.id.asc()).all()

    sections = (
        db.query(PlanSection)
        .filter(PlanSection.document_id == task.plan_document_id)
        .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
        .all()
    )

    issues: list[ReviewIssueCreate] = []
    for rule in rules:
        if rule.rule_type in {"required_keyword", "required_field"}:
            issues.extend(_check_required_keyword(task, db, rule, sections, issue_type="missing_required_keyword"))
        elif rule.rule_type == "forbidden_keyword":
            issues.extend(_check_forbidden_keyword(task, db, rule, sections))
        elif rule.rule_type == "parameter_threshold":
            issues.extend(_check_parameter_threshold(task, db, rule, sections))
        elif rule.rule_type == "required_section":
            issues.extend(_check_required_section(task, db, rule, sections))
        elif rule.rule_type in {"semantic_check", "procedure_required"}:
            _add_log(
                db,
                task.id,
                RuleExecutionLogCreate(
                    rule_type=rule.rule_type,
                    rule_id=rule.id,
                    status="skipped",
                    message=f"{rule.rule_type} is not implemented in MVP.",
                ),
            )
        else:
            _add_log(
                db,
                task.id,
                RuleExecutionLogCreate(
                    rule_type=rule.rule_type,
                    rule_id=rule.id,
                    status="skipped",
                    message=f"Unsupported rule type: {rule.rule_type}",
                ),
            )
    return issues


def _check_required_keyword(
    task: ReviewTask,
    db: Session,
    rule: ReviewRule,
    sections: list[PlanSection],
    issue_type: str,
) -> list[ReviewIssueCreate]:
    keywords = _rule_keywords(rule.required_items, rule.check_object)
    if not keywords:
        _add_log(db, task.id, RuleExecutionLogCreate(rule_type=rule.rule_type, rule_id=rule.id, status="skipped"))
        return []

    for section in sections:
        haystack = f"{section.title}\n{section.content or ''}"
        if contains_any(haystack, keywords):
            _add_log(
                db,
                task.id,
                RuleExecutionLogCreate(
                    rule_type=rule.rule_type,
                    rule_id=rule.id,
                    plan_section_id=section.id,
                    status="passed",
                    matched_text=section.title,
                ),
            )
            return []

    _add_log(
        db,
        task.id,
        RuleExecutionLogCreate(
            rule_type=rule.rule_type,
            rule_id=rule.id,
            status="failed",
            message="Required keyword not found.",
            expected_value=", ".join(keywords),
        ),
    )
    return [
        ReviewIssueCreate(
            issue_type=issue_type,
            risk_level=rule.risk_level,
            issue_title=f"缺少必需关键词：{rule.rule_name}",
            issue_description=f"正式规则要求施工方案包含以下内容之一：{', '.join(keywords)}。",
            source_type="standard_rule",
            source_rule_id=rule.id,
            standard_clause_id=rule.clause_id,
            suggestion="补充规范要求的关键内容。",
        )
    ]


def _check_forbidden_keyword(
    task: ReviewTask,
    db: Session,
    rule: ReviewRule,
    sections: list[PlanSection],
) -> list[ReviewIssueCreate]:
    keywords = _rule_keywords(rule.forbidden_items, None)
    if not keywords:
        _add_log(db, task.id, RuleExecutionLogCreate(rule_type=rule.rule_type, rule_id=rule.id, status="skipped"))
        return []

    issues: list[ReviewIssueCreate] = []
    matched = False
    for section in sections:
        content = f"{section.title}\n{section.content or ''}"
        for keyword in keywords:
            if not contains_any(content, [keyword]):
                continue
            matched = True
            snippet = extract_text_snippet(content, keyword)
            _add_log(
                db,
                task.id,
                RuleExecutionLogCreate(
                    rule_type=rule.rule_type,
                    rule_id=rule.id,
                    plan_section_id=section.id,
                    status="failed",
                    message="Forbidden keyword found.",
                    matched_text=snippet,
                    expected_value=f"不得包含：{keyword}",
                    actual_value=keyword,
                ),
            )
            issues.append(
                ReviewIssueCreate(
                    issue_type="forbidden_content_found",
                    risk_level=rule.risk_level,
                    issue_title=f"发现禁止内容：{keyword}",
                    issue_description=f"章节“{section.title}”命中禁止性规则“{rule.rule_name}”。",
                    plan_section_id=section.id,
                    plan_section_title=section.title,
                    plan_original_text=snippet,
                    source_type="standard_rule",
                    source_rule_id=rule.id,
                    standard_clause_id=rule.clause_id,
                    suggestion="删除或调整与禁止性条文冲突的表述。",
                )
            )
    if not matched:
        _add_log(
            db,
            task.id,
            RuleExecutionLogCreate(rule_type=rule.rule_type, rule_id=rule.id, status="passed", expected_value=", ".join(keywords)),
        )
    return issues


def _check_required_section(
    task: ReviewTask,
    db: Session,
    rule: ReviewRule,
    sections: list[PlanSection],
) -> list[ReviewIssueCreate]:
    keywords = _rule_keywords(rule.required_items, rule.check_object)
    if not keywords:
        _add_log(db, task.id, RuleExecutionLogCreate(rule_type=rule.rule_type, rule_id=rule.id, status="skipped"))
        return []
    for section in sections:
        if contains_any(section.title, keywords):
            _add_log(
                db,
                task.id,
                RuleExecutionLogCreate(
                    rule_type=rule.rule_type,
                    rule_id=rule.id,
                    plan_section_id=section.id,
                    status="passed",
                    matched_text=section.title,
                ),
            )
            return []
    _add_log(
        db,
        task.id,
        RuleExecutionLogCreate(
            rule_type=rule.rule_type,
            rule_id=rule.id,
            status="failed",
            message="Required section not found.",
            expected_value=", ".join(keywords),
        ),
    )
    return [
        ReviewIssueCreate(
            issue_type="missing_required_section",
            risk_level=rule.risk_level,
            issue_title=f"缺少规范要求章节：{rule.rule_name}",
            issue_description=f"正式规则要求存在章节：{', '.join(keywords)}。",
            source_type="standard_rule",
            source_rule_id=rule.id,
            standard_clause_id=rule.clause_id,
            suggestion="补充规范要求的章节。",
        )
    ]


def _check_parameter_threshold(
    task: ReviewTask,
    db: Session,
    rule: ReviewRule,
    sections: list[PlanSection],
) -> list[ReviewIssueCreate]:
    threshold = _parse_threshold(rule.threshold_value, rule.unit)
    if not threshold or not rule.check_object:
        _add_log(
            db,
            task.id,
            RuleExecutionLogCreate(
                rule_type=rule.rule_type,
                rule_id=rule.id,
                status="skipped",
                message="Missing check_object or threshold_value.",
            ),
        )
        return []

    issues: list[ReviewIssueCreate] = []
    found_any = False
    passed_any = False
    expected = f"{rule.operator or ''}{threshold['value']}{threshold['unit']}".strip()

    for section in sections:
        for actual in extract_parameter_values(section.content, rule.check_object):
            found_any = True
            passed = compare_value(actual["value_mm"], rule.operator, threshold["value_mm"])
            if passed:
                passed_any = True
                _add_log(
                    db,
                    task.id,
                    RuleExecutionLogCreate(
                        rule_type=rule.rule_type,
                        rule_id=rule.id,
                        plan_section_id=section.id,
                        status="passed",
                        matched_text=actual["snippet"],
                        expected_value=expected,
                        actual_value=f"{actual['value']}{actual['unit']}",
                    ),
                )
                continue

            _add_log(
                db,
                task.id,
                RuleExecutionLogCreate(
                    rule_type=rule.rule_type,
                    rule_id=rule.id,
                    plan_section_id=section.id,
                    status="failed",
                    message="Parameter threshold violated.",
                    matched_text=actual["snippet"],
                    expected_value=expected,
                    actual_value=f"{actual['value']}{actual['unit']}",
                ),
            )
            issues.append(
                ReviewIssueCreate(
                    issue_type="parameter_violation",
                    risk_level=rule.risk_level,
                    issue_title=f"参数超限：{rule.rule_name}",
                    issue_description=f"“{rule.check_object}”实际值 {actual['value']}{actual['unit']} 不满足 {expected}。",
                    plan_section_id=section.id,
                    plan_section_title=section.title,
                    plan_original_text=actual["snippet"],
                    source_type="standard_rule",
                    source_rule_id=rule.id,
                    standard_clause_id=rule.clause_id,
                    suggestion="按规范阈值调整参数或补充论证说明。",
                )
            )

    if not found_any:
        _add_log(
            db,
            task.id,
            RuleExecutionLogCreate(
                rule_type=rule.rule_type,
                rule_id=rule.id,
                status="failed",
                message="Parameter value not found.",
                expected_value=expected,
            ),
        )
    elif passed_any and not issues:
        return []

    return issues


def _parse_threshold(value: str | None, unit: str | None) -> dict[str, float | str] | None:
    if not value:
        return None
    match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mm|毫米|m|米)?", str(value), re.IGNORECASE)
    if not match:
        return None
    parsed_value = float(match.group("value"))
    parsed_unit = match.group("unit") or unit or "mm"
    return {
        "value": parsed_value,
        "unit": parsed_unit,
        "value_mm": normalize_unit_to_mm(parsed_value, parsed_unit),
    }


def _rule_keywords(items: list | None, fallback: str | None) -> list[str]:
    keywords = [str(item).strip() for item in (items or []) if str(item).strip()]
    if fallback and fallback.strip():
        keywords.append(fallback.strip())
    seen: set[str] = set()
    deduped: list[str] = []
    for keyword in keywords:
        if keyword in seen:
            continue
        seen.add(keyword)
        deduped.append(keyword)
    return deduped


def _add_log(db: Session, task_id: int, log: RuleExecutionLogCreate) -> None:
    db.add(RuleExecutionLog(task_id=task_id, **log.__dict__))
