from __future__ import annotations

from collections.abc import Generator
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import ReviewIssue, ReviewTask
from app.review_issues.schemas import ReviewIssueConfirmRequest
from app.utils.exceptions import PlatformError

ISSUE_ACTIONS = {"accepted", "ignored", "modified", "closed"}
RISK_LEVELS = {"critical", "major", "minor", "suggestion"}


class ReviewIssueService:
    def get_issue(self, db: Session, issue_id: int) -> ReviewIssue:
        issue = db.query(ReviewIssue).filter(ReviewIssue.id == issue_id).first()
        if not issue:
            raise PlatformError(f"Review issue id={issue_id} not found", status_code=404)
        return issue

    def confirm_issue(
        self,
        db: Session,
        issue_id: int,
        data: ReviewIssueConfirmRequest,
        confirmed_by: int | None = None,
    ) -> ReviewIssue:
        if data.action not in ISSUE_ACTIONS:
            raise PlatformError(f"Invalid issue action: {data.action}", status_code=400)
        if data.risk_level and data.risk_level not in RISK_LEVELS:
            raise PlatformError(f"Invalid risk_level: {data.risk_level}", status_code=400)

        issue = self.get_issue(db, issue_id)
        issue.status = data.action
        issue.expert_comment = data.expert_comment
        issue.confirmed_by = confirmed_by
        issue.confirmed_at = datetime.utcnow()

        if data.action == "modified":
            for field in ("issue_title", "issue_description", "risk_level", "suggestion"):
                value = getattr(data, field)
                if value is not None:
                    setattr(issue, field, value)

        self._refresh_task_status(db, issue.task_id)
        db.commit()
        db.refresh(issue)
        return issue

    def _refresh_task_status(self, db: Session, task_id: int) -> None:
        task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
        if not task:
            return
        issues = db.query(ReviewIssue).filter(ReviewIssue.task_id == task_id, ReviewIssue.version == task.version).all()
        task.total_issue_count = len(issues)
        task.critical_issue_count = sum(1 for issue in issues if issue.risk_level == "critical")
        task.major_issue_count = sum(1 for issue in issues if issue.risk_level == "major")
        task.minor_issue_count = sum(1 for issue in issues if issue.risk_level == "minor")
        if not any(issue.status == "pending_confirm" for issue in issues):
            task.status = "completed"
            task.finished_at = task.finished_at or datetime.utcnow()


def get_review_issue_service() -> Generator[ReviewIssueService, None, None]:
    yield ReviewIssueService()
