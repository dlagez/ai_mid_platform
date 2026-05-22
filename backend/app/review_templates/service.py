from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.models import PlanDocument, PlanSection, ReviewTemplate, TemplateSectionRule
from app.review_templates.schemas import (
    ImportTemplateFromDocumentRequest,
    ReviewTemplateCreate,
    ReviewTemplateUpdate,
    TemplateSectionRuleCreate,
    TemplateSectionRuleUpdate,
)
from app.utils.exceptions import PlatformError

TEMPLATE_STATUSES = {"draft", "active", "disabled", "archived"}


class ReviewTemplateService:
    def list_templates(self, db: Session) -> tuple[list[ReviewTemplate], int]:
        query = db.query(ReviewTemplate).filter(ReviewTemplate.status != "archived")
        return query.order_by(ReviewTemplate.created_at.desc()).all(), query.count()

    def get_template(self, db: Session, template_id: int) -> ReviewTemplate:
        template = db.query(ReviewTemplate).filter(ReviewTemplate.id == template_id).first()
        if not template or template.status == "archived":
            raise PlatformError(f"Review template id={template_id} not found", status_code=404)
        return template

    def create_template(self, db: Session, data: ReviewTemplateCreate, created_by: int | None = None) -> ReviewTemplate:
        self._validate_status(data.status)
        template = ReviewTemplate(**data.model_dump(), created_by=created_by)
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    def update_template(self, db: Session, template_id: int, data: ReviewTemplateUpdate) -> ReviewTemplate:
        template = self.get_template(db, template_id)
        values = data.model_dump(exclude_unset=True)
        if "status" in values:
            self._validate_status(values["status"])
        for key, value in values.items():
            setattr(template, key, value)
        db.commit()
        db.refresh(template)
        return template

    def archive_template(self, db: Session, template_id: int) -> ReviewTemplate:
        template = self.get_template(db, template_id)
        template.status = "archived"
        db.commit()
        db.refresh(template)
        return template

    def activate_template(self, db: Session, template_id: int) -> ReviewTemplate:
        template = self.get_template(db, template_id)
        template.status = "active"
        db.commit()
        db.refresh(template)
        return template

    def disable_template(self, db: Session, template_id: int) -> ReviewTemplate:
        template = self.get_template(db, template_id)
        template.status = "disabled"
        db.commit()
        db.refresh(template)
        return template

    def import_from_document(
        self,
        db: Session,
        data: ImportTemplateFromDocumentRequest,
        created_by: int | None = None,
    ) -> tuple[ReviewTemplate, int]:
        document = db.query(PlanDocument).filter(PlanDocument.id == data.document_id).first()
        if not document:
            raise PlatformError(f"Plan document id={data.document_id} not found", status_code=404)

        sections = (
            db.query(PlanSection)
            .filter(PlanSection.document_id == data.document_id)
            .order_by(PlanSection.sort_no.asc())
            .all()
        )
        if not sections:
            raise PlatformError("The selected plan document has no parsed sections.", status_code=400)

        template = ReviewTemplate(
            name=data.name,
            code=data.code,
            work_type=data.work_type,
            source_document_id=data.document_id,
            description=data.description,
            created_by=created_by,
        )
        db.add(template)
        db.flush()

        id_map: dict[int, int] = {}
        for section in sections:
            rule = TemplateSectionRule(
                template_id=template.id,
                parent_id=id_map.get(section.parent_id) if section.parent_id else None,
                section_code=section.section_no,
                standard_title=section.title[:255],
                level=section.level,
                order_no=section.sort_no,
                required=True,
                aliases=[],
                required_points=[],
                min_word_count=0,
                risk_level="major",
                match_strategy="title_semantic",
                enabled=True,
            )
            db.add(rule)
            db.flush()
            id_map[section.id] = rule.id

        db.commit()
        db.refresh(template)
        return template, len(sections)

    def list_section_rules(self, db: Session, template_id: int) -> list[TemplateSectionRule]:
        self.get_template(db, template_id)
        return (
            db.query(TemplateSectionRule)
            .filter(TemplateSectionRule.template_id == template_id)
            .order_by(TemplateSectionRule.order_no.asc(), TemplateSectionRule.id.asc())
            .all()
        )

    def create_section_rule(
        self,
        db: Session,
        template_id: int,
        data: TemplateSectionRuleCreate,
    ) -> TemplateSectionRule:
        self.get_template(db, template_id)
        if data.parent_id:
            self._get_section_rule(db, data.parent_id, template_id=template_id)
        rule = TemplateSectionRule(template_id=template_id, **data.model_dump())
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule

    def update_section_rule(self, db: Session, rule_id: int, data: TemplateSectionRuleUpdate) -> TemplateSectionRule:
        rule = self._get_section_rule(db, rule_id)
        values = data.model_dump(exclude_unset=True)
        parent_id = values.get("parent_id")
        if parent_id:
            parent = self._get_section_rule(db, parent_id, template_id=rule.template_id)
            if parent.id == rule.id:
                raise PlatformError("A section rule cannot be its own parent.", status_code=400)
        for key, value in values.items():
            setattr(rule, key, value)
        db.commit()
        db.refresh(rule)
        return rule

    def delete_section_rule(self, db: Session, rule_id: int) -> TemplateSectionRule:
        rule = self._get_section_rule(db, rule_id)
        rule.enabled = False
        db.commit()
        db.refresh(rule)
        return rule

    def _get_section_rule(
        self,
        db: Session,
        rule_id: int,
        *,
        template_id: int | None = None,
    ) -> TemplateSectionRule:
        query = db.query(TemplateSectionRule).filter(TemplateSectionRule.id == rule_id)
        if template_id is not None:
            query = query.filter(TemplateSectionRule.template_id == template_id)
        rule = query.first()
        if not rule:
            raise PlatformError(f"Template section rule id={rule_id} not found", status_code=404)
        return rule

    def _validate_status(self, status: str) -> None:
        if status not in TEMPLATE_STATUSES:
            raise PlatformError(f"Invalid template status: {status}", status_code=400)


def template_section_rules_to_tree(rules: list[TemplateSectionRule]) -> list[dict]:
    items = {rule.id: _section_rule_to_dict(rule) | {"children": []} for rule in rules}
    roots: list[dict] = []
    for rule in rules:
        item = items[rule.id]
        if rule.parent_id and rule.parent_id in items:
            items[rule.parent_id]["children"].append(item)
        else:
            roots.append(item)
    return roots


def _section_rule_to_dict(rule: TemplateSectionRule) -> dict:
    return {
        "id": rule.id,
        "template_id": rule.template_id,
        "parent_id": rule.parent_id,
        "section_code": rule.section_code,
        "standard_title": rule.standard_title,
        "level": rule.level,
        "order_no": rule.order_no,
        "required": rule.required,
        "aliases": rule.aliases or [],
        "required_points": rule.required_points or [],
        "min_word_count": rule.min_word_count,
        "risk_level": rule.risk_level,
        "match_strategy": rule.match_strategy,
        "enabled": rule.enabled,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def get_review_template_service() -> Generator[ReviewTemplateService, None, None]:
    yield ReviewTemplateService()
