"""HWPX 양식 채움 — 제안 검증과 실패 처리.

이번 E08 번호의 실제 진입점은 validate_proposals 하나로 둔다.
계약(docs/TEAM_CONTRACT.md) 14장에는 제안 검증 계약이 설계되어 있으나,
아직 설계 단계이므로 이번 번호의 입출력은 내부 계약으로 사용한다.
"""

from __future__ import annotations

from typing import Any

def validate_proposals(
    fields: list[dict[str, Any]],
    results: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    blocks: list[Any],
    normalizedIndex: dict[str, str] | None,
    userEdits: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Solar 제안과 규칙 연결 결과를 검증한다.

    Args:
        fields: A 분석 결과의 입력란 목록.
        results: 규칙 연결 결과 목록.
        proposals: Solar 제안 결과 목록.
        blocks: B 추출 결과의 원문 블록 목록.
        normalizedIndex: B 블록 ID와 정리 텍스트를 짝지은 맵 또는 None.
        userEdits: 사용자가 직접 수정한 값 목록 또는 None.

    Returns:
        dict: validation_id, checked, errors, warnings.
    """
    checked: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    field_by_id = {f["fieldId"]: f for f in fields}
    result_by_id = {r["fieldId"]: r for r in results}
    block_by_id = {b.blockId: b for b in blocks}
    user_by_id = {e["fieldId"]: e for e in (userEdits or [])}

    for proposal in proposals:
        field_id = proposal.get("fieldId")
        p_value = proposal.get("value")
        p_transform = proposal.get("valueTransform", "extract")
        p_source_ids = proposal.get("sourceBlockIds", [])
        p_quote = proposal.get("evidenceQuote")
        p_evidence = proposal.get("evidence") or []

        checked_entry: dict[str, Any] = {
            "fieldId": field_id,
            "source": "solar",
            "status": "ok",
            "value": p_value,
            "notes": "",
        }

        # 1) 등록 필드 확인
        if field_id not in field_by_id:
            checked_entry["status"] = "blocked"
            checked_entry["notes"] = "등록된 입력란 ID가 아님"
            errors.append({
                "type": "invalid_field_id",
                "fieldId": field_id,
                "message": "존재하지 않는 입력란 ID를 참조하는 제안",
                "severity": "error",
                "detail": None,
            })
            checked.append(checked_entry)
            continue

        # 2) 규칙 연결 결과 확인
        result = result_by_id.get(field_id)
        if result is None:
            checked_entry["status"] = "blocked"
            checked_entry["notes"] = "규칙 연결 결과가 없음"
            errors.append({
                "type": "invalid_field_id",
                "fieldId": field_id,
                "message": "규칙 연결 결과에 없는 입력란 ID",
                "severity": "error",
                "detail": None,
            })
            checked.append(checked_entry)
            continue

        if result.get("status") != "suggested":
            checked_entry["status"] = "blocked"
            checked_entry["notes"] = "규칙 연결 결과가 검토/충돌 상태"

        # 3) 근거 블록 존재 확인
        block_ids_missing = [sid for sid in p_source_ids if sid not in block_by_id]
        if block_ids_missing:
            checked_entry["status"] = "blocked"
            checked_entry["notes"] = "근거 블록이 원문에 없음"
            for sid in block_ids_missing:
                errors.append({
                    "type": "missing_quote",
                    "fieldId": field_id,
                    "message": "제시된 인용이 원문 블록에서 확인되지 않음",
                    "severity": "error",
                    "detail": {"sourceBlockId": sid, "quote": p_quote},
                })
            checked.append(checked_entry)
            continue

        # 4) 인용 일치 확인 (evidenceQuote)
        if p_quote:
            ok_quote = False
            if p_source_ids:
                for sid in p_source_ids:
                    block = block_by_id.get(sid)
                    if block is not None and _quote_in_block(p_quote, block.text):
                        ok_quote = True
                        break
            else:
                # sourceBlockIds가 비어 있어도 evidenceQuote가 제공됐으면 전체 블록에서 확인
                for block in blocks:
                    if _quote_in_block(p_quote, block.text):
                        ok_quote = True
                        break
            if not ok_quote:
                checked_entry["status"] = "blocked"
                checked_entry["notes"] = "근거 인용이 원문과 일치하지 않음"
                errors.append({
                    "type": "missing_quote",
                    "fieldId": field_id,
                    "message": "제시된 인용이 원문 블록에서 확인되지 않음",
                    "severity": "error",
                    "detail": {"sourceBlockId": p_source_ids[0] if p_source_ids else None, "quote": p_quote},
                })
                checked.append(checked_entry)
                continue

        # 5) 복수 근거 중 하나의 변조 확인 (evidence 목록)
        for ev in p_evidence:
            ev_sid = ev.get("sourceBlockId")
            ev_quote = ev.get("quote")
            if not ev_sid or not ev_quote:
                continue
            block = block_by_id.get(ev_sid)
            if block is None or not _quote_in_block(ev_quote, block.text):
                checked_entry["status"] = "blocked"
                checked_entry["notes"] = "근거 중 하나가 원문과 일치하지 않음"
                if not any(e["type"] == "missing_quote" and e["fieldId"] == field_id for e in errors):
                    errors.append({
                        "type": "missing_quote",
                        "fieldId": field_id,
                        "message": "제시된 인용이 원문 블록에서 확인되지 않음",
                        "severity": "error",
                        "detail": {"sourceBlockId": ev_sid, "quote": ev_quote},
                    })

        # 6) 값 불일치 확인 (규칙 연결 결과의 value와 비교)
        if result.get("status") == "suggested" and result.get("value") is not None:
            r_value = result.get("value")
            if p_value is not None and p_value != r_value:
                checked_entry["status"] = "blocked"
                checked_entry["notes"] = "제안 값이 근거 값과 다름"
                errors.append({
                    "type": "value_mismatch",
                    "fieldId": field_id,
                    "message": "근거와 다른 숫자나 날짜를 담은 제안",
                    "severity": "error",
                    "detail": {"expected": r_value, "proposed": p_value},
                })

        # 7) 단위 변환 근거 확인
        if p_transform == "unit":
            has_reason = _has_unit_reason(result, p_evidence, block_by_id)
            if not has_reason:
                checked_entry["status"] = "blocked"
                checked_entry["notes"] = "단위 변환 근거가 부족함"
                warnings.append({
                    "type": "unit_unclear",
                    "fieldId": field_id,
                    "message": "단위가 불명확해 자동 확정하지 않음",
                    "severity": "warning",
                    "detail": None,
                })

        # 8) 사용자 편집 보호
        if field_id in user_by_id:
            user_val = user_by_id[field_id].get("value")
            if user_val is not None and p_value is not None and p_value != user_val:
                checked_entry["status"] = "ok"
                checked_entry["notes"] = "사용자 편집 값이 우선됨"
                errors.append({
                    "type": "user_value_protected",
                    "fieldId": field_id,
                    "message": "사용자 수정 값이나 선택 상태를 덮어쓰려 한 경우",
                    "severity": "error",
                    "detail": {"userValue": user_val, "proposed": p_value},
                })

        checked.append(checked_entry)

    return {
        "validation_id": "val-001",
        "checked": checked,
        "errors": errors,
        "warnings": warnings,
    }


def _has_unit_reason(
    result: dict[str, Any],
    p_evidence: list[dict[str, Any]],
    block_by_id: dict[str, Any],
) -> bool:
    """단위 변환 근거가 있는지 확인한다."""
    if result.get("sourceBlockIds"):
        for sid in result["sourceBlockIds"]:
            if sid in block_by_id:
                return True
    if result.get("evidence"):
        for ev in result["evidence"]:
            sid = ev.get("sourceBlockId")
            if sid and sid in block_by_id:
                return True
    for ev in p_evidence:
        sid = ev.get("sourceBlockId")
        if sid and sid in block_by_id:
            return True
    return False


def _quote_in_block(quote: str, block_text: str) -> bool:
    """인용문이 블록 텍스트 안에 포함되는지 확인한다."""
    if not quote:
        return True
    return quote in block_text
