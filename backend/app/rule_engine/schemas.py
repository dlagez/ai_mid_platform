from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReviewIssueCreate:
    issue_type: str
    risk_level: str
    issue_title: str
    issue_description: str | None = None
    plan_section_id: int | None = None
    plan_section_title: str | None = None
    plan_original_text: str | None = None
    source_type: str | None = None
    source_rule_id: int | None = None
    source_template_rule_id: int | None = None
    standard_clause_id: int | None = None
    ai_reason: str | None = None
    suggestion: str | None = None


@dataclass
class RuleExecutionLogCreate:
    rule_type: str | None
    status: str
    rule_id: int | None = None
    template_rule_id: int | None = None
    plan_section_id: int | None = None
    message: str | None = None
    matched_text: str | None = None
    expected_value: str | None = None
    actual_value: str | None = None
