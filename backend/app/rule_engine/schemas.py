from __future__ import annotations

from dataclasses import dataclass


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
