"""HWPX 양식 채움 — 결과 생성.

이번 E10 번호의 생성 진입점은 generate_result 하나로 둔다.
계약(docs/TEAM_CONTRACT.md) 16장에는 생성 계약이 설계되어 있으나,
아직 설계 단계이므로 이번 번호의 입출력은 내부 계약으로 사용한다.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any

from hwpx.package import ReadResult, read_hwpx

HWPX_NS = "http://www.hwpzone.org/hwpx"

_TAG_RE = re.compile(r"<hp:t(\s[^>]*)?>(?P<text>.*?)</hp:t>", re.S)


def generate_result(
    a_bytes: bytes,
    a_hash: str,
    fields: list[dict[str, Any]],
    edits: list[dict[str, Any]] | None,
    proposals: list[dict[str, Any]] | None,
    blocks: list[Any] | None,
    normalizedIndex: dict[str, str] | None,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    """검증된 선택 값과 근거를 원본 A에 반영해 결과를 만든다.

    Args:
        a_bytes: 원본 A의 바이트.
        a_hash: 원본 A의 해시.
        fields: A 분석 결과의 입력란 목록.
        edits: 사용자 편집 목록.
        proposals: 최종 제안 목록.
        blocks: B 추출 결과의 원문 블록 목록.
        normalizedIndex: B 원문 블록 ID와 검색·대조용 정리 텍스트를 짝지은 맵.
        validation: 제안 검증 결과.

    Returns:
        dict: result_id, resultHash, resultBytes, changedFields, warnings, errors.
    """
    with zipfile.ZipFile(io.BytesIO(a_bytes)) as archive:
        native = 'Contents/content.hpf' in archive.namelist()
    if native:
        from hwpx.fill import generate_native
        return generate_native(a_bytes, a_hash, edits, proposals, blocks)
    result_id = f"result-{a_hash[:8]}"
    resultHash = a_hash
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    changedFields: list[dict[str, Any]] = []

    if not edits:
        return _no_edits_result(result_id, resultHash, a_bytes)

    selected_edits = [e for e in edits if e.get("selected") is True]

    # 같은 fieldId에 selected=True가 둘 이상이면 충돌
    seen: dict[str, list[dict[str, Any]]] = {}
    for e in selected_edits:
        fid = e.get("fieldId")
        if fid is None:
            continue
        seen.setdefault(fid, []).append(e)
    conflicts = [fid for fid, lst in seen.items() if len(lst) > 1]
    if conflicts:
        for fid in conflicts:
            errors.append({
                "type": "conflict",
                "fieldId": fid,
                "message": "동일한 입력란에 대해 선택된 편집이 여러 개 도착함",
                "severity": "error",
                "detail": {"fieldId": fid, "count": len(seen[fid])},
            })
        return {
            "result_id": result_id,
            "resultHash": resultHash,
            "resultBytes": a_bytes,
            "changedFields": [],
            "unchanged": None,
            "warnings": warnings,
            "errors": errors,
            "summary": None,
        }

    editable_fields = [f for f in fields if f.get("editable")]
    field_index_by_id = {f["fieldId"]: i for i, f in enumerate(editable_fields)}

    pkg = read_hwpx(a_bytes)
    section_name = _find_section_xml_name(pkg)
    if section_name is None:
        errors.append({
            "type": "other",
            "fieldId": None,
            "message": "section XML을 찾을 수 없음",
            "severity": "error",
            "detail": None,
        })
        return {
            "result_id": result_id,
            "resultHash": resultHash,
            "resultBytes": a_bytes,
            "changedFields": [],
            "unchanged": None,
            "warnings": warnings,
            "errors": errors,
            "summary": None,
        }

    section_bytes = pkg.get_bytes(section_name)
    section_text = section_bytes.decode("utf-8")

    edit_by_field: dict[str, str] = {}
    for e in selected_edits:
        fid = e.get("fieldId")
        if fid in field_index_by_id:
            edit_by_field[fid] = e.get("value", "")

    new_text = section_text
    changes_made = False
    for f in editable_fields:
        fid = f["fieldId"]
        if fid not in edit_by_field:
            continue
        old_text = f.get("originalText", "")
        if not old_text:
            warnings.append({
                "type": "other",
                "fieldId": fid,
                "message": "편집 대상 원본 텍스트가 비어 있음",
                "severity": "warning",
                "detail": {"fieldId": fid},
            })
            continue
        value = edit_by_field[fid]
        escaped = _escape_value(value)
        new_text, replaced = _replace_first_t_with_text(new_text, old_text, escaped)
        if not replaced:
            warnings.append({
                "type": "other",
                "fieldId": fid,
                "message": "대응하는 hp:t 요소를 치환하지 못함",
                "severity": "warning",
                "detail": {"fieldId": fid},
            })
            continue
        changes_made = True
        changedFields.append({
            "fieldId": fid,
            "value": value,
            "origin": "manual",
            "sourceBlockIds": None,
        })
        # 넘침 경고: 원본 대비 충분히 길면 overflow_risk
        if len(value) > len(old_text) * 30:
            warnings.append({
                "type": "overflow_risk",
                "fieldId": fid,
                "message": "내용 길이 증가로 넘침 가능성이 있음",
                "severity": "warning",
                "detail": {
                    "originalLength": len(old_text),
                    "newLength": len(value),
                },
            })

    if not changes_made:
        return _no_edits_result(result_id, resultHash, a_bytes)

    result_bytes = _rebuild_zip_with_section(pkg, section_name, new_text.encode("utf-8"))
    return {
        "result_id": result_id,
        "resultHash": resultHash,
        "resultBytes": result_bytes,
        "changedFields": changedFields,
        "unchanged": None,
        "warnings": warnings,
        "errors": errors,
        "summary": None,
    }


def _no_edits_result(result_id: str, resultHash: str, a_bytes: bytes) -> dict[str, Any]:
    return {
        "result_id": result_id,
        "resultHash": resultHash,
        "resultBytes": a_bytes,
        "changedFields": [],
        "unchanged": None,
        "warnings": [],
        "errors": [],
        "summary": None,
    }


def _find_section_xml_name(pkg: ReadResult) -> str | None:
    for name in pkg.item_paths:
        low = name.lower()
        if low.endswith(".xml") and "section" in low:
            return name
    for name in pkg.item_paths:
        if name.lower().endswith(".xml"):
            return name
    return None


def _find_editable_t_elements(text: str) -> list[str]:
    """텍스트 컨텐츠가 있는 hp:t 요소의 텍스트를 순서대로 추출한다."""
    out: list[str] = []
    for m in _TAG_RE.finditer(text):
        if m.group("text").strip():
            out.append(m.group("text"))
    return out


def _replace_t_text_at_index(
    text: str, index: int, old_text: str, new_text: str
) -> tuple[str, int]:
    """index번째 비빈 hp:t 요소의 텍스트를 새 값으로 치환한다.

    _find_editable_t_elements와 같은 필터(비어있지 않은 hp:t)를 사용해
    인덱스를 맞춘다.
    """
    matches = [m for m in _TAG_RE.finditer(text) if m.group("text").strip()]
    if index >= len(matches):
        return text, 0
    m = matches[index]
    start, end = m.start(), m.end()
    tag_body = m.group(0)
    new_tag_body = tag_body.replace(m.group("text"), new_text, 1)
    return text[:start] + new_tag_body + text[end:], 1 if new_tag_body != tag_body else 0


def _replace_first_t_with_text(text: str, old_text: str, new_text: str) -> tuple[str, bool]:
    """text에서 old_text와 일치하는 첫 번째 hp:t의 텍스트를 new_text로 교체한다.

    old_text는 원본 텍스트(escape 전), new_text는 escape된 값.
    일치하면 (새텍스트, True), 없으면 (원본, False).
    """
    pattern = re.compile(r'(<hp:t(\s[^>]*)?>)(.*?)(</hp:t>)', re.S)
    for m in pattern.finditer(text):
        if m.group(3) == old_text:
            start, end = m.start(), m.end()
            new_tag = m.group(1) + new_text + m.group(4)
            return text[:start] + new_tag + text[end:], True
    return text, False


def _escape_value(value: str) -> str:
    """편집 값을 XML 텍스트로 escape한다.

    <br/>는 태그로 인정해 유지하고, 나머지는 텍스트 escape한다.
    """
    if value is None:
        return ""
    parts = value.split("<br/>")
    out_parts: list[str] = []
    for i, part in enumerate(parts):
        if i > 0:
            out_parts.append("<br/>")
        out_parts.append(_escape_text(part))
    return "".join(out_parts)


def _escape_text(s: str) -> str:
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace("'", "&apos;")
    s = s.replace('"', "&quot;")
    return s


def _rebuild_zip_with_section(pkg: ReadResult, section_name: str, new_section_bytes: bytes) -> bytes:
    """원본 패키지에서 특정 section 엔트리를 교체한 새 ZIP 바이트를 만든다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in pkg.item_paths:
            if item == "mimetype":
                zout.writestr(item, pkg.get_bytes(item), compress_type=zipfile.ZIP_STORED)
            elif item == section_name:
                zout.writestr(item, new_section_bytes)
            else:
                zout.writestr(item, pkg.get_bytes(item))
    return buf.getvalue()
