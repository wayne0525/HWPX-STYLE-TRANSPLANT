"""tests/engine/test_tables.py — HWPX 표 격자·병합·중첩 검사.

실제 hwpx/tables.py를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import io
import unittest
import zipfile

from hwpx.xml import read_xml
from hwpx.tables import read_tables, TABLE_NS


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


def _make_table_xml(*, rows, namespaces=None):
    """rows: list of list of cell text (str). 중첩 표는 별도로 만들지 않고, 여기서는 단순 표만 만든다.

    병합은 속성 기반으로 따로 만든다(아래 fixture들).
    """
    ns = 'xmlns="http://www.hwpzone.org/hwpx"'
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<root {ns}>', '<tbl>']
    for i, row in enumerate(rows):
        out.append('<tr n="%d">' % i)
        for j, cell in enumerate(row):
            out.append('<tc n="%d">%s</tc>' % (j, cell))
        out.append('</tr>')
    out.append('</tbl>')
    out.append('</root>')
    return "\n".join(out).encode("utf-8")


def _make_table_with_gridspan(*, rows_spec):
    """rows_spec: list of rows; each row is list of (text, grid_span).

    가로 병합을 gridSpan 속성으로 표현한다.
    """
    ns = 'xmlns="http://www.hwpzone.org/hwpx"'
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


def _make_table_with_vmerge(*, rows_spec):
    """rows_spec: list of rows; each row is list of (text, vmerge).

    vMerge 속성: 1/start면 세로 병합 시작, continue면 이어짐.
    """
    ns = 'xmlns="http://www.hwpzone.org/hwpx"'
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


def _make_nested_table_xml(*, outer_rows, inner_text):
    """셀 하나에 표를 넣는 중첩 표 fixture.

    중첩 표의 텍스트는 부모 셀 본문과 분리하고, 부모 셀 텍스트와 중복 집계하지 않는다.
    """
    ns = 'xmlns="http://www.hwpzone.org/hwpx"'
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<root {ns}>', '<tbl>']
    for i, row in enumerate(outer_rows):
        out.append('<tr n="%d">' % i)
        for j, cell in enumerate(row):
            if isinstance(cell, tuple) and cell[0] == "nested":
                out.append('<tc n="%d">%s</tc>' % (j, cell[1]))
            else:
                out.append('<tc n="%d">%s</tc>' % (j, cell))
        out.append('</tr>')
    out.append('</tbl>')
    out.append('</root>')
    return "\n".join(out).encode("utf-8")


# ---------------------------------------------------------------------------
# 가로 병합
# ---------------------------------------------------------------------------

class TestHorizontalMerge(unittest.TestCase):
    def test_gridspan_cells_have_correct_coords_and_text(self):
        xml = _make_table_with_gridspan(
            rows_spec=[
                [("A", 2), ("B", 1)],
                [("C", 1), ("D", 1)],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)
        self.assertEqual(len(tables.tables), 1)
        t = tables.tables[0]
        self.assertEqual(t.row_count, 2)
        self.assertEqual(t.column_count, 3)

        row0 = t.rows[0]
        self.assertEqual(len(row0), 2)
        self.assertEqual(row0[0].column_index, 0)
        self.assertEqual(row0[0].grid_span, 2)
        self.assertEqual(row0[0].text, "A")
        self.assertEqual(row0[1].column_index, 2)
        self.assertEqual(row0[1].grid_span, 1)
        self.assertEqual(row0[1].text, "B")

        row1 = t.rows[1]
        self.assertEqual(row1[0].text, "C")
        self.assertEqual(row1[1].text, "D")

        # 가로 병합 그룹 존재
        hmerges = [m for m in t.merges if m.type == "hmerge"]
        self.assertTrue(any(m.start_col == 0 and m.spans[0][0] == 2 for m in hmerges))


# ---------------------------------------------------------------------------
# 세로 병합
# ---------------------------------------------------------------------------

class TestVerticalMerge(unittest.TestCase):
    def test_vmerge_cells_have_correct_coords_and_text(self):
        xml = _make_table_with_vmerge(
            rows_spec=[
                [("X", "1"), ("Y", "")],
                [("", "continue"), ("Z", "")],
            ]
        )
        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)
        t = tables.tables[0]
        self.assertEqual(t.row_count, 2)
        self.assertEqual(t.column_count, 2)

        row0 = t.rows[0]
        self.assertEqual(row0[0].text, "X")
        self.assertEqual(row0[0].vmerge, "start")
        self.assertEqual(row0[1].text, "Y")

        row1 = t.rows[1]
        # 세로 병합 이어짐 셀은 텍스트가 비어 있어도 좌표가 있어야 한다.
        self.assertEqual(row1[0].column_index, 0)
        self.assertEqual(row1[0].vmerge, "continue")
        self.assertEqual(row1[0].text, "")
        self.assertEqual(row1[1].text, "Z")

        vmerges = [m for m in t.merges if m.type == "vmerge"]
        self.assertTrue(any(m.start_col == 0 for m in vmerges))


# ---------------------------------------------------------------------------
# 복합 병합
# ---------------------------------------------------------------------------

class TestCombinedMerge(unittest.TestCase):
    def test_gridspan_and_vmerge_together(self):
        xml = _make_hwpx_bytes(  # noqa: F841
            section_paths=["s.xml"],
            section_xmls={
                "s.xml": _make_table_with_gridspan(
                    rows_spec=[
                        [("TopLeft", 2), ("TopRight", 1)],
                        [("", 1), ("BottomRight", 1)],
                    ]
                )
            },
        )
        # 실제 복합 병합 예시는 세로+가로 혼합이 더 분명하므로, 별도 fixture로 만든다.
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<root xmlns="http://www.hwpzone.org/hwpx">'
            '<tbl>'
            '<tr n="0">'
            '<tc n="0" gridSpan="2" vMerge="1">TL</tc>'
            '<tc n="2">TR</tc>'
            '</tr>'
            '<tr n="1">'
            '<tc n="0" gridSpan="2">BL</tc>'
            '<tc n="2">BR</tc>'
            '</tr>'
            '</tbl>'
            '</root>'
        ).encode("utf-8")
        raw = _make_hwpx_bytes(section_paths=["s.xml"], section_xmls={"s.xml": xml})
        res = read_xml(raw)
        tables = read_tables(res)
        t = tables.tables[0]
        self.assertEqual(t.row_count, 2)
        self.assertEqual(t.column_count, 3)

        row0 = t.rows[0]
        self.assertEqual(row0[0].text, "TL")
        self.assertEqual(row0[0].grid_span, 2)
        self.assertEqual(row0[0].vmerge, "start")
        self.assertEqual(row0[1].text, "TR")

        row1 = t.rows[1]
        self.assertEqual(row1[0].text, "BL")
        self.assertEqual(row1[0].grid_span, 2)
        self.assertEqual(row1[1].text, "BR")

        hmerges = [m for m in t.merges if m.type == "hmerge"]
        vmerges = [m for m in t.merges if m.type == "vmerge"]
        self.assertTrue(any(m.start_col == 0 and m.spans[0][0] == 2 for m in hmerges))
        self.assertTrue(any(m.start_col == 0 for m in vmerges))


# ---------------------------------------------------------------------------
# 중첩 표: 부모 셀 본문과 분리, 셀 텍스트 중복 집계 없음
# ---------------------------------------------------------------------------

class TestNestedTable(unittest.TestCase):
    def test_nested_table_separated_from_parent_cell_text(self):
        inner_table_xml = (
            '<tbl xmlns="http://www.hwpzone.org/hwpx">'
            '<tr n="0"><tc n="0">inner-a</tc><tc n="1">inner-b</tc></tr>'
            '</tbl>'
        )
        outer_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<root xmlns="http://www.hwpzone.org/hwpx">'
            '<tbl>'
            '<tr n="0">'
            '<tc n="0">outer-1</tc>'
            '<tc n="1">'
            + inner_table_xml
            + '</tc>'
            '</tr>'
            '<tr n="1">'
            '<tc n="0">outer-2</tc>'
            '<tc n="1">outer-3</tc>'
            '</tr>'
            '</tbl>'
            '</root>'
        ).encode("utf-8")

        raw = _make_hwpx_bytes(
            section_paths=["s.xml"], section_xmls={"s.xml": outer_xml}
        )
        res = read_xml(raw)
        tables = read_tables(res)

        self.assertEqual(len(tables.tables), 2)  # 외부 표 + 중첩 표
        outer = tables.tables[0]
        inner = tables.tables[1]

        # 외부 표의 셀 1,1은 중첩 표를 포함하지만, 텍스트는 외부 셀만의 직접 텍스트로 남는다.
        cell = outer.rows[0][1]
        self.assertTrue(cell.has_inner_table)
        self.assertEqual(cell.text, "")

        # 중첩 표는 별도 표로 읽히고, 그 텍스트는 중첩 표 셀에서 나온다.
        self.assertEqual(inner.row_count, 1)
        self.assertEqual(inner.rows[0][0].text, "inner-a")
        self.assertEqual(inner.rows[0][1].text, "inner-b")

        # 외부 셀 텍스트가 중첩 표 텍스트를 중복해서 포함하지 않는다.
        outer_texts = [c.text for row in outer.rows for c in row]
        joined = "\n".join(outer_texts)
        self.assertNotIn("inner-a", joined)
        self.assertNotIn("inner-b", joined)
        self.assertIn("outer-1", joined)
        self.assertIn("outer-2", joined)
        self.assertIn("outer-3", joined)


# ---------------------------------------------------------------------------
# 실행 확인용
# ---------------------------------------------------------------------------

class TestTablesExecutionMarker(unittest.TestCase):
    def test_this_module_is_executed(self):
        self.assertTrue(True)
