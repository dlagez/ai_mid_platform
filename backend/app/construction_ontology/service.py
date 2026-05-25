from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ConstructionObject
from app.rule_engine.matchers import normalize_text


@dataclass(frozen=True)
class ConstructionObjectHit:
    object_code: str | None
    object_name: str
    object_type: str | None
    matched_terms: list[str]
    related_parameters: list[str]
    related_scenarios: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_code": self.object_code,
            "object_name": self.object_name,
            "object_type": self.object_type,
            "matched_terms": self.matched_terms,
            "related_parameters": self.related_parameters,
            "related_scenarios": self.related_scenarios,
        }


BUILTIN_OBJECTS: tuple[dict[str, Any], ...] = (
    {
        "object_code": "OBJ-PAN-KOU-JIA",
        "object_name": "盘扣架",
        "object_type": "support_system",
        "aliases": ["承插型盘扣式钢管脚手架", "盘扣式支架", "盘扣式脚手架", "盘扣支架"],
        "related_parameters": ["立杆间距", "步距", "水平杆", "扫地杆", "自由端高度", "可调托撑"],
        "related_scenarios": ["搭设", "拆除", "浇筑", "验收"],
    },
    {
        "object_code": "OBJ-JIA-TI",
        "object_name": "架体",
        "object_type": "support_system",
        "aliases": ["支撑架", "支架体系", "脚手架架体"],
        "related_parameters": ["架体高度", "立杆间距", "步距", "连墙件", "剪刀撑"],
        "related_scenarios": ["搭设", "验收", "拆除"],
    },
    {
        "object_code": "OBJ-JIAN-DAO-CHENG",
        "object_name": "剪刀撑",
        "object_type": "bracing",
        "aliases": ["竖向剪刀撑", "水平剪刀撑", "斜撑"],
        "related_parameters": ["设置间距", "搭接长度", "角度"],
        "related_scenarios": ["构造", "搭设", "验收"],
    },
    {
        "object_code": "OBJ-JI-CHU",
        "object_name": "基础构造",
        "object_type": "foundation",
        "aliases": ["基础", "地基", "垫板", "底座", "排水措施"],
        "related_parameters": ["承载力", "垫板厚度", "排水坡度"],
        "related_scenarios": ["基础处理", "承载力验算", "排水"],
    },
    {
        "object_code": "OBJ-HUN-NING-TU-JIAO-ZHU",
        "object_name": "混凝土浇筑",
        "object_type": "procedure",
        "aliases": ["浇筑", "混凝土施工", "浇筑顺序", "浇筑速度"],
        "related_parameters": ["浇筑速度", "分层厚度", "侧压力"],
        "related_scenarios": ["浇筑", "振捣", "养护"],
    },
    {
        "object_code": "OBJ-CHAI-CHU",
        "object_name": "拆除",
        "object_type": "procedure",
        "aliases": ["拆架", "拆模", "拆除顺序", "架体拆除"],
        "related_parameters": ["拆除顺序", "警戒范围"],
        "related_scenarios": ["拆除", "安全防护", "验收"],
    },
)


def recognize_construction_objects(db: Session, text: str | None) -> list[dict[str, Any]]:
    if not text:
        return []

    objects = list(BUILTIN_OBJECTS)
    objects.extend(
        {
            "object_code": item.object_code,
            "object_name": item.object_name,
            "object_type": item.object_type,
            "aliases": item.aliases or [],
            "related_parameters": item.related_parameters or [],
            "related_scenarios": item.related_scenarios or [],
        }
        for item in db.query(ConstructionObject).order_by(ConstructionObject.id.asc()).all()
    )

    normalized_text = normalize_text(text)
    hits: list[ConstructionObjectHit] = []
    seen: set[str] = set()
    for item in objects:
        terms = [item.get("object_name"), *(item.get("aliases") or [])]
        matched = [term for term in terms if term and normalize_text(term) in normalized_text]
        if not matched:
            continue
        key = item.get("object_code") or item.get("object_name")
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            ConstructionObjectHit(
                object_code=item.get("object_code"),
                object_name=str(item.get("object_name") or matched[0]),
                object_type=item.get("object_type"),
                matched_terms=matched,
                related_parameters=[str(x) for x in item.get("related_parameters") or []],
                related_scenarios=[str(x) for x in item.get("related_scenarios") or []],
            )
        )
    return [hit.as_dict() for hit in hits]
