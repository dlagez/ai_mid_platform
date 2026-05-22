from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import PlanSection, ReviewTask, RuleExecutionLog, TemplateSectionRule
from app.rule_engine.matchers import contains_any, find_section_by_title, normalize_text
from app.rule_engine.schemas import ReviewIssueCreate, RuleExecutionLogCreate


def run_template_framework_review(task: ReviewTask, db: Session) -> list[ReviewIssueCreate]:
    if not task.template_id:
        return []

    rules = (
        db.query(TemplateSectionRule)
        .filter(TemplateSectionRule.template_id == task.template_id, TemplateSectionRule.enabled.is_(True))
        .order_by(TemplateSectionRule.order_no.asc(), TemplateSectionRule.id.asc())
        .all()
    )
    sections = (
        db.query(PlanSection)
        .filter(PlanSection.document_id == task.plan_document_id)
        .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
        .all()
    )

    issues: list[ReviewIssueCreate] = []
    for rule in rules:
        matched_section = find_section_by_title(sections, rule.standard_title, rule.aliases)
        issues.extend(_check_required_section(task, db, rule, matched_section))
        if matched_section:
            issues.extend(_check_min_word_count(task, db, rule, matched_section))
            issues.extend(_check_required_points(task, db, rule, matched_section))

    return issues


def _check_required_section(
    task: ReviewTask,
    db: Session,
    rule: TemplateSectionRule,
    matched_section: PlanSection | None,
) -> list[ReviewIssueCreate]:
    if not rule.required:
        _add_log(
            db,
            task.id,
            RuleExecutionLogCreate(
                rule_type="required_section",
                template_rule_id=rule.id,
                plan_section_id=matched_section.id if matched_section else None,
                status="skipped",
                message="Section is not required.",
            ),
        )
        return []

    if matched_section:
        _add_log(
            db,
            task.id,
            RuleExecutionLogCreate(
                rule_type="required_section",
                template_rule_id=rule.id,
                plan_section_id=matched_section.id,
                status="passed",
                message="Required section matched.",
                matched_text=matched_section.title,
            ),
        )
        return []

    _add_log(
        db,
        task.id,
        RuleExecutionLogCreate(
            rule_type="required_section",
            template_rule_id=rule.id,
            status="failed",
            message="Required section missing.",
            expected_value=rule.standard_title,
        ),
    )
    return [
        ReviewIssueCreate(
            issue_type="missing_required_section",
            risk_level=rule.risk_level,
            issue_title=f"缺少必填章节：{rule.standard_title}",
            issue_description=f"模板要求包含章节“{rule.standard_title}”，当前施工方案未匹配到该章节。",
            source_type="template_rule",
            source_template_rule_id=rule.id,
            suggestion=f"补充“{rule.standard_title}”章节及相关内容。",
        )
    ]


def _check_min_word_count(
    task: ReviewTask,
    db: Session,
    rule: TemplateSectionRule,
    section: PlanSection,
) -> list[ReviewIssueCreate]:
    if not rule.min_word_count or rule.min_word_count <= 0:
        return []

    actual_count = len(normalize_text(section.content))
    if actual_count >= rule.min_word_count:
        _add_log(
            db,
            task.id,
            RuleExecutionLogCreate(
                rule_type="min_word_count",
                template_rule_id=rule.id,
                plan_section_id=section.id,
                status="passed",
                expected_value=str(rule.min_word_count),
                actual_value=str(actual_count),
            ),
        )
        return []

    _add_log(
        db,
        task.id,
        RuleExecutionLogCreate(
            rule_type="min_word_count",
            template_rule_id=rule.id,
            plan_section_id=section.id,
            status="failed",
            message="Section content length is below minimum.",
            expected_value=str(rule.min_word_count),
            actual_value=str(actual_count),
        ),
    )
    return [
        ReviewIssueCreate(
            issue_type="insufficient_content",
            risk_level=rule.risk_level,
            issue_title=f"章节内容不足：{rule.standard_title}",
            issue_description=f"章节“{section.title}”内容长度为 {actual_count}，低于模板要求 {rule.min_word_count}。",
            plan_section_id=section.id,
            plan_section_title=section.title,
            plan_original_text=section.content,
            source_type="template_rule",
            source_template_rule_id=rule.id,
            suggestion="补充该章节内容，使其满足模板深度要求。",
        )
    ]


def _check_required_points(
    task: ReviewTask,
    db: Session,
    rule: TemplateSectionRule,
    section: PlanSection,
) -> list[ReviewIssueCreate]:
    required_points = [str(item).strip() for item in (rule.required_points or []) if str(item).strip()]
    if not required_points:
        return []

    issues: list[ReviewIssueCreate] = []
    for point in required_points:
        if contains_any(section.content, [point]):
            _add_log(
                db,
                task.id,
                RuleExecutionLogCreate(
                    rule_type="required_point",
                    template_rule_id=rule.id,
                    plan_section_id=section.id,
                    status="passed",
                    matched_text=point,
                ),
            )
            continue

        _add_log(
            db,
            task.id,
            RuleExecutionLogCreate(
                rule_type="required_point",
                template_rule_id=rule.id,
                plan_section_id=section.id,
                status="failed",
                message="Required point missing.",
                expected_value=point,
            ),
        )
        issues.append(
            ReviewIssueCreate(
                issue_type="missing_required_point",
                risk_level=rule.risk_level,
                issue_title=f"章节缺少必要内容点：{point}",
                issue_description=f"章节“{section.title}”未包含模板要求的内容点“{point}”。",
                plan_section_id=section.id,
                plan_section_title=section.title,
                plan_original_text=section.content,
                source_type="template_rule",
                source_template_rule_id=rule.id,
                suggestion=f"在“{section.title}”中补充“{point}”相关说明。",
            )
        )
    return issues


def _add_log(db: Session, task_id: int, log: RuleExecutionLogCreate) -> None:
    task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
    db.add(RuleExecutionLog(task_id=task_id, version=task.version if task else 1, **log.__dict__))
