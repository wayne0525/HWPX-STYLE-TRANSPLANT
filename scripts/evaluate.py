#!/usr/bin/env python3
"""scripts/evaluate.py - 사람 정답 기반 품질 평가 진입점.

종료 코드:
- 0: 통과
- 1: 품질 실패
- 2: 자료 미검증

이번 번호는 실제 업무 양식/사람 검토가 없으므로
합성 fixture 기준으로만 검사한다.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

from hwpx.analyze import analyze_a
from hwpx.generate import generate_result
from hwpx.package import ReadResult, read_hwpx
from hwpx.validate import validate_output
from hwpx.xml import read_xml


_TAG_RE_EVAL = re.compile(r'<hp:t(\s[^>]*)?>(?P<text>.*?)</hp:t>', re.S)


def _first_xml_name(pkg):
    for name in pkg.item_paths:
        if name.lower().endswith('.xml'):
            return name
    return None


def _escape_text(s: str) -> str:
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s


def _find_t_with_text(xml_text: str, target_text: str):
    for m in _TAG_RE_EVAL.finditer(xml_text):
        if m.group('text') == target_text:
            return m
    return None


def evaluate_quality(
    a_bytes: bytes,
    a_sha256: str,
    b_text: str | None,
    gold_answers: dict[str, str | None],
    edits: list[dict[str, Any]] | None = None,
    human_reviewed: bool = False,
    human_review_note: str = "",
) -> dict[str, Any]:
    """하나의 양식 A에 대해 사람 정답 기준으로 품질을 평가한다.

    Args:
        a_bytes: 양식 원본 A 바이트.
        a_sha256: 원본 A 해시.
        b_text: 내용 원본 B 텍스트(기록용, 이번 구현에서는 직접 사용하지 않음).
        gold_answers: fieldId -> 기대값(문자열 또는 None=미기입).
        edits: 생성 시 적용할 편집 목록. 없으면 gold_answers를 자동 편집으로 간주하지 않는다.
        human_reviewed: 사람 검토가 있었는지.
        human_review_note: 사람 검토 메모.

    Returns:
        dict: passed, exit_code, form_results, metrics, notes, human_reviewed, human_review_note.
    """
    notes: list[str] = []
    form_results: list[dict[str, Any]] = []

    pkg = read_hwpx(a_bytes)
    section_name = _first_xml_name(pkg)
    xml_result = read_xml(pkg)
    analysis = analyze_a(
        xml_result,
        a_bytes=a_bytes,
        a_sha256=a_sha256,
    )
    fields = analysis.fields

    detected_ids = [f.get("fieldId") for f in fields if f.get("fieldId")]
    gold_ids = list(gold_answers.keys())

    # 탐지 정밀도/재현율
    detected_set = set(detected_ids)
    gold_set = set(gold_ids)
    true_positives = detected_set & gold_set
    precision = len(true_positives) / len(detected_set) if detected_set else 0.0
    recall = len(true_positives) / len(gold_set) if gold_set else 0.0

    # 생성 결과 준비
    result_bytes = a_bytes
    result_fields = fields
    protected_changed = False
    validation_passed = False
    if edits is not None:
        gen = generate_result(
            a_bytes,
            a_sha256,
            fields,
            edits,
            None,
            None,
            None,
            None,
        )
        result_bytes = gen["resultBytes"] or a_bytes
        if gen.get("errors"):
            notes.append(f"생성 오류: {json.dumps(gen.get('errors'))}")
        # 검증으로 재추출
        v = validate_output(result_bytes, a_bytes, fields, edits, a_sha256)
        validation_passed = v['passed'] and not gen.get('errors')
        if not v["passed"]:
            notes.append(f"구조 검증 실패: {json.dumps(v.get('errors'))}")
        # 보호 구조 변경 여부
        for check in v.get("checks", []):
            if check.get("name") == "protected-preserved" and check.get("status") != "passed":
                protected_changed = True
        # 적용값 재추출: 여기선 간단히 필드가 결과에 남아있는지만 본다
        result_fields = v.get("report", {}).get("appliedFieldIds", [])
    else:
        notes.append("편집이 없어 생성 결과를 만들지 않음; 정답 평가는 미실행")

    # 정답 평가
    missing: list[str] = []
    miswrite: list[dict[str, Any]] = []
    if edits is not None:
        new_pkg = read_hwpx(result_bytes)
        new_section_name = _first_xml_name(new_pkg)
        new_section_text = new_pkg.get_bytes(new_section_name).decode("utf-8")
        for field_id, expected in gold_answers.items():
            if pkg.has_path('Contents/content.hpf'):
                from hwpx.fill import read_field_value
                try:
                    actual = read_field_value(a_bytes, result_bytes, field_id, edits)
                except ValueError:
                    missing.append(field_id)
                    continue
                if expected is None:
                    if actual:
                        miswrite.append({'fieldId': field_id, 'expected': None, 'actual': actual})
                elif not actual:
                    missing.append(field_id)
                elif actual != expected:
                    miswrite.append({'fieldId': field_id, 'expected': expected, 'actual': actual})
                continue
            field = next((f for f in fields if f.get("fieldId") == field_id), None)
            original_text = field.get("originalText", "") if field else ""
            if expected is None:
                if original_text and original_text in new_section_text:
                    miswrite.append({"fieldId": field_id, "expected": None, "actual": "원문 유지"})
                continue
            escaped_expected = _escape_text(expected)
            t_match = _find_t_with_text(new_section_text, original_text)
            if t_match is None:
                if escaped_expected in new_section_text:
                    continue  # 원문 사라지고 새 값 있음
                missing.append(field_id)
            else:
                if t_match.group("text") == escaped_expected:
                    continue  # 정상 치환
                if escaped_expected in new_section_text:
                    miswrite.append({"fieldId": field_id, "expected": expected, "actual": "원문 유지/중복"})
                else:
                    missing.append(field_id)

    filled_count = len(gold_ids) - len(missing)
    denominator = len(gold_ids)
    fill_rate = filled_count / denominator if denominator else 0.0

    form_results.append({
        "form": "synthetic",
        "detected_field_count": len(detected_ids),
        "gold_field_count": denominator,
        "precision": precision,
        "recall": recall,
        "filled_count": filled_count,
        "fill_rate": fill_rate,
        "missing_field_ids": missing,
        "miswrite_count": len(miswrite),
        "miswrite_examples": miswrite[:5],
        "protected_changed": protected_changed,
        "structural_damage_count": 1 if protected_changed else 0,
        "validation_passed": validation_passed,
    })

    # 통과 판정
    has_defect = (len(missing) > 0) or (len(miswrite) > 0) or (protected_changed) or (recall < 1.0) or (precision < 1.0) or not validation_passed
    exit_code = 1 if has_defect else 0
    passed = not has_defect

    if not human_reviewed:
        notes.append("사람 검토가 없어 실제 평가는 미검증")
        if edits is None:
            exit_code = 2
            passed = False

    return {
        "passed": passed,
        "exit_code": exit_code,
        "form_results": form_results,
        "metrics": {
            "fill_rate": fill_rate,
            "precision": precision,
            "recall": recall,
            "miswrite_count": len(miswrite),
            "missing_count": len(missing),
            "protected_changed": protected_changed,
        },
        "notes": notes,
        "human_reviewed": human_reviewed,
        "human_review_note": human_review_note,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. 인자가 없으면 합성 fixture 평가를 실행하고 종료 코드를 반환한다."""
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return _run_synth_evaluation()
    return _run_cli(argv)


def _run_synth_evaluation() -> int:
    from pathlib import Path

    root = Path("C:/MABC/HWPX-STYLE-TRANSPLANT")
    fixtures_json = root / "tests" / "fixtures" / "fixtures.json"
    if not fixtures_json.exists():
        print("fixtures.json 없음", file=sys.stderr)
        return 2

    meta = json.loads(fixtures_json.read_text(encoding="utf-8"))
    exit_codes: list[int] = []
    for file in meta["files"]:
        name = file["name"]
        kind = file.get("kind", "unknown")
        a_bytes = (root / "tests" / "fixtures" / name).read_bytes()
        a_sha256 = file["bytes_sha256"]
        gold = _gold_for(name)
        if gold is None:
            print(f"건너뜀: {name} (정답 정의 없음)")
            exit_codes.append(2)
            continue
        edits = _edits_for(name, gold)
        result = evaluate_quality(
            a_bytes,
            a_sha256,
            b_text=None,
            gold_answers=gold,
            edits=edits,
            human_reviewed=False,
            human_review_note="합성 fixture 기준; 실제 사람 검토 없음",
        )
        print(f"--- {name} ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        exit_codes.append(result["exit_code"])
    if 1 in exit_codes:
        return 1
    if 2 in exit_codes:
        return 2
    return 0


def _gold_for(name: str) -> dict[str, str | None] | None:
    """합성 사람 정답. 실제 업무 정답이 아니므로 임의 정의임을 문서에 남긴다."""
    mapping = {
        "company_report.hwpx": {"f-company_report-001": "홍길동, 김철수, 이영호가 수행한 보고"},
        "event_plan.hwpx": {"f-event_plan-001": "행사명: 테스트데이, 일시: 2026-09-20, 장소: 서울"},
        "invoice.hwpx": {"f-invoice-001": "공급자: A회사, 공급받는 자: B회사, 금액: 1000000원"},
        "meeting_minutes.hwpx": {"f-meeting_minutes-001": "회의명: 주간회의, 일시: 2026-09-16, 참석자: 홍길동, 김철수"},
        "patent_spec.hwpx": {"f-patent_spec-001": "청구항 1: 장치, 청구항 2: 방법, 청구항 3: 시스템"},
        "eval_unused.hwpx": None,
    }
    return mapping.get(name)


def _edits_for(name: str, gold: dict[str, str | None]) -> list[dict[str, Any]]:
    """합성 편집 목록. 실제 사용자 편집이 아니므로 임의 정의."""
    edits = []
    for field_id, value in gold.items():
        edits.append({"fieldId": field_id, "value": value, "selected": True, "origin": "manual"})
    return edits


if __name__ == "__main__":
    sys.exit(main())
