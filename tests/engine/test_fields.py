"""tests/engine/test_fields.py -- 라벨과 복합 입력란 검사.

실제 hwpx.analyze.analyze_fields를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import unittest
import hashlib
import io
import zipfile

from hwpx.package import read_hwpx
from hwpx.xml import read_xml
from hwpx.tables import read_tables
from hwpx.analyze import analyze_a, analyze_fields, CONTENT_NS


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _content_hpf(sections: list[str]) -> bytes:
    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append('<HpF xmlns="http://www.hwpzone.org/hwpx">')
    for name in sections:
        parts.append(f'<section href="{name}"/>')
    parts.append('</HpF>')
    return "".join(parts).encode("utf-8")


def _section_bytes(label: str, paras: list[str], tables: list[bytes] | None = None) -> bytes:
    inner: list[str] = []
    for p in paras:
        if p == "":
            inner.append('<hp:p><hp:t></hp:t></hp:p>')
        elif p == "empty":
            inner.append('<hp:p><hp:t/></hp:p>')
        elif p == "label":
            inner.append('<hp:p><hp:t>이름:</hp:t></hp:p>')
        elif p == "value":
            inner.append('<hp:p><hp:t>홍길동</hp:t></hp:p>')
        else:
            inner.append(f'<hp:p><hp:t>{p}</hp:t></hp:p>')
    if tables:
        for t in tables:
            if isinstance(t, bytes):
                inner.append(t.decode("utf-8"))
            elif isinstance(t, str):
                inner.append(t)
            else:
                inner.extend(t)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<hp:section xmlns:hp="http://www.hwpzone.org/hwpx">'
        + "".join(inner)
        + "</hp:section>"
    ).encode("utf-8")


def _simple_table(rows: list[list[str]], first_row_header: bool = True, first_col_header: bool = True) -> str:
    """간단한 표 XML 문자열(<hp:tbl>...</hp:tbl>)을 반환한다.

    rows: 각 행은 셀 텍스트 리스트.
    첫 행과 첫 열이 헤더 역할을 한다고 가정한다(이번 단순 구현 기준).
    """
    body: list[str] = []
    for r_idx, cells in enumerate(rows):
        cells_xml: list[str] = []
        for c_idx, text in enumerate(cells):
            if text == "":
                cells_xml.append('<hp:tc><hp:t></hp:t></hp:tc>')
            elif text == "empty":
                cells_xml.append('<hp:tc><hp:t/></hp:tc>')
            else:
                cells_xml.append(f'<hp:tc><hp:t>{text}</hp:t></hp:tc>')
        body.append(f'<hp:tr>{"".join(cells_xml)}</hp:tr>')
    return (
        '<hp:tbl xmlns:hp="http://www.hwpzone.org/hwpx">'
        + "".join(body)
        + "</hp:tbl>"
    )


def _hwpx_bytes(section_entries: list[tuple[str, list[str], list[str] | None]]) -> bytes:
    section_names: list[str] = []
    section_data: dict[str, bytes] = {}
    for entry in section_entries:
        if len(entry) == 2:
            name, paras = entry
            tables = None
        else:
            name, paras, tables = entry
        idx = len(section_names) + 1
        oname = f"section{idx}.xml"
        section_names.append(oname)
        section_data[oname] = _section_bytes(name, paras, tables)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("Content.hpf", _content_hpf(section_names))
        for oname, data in section_data.items():
            zf.writestr(oname, data)
    return buf.getvalue()


class TestAnalyzeFields(unittest.TestCase):
    def test_find_value_cells_in_diff_fixtures(self):
        # fixture 1: 문단 라벨 + 값
        b1 = _hwpx_bytes([
            ("S1", ["이름:", "홍길동"]),
        ])
        sha1 = _sha256(b1)
        xml1 = read_xml(b1)
        cand1 = analyze_a(xml1, a_bytes=b1, a_sha256=sha1).fields
        tables1 = read_tables(xml1)
        fields1 = analyze_fields(xml1, tables1, cand1, a_bytes=b1, a_sha256=sha1).fields

        # fixture 2: 표 값
        tbl2 = _simple_table([
            ["구분", "값"],
            ["성명", "김철수"],
        ])
        b2 = _hwpx_bytes([
            ("S2", [""], [tbl2]),
        ])
        sha2 = _sha256(b2)
        xml2 = read_xml(b2)
        cand2 = analyze_a(xml2, a_bytes=b2, a_sha256=sha2).fields
        tables2 = read_tables(xml2)
        fields2 = analyze_fields(xml2, tables2, cand2, a_bytes=b2, a_sha256=sha2).fields

        # 각 fixture에서 값 칸이 필드로 잡혔는지 확인
        self.assertTrue(any(f["originalText"] == "홍길동" for f in fields1))
        self.assertTrue(any(f["originalText"] == "김철수" for f in fields2))

    def test_empty_decoration_cell_not_falsely_detected(self):
        # 빈 셀이 있는 표에서 빈 장식 셀은 입력란으로 오탐하지 않음
        tbl = _simple_table([
            ["구분", "값"],
            ["성명", "홍길동"],
            ["", ""],
        ])
        b = _hwpx_bytes([
            ("S", [""], [tbl]),
        ])
        sha = _sha256(b)
        xml = read_xml(b)
        cand = analyze_a(xml, a_bytes=b, a_sha256=sha).fields
        tables = read_tables(xml)
        fields = analyze_fields(xml, tables, cand, a_bytes=b, a_sha256=sha).fields

        texts = [f["originalText"] for f in fields]
        self.assertIn("홍길동", texts)
        self.assertNotIn("", texts)
        self.assertEqual(len(fields), 1)

    def test_composite_input_fields_same_cell_two_fields(self):
        # 같은 셀에 "직명 / 성명"처럼 복합 값이 있으면 별도 입력 구간으로 연결
        tbl = _simple_table([
            ["구분", "내용"],
            ["직위", "직명 / 성명"],
        ])
        b = _hwpx_bytes([
            ("S", [""], [tbl]),
        ])
        sha = _sha256(b)
        xml = read_xml(b)
        cand = analyze_a(xml, a_bytes=b, a_sha256=sha).fields
        tables = read_tables(xml)
        fields = analyze_fields(xml, tables, cand, a_bytes=b, a_sha256=sha).fields

        labels = [f["label"] for f in fields]
        texts = [f["originalText"] for f in fields]

        # 복합 값이 두 필드로 나뉘어야 함
        self.assertTrue(any("직명" in t for t in texts))
        self.assertTrue(any("성명" in t for t in texts))
        self.assertEqual(len(fields), 2)

    def test_composite_address_zip_fields(self):
        # "주소 / 우편번호" 복합 입력란도 별도 필드로 분리
        tbl = _simple_table([
            ["구분", "내용"],
            ["주소", "서울특별시 / 04524"],
        ])
        b = _hwpx_bytes([
            ("S", [""], [tbl]),
        ])
        sha = _sha256(b)
        xml = read_xml(b)
        cand = analyze_a(xml, a_bytes=b, a_sha256=sha).fields
        tables = read_tables(xml)
        fields = analyze_fields(xml, tables, cand, a_bytes=b, a_sha256=sha).fields

        texts = [f["originalText"] for f in fields]
        self.assertTrue(any("서울특별시" in t for t in texts))
        self.assertTrue(any("04524" in t for t in texts))
        self.assertEqual(len(fields), 2)


if __name__ == "__main__":
    unittest.main()
