from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.db.models import ChapterReviewProfile, CheckpointMatchResult, PlanSection, ReviewCheckpoint, ReviewTask
from app.rule_engine.matchers import normalize_text
from app.utils.exceptions import PlatformError


SELECTED_THRESHOLD = 0.45
MAX_SELECTED_PER_SECTION = 3
RERANK_CANDIDATE_LIMIT_PER_SECTION = 12
MIN_PRIMARY_OBJECT_MATCH = 0.5
MIN_RERANK_SCORE = 0.55
MIN_STRONG_SEMANTIC_WITHOUT_OBJECT = 0.35

GENERIC_TERMS = {
    "一般",
    "严格",
    "要求",
    "规定",
    "符合",
    "不得",
    "严禁",
    "应当",
    "必须",
    "施工",
    "工程",
    "现场",
    "人员",
    "作业",
    "安全",
    "质量",
    "措施",
    "技术",
    "检查",
    "验收",
    "管理",
    "材料",
    "设备",
    "构造",
    "安装",
    "拆除",
    "浇筑",
    "养护",
    "设置",
    "采用",
    "进行",
    "组织",
    "方案",
    "体系",
    "标准",
    "阶段",
    "小组",
    "组长",
    "成员",
    "项目",
    "结构",
    "模板",
    "支撑",
    "混凝土",
    "钢筋",
    "钢管",
    "荷载",
    "架体",
    "脚手架",
}

GENERIC_PHRASES = {
    "施工人员",
    "施工设备",
    "安全措施",
    "技术措施",
    "质量控制",
    "检查验收",
    "模板工程",
    "混凝土浇筑",
}

NORMALIZED_GENERIC_TERMS = {normalize_text(item) for item in GENERIC_TERMS}
NORMALIZED_GENERIC_PHRASES = {normalize_text(item) for item in GENERIC_PHRASES}


@dataclass
class SectionMatchProfile:
    section_id: int
    object_terms: list[str]
    chapter_title: str | None = None
    chapter_path: str | None = None
    evidence_text: str | None = None


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
        rows = query.all()
        self._attach_match_profiles(db, task, rows)
        return rows, total

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
        section_profiles = _merge_profiles_by_section(profiles)

        checkpoints = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.status == "active").order_by(ReviewCheckpoint.id.asc()).all()

        db.query(CheckpointMatchResult).filter(CheckpointMatchResult.task_id == task.id).delete(
            synchronize_session=False
        )
        best_by_key: dict[tuple[int, int], dict[str, Any]] = {}
        for profile in section_profiles:
            for checkpoint in checkpoints:
                score, dimensions, reason = score_checkpoint(profile, checkpoint)
                row_key = (profile.section_id, checkpoint.id)
                previous = best_by_key.get(row_key)
                if previous is not None and previous["score"] > score:
                    continue
                best_by_key[row_key] = {
                    "profile": profile,
                    "checkpoint": checkpoint,
                    "score": score,
                    "dimensions": dimensions,
                    "reason": reason,
                }

        selected_keys = _select_section_checkpoint_keys(best_by_key)
        now = datetime.utcnow()
        for section_id, checkpoint_id in selected_keys:
            scored = best_by_key[(section_id, checkpoint_id)]
            db.add(
                CheckpointMatchResult(
                    task_id=task.id,
                    section_id=section_id,
                    checkpoint_id=checkpoint_id,
                    match_score=round(scored["score"], 2),
                    match_reason=scored["reason"],
                    match_dimensions=scored["dimensions"],
                    status="selected",
                    updated_at=now,
                )
            )
        db.commit()
        return {
            "task_id": task.id,
            "selected_count": len(selected_keys),
            "candidate_count": 0,
            "items": [],
        }

    def _attach_match_profiles(
        self,
        db: Session,
        task: ReviewTask,
        rows: list[CheckpointMatchResult],
    ) -> None:
        section_ids = {row.section_id for row in rows}
        if not section_ids:
            return
        profiles = (
            db.query(ChapterReviewProfile)
            .filter(
                ChapterReviewProfile.section_id.in_(section_ids),
                ChapterReviewProfile.status == "active",
                (
                    (ChapterReviewProfile.task_id == task.id)
                    | (
                        (ChapterReviewProfile.task_id.is_(None))
                        & (ChapterReviewProfile.document_id == task.plan_document_id)
                    )
                ),
            )
            .order_by(ChapterReviewProfile.task_id.desc().nullslast(), ChapterReviewProfile.id.asc())
            .all()
        )
        profile_by_section_id: dict[int, ChapterReviewProfile] = {}
        for profile in profiles:
            profile_by_section_id.setdefault(profile.section_id, profile)
        for row in rows:
            row.profile = profile_by_section_id.get(row.section_id)


def score_checkpoint(profile: ChapterReviewProfile | SectionMatchProfile, checkpoint: ReviewCheckpoint) -> tuple[float, dict[str, Any], str]:
    object_match, object_pairs = _list_match(profile.object_terms or [], checkpoint.object_terms or [])
    context_match, context_pairs = _context_match(profile, checkpoint)
    semantic_similarity = _semantic_similarity(profile, checkpoint)

    score = (
        object_match * 0.65
        + context_match * 0.15
        + semantic_similarity * 0.20
    )
    dimensions = {
        "object_match": round(object_match, 2),
        "context_match": round(context_match, 2),
        "semantic_similarity": round(semantic_similarity, 2),
        "object_pairs": object_pairs,
        "context_pairs": context_pairs,
    }
    reason = _build_reason(dimensions)
    return min(score, 1.0), dimensions, reason


def _semantic_similarity(profile: ChapterReviewProfile | SectionMatchProfile, checkpoint: ReviewCheckpoint) -> float:
    profile_text = " ".join(
        [
            profile.chapter_title or "",
            profile.chapter_path or "",
            " ".join(profile.object_terms or []),
            profile.evidence_text or "",
        ]
    )
    checkpoint_text = " ".join(
        [
            checkpoint.rule_text or "",
            " ".join(checkpoint.object_terms or []),
        ]
    )
    left = _tokens(profile_text)
    right = _tokens(checkpoint_text)
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left | right), 1)


def _context_match(profile: ChapterReviewProfile | SectionMatchProfile, checkpoint: ReviewCheckpoint) -> tuple[float, list[dict[str, str]]]:
    checkpoint_context = _extract_signal_terms(checkpoint.rule_text or "")
    return _list_match(
        [
            profile.chapter_title or "",
            profile.chapter_path or "",
            *(profile.object_terms or []),
        ],
        checkpoint_context,
        allow_generic=False,
    )


def _list_match(
    left_values: list | None,
    right_values: list | None,
    *,
    allow_generic: bool = False,
) -> tuple[float, list[dict[str, str]]]:
    left = _normalized_terms(left_values, allow_generic=allow_generic)
    right = _normalized_terms(right_values, allow_generic=allow_generic)
    if not left or not right:
        return 0.0, []
    hits = 0
    pairs: list[dict[str, str]] = []
    for r_raw, r_item in right:
        matched_left = next((l_raw for l_raw, l_item in left if _term_match(l_item, r_item)), None)
        if matched_left:
            hits += 1
            pairs.append({"left": matched_left, "right": r_raw})
    return min(1.0, hits / max(len(right), 1)), pairs


@lru_cache(maxsize=100_000)
def _term_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if _is_generic_term(left) or _is_generic_term(right):
        return False
    if left == right and len(left) >= 2:
        return True
    shorter = min(len(left), len(right))
    longer = max(len(left), len(right))
    if shorter < 3:
        return False
    if right in left or left in right:
        if shorter / max(longer, 1) < 0.5 and shorter < 5:
            return False
        return True
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / max(min(len(left_tokens), len(right_tokens)), 1)
    jaccard = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return overlap >= 0.75 and jaccard >= 0.35


def _select_section_checkpoint_keys(best_by_key: dict[tuple[int, int], dict[str, Any]]) -> set[tuple[int, int]]:
    by_section: dict[int, list[tuple[tuple[int, int], dict[str, Any]]]] = defaultdict(list)
    for key, scored in best_by_key.items():
        by_section[key[0]].append((key, scored))

    selected: set[tuple[int, int]] = set()
    for section_items in by_section.values():
        ranked = sorted(
            section_items,
            key=lambda item: (
                item[1]["score"],
                -(item[0][1] or 0),
            ),
            reverse=True,
        )
        reranked = _rerank_section_candidates(ranked[:RERANK_CANDIDATE_LIMIT_PER_SECTION])
        for key, scored in reranked[:MAX_SELECTED_PER_SECTION]:
            if _is_selectable(scored):
                selected.add(key)
    return selected


def _rerank_section_candidates(
    candidates: list[tuple[tuple[int, int], dict[str, Any]]],
) -> list[tuple[tuple[int, int], dict[str, Any]]]:
    reranked: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for key, scored in candidates:
        dimensions = scored["dimensions"]
        rerank_score = _local_rerank_score(scored)
        dimensions["rerank_score"] = round(rerank_score, 2)
        dimensions["rerank_decision"] = "accepted" if rerank_score >= MIN_RERANK_SCORE else "rejected"
        scored["score"] = min(1.0, scored["score"] * 0.7 + rerank_score * 0.3)
        scored["reason"] = _build_reason(dimensions)
        reranked.append((key, scored))
    return sorted(
        reranked,
        key=lambda item: (
            item[1]["dimensions"].get("rerank_score", 0),
            item[1]["score"],
            -(item[0][1] or 0),
        ),
        reverse=True,
    )


def _local_rerank_score(scored: dict[str, Any]) -> float:
    dimensions = scored["dimensions"]
    object_match = float(dimensions.get("object_match") or 0)
    context_match = float(dimensions.get("context_match") or 0)
    semantic_similarity = float(dimensions.get("semantic_similarity") or 0)
    object_pairs = dimensions.get("object_pairs") or []
    context_pairs = dimensions.get("context_pairs") or []

    strong_object_bonus = 0.15 if _has_specific_pairs(object_pairs) else 0.0
    context_bonus = 0.08 if _has_specific_pairs(context_pairs) else 0.0
    weak_penalty = 0.25 if not object_pairs else 0.0
    return max(
        0.0,
        min(
            1.0,
            object_match * 0.72
            + context_match * 0.10
            + semantic_similarity * 0.18
            + strong_object_bonus
            + context_bonus
            - weak_penalty,
        ),
    )


def _is_selectable(scored: dict[str, Any]) -> bool:
    dimensions = scored["dimensions"]
    object_match = float(dimensions.get("object_match") or 0)
    semantic_similarity = float(dimensions.get("semantic_similarity") or 0)
    rerank_score = float(dimensions.get("rerank_score") or 0)
    if scored["score"] < SELECTED_THRESHOLD or rerank_score < MIN_RERANK_SCORE:
        return False
    if object_match >= MIN_PRIMARY_OBJECT_MATCH and _has_specific_pairs(dimensions.get("object_pairs") or []):
        return True
    return semantic_similarity >= MIN_STRONG_SEMANTIC_WITHOUT_OBJECT


def _build_reason(dimensions: dict[str, Any]) -> str:
    labels = []
    for key, label in [
        ("object_match", "对象"),
        ("context_match", "上下文"),
        ("semantic_similarity", "语义"),
        ("rerank_score", "二阶段"),
    ]:
        value = float(dimensions.get(key) or 0)
        if value > 0:
            labels.append(f"{label}={value:.2f}")
    decision = dimensions.get("rerank_decision")
    if decision:
        labels.append(f"rerank={decision}")
    return "；".join(labels) if labels else "未命中主要维度"


def _has_specific_pairs(pairs: list[dict[str, str]]) -> bool:
    return any(
        not _is_generic_term(normalize_text(pair.get("left") or ""))
        and not _is_generic_term(normalize_text(pair.get("right") or ""))
        for pair in pairs
    )


def _match_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(str(item or "") for item in value.values())
    return str(value)


def _merge_profiles_by_section(profiles: list[ChapterReviewProfile]) -> list[SectionMatchProfile]:
    grouped: dict[int, list[ChapterReviewProfile]] = defaultdict(list)
    for profile in profiles:
        grouped[profile.section_id].append(profile)

    merged: list[SectionMatchProfile] = []
    for section_id, rows in grouped.items():
        first = rows[0]
        object_terms = _unique_limited(
            term
            for row in rows
            for term in (row.object_terms or [])
        )
        evidence_text = "\n".join(
            _unique_limited(
                (row.evidence_text or "").strip()
                for row in rows
                if (row.evidence_text or "").strip()
            )[:30]
        )
        merged.append(
            SectionMatchProfile(
                section_id=section_id,
                object_terms=object_terms,
                chapter_title=first.chapter_title,
                chapter_path=first.chapter_path,
                evidence_text=evidence_text[:4000],
            )
        )
    return merged


def _unique_limited(values: Any, limit: int = 80) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        normalized = normalize_text(text)
        if not text or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _normalized_terms(values: list | None, *, allow_generic: bool) -> list[tuple[str, str]]:
    terms: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in values or []:
        raw = _match_text(item).strip()
        normalized = normalize_text(raw)
        if not normalized or normalized in seen:
            continue
        if not allow_generic and _is_generic_term(normalized):
            continue
        seen.add(normalized)
        terms.append((raw, normalized))
    return terms


def _extract_signal_terms(text: str) -> list[str]:
    terms: list[str] = []
    for phrase in re.split(r"[，,。；;：:（）()【】\[\]《》<>、\s]+", text):
        cleaned = phrase.strip()
        if cleaned and not _is_generic_term(normalize_text(cleaned)):
            terms.append(cleaned)
    return terms[:20]


def _is_generic_term(term: str) -> bool:
    if not term or len(term) < 2:
        return True
    if term in NORMALIZED_GENERIC_TERMS or term in NORMALIZED_GENERIC_PHRASES:
        return True
    if len(term) <= 4 and any(generic in term for generic in NORMALIZED_GENERIC_TERMS):
        return True
    return False


@lru_cache(maxsize=20_000)
def _tokens(text: str) -> frozenset[str]:
    normalized = normalize_text(text)
    tokens = {normalized[i : i + 2] for i in range(max(len(normalized) - 1, 0)) if len(normalized[i : i + 2]) == 2}
    return frozenset(token for token in tokens if token.strip())


def get_checkpoint_matcher_service() -> Generator[CheckpointMatcherService, None, None]:
    yield CheckpointMatcherService()
