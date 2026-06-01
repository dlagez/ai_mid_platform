from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ReviewTask, RuleExecutionLog
from app.rule_engine.schemas import RuleExecutionLogCreate


def run_standard_rule_review(task: ReviewTask, db: Session) -> None:
    """Standard rule review — currently disabled as ReviewRule has been removed."""
    pass
