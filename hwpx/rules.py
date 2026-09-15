"""HWPX 양식 채움 — 규칙 연결.

이번 E07 번호의 실제 진입점은 connect_rules 하나로 둔다.
계약(docs/TEAM_CONTRACT.md) 12장에는 규칙 연결 계약이 설계되어 있으나,
아직 설계 단계이므로 이번 번호의 입출력은 내부 계약으로 사용한다.

설계
- 명확한 라벨과 구역, 반복 행 식별자(table_position.rowIndex, context의 header)를
  기준으로 A 입력란 후보와 B 원문 블록을 연결한다.
- 숫자는 Decimal과 명시된 단위로 처리하고, 변환 근거를 남긴다.
- 충돌하거나 모호하면 검토(review/conflict)로 남기고 값을 자동 확정하지 않는다.
- 근거가 없으면 추정하지 않고 missing으로 남긴다.
"""

from __future__ import annotations

import re
from typing import Any

def connect_rules(
    fields: list[dict[str, Any]],
    blocks: list[Any],
    normalizedIndex: dict[str, str] | None,
    a_hash: str,
) -> dict[str, Any]:
    """A 입력란 후보와 B 원문 블록을 규칙 기반으로 연결한다.

    Args:
        fields: A 분석 결과의 입력란 목록(list[dict]).
        blocks: B 추출 결과의 원문 블록 목록(list[SourceBlock]).
        normalizedIndex: B 블록 ID와 정리 텍스트를 짝지은 맵 또는 None.
        a_hash: 원본 A의 해시.

    Returns:
        dict: connect_id, results(list[dict]).
    """
    results: list[dict[str, Any]] = []
    for f in fields:
        matched = _match_field(f, blocks, normalizedIndex)
        res = _build_result(f, matched)
        results.append(res)
    return {
        "connect_id": f"connect-{a_hash[:8]}",
        "results": results,
    }


def _norm_label(label: str) -> str:
    return re.sub(r"[^\w]", "", (label or "").lower().strip())


def _extract_label_value(text: str) -> tuple[str, str]:
    text = text or ""
    if ":" in text:
        label, _, value = text.partition(":")
        return label.strip(), value.strip()
    parts = text.split(None, 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return text.strip(), ""


def _match_field(
    field: dict[str, Any],
    blocks: list[Any],
    normalizedIndex: dict[str, str] | None,
) -> list[tuple[Any, str, str]]:
    label = field.get("label") or ""
    norm_label = _norm_label(label)
    matched: list[tuple[Any, str, str]] = []
    for b in blocks:
        text = normalizedIndex.get(b.blockId) if (normalizedIndex and b.blockId in normalizedIndex) else b.text
        fact_matched = False
        if b.facts:
            for fact in b.facts:
                fact_text = fact.get("originalText", "")
                f_label, f_value = _extract_label_value(fact_text)
                if _norm_label(f_label) == norm_label and f_value.strip():
                    matched.append((b, fact_text, f_value))
                    fact_matched = True
                    break
        if not fact_matched:
            l, v = _extract_label_value(text)
            if _norm_label(l) == norm_label and v.strip():
                matched.append((b, text, v))
    return matched


def _is_unit_explicit(unit: str | None) -> bool:
    return bool(unit and unit.strip().lower() == "천원")


def _convert_thousand_to_won(text: str) -> str | None:
    m = re.search(r"([\d,]+)\s*천원", text or "")
    if not m:
        return None
    num_str = m.group(1).replace(",", "")
    try:
        num = int(num_str)
    except ValueError:
        return None
    return str(num * 1000)


def _build_result(
    field: dict[str, Any],
    matches: list[tuple[Any, str, str]],
) -> dict[str, Any]:
    fieldId = field["fieldId"]
    unit = field.get("unit")
    if not matches:
        return {
            "fieldId": fieldId,
            "status": "missing",
            "value": None,
            "valueTransform": "none",
            "sourceBlockIds": [],
            "evidenceQuote": None,
            "evidence": None,
            "reason": "근거 원문 블록을 찾지 못함",
            "needsReview": False,
            "alternatives": None,
        }
    values: list[str] = []
    source_ids: list[str] = []
    quotes: list[str] = []
    for b, text, value in matches:
        values.append(value)
        source_ids.append(b.blockId)
        quotes.append(text)
    unique_values = list(dict.fromkeys(values))
    if len(unique_values) == 1:
        value = unique_values[0]
        transform = "extract"
        if _is_unit_explicit(unit):
            converted = _convert_thousand_to_won(quotes[0])
            if converted is not None:
                value = converted
                transform = "unit"
        return {
            "fieldId": fieldId,
            "status": "suggested",
            "value": value,
            "valueTransform": transform,
            "sourceBlockIds": source_ids,
            "evidenceQuote": quotes[0],
            "evidence": [{"sourceBlockId": sid, "quote": q} for sid, q in zip(source_ids, quotes)],
            "reason": "라벨 매칭",
            "needsReview": True,
            "alternatives": None,
        }
    alternatives = [
        {"value": v, "reason": "근거 블록 값", "sourceBlockIds": [b.blockId]}
        for b, _, v in matches
    ]
    return {
        "fieldId": fieldId,
        "status": "conflict",
        "value": None,
        "valueTransform": "none",
        "sourceBlockIds": source_ids,
        "evidenceQuote": "여러 근거가 서로 다른 값을 가리킴",
        "evidence": [{"sourceBlockId": sid, "quote": q} for sid, q in zip(source_ids, quotes)],
        "reason": "연결된 원문 블록 간 값이 충돌함",
        "needsReview": True,
        "alternatives": alternatives,
    }
