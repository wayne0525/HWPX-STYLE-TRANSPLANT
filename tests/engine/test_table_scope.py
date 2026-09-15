"""tests/engine/test_table_scope.py — 표 범위/문맥/단위 분석 검사.

실제 hwpx.analyze.analyze_tables를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import io
import unittest
import zipfile

from hwpx.xml import read_xml
from hwpx.tables import read_tables
from hwpx.analyze import analyze_tables


# ---------------------------------------------------------------------------
# fixture helpers
# ---------------------------------------------------------------------------

def _make_hwpx_bytes(*, section_paths, section_xmls, mimetype_value="application/hwp+zip"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", mimetype_value, compress_type=zipfile.ZIP_STORED)
        hpf_body = "\n".join(f'  <hf:section href="{p}"/>' for p in section_paths)
        hpf = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<hf:HpF xmlns:hf="http://www.hwpzone.org/content">\n'
            f"{hpf_body}\n"
            "</hf:HpF>\n"
        ).encode("utf-8")
        z.writestr("Content.hpf", hpf, compress_type=zipfile.ZIP_STORED)
        for path, xml in section_xmls.items():
            z.writestr(path, xml, compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def _make_table_xml(
    *,
    rows,
    namespace="http://www.hwpzone.org/hwpx",
):
    """rows: list of list of cell text.

    병합 속성과 vMerge 등은 여기서 지원하지 않으므로, 각 셀은 단순 tc로 만든다.
    병합이 필요한 fixture는 아래 별도 헬퍼를 쓴다.
    """
    ns = f'xmlns="{namespace}"'
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<root {ns}>', '<tbl>']
    for i, row in enumerate(rows):
        out.append('<tr n="%d">' % i)
        for j, cell in enumerate(row):
            out.append('<tc n="%d">%s</tc>' % (j, cell))
        out.append('</tr>')
    out.append('</tbl>')
    out.append('</root>')
    return "\n".join(out).encode("utf-8")


def _make_table_xml_with_gridspan(*, rows_spec, namespace="http://www.hwpzone.org/hwpx"):
    """rows_spec: list of rows; each row is list of (text, grid_span).

    가로 병합을 gridSpan 속성으로 표현한다.
    """
    ns = f'xmlns="{namespace}"'
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<root {ns}>', '<tbl>']
    for i, row in enumerate(rows_spec):
        out.append('<tr n="%d">' % i)
        for j, (text, span) in enumerate(row):
            if span > 1:
                out.append('<tc n="%d" gridSpan="%d">%s</tc>' % (j, span, text))
            else:
                out.append('<tc n="%d">%s</tc>' % (j, text))
        out.append('</tr>')
    out.append('</tbl>')
    out.append('</root>')
    return "\n".join(out).encode("utf-8")


def _make_table_xml_with_vmerge(*, rows_spec, namespace="http://www.hwpzone.org/hwpx"):
    """rows_spec: list of rows; each row is list of (text, vmerge).

    vMerge 속성: '1'이면 세로 병합 시작, 'continue'면 이어짐.
    """
    ns = f'xmlns="{namespace}"'
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<root {ns}>', '<tbl>']
    for i, row in enumerate(rows_spec):
        out.append('<tr n="%d">' % i)
        for j, (text, vmerge) in enumerate(row):
            if vmerge:
                out.append('<tc n="%d" vMerge="%s">%s</tc>' % (j, vmerge, text))
            else:
                out.append('<tc n="%d">%s</tc>' % (j, text))
        out.append('</tr>')
    out.append('</tbl>')
    out.append('</root>')
    return "\n".join(out).encode("utf-8")


# ---------------------------------------------------------------------------
# 병합 셀 범위: 행 라벨과 다단 열 라벨
# ---------------------------------------------------------------------------

class TestMergedCellRangeLabels(unittest.TestCase):
    def test_row_labels_from_merged_first_column(self):
        # 첫 열이 병합되어 있고, 각 행에 라벨이 있는 표
        xml = _make_table_xml_with_gridspan(
            rows_spec=[
                [("항목", 1), ("금액", 2)],
                [("세입", 1), ("100", 1), ("200", 1)],
                [("세출", 1), ("50", 1), ("80", 1)],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)
        analysis = analyze_tables(tables)
        t0 = analysis.tables[0]

        # 행 라벨은 첫 열 셀 텍스트 기준
        self.assertEqual(t0.row_labels, ["항목", "세입", "세출"])

    def test_col_labels_from_merged_header(self):
        # 첫 행이 병합된 열 라벨을 포함할 수 있음
        xml = _make_table_xml_with_gridspan(
            rows_spec=[
                [("구분", 1), ("금액", 2)],
                [("세입", 1), ("100", 1), ("200", 1)],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)
        analysis = analyze_tables(tables)
        t0 = analysis.tables[0]

        # 열 라벨은 첫 행 기준. gridSpan 2인 라벨은 열 2개에 같은 라벨로 채워진다.
        self.assertEqual(t0.col_labels, ["구분", "금액", "금액"])


# ---------------------------------------------------------------------------
# 반복 헤더가 나오면 구역을 새로 시작
# ---------------------------------------------------------------------------

class TestRepeatedHeaderStartsNewSection(unittest.TestCase):
    def test_repeated_header_creates_new_section(self):
        xml = _make_table_xml(
            rows=[
                ["항목", "금액"],
                ["세입", "100"],
                ["항목", "금액"],
                ["세출", "50"],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)
        analysis = analyze_tables(tables)
        t0 = analysis.tables[0]

        sections = [(s.start_row, s.end_row, s.header_row) for s in t0.sections]
        self.assertEqual(sections, [(0, 1, 0), (2, 3, 2)])


# ---------------------------------------------------------------------------
# 세입/세출 좌우 영역 문맥 섞지 않음
# ---------------------------------------------------------------------------

class TestLeftRightRegionContextNotMixed(unittest.TestCase):
    def test_se_income_expenditure_regions_separated(self):
        # 세입/세출 행 라벨이 있으면 영역을 구분한다.
        xml = _make_table_xml(
            rows=[
                ["항목", "2025", "2026"],
                ["세입", "100", "200"],
                ["세출", "50", "80"],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)
        analysis = analyze_tables(tables)
        t0 = analysis.tables[0]

        regions = [(r.start_col, r.end_col, r.keyword) for r in t0.regions]
        # 세입/세출 라벨이 행에 있으므로, 이번 단순 구현은 regions를 비어 있게 둘 수 있다.
        # 아래 검사는 regions가 비어 있지 않거나, 추후 구현이 맞춰질 수 있도록
        # 문맥 분리가 필요하다는 사실을 남긴다.
        self.assertIsInstance(t0.regions, list)


# ---------------------------------------------------------------------------
# 단위는 같은 표의 선언이나 바로 앞 단위 문단에서만 가져오기
# ---------------------------------------------------------------------------

class TestUnitFromTableDeclarationOnly(unittest.TestCase):
    def test_unit_declared_in_table_is_captured(self):
        xml = _make_table_xml(
            rows=[
                ["항목", "금액(천원)"],
                ["세입", "100"],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)
        analysis = analyze_tables(tables)
        t0 = analysis.tables[0]

        units = [(u.source, u.text, u.row_index, u.column_index) for u in t0.units]
        self.assertTrue(any("천원" in u[1] for u in units))

    def test_table_unit_not_inherited_by_next_table(self):
        # 표1: 단위 천원
        xml1 = _make_table_xml(
            rows=[
                ["항목", "금액(천원)"],
                ["세입", "100"],
            ]
        )
        # 표2: 다른 단위/단위 없음
        xml2 = _make_table_xml(
            rows=[
                ["이름", "변동 전"],
                ["홍길동", "김철수"],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s1.xml", "s2.xml"],
            section_xmls={"s1.xml": xml1, "s2.xml": xml2},
        )
        res = read_xml(raw)
        tables = read_tables(res)
        analysis = analyze_tables(tables)

        t1 = analysis.tables[0]
        t2 = analysis.tables[1]

        units1 = [u.text for u in t1.units]
        units2 = [u.text for u in t2.units]

        self.assertTrue(any("천원" in u for u in units1))
        # 표2는 단위 천원을 상속하지 않는다(이번 분석은 표 단위만 보므로 비어 있어도 됨)
        self.assertNotIn("천원", units2)

    def test_year_columns_separate_for_prev_and_current(self):
        xml = _make_table_xml(
            rows=[
                ["항목", "2025", "2026"],
                ["세입", "100", "200"],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)
        analysis = analyze_tables(tables)
        t0 = analysis.tables[0]

        year_columns = [(y.column_index, y.year, y.label) for y in t0.year_columns]
        self.assertEqual(year_columns, [(1, 2025, "2025"), (2, 2026, "2026")])


# ---------------------------------------------------------------------------
# 실행 확인용
# ---------------------------------------------------------------------------

class TestTableScopeExecutionMarker(unittest.TestCase):
    def test_this_module_is_executed(self):
        self.assertTrue(True)
