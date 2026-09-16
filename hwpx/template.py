"""
표 셀 후보 분석 — team/engine-dylan 7f44546 기반

실제 HWPX의 manifest 순서와 셀 주소를 사용한다
공통 반환 형식은 public_fields에서 변환한다
"""
import hashlib
import re
import json
from typing import List, Optional

from lxml import etree
from hwpx.xml import read_xml, _reject_doctype_and_entities

NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


def parse_xml(raw):
    _reject_doctype_and_entities(raw)
    return etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))


def target(root, field, *, create=False):
    """Resolve a server-derived position without descending into nested cells."""
    loc = field['location']
    tables = root.findall('.//hp:tbl', NS)
    index = loc['table_path'][0]
    if not 0 <= index < len(tables):
        raise ValueError('Invalid table position')
    matches = []
    for cell in tables[index].findall('hp:tr/hp:tc', NS):
        addr = cell.find('hp:cellAddr', NS)
        if addr is not None and (int(addr.get('rowAddr')), int(addr.get('colAddr'))) == (loc['row'], loc['col']):
            matches.append(cell)
    if len(matches) != 1:
        raise ValueError('Ambiguous cell position')
    cell = matches[0]
    allowed = {'subList', 'p', 'run', 't', 'linesegarray', 'lineseg'}
    sub = cell.find('hp:subList', NS)
    if sub is None or any(etree.QName(n).localname not in allowed for n in sub.iter() if isinstance(n.tag, str)):
        raise ValueError('Cell contains unsupported controls')
    ps = sub.findall('hp:p', NS)
    pi, ri = loc.get('paragraph_index', 0), loc.get('run_index', 0)
    if not 0 <= pi < len(ps):
        raise ValueError('Missing paragraph')
    runs = ps[pi].findall('hp:run', NS)
    if not 0 <= ri < len(runs):
        raise ValueError('Missing styled run')
    ts = runs[ri].findall('hp:t', NS)
    if len(ts) > 1 or (ts and len(ts[0])):
        raise ValueError('Compound text requires review')
    if field['rule'] != 'rule4' and any((t.text or '').strip() for t in sub.findall('.//hp:t', NS)):
        raise ValueError('Cell is not empty')
    if not ts and create:
        ts = [etree.SubElement(runs[ri], '{'+NS['hp']+'}t')]
    return ts[0] if ts else None


def public_fields(analysis):
    result = []
    for f in analysis['fields']:
        loc = f['location']
        result.append({
            'fieldId': f['field_id'], 'candidateId': f['field_id'], 'label': f['label'],
            'originalText': f.get('original_text', ''), 'context': [f['context']],
            'unit': None if f['unit'] == 'text' else f['unit'], 'editable': f['editable'],
            'required': f['required'], 'status': 'normal' if f['editable'] else 'blocked',
            'location': {'section': {'path': loc['section']},
                         'table': {'tableIndex': loc['table_path'][0]},
                         'row': {'rowIndex': loc['row']}, 'column': {'columnIndex': loc['col']},
                         'paragraph': {'paragraphIndex': loc.get('paragraph_index', 0)}}})
    return result


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _cell_text(tc) -> str:
    """셀 안의 모든 hp:t 텍스트를 이어 붙인 원문(공백 포함)."""
    parts: List[str] = []
    sub = tc.find("hp:subList", NS)
    if sub is None:
        return ""
    for p in sub.findall("hp:p", NS):
        for run in p.findall("hp:run", NS):
            for t in run.findall("hp:t", NS):
                parts.extend(t.itertext())
    return "".join(parts)


def _cell_text_stripped(tc) -> str:
    return _cell_text(tc).strip()


def _is_guidance(tc) -> bool:
    return _cell_text_stripped(tc).startswith("※")


def _is_empty(tc) -> bool:
    return _cell_text_stripped(tc) == ""


def _is_placeholder_or_unit_only(tc) -> bool:
    """자리표시자나 단위만 있는 셀인가? (실제 입력값이 아님)"""
    t = _cell_text_stripped(tc)
    if not t:
        return False
    p = r"[\s()]*"
    if re.fullmatch(p, t):
        return True
    if re.fullmatch(p + r"원\s*", t):
        return True
    if re.fullmatch(p + r"천원\s*", t):
        return True
    if re.fullmatch(p + r"년\s*월\s*일\s*", t):
        return True
    if re.fullmatch(p + r"\d*\s*\.\s*\d*\s*\.\s*\d*\s*", t):
        return True
    if re.fullmatch(p + r"\(.*\)\s*", t) and 1 <= len(t) <= 18:
        return True
    return False


def _is_row_label_text(t: str) -> bool:
    """행 라벨(총계/합계/소계/순계/계)인지. 규칙1 라벨 후보에서 제외."""
    return t.strip() in {"총계", "합계", "소계", "순계", "계"}


def _merge_info(tc) -> Optional[dict]:
    span = tc.find("hp:cellSpan", NS)
    if span is None:
        return None
    col_span = int(span.get("colSpan", 1))
    row_span = int(span.get("rowSpan", 1))
    if col_span == 1 and row_span == 1:
        return None
    addr = tc.find("hp:cellAddr", NS)
    col_addr = int(addr.get("colAddr", 0)) if addr is not None else 0
    row_addr = int(addr.get("rowAddr", 0)) if addr is not None else 0
    return {
        "type": "cell",
        "colAddr": col_addr,
        "rowAddr": row_addr,
        "colSpan": col_span,
        "rowSpan": row_span,
    }


def _is_nested_table(tc) -> bool:
    """셀 안에 또 표가 들어 있으면 True (중첩 표)."""
    return tc.find(".//hp:tbl", NS) is not None


def _header_cols(tbl) -> set:
    """헤더 행 판단: 첫 행(행0)에 텍스트 있는 셀이 하나라도 있으면
    그 행의 열들만 헤더 열로 본다. (단일 열 표 등 예외 처리 포함)"""
    header = tbl.find("hp:tr", NS)
    if header is None:
        return set()
    cols = set()
    for tc in header.findall("hp:tc", NS):
        addr = tc.find("hp:cellAddr", NS)
        col = int(addr.get("colAddr", 0)) if addr is not None else 0
        if _cell_text_stripped(tc):
            cols.add(col)
    return cols


def _is_label_cell(tc) -> bool:
    """규칙1에서 라벨로 볼 수 있는 셀인가?"""
    t = _cell_text_stripped(tc)
    if not t:
        return False
    if _is_guidance(tc):
        return False
    if _is_placeholder_or_unit_only(tc):
        return False
    if re.fullmatch(r"[\d\s,.]+", t):
        return False
    return True


def _label_unit(label: str, right_tc) -> str:
    """규칙1: 라벨 텍스트 + 오른쪽 셀 내용으로 단위 추정."""
    if "우편" in label or re.search(r"우편\s*번호", label):
        return "postal-code"
    if "전화" in label or "팩스" in label or "연락처" in label:
        return "phone"
    if "이메일" in label or "e-mail" in label:
        return "email"
    if "성명" in label or "이름" in label:
        return "person-name"
    if re.search(r"금액|천원|원\s*$", label):
        return "money"
    if "년" in label and "월" in label and "일" in label:
        return "date"
    if "회원" in label or re.search(r"\b수\b", label):
        return "number"
    return "text"


def _placeholder_unit(t: str) -> str:
    """규칙3: 자리표시자/단위 셀의 단위."""
    if "천원" in t:
        return "money"
    if re.search(r"원\b", t):
        return "money"
    if re.search(r"년.*월.*일", t) or re.search(r"\d.*\.\s*\d.*\.\s*\d", t):
        return "date"
    return "text"


def _is_required_label(label: str) -> bool:
    """라벨 문구로 필수 여부 추정."""
    kws = ("성명", "주소", "우편", "전화", "이메일", "대표", "실무", "시설명", "법인명")
    return any(k in label for k in kws)


# 규칙4: 한 셀 안의 "라벨 :" 패턴에서 콜론 뒤 빈자리
# ---------------------------------------------------------------------------

# A.hwpx에서 확인된 라벨 목록 (좁게 시작 — 확인된 것만)
_RULE4_LABELS = [
    "프로그램명",
    "직명",
    "성명",
    "주소",
    "우편번호",
    "연락처",
    "전화",
    "팩스",
    "이메일",
    "E-Mail",
    "대표전화",
    "FAX",
    "홈페이지",
    "등록기관",
    "등록일",
    "시설명",
    "설립목적",
    "지원근거및  내용",
    "상근직원수",
    "회원수",
    "성명 및 직위",
    "사무실(직통)",
    "휴대전화",
    "신청사업담당자 전화(휴대폰)",
]

# 라벨 → 예상 단위
_RULE4_LABEL_UNIT = {
    "우편번호": "postal-code",
    "전화": "phone",
    "팩스": "phone",
    "연락처": "phone",
    "이메일": "email",
    "E-Mail": "email",
    "대표전화": "phone",
    "FAX": "phone",
    "성명": "person-name",
    "성명 및 직위": "person-name",
    "직명": "person-name",
    "프로그램명": "text",
    "시설명": "text",
    "주소": "text",
    "등록기관": "text",
    "등록일": "date",
    "설립목적": "text",
    "지원근거및  내용": "text",
    "상근직원수": "number",
    "회원수": "number",
    "홈페이지": "text",
    "사무실(직통)": "phone",
    "휴대전화": "phone",
    "신청사업담당자 전화(휴대폰)": "phone",
}

# 라벨을 정규식으로 매칭하기 위한 패턴 (어쩔 수 없이 한글/특수문자 포함).
# 각 라벨을 리터럴로 매칭하고, 뒤에 ':' 또는 ': '가 오는지 확인.
# 우선순위: 긴 라벨 먼저.
_RULE4_LABEL_PATTERNS = sorted(
    [(r'\s*'.join(re.escape(ch) for ch in label if not ch.isspace()), label) for label in _RULE4_LABELS],
    key=lambda x: -len(x[0]),
)


def _rule4_find_in_cell(tc, table_idx, row, col, sec_path) -> list:
    """한 셀에서 규칙4 후보를 찾는다.

    한 셀 내 문단들을 순회하며, 각 문단의 run 텍스트를 '라벨 :값' 패턴으로
    검사한다. ※로 시작하는 문단은 건너뛴다.
    반환: 후보 dict 목록 (아직 field_id 없음).
    """
    sub = tc.find("hp:subList", NS)
    if sub is None:
        return []

    candidates = []
    for pi, p in enumerate(sub.findall("hp:p", NS)):
        # ※ 안내문 문단은 통째로 건너뛴다.
        p_text_all = "".join((t.text or "") for t in p.findall("hp:t", NS))
        if p_text_all.strip().startswith("※"):
            continue

        # 이 문단의 run들을 순회하며, 각 run의 텍스트에서 라벨 패턴을 찾는다.
        # 실제 채움 위치를 특정하려면 run 인덱스 + 문자 오프셋이 필요하다.
        # 여러 run에 걸쳐 라벨이 있을 수 있으나, A.hwpx에서는 각 라벨이
        # 하나의 hp:t 안에 들어 있으므로 run 단위로 처리한다.
        for ri, run in enumerate(p.findall("hp:run", NS)):
            t = run.find("hp:t", NS)
            if t is None or not t.text:
                continue
            run_text = t.text

            # 이 run에서 발견된 라벨들을 수집 (중복 매칭 방지용 taken 범위)
            taken_ranges: list = []  # (start, end) 문자 범위

            for escaped, label in _RULE4_LABEL_PATTERNS:
                # run_text 안에서 이 라벨을 찾음 (첫 번째 매칭만)
                m = re.search(escaped, run_text)
                if m is None:
                    continue
                label_start, label_end = m.start(), m.end()

                # 이미 다른 라벨이 점유한 범위와 겹치면 스킵
                if any(label_start < e and label_end > s for s, e in taken_ranges):
                    continue

                # 라벨 뒤에 ':' 또는 ': '가 오는지 확인
                # 라벨과 ':' 사이에 공백이 있을 수 있으므로
                # 라벨 끝 ~ ':' 사이 공백을 허용한 패턴으로 찾는다.
                pat = re.compile(r":" + r"\s*$")  # placeholder, 사용되지 않음
                after = run_text[label_end:]
                # ':' 앞에 공백이 0개 이상 올 수 있음
                m_colon = re.match(r"\s*:", after)
                if m_colon is None:
                    continue
                colon_pos = label_end + m_colon.end() - 1  # ':' 문자 위치
                # val_start = ':' 다음 위치
                val_start = colon_pos + 1
                # ':' 뒤 공백을 건너뛰고 값 텍스트 시작
                val_text = run_text[val_start:].lstrip()
                for other_pattern, other_label in _RULE4_LABEL_PATTERNS:
                    if other_label == label:
                        continue
                    following = re.search(other_pattern + r'\s*:', val_text)
                    if following and not val_text[:following.start()].strip(' \t\r\n()[]{}'):
                        val_text = ''
                        break
                # 값이 있으면(공백이 아닌 텍스트가 뒤에 더 있으면) 후보인지 재평가
                if val_text:
                    # 첫 번째 토큰이 닫는 괄호면 값 없음으로 간주
                    m_first = re.match(r"[^\s]+", val_text)
                    if m_first and m_first.group() in {")", "]", "}", "）"}:
                        val_text = ""
                    # 첫 번째 토큰이 다른 라벨이면 값 없음으로 간주
                    # (현재 라벨의 값이 비어 있고 뒤에 다른 라벨이 오는 경우)
                    elif m_first:
                        first_token = m_first.group()
                        for other_escaped, other_label in _RULE4_LABEL_PATTERNS:
                            if other_label == label:
                                continue
                            if re.match(other_escaped + r"(\s|$)", first_token):
                                val_text = ""
                                break
                # 값이 있으면(공백이 아닌 텍스트가 뒤에 더 있으면) 후보 아님
                if val_text:
                    # 값이 이미 있음 → 후보에서 제외
                    after_colon = run_text[val_start:]
                    spaces_after = 0
                    while (val_start + spaces_after < len(run_text)
                           and run_text[val_start + spaces_after] == " "):
                        spaces_after += 1
                    taken_ranges.append((label_start, colon_pos + 1 + spaces_after))
                    continue

                # 여기까지: 라벨 + (공백) + ':' + (공백만) → 후보
                # 실제 삽입 위치: ':' 바로 뒤 (val_start)
                insert_offset = val_start  # run 텍스트 내 오프셋

                # 단위
                unit = _RULE4_LABEL_UNIT.get(label, "text")

                # 필수 여부
                required = _is_required_label(label)

                # 문맥
                context = (
                    f"라벨 '{label}' 뒤 빈자리 (표#{table_idx}, "
                    f"행{row}, 열{col}, 문단{pi}, run{ri})"
                )

                candidates.append(
                    _field(
                        field_id="",
                        label=label,
                        location={
                            "type": "cell",
                            "section": sec_path,
                            "table_path": [table_idx, 0],
                            "row": row,
                            "col": col,
                            "paragraph_index": pi,
                            "run_index": ri,
                            "insert_offset": insert_offset,
                        },
                        context=context,
                        unit=unit,
                        editable=True,
                        required=required,
                        merge_info=_merge_info(tc),
                        rule="rule4",
                        notes=None,
                    )
                )

                # 점유 범위: 라벨 시작 ~ ':' 뒤 공백 끝까지
                after_colon = run_text[val_start:]
                spaces_after = 0
                while (val_start + spaces_after < len(run_text)
                       and run_text[val_start + spaces_after] == " "):
                    spaces_after += 1
                taken_ranges.append((label_start, colon_pos + 1 + spaces_after))

    return candidates


def _is_guidance_tc(tc) -> bool:
    """셀 전체에 ※ 안내문이 있으면 True. 규칙4에서도 제외 기준으로 사용."""
    return _is_guidance(tc)


# ---------------------------------------------------------------------------
# analyze_a
# ---------------------------------------------------------------------------

def analyze_a(raw: bytes) -> dict:
    """A 양식 HWPX를 읽어 입력란 후보 목록을 반환한다. (MVP: 표 셀만)

    입력은 원본 HWPX 바이트이며 편집 위치는 서버 내부 정보다
    """
    # --- 원본 해시 ---
    a_hash = hashlib.sha256(raw).hexdigest()

    document = read_xml(raw)

    all_fields: List[dict] = []
    warnings: List[str] = []
    table_idx_global = 0  # 문서 순서대로 세는 최상위 표 인덱스

    roots = {}
    for section in document.sections:
        sec_path = section.path
        root = parse_xml(section.bytes)
        roots[sec_path] = root

        tables = root.findall(".//hp:tbl", NS)
        for t_idx, tbl in enumerate(tables):
            table_idx_global = t_idx
            cell_map: dict = {}
            for tc in tbl.findall("hp:tr/hp:tc", NS):
                addr = tc.find("hp:cellAddr", NS)
                col = int(addr.get("colAddr", 0)) if addr is not None else 0
                row = int(addr.get("rowAddr", 0)) if addr is not None else 0
                cell_map[(col, row)] = tc

            if not cell_map:
                continue

            max_row = max(r for _, r in cell_map)
            max_col = max(c for c, _ in cell_map)

            taken: set = set()

            # ------------------------------------------------------------------
            # 규칙 1: 라벨 셀 + 오른쪽 빈 셀
            # ------------------------------------------------------------------
            for (col, row), tc in sorted(cell_map.items()):
                if (col, row) in taken:
                    continue
                if _is_nested_table(tc):
                    continue
                if not _is_label_cell(tc):
                    continue
                txt = _cell_text_stripped(tc)
                if _is_row_label_text(txt):
                    continue
                required = _is_required_label(txt)
                span = tc.find("hp:cellSpan", NS)
                right_col = col + (int(span.get("colSpan", "1")) if span is not None else 1)
                if right_col > max_col:
                    continue
                right_tc = cell_map.get((right_col, row))
                if right_tc is None:
                    continue
                if _is_guidance(right_tc):
                    continue
                if not _is_empty(right_tc):
                    continue
                unit = _label_unit(txt, _cell_text_stripped(right_tc))
                taken.add((right_col, row))
                all_fields.append(_field(
                    field_id="",
                    label=txt,
                    location={"type": "cell", "section": sec_path,
                              "table_path": [table_idx_global, 0],
                              "row": row, "col": right_col},
                    context=f"라벨 '{txt}' 오른쪽 셀 (표#{table_idx_global}, 행{row}, 열{col+1})",
                    unit=unit,
                    editable=True,
                    required=required,
                    merge_info=_merge_info(right_tc),
                    rule="rule1",
                    notes=None,
                ))

            # ------------------------------------------------------------------
            # 규칙 4: 한 셀 안의 "라벨 :" 뒤 빈자리
            # ------------------------------------------------------------------
            for (col, row), tc in sorted(cell_map.items()):
                if (col, row) in taken:
                    continue
                if _is_nested_table(tc):
                    continue
                rule4_candidates = _rule4_find_in_cell(
                    tc, table_idx_global, row, col, sec_path
                )
                for fc in rule4_candidates:
                    taken.add((col, row))
                    all_fields.append(fc)

            # ------------------------------------------------------------------
            # 규칙 2: 헤더 행 아래 빈 셀
            # ------------------------------------------------------------------
            header_cols = _header_cols(tbl)
            if header_cols:
                for (col, row), tc in sorted(cell_map.items()):
                    if (col, row) in taken:
                        continue
                    if row == 0:
                        continue
                    if col not in header_cols:
                        continue
                    if _is_guidance(tc):
                        continue
                    if not _is_empty(tc):
                        continue
                    taken.add((col, row))
                    all_fields.append(_field(
                        field_id="",
                        label="",
                        location={"type": "cell", "section": sec_path,
                                  "table_path": [table_idx_global, 0],
                                  "row": row, "col": col},
                        context=f"헤더 행 아래 빈 셀 (표#{table_idx_global}, 행{row}, 열{col})",
                        unit="text",
                        editable=True,
                        required=False,
                        merge_info=_merge_info(tc),
                        rule="rule2",
                        notes=None,
                    ))

            # ------------------------------------------------------------------
            # 규칙 3: 자리표시자/단위만 있는 셀
            # ------------------------------------------------------------------
            for (col, row), tc in sorted(cell_map.items()):
                if (col, row) in taken:
                    continue
                if _is_guidance(tc):
                    continue
                if _is_placeholder_or_unit_only(tc):
                    taken.add((col, row))
                    t = _cell_text_stripped(tc)
                    all_fields.append(_field(
                        field_id="",
                        label="",
                        location={"type": "cell", "section": sec_path,
                                  "table_path": [table_idx_global, 0],
                                  "row": row, "col": col},
                        context=f"자리표시자/단위만 있는 셀: '{t}' (표#{table_idx_global}, 행{row}, 열{col})",
                        unit=_placeholder_unit(t),
                        editable=True,
                        required=False,
                        merge_info=_merge_info(tc),
                        rule="rule3",
                        notes=None,
                    ))

            table_idx_global += 1

    # --- field_id 부여 ---
    for f in all_fields:
        position = json.dumps(f['location'], sort_keys=True)
        f["field_id"] = 'f-' + hashlib.sha256((a_hash + position).encode()).hexdigest()[:24]
        try:
            node = target(roots[f['location']['section']], f, create=False)
            f['original_text'] = (node.text or '') if node is not None else ''
        except ValueError as exc:
            f['editable'] = False
            f['notes'] = str(exc)
        if f['rule'] == 'rule3':
            f['editable'] = False
            f['notes'] = '단위/자리표시자 구간은 검토 필요'

    status = "ok" if all_fields else "partial"
    if not all_fields:
        warnings.append("입력란 후보가 없음")

    return {
        "analysis_id": f"a-{a_hash[:24]}",
        "a_hash": a_hash,
        "file_kind": "hwpx",
        "analysis_status": status,
        "warnings": warnings,
        "failure": None,
        "fields": all_fields,
    }


# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------

def _field(field_id, label, location, context, unit, editable,
           required=False, merge_info=None, rule=None, notes=None) -> dict:
    return {
        "field_id": field_id,
        "label": label,
        "location": location,
        "context": context,
        "unit": unit,
        "editable": editable,
        "required": required,
        "merge_info": merge_info,
        "status": "ok",
        "rule": rule,
        "notes": notes,
    }
