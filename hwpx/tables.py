"""HWPX 표 격자·병합·중첩 테이블 읽기.

이번 E03 번호의 실제 진입점은 read_tables 하나로 둔다.
계약(docs/TEAM_CONTRACT.md)에는 아직 표 함수 계약이 없으므로,
이번 번호의 함수명과 입출력은 내부 계약으로 사용한다.

설계
- 행과 열 격자, 병합 범위, 셀 좌표를 구성한다.
- 중첩 표는 부모 셀 본문과 분리한다.
- 셀 텍스트를 중복 집계하지 않는다.
- 가로/세로/복합 병합과 중첩 표에서 셀 좌표와 원문이 일치해야 한다.
- 표 요소는 namespace URI로 찾는다(접두자 달라도 같은 URI면 같은 표).
"""

from __future__ import annotations

from typing import Any

from hwpx.errors import DomainError, TABLE_COORD_BAD
from hwpx.xml import XmlReadResult


# ---------------------------------------------------------------------------
# 이번 번호가 다루는 표 관련 namespace/요소
# ---------------------------------------------------------------------------

# HWPX 표 관련 URI 후보. 실제 문서는 이 외에도 여러 네임스페이스를 쓸 수 있고,
# 이번 번호는 우선 아래 URI를 표 관련 내부 URI로 본다.
TABLE_NS = "http://www.hwpzone.org/hwpx"

# 표 관련 로컬 이름 후보. 실제 속성/구조는 HWpX 버전에 따라 다를 수 있으므로,
# 이번 번호는 아래 로컬 이름을 우선 찾고, 없으면 표 모델을 만들지 않는다.
TABLE_LOCALS = ("tbl",)
ROW_LOCALS = ("tr",)
CELL_LOCALS = ("tc",)

# 병합 관련 속성 후보
GRID_SPAN_ATTRS = ("gridSpan",)
VMERGE_ATTRS = ("vMerge",)


def read_tables(xml_result: XmlReadResult) -> TablesReadResult:
    """read_xml 결과에서 표 격자/병합/셀 좌표를 읽는다.

    중첩 표는 부모 셀 본문과 분리하고, 셀 텍스트를 중복 집계하지 않는다.
    """
    tables: list[TableReadResult] = []
    for section in xml_result.sections:
        section_tables = _read_section_tables(section)
        tables.extend(section_tables)
    return TablesReadResult(
        original_bytes=xml_result.original_bytes,
        original_sha256=xml_result.original_sha256,
        tables=tables,
    )


def read_section_tables(section: Any) -> list[TableReadResult]:
    """한 section에서 표들을 찾는다. section 단위로 표를 읽을 때 사용한다."""
    return _read_section_tables(section)


def _read_section_tables(section: Any) -> list[TableReadResult]:
    """한 section에서 표들을 찾는다.

    section 트리 전체를 순회하면서 표 요소를 찾고, 각 표의 행/셀을 구성한다.
    """
    tables: list[TableReadResult] = []
    for tbl_el in _find_tables(section.tree.root):
        table = _build_table(tbl_el)
        if table is not None:
            tables.append(table)
    return tables


def _find_tables(root: Any) -> list[Any]:
    """표 요소들을 찾는다.

    namespace URI + 로컬 이름 기준으로 찾는다.
    """
    found: list[Any] = []
    for el in _iter_elements(root):
        if _is_named(el, TABLE_NS, TABLE_LOCALS):
            found.append(el)
    return found


def _is_named(el: Any, ns_uri: str, locals_: tuple[str, ...]) -> bool:
    return el.ns_uri == ns_uri and el.local in locals_


def _iter_elements(el: Any):
    yield el
    for child in el.children:
        yield from _iter_elements(child)


def _build_table(tbl_el: Any) -> TableReadResult | None:
    """표 요소에서 행/열 격자와 병합/셀 좌표를 구성한다.

    행은 tr, 셀은 tc로 본다.
    이번 번호는 셀 좌표와 병합 범위를 구성하고, 셀 텍스트를 중복 집계하지 않는다.
    """
    rows_el = [c for c in tbl_el.children if _is_named(c, TABLE_NS, ROW_LOCALS)]
    if not rows_el:
        return None

    tables_rows: list[list[CellCoord]] = []
    merge_groups: list[MergeGroup] = []

    # 행/셀 순회하면서 열 인덱스를 추적한다.
    # 실제 HWpx는 병합으로 인해 한 행에서 셀 수가 달라질 수 있으므로,
    # 이번 번호는 각 행의 셀을 순서대로 열에 배치하고, gridSpan을 열 점유로 본다.
    # 세로 병합(vMerge)은 아래 행에서 같은 열을 계속 점유하는 것으로 처리한다.

    col_cursor_by_row: dict[int, int] = {}
    v_merge_occupancy: dict[int, Any] = {}  # 열 인덱스 -> (행인덱스, 셀)

    for row_index, row_el in enumerate(rows_el):
        cells_in_row: list[CellCoord] = []
        col = col_cursor_by_row.get(row_index, 0)

        for cell_el in [c for c in row_el.children if _is_named(c, TABLE_NS, CELL_LOCALS)]:
            grid_span = _int_attr(cell_el, GRID_SPAN_ATTRS)
            if grid_span < 1:
                grid_span = 1
            vmerge = _vmerge_value(cell_el)

            # 세로 병합 계속 셀인지 확인
            if vmerge == "continue":
                # 이전 행에서 이 열을 점유한 병합이 있으면 이어받는다.
                if col in v_merge_occupancy:
                    prev = v_merge_occupancy[col]
                    # 가로 병합 시작 셀 정보를 그대로 재사용할 수 있도록
                    # 여기서는 병합 그룹에 계속 셀을 추가한다.
                    merge_groups.append(MergeGroup(
                        type="vmerge",
                        start_row=prev.start_row,
                        start_col=prev.start_col,
                        cells=[(row_index, col)],
                        spans=[(grid_span, 1)],
                    ))
                    cells_in_row.append(CellCoord(
                        row_index=row_index,
                        column_index=col,
                        grid_span=grid_span,
                        vmerge="continue",
                        text=_cell_text(cell_el),
                        has_inner_table=_has_inner_table(cell_el),
                    ))
                    col += grid_span
                    continue

            # 새 셀 시작
            cell = CellCoord(
                row_index=row_index,
                column_index=col,
                grid_span=grid_span,
                vmerge=vmerge,
                text=_cell_text(cell_el),
                has_inner_table=_has_inner_table(cell_el),
            )
            cells_in_row.append(cell)

            if vmerge == "start":
                merge_groups.append(MergeGroup(
                    type="vmerge",
                    start_row=row_index,
                    start_col=col,
                    cells=[(row_index, col)],
                    spans=[(grid_span, 1)],
                ))
                v_merge_occupancy[col] = MergeSpanRef(
                    start_row=row_index,
                    start_col=col,
                    grid_span=grid_span,
                )

            col += grid_span

        tables_rows.append(cells_in_row)
        col_cursor_by_row[row_index] = col

    if not tables_rows:
        return None

    row_count = len(tables_rows)
    column_count = max((r[-1].column_index + r[-1].grid_span for r in tables_rows if r), default=0)

    # 가로 병합 그룹 구하기
    hmerge_groups = _build_hmerge_groups(tables_rows)

    # 중첩 표 찾기: 셀 내부에 tbl이 있으면 중첩 표로 별도 처리
    inner_tables = _find_inner_tables(tbl_el)

    return TableReadResult(
        element_tag=tbl_el.tag,
        row_count=row_count,
        column_count=column_count,
        rows=tables_rows,
        merges=hmerge_groups + merge_groups,
        inner_tables=inner_tables,
    )


def _int_attr(el: Any, candidates: tuple[str, ...]) -> int:
    for name in candidates:
        val = el.attributes.get(name)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                return 1
    return 1


def _vmerge_value(el: Any) -> str:
    for name in VMERGE_ATTRS:
        val = el.attributes.get(name)
        if val is not None:
            v = str(val).strip().lower()
            if v in ("continue", "restart", "start", "1", "true"):
                return "continue" if v in ("continue",) else "start"
            if v == "restart":
                return "start"
    return ""


def _cell_text(cell_el: Any) -> str:
    """셀의 직접 텍스트를 수집하되, 중첩 표 내부 텍스트는 포함하지 않는다.

    셀 텍스트를 중복 집계하지 않기 위해, 중첩 표 자식은 순회하지 않는다.
    셀 자신의 텍스트(직접 텍스트 노드)도 포함한다.
    """
    parts: list[str] = []
    if cell_el.text:
        parts.append(cell_el.text)
    for child in cell_el.children:
        if _is_named(child, TABLE_NS, TABLE_LOCALS):
            continue
        parts.append(_iter_text(child))
    return "\n".join(p for p in parts if p).strip()


def _iter_text(el: Any) -> str:
    if el.text:
        return el.text
    parts: list[str] = []
    for child in el.children:
        parts.append(_iter_text(child))
    return "".join(parts)


def _has_inner_table(cell_el: Any) -> bool:
    for child in cell_el.children:
        if _is_named(child, TABLE_NS, TABLE_LOCALS):
            return True
    return False


def _find_inner_tables(tbl_el: Any) -> list[InnerTableRef]:
    """셀 내부에 있는 중첩 표를 찾는다.

    중첩 표는 부모 셀 본문과 분리하고, 별도 표처럼 다룬다.
    """
    out: list[InnerTableRef] = []
    for row_el in [c for c in tbl_el.children if _is_named(c, TABLE_NS, ROW_LOCALS)]:
        for cell_el in [c for c in row_el.children if _is_named(c, TABLE_NS, CELL_LOCALS)]:
            for child in cell_el.children:
                if _is_named(child, TABLE_NS, TABLE_LOCALS):
                    inner = _build_table(child)
                    if inner is not None:
                        out.append(InnerTableRef(
                            parent_cell=(cell_el is not None, row_el, cell_el),
                            inner_table=inner,
                        ))
    return out


def _build_hmerge_groups(rows: list[list[CellCoord]]) -> list[MergeGroup]:
    """가로 병합 그룹을 구성한다.

    같은 행에서 gridSpan > 1인 셀이 있으면 그 범위만큼 병합으로 본다.
    """
    groups: list[MergeGroup] = []
    for row_index, row in enumerate(rows):
        col = 0
        for cell in row:
            if cell.grid_span > 1:
                groups.append(MergeGroup(
                    type="hmerge",
                    start_row=row_index,
                    start_col=cell.column_index,
                    cells=[(row_index, cell.column_index)],
                    spans=[(cell.grid_span, 1)],
                ))
            col += cell.grid_span
    return groups


class CellCoord:
    """표의 한 셀 좌표와 내용.

    셀 텍스트를 중복 집계하지 않기 위해, 셀의 직접 텍스트만 담는다.
    """

    __slots__ = (
        "row_index",
        "column_index",
        "grid_span",
        "vmerge",
        "text",
        "has_inner_table",
    )

    def __init__(
        self,
        *,
        row_index: int,
        column_index: int,
        grid_span: int,
        vmerge: str,
        text: str,
        has_inner_table: bool,
    ) -> None:
        self.row_index = row_index
        self.column_index = column_index
        self.grid_span = grid_span
        self.vmerge = vmerge
        self.text = text
        self.has_inner_table = has_inner_table


class MergeGroup:
    """병합 범위 하나.

    type: hmerge / vmerge
    """

    __slots__ = ("type", "start_row", "start_col", "cells", "spans")

    def __init__(
        self,
        *,
        type: str,
        start_row: int,
        start_col: int,
        cells: list[tuple[int, int]],
        spans: list[tuple[int, int]],
    ) -> None:
        self.type = type
        self.start_row = start_row
        self.start_col = start_col
        self.cells = cells
        self.spans = spans


class MergeSpanRef:
    """세로 병합 점유 참조."""

    __slots__ = ("start_row", "start_col", "grid_span")

    def __init__(self, *, start_row: int, start_col: int, grid_span: int) -> None:
        self.start_row = start_row
        self.start_col = start_col
        self.grid_span = grid_span


class InnerTableRef:
    """부모 셀 안에 중첩된 표 참조."""

    __slots__ = ("parent_cell", "inner_table", "parent_row_index", "parent_column_index")

    def __init__(
        self,
        *,
        parent_cell: tuple[bool, Any, Any],
        inner_table: TableReadResult,
        parent_row_index: int | None = None,
        parent_column_index: int | None = None,
    ) -> None:
        self.parent_cell = parent_cell
        self.inner_table = inner_table
        self.parent_row_index = parent_row_index
        self.parent_column_index = parent_column_index


class TableReadResult:
    """표 하나 읽기 결과."""

    __slots__ = (
        "element_tag",
        "row_count",
        "column_count",
        "rows",
        "merges",
        "inner_tables",
    )

    def __init__(
        self,
        *,
        element_tag: str,
        row_count: int,
        column_count: int,
        rows: list[list[CellCoord]],
        merges: list[MergeGroup],
        inner_tables: list[InnerTableRef],
    ) -> None:
        self.element_tag = element_tag
        self.row_count = row_count
        self.column_count = column_count
        self.rows = rows
        self.merges = merges
        self.inner_tables = inner_tables


class TablesReadResult:
    """read_tables 결과."""

    __slots__ = ("original_bytes", "original_sha256", "tables")

    def __init__(self, *, original_bytes: bytes, original_sha256: str, tables: list[TableReadResult]) -> None:
        self.original_bytes = original_bytes
        self.original_sha256 = original_sha256
        self.tables = tables
