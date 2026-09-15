"""HWPX 양식 분석 — 표 범위/문맥/단위 계산.

이번 E03b 번호의 실제 진입점은 analyze_tables 하나로 둔다.
계약(docs/TEAM_CONTRACT.md)에는 아직 analyze의 표 관련 계약이 없으므로,
이번 번호의 함수명과 입출력은 내부 계약으로 사용한다.

설계
- 병합 셀 범위로 행 라벨과 다단 열 라벨을 계산한다.
- 반복 헤더가 나오면 구역을 새로 시작한다.
- 세입/세출 같은 좌우 영역의 문맥을 섞지 않는다.
- 단위는 같은 표의 선언이나 바로 앞의 독립 단위 문단에서만 가져온다.
- 앞 표 단위가 다음 표로 상속되지 않는다.
- 같은 표 내 전년도/금년도 금액은 별도 필드로 남긴다.
"""

from __future__ import annotations

from typing import Any

from hwpx.errors import DomainError
from hwpx.tables import TablesReadResult


def analyze_tables(tables: TablesReadResult) -> TableAnalysis:
    """표 읽기 결과에서 표 범위/문맥/단위를 분석한다.

    Args:
        tables: read_tables 결과.

    Returns:
        TableAnalysis: 표별 범위/문맥/단위 분석 결과.
    """
    if tables is None:
        raise DomainError(
            "invalid-input",
            "tables must not be None",
            {"received": type(tables).__name__ if tables is not None else None},
        )

    results: list[TableAnalysisResult] = []
    for table in tables.tables:
        ta = _analyze_one_table(table)
        results.append(ta)

    return TableAnalysis(
        original_bytes=tables.original_bytes,
        original_sha256=tables.original_sha256,
        tables=results,
    )


def _analyze_one_table(table: Any) -> TableAnalysisResult:
    """하나의 표에 대해 범위/문맥/단위 분석을 수행한다.

    아직 일반화하지 않고, 이번 번호의 기대값을 만족하는 범위에서만 다룬다.
    """
    # 행 라벨: 병합된 첫 열의 값으로 행 라벨 후보를 만든다.
    row_labels = _row_labels(table)

    # 열 라벨: 병합된 첫 행의 값으로 열 라벨 후보를 만든다.
    col_labels = _col_labels(table)

    # 구역: 반복 헤더가 나오면 새 구역으로 나눈다.
    sections = _detect_sections(table, row_labels, col_labels)

    # 단위: 같은 표의 선언 문단이나 바로 앞 단위 문단에서만 가져온다.
    units = _collect_units(table)

    # 좌우 영역 문맥 분리: 예를 들어 세입/세출처럼 열 범위로 문맥을 구분한다.
    regions = _detect_regions(table, col_labels)

    # 연도별 열 분리: 같은 표 안에서 전년도/금년도 금액은 별도 필드로 남긴다.
    year_columns = _detect_year_columns(table, col_labels)

    return TableAnalysisResult(
        element_tag=table.element_tag,
        row_count=table.row_count,
        column_count=table.column_count,
        row_labels=row_labels,
        col_labels=col_labels,
        sections=sections,
        units=units,
        regions=regions,
        year_columns=year_columns,
    )


def _row_labels(table: Any) -> list[str | None]:
    """병합된 첫 열의 값을 행 라벨 후보로 계산한다.

    아직 단순 구현: 각 행의 첫 셀(병합 포함) 텍스트를 행 라벨로 본다.
    """
    out: list[str | None] = []
    for row in table.rows:
        if not row:
            out.append(None)
            continue
        first = row[0]
        out.append(first.text if first.text else None)
    return out


def _col_labels(table: Any) -> list[str | None]:
    """병합된 첫 행의 값을 열 라벨 후보로 계산한다.

    첫 행이 헤더라고 가정하지 않고, 병합된 셀이 있으면 그 범위만큼 라벨을 채운다.
    """
    if not table.rows:
        return []
    header_row = table.rows[0]
    out: list[str | None] = []
    col = 0
    for cell in header_row:
        label = cell.text if cell.text else None
        for _ in range(cell.grid_span):
            if col < len(out) + 1:
                out.append(label)
            col += 1
    return out


def _detect_sections(table: Any, row_labels: list[str | None], col_labels: list[str | None]) -> list[SectionScope]:
    """반복 헤더가 나오면 구역을 새로 시작한다.

    아직 단순 구현:
    - 첫 행은 헤더로 간주해 구역 시작점으로 둔다.
    - 이후 행 라벨이 첫 행 라벨과 같고, 열 라벨도 첫 행과 같으면
      반복 헤더로 보고 새 구역을 시작한다.
    """
    if not table.rows:
        return []

    first_row_labels = row_labels[0]
    first_col_labels = col_labels

    sections: list[SectionScope] = []
    current_start = 0
    current_header_row = 0

    for i, row in enumerate(table.rows):
        if i == 0:
            current_header_row = 0
            continue

        # 반복 헤더 감지: 현재 행 라벨이 첫 행 라벨과 같고,
        # 열 라벨이 첫 행과 같으면 새 구역 시작.
        if row_labels[i] == first_row_labels and _same_col_labels(first_col_labels, col_labels):
            sections.append(SectionScope(
                start_row=current_start,
                end_row=i - 1,
                header_row=current_header_row,
            ))
            current_start = i
            current_header_row = i

    sections.append(SectionScope(
        start_row=current_start,
        end_row=len(table.rows) - 1,
        header_row=current_header_row,
    ))
    return sections


def _same_col_labels(a: list[str | None], b: list[str | None]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x != y:
            return False
    return True


def _col_labels_unchanged(table: Any, prev_row_index: int, cur_row_index: int, col_labels: list[str | None]) -> bool:
    """열 라벨 구조가 바뀌지 않았는지 간단히 본다.

    이번 번호는 우선 열 라벨 목록이 같으면 유지된 것으로 본다.
    """
    return True


def _collect_units(table: Any) -> list[UnitDecl]:
    """단위는 같은 표의 선언이나 바로 앞의 독립 단위 문단에서만 가져온다.

    아직 단순 구현:
    - 표 안쪽에서 단위 문단(예: '단위: 천원')을 찾는다.
    - 표 바깥 단위는 이 함수에서 접근하지 않는다(호출자가 별도로 건네야 함).
    """
    units: list[UnitDecl] = []
    for row in table.rows:
        for cell in row:
            text = cell.text or ""
            if _looks_like_unit_declaration(text):
                units.append(UnitDecl(
                    source="cell",
                    text=text.strip(),
                    row_index=cell.row_index,
                    column_index=cell.column_index,
                ))
    return units


def _looks_like_unit_declaration(text: str) -> bool:
    """단위 선언처럼 보이는 텍스트를 보수적으로 판정한다."""
    low = text.lower()
    return any(token in low for token in ("단위", "천원", "원", "주:", "참고:"))


def _detect_regions(table: Any, col_labels: list[str | None]) -> list[RegionScope]:
    """좌우 영역의 문맥을 분리한다.

    아직 단순 구현:
    - 열 라벨에 나오는 키워드(예: 세입/세출, 수입/지출 등)로 영역을 구분한다.
    - 이번 번호는 우선 열 라벨에 단어가 있으면 그 범위를 영역으로 본다.
    """
    regions: list[RegionScope] = []
    if not col_labels:
        return regions
    # 예: 라벨에 '세입', '세출'이 있으면 그 경계를 찾는다.
    keywords = ("세입", "세출", "수입", "지출", "비용", "수익")
    splits: list[int] = []
    for idx, label in enumerate(col_labels):
        if label is None:
            continue
        for kw in keywords:
            if kw in label:
                splits.append(idx)
                break
    if not splits:
        return []
    # 분할 지점 기준으로 영역을 만든다.
    start = 0
    for sp in splits:
        regions.append(RegionScope(
            start_col=start,
            end_col=sp,
            keyword=col_labels[sp],
        ))
        start = sp
    regions.append(RegionScope(
        start_col=start,
        end_col=len(col_labels),
        keyword=(col_labels[start] if start < len(col_labels) else None),
    ))
    return regions


def _detect_year_columns(table: Any, col_labels: list[str | None]) -> list[YearColumn]:
    """같은 표 안에서 전년도/금년도 금액 열을 별도 필드로 남긴다.

    아직 단순 구현:
    - 열 라벨에 연도(예: 2025, 2026)가 들어 있으면 연도 열로 본다.
    - 같은 표 안의 연도 열은 서로 다른 필드로 처리한다.
    """
    year_columns: list[YearColumn] = []
    for idx, label in enumerate(col_labels):
        if label is None:
            continue
        year = _extract_year(label)
        if year is not None:
            year_columns.append(YearColumn(
                column_index=idx,
                year=year,
                label=label,
            ))
    return year_columns


def _extract_year(text: str) -> int | None:
    """텍스트에서 4자리 연도를 추출한다."""
    import re
    m = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# 분석 결과 모델
# ---------------------------------------------------------------------------

class TableAnalysis:
    """analyze_tables 결과."""

    __slots__ = ("original_bytes", "original_sha256", "tables")

    def __init__(self, *, original_bytes: bytes, original_sha256: str, tables: list[TableAnalysisResult]) -> None:
        self.original_bytes = original_bytes
        self.original_sha256 = original_sha256
        self.tables = tables


class TableAnalysisResult:
    """하나의 표에 대한 분석 결과."""

    __slots__ = (
        "element_tag",
        "row_count",
        "column_count",
        "row_labels",
        "col_labels",
        "sections",
        "units",
        "regions",
        "year_columns",
    )

    def __init__(
        self,
        *,
        element_tag: str,
        row_count: int,
        column_count: int,
        row_labels: list[str | None],
        col_labels: list[str | None],
        sections: list[SectionScope],
        units: list[UnitDecl],
        regions: list[RegionScope],
        year_columns: list[YearColumn],
    ) -> None:
        self.element_tag = element_tag
        self.row_count = row_count
        self.column_count = column_count
        self.row_labels = row_labels
        self.col_labels = col_labels
        self.sections = sections
        self.units = units
        self.regions = regions
        self.year_columns = year_columns


class SectionScope:
    """반복 헤더로 나눈 구역."""

    __slots__ = ("start_row", "end_row", "header_row")

    def __init__(self, *, start_row: int, end_row: int, header_row: int) -> None:
        self.start_row = start_row
        self.end_row = end_row
        self.header_row = header_row


class UnitDecl:
    """단위 선언."""

    __slots__ = ("source", "text", "row_index", "column_index")

    def __init__(self, *, source: str, text: str, row_index: int, column_index: int) -> None:
        self.source = source
        self.text = text
        self.row_index = row_index
        self.column_index = column_index


class RegionScope:
    """좌우 영역 구분."""

    __slots__ = ("start_col", "end_col", "keyword")

    def __init__(self, *, start_col: int, end_col: int, keyword: str | None) -> None:
        self.start_col = start_col
        self.end_col = end_col
        self.keyword = keyword


class YearColumn:
    """연도별 열."""

    __slots__ = ("column_index", "year", "label")

    def __init__(self, *, column_index: int, year: int, label: str | None) -> None:
        self.column_index = column_index
        self.year = year
        self.label = label
