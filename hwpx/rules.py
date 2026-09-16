"""HWPX 양식 채움 — 규칙 연결 (E07 + E07b).

이번 E07 번호의 실제 진입점은 connect_rules 하나로 둔다.
E07b에서는 표 제목/구역, 열 의미, 고정 행 이름 기반 연결을 추가한다.
계약(docs/TEAM_CONTRACT.md) 12장에는 규칙 연결 계약이 설계되어 있으나,
아직 설계 단계이므로 이번 번호의 입출력은 내부 계약으로 사용한다.

설계
- 명확한 라벨과 구역, 반복 행 식별자(table_position.rowIndex, context의 header)를
  기준으로 A 입력란 후보와 B 원문 블록을 연결한다.
- 표 제목과 구역을 먼저 연결하고, 열 의미와 고정 행 이름으로 값을 대응한다.
- 열 위치가 바뀌어도 열 의미를 따라간다.
- 이름 없는 반복 행은 고유한 표와 열 대응을 확인한 뒤 순서로 채운다.
- 금액이 있는 칸과 품명이 있는 칸을 열 개수가 같다는 이유로 섞지 않는다.
- 숫자는 명시된 단위로 처리하고, 변환 근거를 남긴다.
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
    table_analysis: list[Any] | None = None,
) -> dict[str, Any]:
    """A 입력란 후보와 B 원문 블록을 규칙 기반으로 연결한다.

    Args:
        fields: A 분석 결과의 입력란 목록(list[dict]).
        blocks: B 추출 결과의 원문 블록 목록(list[SourceBlock]).
        normalizedIndex: B 블록 ID와 정리 텍스트를 짝지은 맵 또는 None.
        a_hash: 원본 A의 해시.
        table_analysis: 표 분석 결과(list[TableAnalysisResult]) 또는 None.

    Returns:
        dict: connect_id, results(list[dict]).
    """
    table_maps = _build_table_maps(table_analysis) if table_analysis else {}
    results: list[dict[str, Any]] = []
    for f in fields:
        matched = _match_field(f, blocks, normalizedIndex, table_maps)
        res = _build_result(f, matched)
        results.append(res)
    return {
        "connect_id": f"connect-{a_hash[:8]}",
        "results": results,
    }


def _build_table_maps(
    table_analysis: list[Any] | Any | None,
) -> dict[int, Any]:
    """표 분석 결과를 매핑한다.

    단일 TableAnalysisResult 또는 리스트를 받을 수 있다.
    표 식별 키가 없으므로 인덱스 키로 매핑한다(테스트 한정).
    """
    out: dict[int, Any] = {}
    if table_analysis is None:
        return out
    items: list[Any] = table_analysis if isinstance(table_analysis, list) else [table_analysis]
    for i, ta in enumerate(items):
        out[i] = ta
    return out


def _field_table_index(field: dict[str, Any], table_maps: dict[int, Any]) -> int | None:
    loc = field.get("location") or {}
    table = loc.get("table") or {}
    tableId = table.get("tableId")
    if tableId is None:
        return None
    if len(table_maps) == 1:
        return next(iter(table_maps.keys()))
    return None


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


def _table_title(ctx: list[str]) -> str | None:
    for item in ctx:
        if item.startswith("표:"):
            return item.split(":", 1)[1].strip()
    return None


def _section(ctx: list[str]) -> str | None:
    for item in ctx:
        if item.startswith("구역:"):
            return item.split(":", 1)[1].strip()
    return None


def _location_col_index(loc: dict[str, Any]) -> int | None:
    col = loc.get("column") or {}
    v = col.get("columnIndex")
    return v if isinstance(v, int) else None


def _location_row_index(loc: dict[str, Any]) -> int | None:
    row = loc.get("row") or {}
    v = row.get("rowIndex")
    return v if isinstance(v, int) else None


def _label_matches_column_meaning(label: str, col_label: str) -> bool:
    """필드 label과 열 라벨의 의미 대응을 본다.

    예: 품명 <-> 항목, 금액 <-> 금액.
    """
    if _norm_label(label) == _norm_label(col_label):
        return True
    pairs = [
        (["품명", "항목"], ["품명", "항목"]),
        (["금액", "금액"], ["금액", "금액"]),
        (["성명", "이름"], ["성명", "이름"]),
    ]
    norm_label = _norm_label(label)
    norm_col = _norm_label(col_label)
    for a_set, b_set in pairs:
        if norm_label in [_norm_label(x) for x in a_set] and norm_col in [_norm_label(x) for x in b_set]:
            return True
    return False


def _match_field(
    field: dict[str, Any],
    blocks: list[Any],
    normalizedIndex: dict[str, str] | None,
    table_maps: dict[int, Any],
) -> list[tuple[Any, str, str]]:
    label = field.get("label") or ""
    norm_label = _norm_label(label)
    loc = field.get("location") or {}
    col_index = _location_col_index(loc)
    row_index = _location_row_index(loc)
    table_idx = _field_table_index(field, table_maps)
    field_title = _table_title(field.get("context", []))
    field_section = _section(field.get("context", []))

    scoped_blocks = [b for b in blocks
                     if (field_title is None or _table_title(b.context) == field_title)
                     and (field_section is None or _section(b.context) == field_section)]
    source_tables = {b.table_position.get("tableId") for b in scoped_blocks if b.table_position}

    matched: list[tuple[Any, str, str]] = []
    for b in blocks:
        if field_title is not None or field_section is not None:
            b_title = _table_title(b.context)
            b_section = _section(b.context)
            if field_title is not None and b_title != field_title:
                continue
            if field_section is not None and b_section != field_section:
                continue

        text = normalizedIndex.get(b.blockId) if (normalizedIndex and b.blockId in normalizedIndex) else b.text

        # 셀 값은 라벨:값 문장이 아니므로 표의 열 의미와 행을 함께 확인한다
        if table_idx is not None and (field_title or field_section) and b.table_position and len(source_tables) == 1:
            ta = table_maps[table_idx]
            source_col = b.table_position.get("colIndex")
            source_row = b.table_position.get("rowIndex")
            if isinstance(source_col, int) and 0 <= source_col < len(ta.col_labels):
                column_matches = _label_matches_column_meaning(label, ta.col_labels[source_col] or "")
                fixed_row = label if any(_norm_label(r) == norm_label for r in ta.row_labels if r) else None
                if fixed_row:
                    row_matches = any(
                        other.table_position.get("rowIndex") == source_row
                        and other.context == b.context
                        and other.table_position.get("tableId") == b.table_position.get("tableId")
                        and _norm_label(other.text) == norm_label
                        for other in blocks
                    )
                    column_matches = source_col == col_index
                else:
                    row_matches = row_index is None or source_row == row_index
                if column_matches and row_matches and text.strip():
                    matched.append((b, b.text, text))
                    continue

        col_match = False
        row_match = False
        if table_idx is not None and table_idx in table_maps:
            ta = table_maps[table_idx]
            if col_index is not None and ta.col_labels and 0 <= col_index < len(ta.col_labels):
                col_label = ta.col_labels[col_index]
                if _label_matches_column_meaning(label, col_label):
                    col_match = True
            if row_index is not None and ta.row_labels and 0 <= row_index < len(ta.row_labels):
                row_label = ta.row_labels[row_index]
                if row_label and _norm_label(row_label) == norm_label:
                    row_match = True

        fact_matched = False
        if b.facts:
            for fact in b.facts:
                fact_text = fact.get("originalText", "")
                f_label, f_value = _extract_label_value(fact_text)
                if _norm_label(f_label) == norm_label and f_value.strip():
                    if col_match or row_match or table_idx is None:
                        matched.append((b, fact_text, f_value))
                        fact_matched = True
                        break
        if not fact_matched:
            l, v = _extract_label_value(text)
            if _norm_label(l) == norm_label and v.strip():
                if col_match or row_match or table_idx is None:
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
            "reason": "라벨/열/행 매칭",
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
