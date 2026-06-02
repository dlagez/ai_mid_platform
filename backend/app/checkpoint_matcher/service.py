from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.db.models import ChapterReviewProfile, CheckpointMatchResult, PlanSection, ReviewCheckpoint, ReviewTask
from app.rule_engine.matchers import normalize_text
from app.utils.exceptions import PlatformError


SELECTED_THRESHOLD = 0.25
FALLBACK_SELECTED_THRESHOLD = 0.20
MAX_SELECTED_PER_SECTION = 3


class CheckpointMatcherService:
    def list_task_matches(
        self,
        db: Session,
        task_id: int,
        *,
        status: str | None = None,
        matched_only: bool = False,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[list[CheckpointMatchResult], int]:
        task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
        if not task:
            raise PlatformError(f"Review task id={task_id} not found", status_code=404)
        query = (
            db.query(CheckpointMatchResult)
            .join(PlanSection, PlanSection.id == CheckpointMatchResult.section_id)
            .filter(
                CheckpointMatchResult.task_id == task.id,
                PlanSection.level >= 3,
            )
        )
        if status:
            query = query.filter(CheckpointMatchResult.status == status)
        elif matched_only:
            query = query.filter(CheckpointMatchResult.status != "candidate")
        total = query.count()
        query = query.options(joinedload(CheckpointMatchResult.checkpoint), joinedload(CheckpointMatchResult.section)).order_by(
            CheckpointMatchResult.section_id.asc(), CheckpointMatchResult.match_score.desc(), CheckpointMatchResult.id.asc()
        )
        if page is not None and page_size is not None:
            query = query.offset((page - 1) * page_size).limit(page_size)
        return query.all(), total

    def match_task_checkpoints(self, db: Session, task_id: int) -> dict[str, Any]:
        task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
        if not task:
            raise PlatformError(f"Review task id={task_id} not found", status_code=404)

        profiles = (
            db.query(ChapterReviewProfile)
            .join(PlanSection, PlanSection.id == ChapterReviewProfile.section_id)
            .filter(
                ChapterReviewProfile.task_id == task.id,
                ChapterReviewProfile.status == "active",
                PlanSection.level >= 3,
            )
            .order_by(ChapterReviewProfile.id.asc())
            .all()
        )
        if not profiles:
            profiles = (
                db.query(ChapterReviewProfile)
                .join(PlanSection, PlanSection.id == ChapterReviewProfile.section_id)
                .filter(
                    ChapterReviewProfile.task_id.is_(None),
                    ChapterReviewProfile.document_id == task.plan_document_id,
                    ChapterReviewProfile.status == "active",
                    PlanSection.level >= 3,
                )
                .order_by(ChapterReviewProfile.id.asc())
                .all()
            )
        if not profiles:
            raise PlatformError(
                "No chapter review profiles found. Generate chapter profiles from Upload Construction Plan before matching checkpoints.",
                status_code=400,
            )

        checkpoints = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.status == "active").order_by(ReviewCheckpoint.id.asc()).all()

        db.query(CheckpointMatchResult).filter(CheckpointMatchResult.task_id == task.id).delete(
            synchronize_session=False
        )
        existing_by_key: dict[tuple[int, int], CheckpointMatchResult] = {}
        best_score_by_key: dict[tuple[int, int], float] = {}
        status_by_key: dict[tuple[int, int], str] = {}
        for profile in profiles:
            scored_matches = []
            for checkpoint in checkpoints:
                score, dimensions, reason = score_checkpoint(profile, checkpoint)
                scored_matches.append(
                    {
                        "checkpoint": checkpoint,
                        "score": score,
                        "dimensions": dimensions,
                        "reason": reason,
                    }
                )
            selected_checkpoint_ids = _select_checkpoint_ids(scored_matches)

            for scored in scored_matches:
                checkpoint = scored["checkpoint"]
                score = scored["score"]
                dimensions = scored["dimensions"]
                reason = scored["reason"]
                row_key = (profile.section_id, checkpoint.id)
                previous_score = best_score_by_key.get(row_key)
                if previous_score is not None and previous_score > score:
                    continue
                best_score_by_key[row_key] = score
                status = "selected" if checkpoint.id in selected_checkpoint_ids else "candidate"
                status_by_key[row_key] = status
                row = existing_by_key.get(row_key)
                values = {
                    "task_id": task.id,
                    "section_id": profile.section_id,
                    "checkpoint_id": checkpoint.id,
                    "match_score": round(score, 2),
                    "match_reason": reason,
                    "match_dimensions": dimensions,
                    "status": status,
                    "updated_at": datetime.utcnow(),
                }
                if row:
                    for key, value in values.items():
                        setattr(row, key, value)
                else:
                    row = CheckpointMatchResult(**values)
                    db.add(row)
                    existing_by_key[row_key] = row
        db.commit()
        return {
            "task_id": task.id,
            "selected_count": sum(1 for status in status_by_key.values() if status == "selected"),
            "candidate_count": sum(1 for status in status_by_key.values() if status == "candidate"),
            "items": [],
        }


def score_checkpoint(profile: ChapterReviewProfile, checkpoint: ReviewCheckpoint) -> tuple[float, dict[str, Any], str]:
    object_match = _list_match(profile.object_terms or [], checkpoint.object_terms or [])
    context_match = _list_match(
        [profile.chapter_title or "", profile.chapter_path or ""],
        [checkpoint.clause_no or ""],
    )
    semantic_similarity = _semantic_similarity(profile, checkpoint)

    score = (
        object_match * 0.45
        + context_match * 0.25
        + semantic_similarity * 0.30
    )
    dimensions = {
        "object_match": round(object_match, 2),
        "context_match": round(context_match, 2),
        "semantic_similarity": round(semantic_similarity, 2),
    }
    reason_parts = [name for name, value in dimensions.items() if value > 0]
    reason = "命中维度：" + "、".join(reason_parts) if reason_parts else "未命中主要维度"
    return min(score, 1.0), dimensions, reason


def _semantic_similarity(profile: ChapterReviewProfile, checkpoint: ReviewCheckpoint) -> float:
    profile_text = " ".join(
        [
            profile.chapter_title or "",
            profile.chapter_path or "",
            profile.source_text or "",
            " ".join(profile.object_terms or []),
        ]
    )
    checkpoint_text = " ".join(
        [
            checkpoint.rule_text or "",
            checkpoint.clause_text or "",
            " ".join(checkpoint.object_terms or []),
        ]
    )
    left = _tokens(profile_text)
    right = _tokens(checkpoint_text)
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left | right), 1)


def _list_match(left_values: list | None, right_values: list | None) -> float:
    left = [normalize_text(_match_text(item)) for item in (left_values or []) if normalize_text(_match_text(item))]
    right = [normalize_text(_match_text(item)) for item in (right_values or []) if normalize_text(_match_text(item))]
    if not left or not right:
        return 0.0
    hits = 0
    for r_item in right:
        if any(_term_match(l_item, r_item) for l_item in left):
            hits += 1
    return min(1.0, hits / max(len(right), 1))


@lru_cache(maxsize=100_000)
def _term_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if right in left or left in right:
        return True
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / max(min(len(left_tokens), len(right_tokens)), 1) >= 0.6


def _select_checkpoint_ids(scored_matches: list[dict[str, Any]]) -> set[int]:
    ranked = sorted(
        scored_matches,
        key=lambda item: (
            item["score"],
            -(item["checkpoint"].id or 0),
        ),
        reverse=True,
    )
    selected = [item for item in ranked if item["score"] >= SELECTED_THRESHOLD][:MAX_SELECTED_PER_SECTION]
    if not selected and ranked and ranked[0]["score"] >= FALLBACK_SELECTED_THRESHOLD:
        selected = [ranked[0]]
    return {item["checkpoint"].id for item in selected}


def _match_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(str(item or "") for item in value.values())
    return str(value)


@lru_cache(maxsize=20_000)
def _tokens(text: str) -> frozenset[str]:
    normalized = normalize_text(text)
    tokens = {normalized[i : i + 2] for i in range(max(len(normalized) - 1, 0)) if len(normalized[i : i + 2]) == 2}
    return frozenset(token for token in tokens if token.strip())


def get_checkpoint_matcher_service() -> Generator[CheckpointMatcherService, None, None]:
    yield CheckpointMatcherService()
