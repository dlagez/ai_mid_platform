from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import PlanDocument, PlanParseResult, PlanSection, ReviewTask, RuleExecutionLog, TemplateSectionRule
from app.rule_engine.matchers import contains_any, find_section_by_title, normalize_text
from app.rule_engine.schemas import RuleExecutionLogCreate


def run_template_framework_review(task: ReviewTask, db: Session) -> None:
    """Template framework review — issue generation removed."""
    if not task.template_id:
        return

    rules = (
        db.query(TemplateSectionRule)
        .filter(TemplateSectionRule.template_id == task.template_id, TemplateSectionRule.enabled.is_(True))
        .order_by(TemplateSectionRule.order_no.asc(), TemplateSectionRule.id.asc())
        .all()
    )
    sections = (
        db.query(PlanSection)
        .join(PlanParseResult, PlanParseResult.id == PlanSection.parse_result_id)
        .join(PlanDocument, PlanDocument.id == PlanSection.document_id)
        .filter(
            PlanSection.document_id == task.plan_document_id,
            PlanParseResult.section_parse_mode == PlanDocument.section_parse_mode,
            PlanParseResult.parse_status == "parsed",
        )
        .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
        .all()
    )

    for rule in rules:
        matched_section = find_section_by_title(sections, rule.standard_title, rule.aliases)
        _check_required_section(task, db, rule, matched_section)
        if matched_section:
            _check_min_word_count(task, db, rule, matched_section)
            _check_required_points(task, db, rule, matched_section)


def _check_required_section(
    task: ReviewTask,
    db: Session,
    rule: TemplateSectionRule,
    matched_section: PlanSection | None,
) -> None:
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
        return

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
        return

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


def _check_min_word_count(
    task: ReviewTask,
    db: Session,
    rule: TemplateSectionRule,
    section: PlanSection,
) -> None:
    if not rule.min_word_count or rule.min_word_count <= 0:
        return

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
        return

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


def _check_required_points(
    task: ReviewTask,
    db: Session,
    rule: TemplateSectionRule,
    section: PlanSection,
) -> None:
    required_points = [str(item).strip() for item in (rule.required_points or []) if str(item).strip()]
    if not required_points:
        return

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


def _add_log(db: Session, task_id: int, log: RuleExecutionLogCreate) -> None:
    task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
    db.add(RuleExecutionLog(task_id=task_id, version=task.version if task else 1, **log.__dict__))
