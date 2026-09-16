"""
hwpx/fill.py — A 양식 HWPX에 B의 값을 채워 새 HWPX(C)를 만든다.

계약: docs/contracts/engine.md §3
"""
import hashlib
import io
import os
import zipfile
from typing import Any, Dict, List, Optional

from lxml import etree

from hwpx.package import file_hash

NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


# ---------------------------------------------------------------------------
# fill_a
# ---------------------------------------------------------------------------

def fill_a(
    a_path: str,
    analysis: Dict[str, Any],
    fills: List[Dict[str, Any]],
    out_path: str,
) -> Dict[str, Any]:
    """A 양식 HWPX에 fills를 채워 새 HWPX(C)를 저장한다.

    계약: docs/contracts/engine.md §3.1
    """
    # --- A 해시 검증 ---
    a_current_hash = file_hash(a_path)
    expected_hash = analysis.get("a_hash", "")
    if a_current_hash != expected_hash:
        return {
            "a_hash": expected_hash,
            "c_path": out_path,
            "c_hash": "",
            "applied": [],
            "rejected": [],
            "warnings": [f"A 해시가 분석 시점과 다름: 예상 {expected_hash}, 실제 {a_current_hash}"],
            "failure": {"reason": "A 해시 불일치", "detail": f"예상 {expected_hash}, 실제 {a_current_hash}"},
        }

    # --- fills 검증: 중복 field_id (동일 field_id 반복은 해당 항목만 거부) ---
    seen_fids: set = set()
    for item in fills:
        fid = item.get("field_id", "")
        value = item.get("value", "")
        if fid in seen_fids:
            # rejected 리스트는 아직 정의 전 — 이 지점은 호출 전 검증에서 걸러져야 함
            # 실제 중복 체크는 아래 targets 수집에서 처리한다.
            pass
        seen_fids.add(fid)

    # --- fields 색인 ---
    fields_by_id = {f["field_id"]: f for f in analysis.get("fields", [])}

    applied: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    # --- 수정 대상 수집 ---
    targets: Dict[str, Dict[str, Any]] = {}
    for item in fills:
        fid = item.get("field_id", "")
        value = item.get("value", "")
        if fid in seen_fids and fid in targets:
            # 이미 처리된 field_id의 중복 등장 → 해당 항목만 rejected
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": f"fills에 중복 field_id: {fid}",
                "status": "rejected",
            })
            continue
        if fid not in fields_by_id:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": "analysis에 없는 field_id",
                "status": "rejected",
            })
            continue
        field = fields_by_id[fid]
        if field.get("editable") is False:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": "editable=false — 편집 불가",
                "status": "rejected",
            })
            continue
        if field.get("rule") == "rule3":
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": "rule3은 단위 보존 규칙 미정 — 이번 단계 범위 밖",
                "status": "rejected",
            })
            continue
        targets[fid] = {"field": field, "value": value}

    if not targets:
        return _save_c(a_path, out_path, applied, rejected, expected_hash, analysis)

    # --- 수정할 섹션 결정 ---
    modified_sections: set = set()
    for fid, tgt in targets.items():
        sec = tgt["field"]["location"].get("section", "")
        if sec:
            modified_sections.add(sec)

    # --- ZIP 열기 ---
    try:
        zf = zipfile.ZipFile(a_path, "r")
    except (zipfile.BadZipFile, OSError, FileNotFoundError) as exc:
        return {
            "a_hash": expected_hash,
            "c_path": out_path,
            "c_hash": "",
            "applied": applied,
            "rejected": rejected,
            "warnings": [],
            "failure": {"reason": "ZIP 열기 실패", "detail": str(exc)},
        }

    try:
        all_entries = {info.filename: zf.read(info.filename) for info in zf.infolist()}
        infolist = zf.infolist()
    finally:
        zf.close()

    # --- 섹션 XML 수정 ---
    xml_decl: Dict[str, str] = {}
    for sec_path in modified_sections:
        if sec_path not in all_entries:
            rejected.append({
                "field_id": "",
                "value": "",
                "reason": f"섹션 없음: {sec_path}",
                "status": "rejected",
            })
            continue
        xml_bytes = all_entries[sec_path]
        decl = _extract_xml_decl(xml_bytes)
        xml_decl[sec_path] = decl

        try:
            root = etree.fromstring(xml_bytes)
        except Exception as exc:
            rejected.append({
                "field_id": "",
                "value": "",
                "reason": f"섹션 파싱 실패: {sec_path} ({exc})",
                "status": "rejected",
            })
            continue

        # 해당 섹션의 targets
        sec_targets = [(fid, tgt) for fid, tgt in targets.items()
                       if tgt["field"]["location"].get("section") == sec_path]

        # rule4 먼저 처리 (offset 역순)
        rule4_targets = [(fid, tgt) for fid, tgt in sec_targets if tgt["field"]["rule"] == "rule4"]
        rule4_targets.sort(key=lambda x: x[1]["field"]["location"].get("insert_offset", 0), reverse=True)
        rule4_result = _apply_rule4(root, rule4_targets)
        applied.extend(rule4_result["applied"])
        rejected.extend(rule4_result["rejected"])

        # rule1/rule2 처리
        rule12_targets = [(fid, tgt) for fid, tgt in sec_targets if tgt["field"]["rule"] in ("rule1", "rule2")]
        rule12_result = _apply_rule12(root, rule12_targets)
        applied.extend(rule12_result["applied"])
        rejected.extend(rule12_result["rejected"])

        # 수정된 XML 직렬화
        new_xml = _serialize_xml(root, xml_decl.get(sec_path, ""))
        all_entries[sec_path] = new_xml
        modified_sections.add(sec_path)

    # --- 결과 저장 ---
    return _save_c(a_path, out_path, applied, rejected, expected_hash, analysis, all_entries, infolist)


# ---------------------------------------------------------------------------
# XML 선언/직렬화
# ---------------------------------------------------------------------------

def _extract_xml_decl(xml_bytes: bytes) -> str:
    """XML bytes에서 선언 부분(<?xml ...?>)을 추출한다."""
    if xml_bytes.startswith(b"\xef\xbb\xbf"):
        xml_bytes = xml_bytes[3:]
    end_idx = xml_bytes.find(b">")
    if end_idx == -1:
        return ""
    if xml_bytes[:5] == b"<?xml":
        decl = xml_bytes[:end_idx + 1].decode("utf-8", errors="replace")
        return decl
    return ""


def _serialize_xml(root: etree._Element, xml_decl: str) -> bytes:
    """XML 트리를 bytes로 직렬화한다. 선언을 앞에 붙인다."""
    body = etree.tostring(root, xml_declaration=False, encoding="UTF-8")
    if xml_decl:
        return xml_decl.encode("utf-8") + body
    else:
        decl = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        return decl.encode("utf-8") + body


# ---------------------------------------------------------------------------
# 셀 맵
# ---------------------------------------------------------------------------

def _build_cell_map(tbl: etree._Element) -> Dict[tuple, etree._Element]:
    """표의 셀 주소 (row, col) → tc 매핑."""
    cell_map: Dict[tuple, etree._Element] = {}
    for tc in tbl.findall(".//hp:tc", NS):
        addr = tc.find("hp:cellAddr", NS)
        col = int(addr.get("colAddr", 0)) if addr is not None else 0
        row = int(addr.get("rowAddr", 0)) if addr is not None else 0
        cell_map[(row, col)] = tc
    return cell_map


def _find_table(root: etree._Element, table_path: List[int]) -> Optional[etree._Element]:
    """table_path의 첫 요소로 표를 찾는다."""
    tables = root.findall(".//hp:tbl", NS)
    t_idx = table_path[0] if table_path else 0
    if 0 <= t_idx < len(tables):
        return tables[t_idx]
    return None


# ---------------------------------------------------------------------------
# 규칙 4 적용
# ---------------------------------------------------------------------------

def _apply_rule4(root: etree._Element, targets: List[tuple]) -> Dict[str, List[Dict[str, Any]]]:
    """rule4 대상: paragraph_index → run_index → insert_offset에 값 삽입.

    fill_a에서 offset 역순 정렬 후의 targets를 받는다.
    """
    applied: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    if not targets:
        return {"applied": applied, "rejected": rejected}

    for fid, tgt in targets:
        field = tgt["field"]
        value = tgt["value"]
        loc = field["location"]
        table_path = loc.get("table_path", [])
        tbl = _find_table(root, table_path)
        if tbl is None:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": f"표를 찾을 수 없음: table_path={table_path}",
                "status": "rejected",
            })
            continue

        cell_map = _build_cell_map(tbl)
        key = (loc.get("row", 0), loc.get("col", 0))
        tc = cell_map.get(key)
        if tc is None:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": f"셀을 찾을 수 없음: ({key[0]}, {key[1]})",
                "status": "rejected",
            })
            continue

        pi = loc.get("paragraph_index", 0)
        ri = loc.get("run_index", 0)
        offset = loc.get("insert_offset", 0)

        sub = tc.find("hp:subList", NS)
        if sub is None:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": "subList 없음",
                "status": "rejected",
            })
            continue

        paragraphs = sub.findall("hp:p", NS)
        if pi >= len(paragraphs):
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": f"문단 인덱스 초과: {pi} >= {len(paragraphs)}",
                "status": "rejected",
            })
            continue
        p = paragraphs[pi]
        runs = p.findall("hp:run", NS)
        if ri >= len(runs):
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": f"run 인덱스 초과: {ri} >= {len(runs)}",
                "status": "rejected",
            })
            continue
        run = runs[ri]
        t = run.find("hp:t", NS)
        if t is None:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": "hp:t 없음 — run에 hp:t가 없음",
                "status": "rejected",
            })
            continue

        original = t.text or ""
        if offset > len(original):
            offset = len(original)
        new_text = original[:offset] + value + original[offset:]
        t.text = new_text
        applied.append({
            "field_id": fid,
            "value": value,
            "location": loc,
            "status": "applied",
            "reason": f"라벨 '{field['label']}' 뒤 insert_offset={offset}에 삽입",
        })

    return {"applied": applied, "rejected": rejected}


# ---------------------------------------------------------------------------
# 규칙 1/2 적용
# ---------------------------------------------------------------------------

def _apply_rule12(
    root: etree._Element,
    targets: List[tuple],
) -> Dict[str, List[Dict[str, Any]]]:
    """rule1/rule2 대상: 셀 (row, col)의 첫 문단 첫 run에 hp:t 추가/수정.

    rule1과 rule2 모두 location.row, location.col이 편집 대상 셀을 가리킨다.
    (rule1은 이미 col+1로 저장됨)
    """
    applied: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    if not targets:
        return {"applied": applied, "rejected": rejected}

    for fid, tgt in targets:
        field = tgt["field"]
        value = tgt["value"]
        loc = field["location"]
        table_path = loc.get("table_path", [])
        tbl = _find_table(root, table_path)
        if tbl is None:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": f"표를 찾을 수 없음: table_path={table_path}",
                "status": "rejected",
            })
            continue

        cell_map = _build_cell_map(tbl)
        key = (loc.get("row", 0), loc.get("col", 0))
        tc = cell_map.get(key)
        if tc is None:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": f"셀을 찾을 수 없음: ({key[0]}, {key[1]})",
                "status": "rejected",
            })
            continue

        # 첫 문단(hp:p)만 수정
        sub = tc.find("hp:subList", NS)
        if sub is None:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": "subList 없음",
                "status": "rejected",
            })
            continue
        first_p = sub.find("hp:p", NS)
        if first_p is None:
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": "첫 문단(hp:p) 없음",
                "status": "rejected",
            })
            continue

        runs = first_p.findall("hp:run", NS)
        if runs:
            first_run = runs[0]
            t = first_run.find("hp:t", NS)
            if t is None:
                # hp:t가 없으면 새로 추가 (charPrIDRef 유지)
                new_t = etree.SubElement(first_run, "{%s}t" % NS["hp"])
                new_t.text = value
            else:
                t.text = value
            applied.append({
                "field_id": fid,
                "value": value,
                "location": loc,
                "status": "applied",
                "reason": f"{'라벨' if field['rule'] == 'rule1' else '헤더 아래'} 셀에 기입",
            })
        else:
            # run이 없으면 수동 편집 필요
            rejected.append({
                "field_id": fid,
                "value": value,
                "reason": "거부: run 없음 — 수동 편집 필요",
                "status": "rejected",
            })

    return {"applied": applied, "rejected": rejected}


# ---------------------------------------------------------------------------
# 저장
# ---------------------------------------------------------------------------

def _save_c(
    a_path: str,
    out_path: str,
    applied: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    expected_hash: str,
    analysis: Dict[str, Any],
    all_entries: Optional[Dict[str, bytes]] = None,
    infolist: Optional[Any] = None,
) -> Dict[str, Any]:
    """C HWPX를 저장하고 결과를 반환한다."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    if all_entries is None or infolist is None:
        try:
            zf = zipfile.ZipFile(a_path, "r")
            all_entries = {info.filename: zf.read(info.filename) for info in zf.infolist()}
            infolist = zf.infolist()
            zf.close()
        except Exception as exc:
            return {
                "a_hash": expected_hash,
                "c_path": out_path,
                "c_hash": "",
                "applied": applied,
                "rejected": rejected,
                "warnings": [],
                "failure": {"reason": "ZIP 읽기 실패", "detail": str(exc)},
            }

    # C 저장
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in infolist:
            filename = info.filename
            data = all_entries.get(filename, b"")
            if filename == "mimetype":
                zout.writestr(zipfile.ZipInfo(filename), data, compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr(filename, data)

    c_hash = file_hash(out_path)
    warnings = ["한글에서 열어 줄 배치 확인 필요 (hp:linesegarray는 수정하지 않음)"]
    if rejected:
        warnings.append(f"거부된 필드 {len(rejected)}개")

    return {
        "a_hash": expected_hash,
        "c_path": out_path,
        "c_hash": c_hash,
        "applied": applied,
        "rejected": rejected,
        "warnings": warnings,
        "failure": None,
    }
