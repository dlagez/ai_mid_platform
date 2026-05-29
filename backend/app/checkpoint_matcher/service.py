from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.db.models import ChapterReviewProfile, CheckpointMatchResult, ReviewCheckpoint, ReviewTask
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
        query = db.query(CheckpointMatchResult).filter(CheckpointMatchResult.task_id == task.id)
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
            .filter(ChapterReviewProfile.task_id == task.id)
            .order_by(ChapterReviewProfile.id.asc())
            .all()
        )
        if not profiles:
            profiles = (
                db.query(ChapterReviewProfile)
                .filter(
                    ChapterReviewProfile.task_id.is_(None),
                    ChapterReviewProfile.document_id == task.plan_document_id,
                )
                .order_by(ChapterReviewProfile.id.asc())
                .all()
            )
        if not profiles:
            raise PlatformError(
                "No chapter review profiles found. Generate chapter profiles from Upload Construction Plan before matching checkpoints.",
                status_code=400,
            )

        checkpoint_query = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.status == "active")
        if task.work_type:
            scoped_query = checkpoint_query.filter(
                or_(ReviewCheckpoint.work_type == task.work_type, ReviewCheckpoint.work_type.is_(None), ReviewCheckpoint.work_type == "")
            )
            checkpoints = scoped_query.order_by(ReviewCheckpoint.priority.desc(), ReviewCheckpoint.id.asc()).all()
            if not checkpoints:
                checkpoints = checkpoint_query.order_by(ReviewCheckpoint.priority.desc(), ReviewCheckpoint.id.asc()).all()
        else:
            checkpoints = checkpoint_query.order_by(ReviewCheckpoint.priority.desc(), ReviewCheckpoint.id.asc()).all()

        selected_count = 0
        candidate_count = 0
        existing_rows = (
            db.query(CheckpointMatchResult)
            .filter(CheckpointMatchResult.task_id == task.id)
            .all()
        )
        existing_by_key = {(row.section_id, row.checkpoint_id): row for row in existing_rows}
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
                status = "selected" if checkpoint.id in selected_checkpoint_ids else "candidate"
                if status == "selected":
                    selected_count += 1
                else:
                    candidate_count += 1
                row = existing_by_key.get((profile.section_id, checkpoint.id))
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
                    existing_by_key[(profile.section_id, checkpoint.id)] = row
        db.commit()
        return {
            "task_id": task.id,
            "selected_count": selected_count,
            "candidate_count": candidate_count,
            "items": [],
        }


def score_checkpoint(profile: ChapterReviewProfile, checkpoint: ReviewCheckpoint) -> tuple[float, dict[str, Any], str]:
    chapter_type_match = _chapter_type_match(profile.chapter_type, checkpoint.chapter_types)
    object_match = _object_match(profile.construction_objects or [], checkpoint.target_objects or [])
    parameter_match = _list_match(_profile_parameter_terms(profile.mentioned_parameters or []), checkpoint.target_parameters or [])
    scenario_match = _scenario_match(profile, checkpoint)
    missing_expectation_match = _list_match(profile.expected_missing_objects or [], (checkpoint.expected_items or []) + (checkpoint.target_objects or []))
    title_keyword_match = _title_keyword_match(profile, checkpoint)
    mandatory_boost = 1.0 if checkpoint.is_mandatory else 0.0
    semantic_similarity = _semantic_similarity(profile, checkpoint)

    score = (
        chapter_type_match * 0.20
        + object_match * 0.25
        + parameter_match * 0.15
        + scenario_match * 0.15
        + missing_expectation_match * 0.10
        + title_keyword_match * 0.10
        + mandatory_boost * 0.03
        + semantic_similarity * 0.02
    )
    dimensions = {
        "chapter_type_match": round(chapter_type_match, 2),
        "construction_object_match": round(object_match, 2),
        "parameter_match": round(parameter_match, 2),
        "scenario_match": round(scenario_match, 2),
        "missing_expectation_match": round(missing_expectation_match, 2),
        "title_keyword_match": round(title_keyword_match, 2),
        "mandatory_boost": round(mandatory_boost, 2),
        "semantic_similarity": round(semantic_similarity, 2),
    }
    reason_parts = [name for name, value in dimensions.items() if value > 0]
    reason = "命中维度：" + "、".join(reason_parts) if reason_parts else "未命中主要维度"
    return min(score, 1.0), dimensions, reason


def _chapter_type_match(chapter_type: str | None, checkpoint_types: list | None) -> float:
    if not chapter_type or not checkpoint_types:
        return 0.0
    normalized = normalize_text(chapter_type)
    candidates = [normalize_text(str(item)) for item in checkpoint_types]
    if normalized in candidates:
        return 1.0
    chapter_alias = _chapter_type_alias(chapter_type)
    if any(chapter_alias and chapter_alias == _chapter_type_alias(item) for item in checkpoint_types):
        return 0.8
    return 0.0


def _chapter_type_alias(value: Any) -> str:
    text = str(value)
    if text in {"construction_technology", "construction_process", "施工工艺", "施工技术", "工艺技术", "施工方法", "施工流程"}:
        return "construction_process"
    if text in {"safety_control", "safety_measure", "安全措施", "安全管理"}:
        return "safety_measure"
    if text in {"quality_control", "质量控制", "质量管理", "质量保证"}:
        return "quality_control"
    if text in {"technical_preparation", "技术准备", "施工准备"}:
        return "technical_preparation"
    if text in {"layout", "施工平面布置", "平面布置", "场地准备"}:
        return "layout"
    if text in {"emergency", "emergency_plan", "应急预案", "应急处置"}:
        return "emergency_plan"
    if text in {"calculation", "计算书", "验算"}:
        return "calculation"
    if text in {"project_overview", "工程概况"}:
        return "project_overview"
    return normalize_text(text)


def _object_match(profile_objects: list[dict[str, Any]], target_objects: list | None) -> float:
    if not target_objects:
        return 0.0
    profile_terms: list[str] = []
    for item in profile_objects:
        profile_terms.append(str(item.get("object_name", "")))
        profile_terms.append(str(item.get("object_type", "")))
        profile_terms.extend(str(term) for term in item.get("matched_terms") or [])
        profile_terms.extend(str(term) for term in item.get("related_scenarios") or [])
        profile_terms.extend(str(term) for term in item.get("related_parameters") or [])
    return _list_match(profile_terms, target_objects)


def _scenario_match(profile: ChapterReviewProfile, checkpoint: ReviewCheckpoint) -> float:
    profile_terms = (profile.mentioned_methods or []) + (profile.mentioned_risks or []) + (profile.subdomains or [])
    checkpoint_terms = (checkpoint.keywords or []) + list((checkpoint.applicable_condition or {}).values())
    return _list_match(profile_terms, checkpoint_terms)


def _title_keyword_match(profile: ChapterReviewProfile, checkpoint: ReviewCheckpoint) -> float:
    profile_terms = [
        profile.chapter_title or "",
        profile.chapter_path or "",
        profile.summary or "",
        profile.main_domain or "",
        *(profile.subdomains or []),
    ]
    checkpoint_terms = [
        checkpoint.checkpoint_name or "",
        checkpoint.check_goal or "",
        checkpoint.work_type or "",
        *(checkpoint.chapter_types or []),
        *(checkpoint.target_objects or []),
        *(checkpoint.keywords or []),
        *(checkpoint.expected_items or []),
    ]
    return _list_match(profile_terms, checkpoint_terms)


def _semantic_similarity(profile: ChapterReviewProfile, checkpoint: ReviewCheckpoint) -> float:
    profile_text = " ".join(
        [
            profile.chapter_title or "",
            profile.summary or "",
            " ".join(profile.mentioned_methods or []),
            " ".join(_profile_parameter_terms(profile.mentioned_parameters or [])),
        ]
    )
    checkpoint_text = " ".join(
        [
            checkpoint.checkpoint_name or "",
            checkpoint.check_goal or "",
            checkpoint.clause_text or "",
            " ".join(checkpoint.keywords or []),
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
            item["checkpoint"].priority or 0,
            -(item["checkpoint"].id or 0),
        ),
        reverse=True,
    )
    selected = [item for item in ranked if item["score"] >= SELECTED_THRESHOLD][:MAX_SELECTED_PER_SECTION]
    if not selected and ranked and ranked[0]["score"] >= FALLBACK_SELECTED_THRESHOLD:
        selected = [ranked[0]]
    return {item["checkpoint"].id for item in selected}


def _profile_parameter_terms(parameters: list | None) -> list[str]:
    terms: list[str] = []
    for item in parameters or []:
        if isinstance(item, dict):
            terms.extend(str(item.get(key) or "") for key in ("name", "value", "unit", "source_text"))
        else:
            terms.append(str(item))
    return [term.strip() for term in terms if term.strip()]


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
