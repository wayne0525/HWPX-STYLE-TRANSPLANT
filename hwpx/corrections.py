"""HWPX 양식 채움 — 후보 보정과 편집 준비.

이번 E09b 번호의 후보 보정 진입점은 correct_candidates 하나로 둔다.
계약(docs/TEAM_CONTRACT.md) 15장에는 후보 보정 계약이 설계되어 있으나,
아직 설계 단계이므로 이번 번호의 입출력은 내부 계약으로 사용한다.
"""

from __future__ import annotations

from typing import Any

def correct_candidates(
    fields: list[dict[str, Any]],
    corrections: list[dict[str, Any]],
    a_hash: str,
) -> dict[str, Any]:
    """분석 결과의 입력란 후보 표시를 조정한다.

    Args:
        fields: A 분석 결과의 입력란 목록.
        corrections: 후보 보정 목록.
        a_hash: 원본 A의 해시.

    Returns:
        dict: correction_id, corrected, warnings.
    """
    corrected: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    candidate_by_id = {f["candidateId"]: f for f in fields if "candidateId" in f}

    for corr in corrections:
        candidate_id = corr.get("candidateId")
        label = corr.get("label")
        enabled = corr.get("enabled")

        entry: dict[str, Any] = {
            "candidateId": candidate_id,
            "label": None,
            "enabled": False,
            "aHash": a_hash,
        }

        if candidate_id not in candidate_by_id:
            warnings.append({
                "type": "invalid_field_id",
                "fieldId": None,
                "message": f"보정 대상 후보 ID가 존재하지 않음: {candidate_id}",
                "severity": "warning",
                "detail": {"candidateId": candidate_id},
            })
            corrected.append(entry)
            continue

        f = candidate_by_id[candidate_id]

        # 보호 위치(보정 불가) 처리
        if not f.get("editable", False):
            warnings.append({
                "type": "conflict",
                "fieldId": f.get("fieldId"),
                "message": "보호 위치의 후보는 보정할 수 없음",
                "severity": "warning",
                "detail": {"candidateId": candidate_id},
            })
            entry["label"] = f.get("label")
            entry["enabled"] = f.get("enabled", False) if "enabled" in f else False
            corrected.append(entry)
            continue

        entry["label"] = label if label is not None else f.get("label")
        entry["enabled"] = bool(enabled) if enabled is not None else True
        corrected.append(entry)

    return {
        "correction_id": f"corr-{a_hash[:8]}",
        "corrected": corrected,
        "warnings": warnings,
    }
