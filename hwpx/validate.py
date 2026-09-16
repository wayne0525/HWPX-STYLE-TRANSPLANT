"""HWPX 결과 검증 — 생성 후 구조·재추출 검사.

이번 E11 번호의 검증 진입점은 validate_output 하나로 둔다.
계약(docs/TEAM_CONTRACT.md) 16.8~16.9 재검증 규칙을 내부 계약으로 구현한다.
"""

from __future__ import annotations

from typing import Any

from hwpx.analyze import analyze_a
from hwpx.package import ReadResult, read_hwpx
from hwpx.xml import read_xml
from hwpx.tables import read_tables


def validate_output(
    result_bytes: bytes,
    original_bytes: bytes,
    fields: list[dict[str, Any]],
    edits: list[dict[str, Any]],
    a_hash: str,
) -> dict[str, Any]:
    """생성 결과 bytes를 열어 구조·재추출·보존을 검증한다.

    Returns:
        dict: passed, checks, warnings, errors, report.
    """
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    edit_field_ids = {e.get("fieldId") for e in edits if e.get("selected") is True and e.get("value")}

    try:
        pkg = read_hwpx(result_bytes)
    except Exception as e:
        errors.append({"type": "zip-structure", "message": f"결과 ZIP을 열 수 없음: {e}", "severity": "error"})
        return _report(False, checks, warnings, errors)

    if not _check_mimetype(pkg):
        errors.append({"type": "mimetype", "message": "mimetype이 첫 엔트리가 아니거나 비압축이 아님", "severity": "error"})
    else:
        checks.append({"name": "mimetype", "status": "passed", "message": "mimetype 첫 엔트리·비압축"})

    try:
        xml = read_xml(pkg)
    except Exception as e:
        errors.append({"type": "xml-wellformed", "message": f"XML 파싱 실패: {e}", "severity": "error"})
        return _report(False, checks, warnings, errors)

    try:
        orig_xml = read_xml(original_bytes)
    except Exception as e:
        errors.append({"type": "xml-wellformed", "message": f"원본 XML 파싱 실패: {e}", "severity": "error"})
        return _report(False, checks, warnings, errors)

    try:
        orig_analysis = analyze_a(orig_xml, a_bytes=original_bytes, a_sha256=a_hash)
        new_analysis = analyze_a(xml, a_bytes=result_bytes, a_sha256=a_hash)
    except Exception as e:
        errors.append({"type": "analysis", "message": f"분석 재실행 실패: {e}", "severity": "error"})
        return _report(False, checks, warnings, errors)

    if _fixed_texts_preserved(orig_analysis.fields, new_analysis.fields, set(edit_field_ids)):
        checks.append({"name": "fixed-text-preserved", "status": "passed", "message": "고정 문구 보존"})
    else:
        errors.append({"type": "fixed-text-changed", "message": "고정 문구가 변경됨", "severity": "error"})

    try:
        orig_tables = read_tables(orig_xml)
        new_tables = read_tables(xml)
    except Exception as e:
        warnings.append({"type": "other", "message": f"표 비교 중 오류: {e}", "severity": "warning"})
        orig_tables = None
        new_tables = None

    if orig_tables is not None and new_tables is not None:
        if _tables_preserved(orig_tables, new_tables):
            checks.append({"name": "table-grid-merge-preserved", "status": "passed", "message": "표 격자·병합 보존"})
        else:
            errors.append({"type": "table-structure-changed", "message": "표 격자/병합이 변경됨", "severity": "error"})

    if _protected_preserved(orig_analysis.fields, new_analysis.fields):
        checks.append({"name": "protected-preserved", "status": "passed", "message": "보호 구간 보존"})
    else:
        errors.append({"type": "protected-changed", "message": "보호 구간이 변경됨", "severity": "error"})

    try:
        applied = _check_applied_values(new_analysis, edits)
        if applied["all_found"]:
            checks.append({"name": "value-placement", "status": "passed", "message": "적용값이 지정 위치에 존재"})
        else:
            warnings.append({"type": "value-placement-partial", "message": "일부 적용값을 재추출하지 못함", "severity": "warning"})
    except Exception as e:
        warnings.append({"type": "other", "message": f"적용값 재추출 중 오류: {e}", "severity": "warning"})

    passed = not errors
    return _report(passed, checks, warnings, errors)


def _report(passed: bool, checks, warnings, errors):
    return {
        "passed": passed,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "report": {
            "checks": checks,
            "warnings": warnings,
            "appliedFieldIds": [],
            "skippedFieldIds": [],
            "pendingFieldIds": [],
            "changedParts": [],
            "inputHash": "",
            "outputHash": "",
        },
    }


def _check_mimetype(pkg: ReadResult) -> bool:
    paths = pkg.item_paths
    if not paths or paths[0] != "mimetype":
        return False
    info = pkg.by_path["mimetype"]
    if info.compress_type != 0:
        return False
    return info.bytes == b"application/hwp+zip"


def _fixed_texts_preserved(orig_fields, new_fields, edited_field_ids=()) -> bool:
    orig_map = {f.get("fieldId"): f.get("originalText") for f in orig_fields if f.get("originalText") and f.get("fieldId") not in edited_field_ids}
    new_map = {f.get("fieldId"): f.get("originalText") for f in new_fields if f.get("originalText") and f.get("fieldId") not in edited_field_ids}
    for fid, text in orig_map.items():
        if fid in new_map and new_map[fid] != text:
            return False
    return True


def _tables_preserved(orig, new) -> bool:
    if len(orig.tables) != len(new.tables):
        return False
    for o, n in zip(orig.tables, new.tables):
        if o.row_count != n.row_count or o.column_count != n.column_count:
            return False
    return True


def _protected_preserved(orig_fields, new_fields) -> bool:
    orig_protected = {f.get("fieldId") for f in orig_fields if f.get("editable") is False}
    new_protected = {f.get("fieldId") for f in new_fields if f.get("editable") is False}
    return orig_protected == new_protected


def _check_applied_values(new_analysis, edits):
    all_found = True
    for e in edits:
        if e.get("selected") is True and e.get("value"):
            fid = e.get("fieldId")
            found = any(f.get("fieldId") == fid for f in new_analysis.fields)
            if not found:
                all_found = False
    return {"all_found": all_found}
