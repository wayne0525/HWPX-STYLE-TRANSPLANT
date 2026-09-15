"""HWPX 양식 분석 — 표 범위/문맥/단위 계산.

이번 E03b 번호의 실제 진입점은 analyze_tables 하나로 둔다.
계약(docs/TEAM_CONTRACT.md)에는 아직 analyze의 표 관련 계약이 없으므로,
이번 번호의 함수명과 입출력은 내부 계약으로 사용한다.

설계
- 병합 셀 범위로 행 라벨과 다단 열 라벨을 계산한다.
- 반복 헤더가 나오면 구역을 새로 시작한다.
- 세입/세출 같은 좌우 영역의 문맥을 섞지 않는다.
- 단위는 같은 표의 선언이나 바로 앞 독립 단위 문단에서만 가져온다.
- 앞 표 단위가 다음 표로 상속되지 않는다.
- 같은 표 내 전년도/금년도 금액은 별도 필드로 남긴다.
"""

from __future__ import annotations

from typing import Any

from hwpx.errors import DomainError
from hwpx.tables import TablesReadResult

CONTENT_NS = "http://www.hwpzone.org/hwpx"


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


# ---------------------------------------------------------------------------
# A 양식 분석: analyze_a + candidates
# ---------------------------------------------------------------------------

def analyze_a(xml_result, *, a_bytes: bytes, a_sha256: str) -> AAnalysis:
    """A 양식 원본의 입력란 후보와 구조 정보를 분석한다.

    이번 E04 번호의 실제 진입점은 analyze_a 하나로 둔다.
    계약(docs/TEAM_CONTRACT.md)에는 아직 analyze_a의 후보/ID 계약이
    충분히 없으므로, 이번 번호의 입출력은 내부 계약으로 사용한다.

    설계
    - candidates와 안정적인 ID를 구현한다.
    - 공백 hp:t, 자체 닫힘 hp:t, 텍스트 없는 run을 구별한다.
    - 고정 문구와 제어 개체 영역은 편집 후보로 열지 않는다(editable=False).
    - 같은 A의 ID는 재분석 때 같다.
    """
    if xml_result is None:
        raise DomainError(
            "invalid-input",
            "xml_result must not be None",
            {},
        )
    if not isinstance(a_bytes, (bytes, bytearray)):
        raise DomainError(
            "invalid-input",
            "a_bytes must be bytes-like",
            {"received_type": type(a_bytes).__name__},
        )

    candidates = _build_candidates(xml_result, a_bytes, a_sha256)
    return AAnalysis(
        analysis_id=_analysis_id(a_sha256),
        a_hash=a_sha256,
        file_kind="hwpx",
        analysis_status="partial",
        warnings=_analysis_warnings(xml_result, candidates),
        fields=_to_fields(candidates),
        normalizedIndex=None,
    )


def _analysis_id(a_sha256: str) -> str:
    return f"a-{a_sha256[:16]}"


def _analysis_warnings(xml_result, candidates: list[Candidate]) -> list[str]:
    warns: list[str] = []
    protected = [c for c in candidates if not c.editable]
    if protected:
        warns.append(f"{len(protected)} protected candidates excluded from editing")
    return warns


def _to_fields(candidates: list[Candidate]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for c in candidates:
        fields.append({
            "fieldId": c.field_id,
            "candidateId": c.candidate_id,
            "label": c.label,
            "originalText": c.original_text,
            "context": c.context,
            "unit": c.unit,
            "editable": c.editable,
            "required": c.required,
            "status": c.status,
            "location": c.location,
        })
    return fields


def _build_candidates(xml_result, a_bytes: bytes, a_sha256: str) -> list[Candidate]:
    """현재 범위: 문단/표 요소에서 편집 후보를 만든다.

    이번 번호는 우선 문단(p) 수준에서 후보를 수집하고,
    고정 문구/제어 개체/빈 요소는 editable=False로 표시한다.
    """
    candidates: list[Candidate] = []
    counter = 0

    for section in xml_result.sections:
        section_candidates = _section_candidates(section, a_sha256, counter)
        candidates.extend(section_candidates)
        counter = _max_id(counter, section_candidates)

    # 안정적 ID를 부여하기 위해 최종 정렬/할당을 한 번 더 한다.
    # 이번 단순 구현에서는 이미 부여된 candidate_id를 유지한다.
    return candidates


def _section_candidates(section, a_sha256: str, base_id: int) -> list[Candidate]:
    """한 section에서 문단/표 후보를 만든다.

    이번 번호는 우선 문단(p) 수준에서 후보를 수집한다.
    빈 문단/고정 문구/제어 개체는 editable=False로 둔다.
    """
    out: list[Candidate] = []
    for el in _iter_named_elements(section.tree.root, CONTENT_NS, ("p",)):
        cid = _candidate_id(a_sha256, base_id + len(out), el)
        (cand, new_base) = _paragraph_candidate(el, cid, a_sha256, len(out))
        if cand is not None:
            out.append(cand)
    return out


def _max_id(base: int, candidates: list[Candidate]) -> int:
    if not candidates:
        return base
    last = candidates[-1].field_id.split("-")[-1]
    try:
        return int(last) + 1
    except (TypeError, ValueError):
        return base + len(candidates)


def _iter_named_elements(root, ns_uri: str, locals_: tuple[str, ...]) -> list:
    found: list = []
    for el in _iter_elements(root):
        if el.ns_uri == ns_uri and el.local in locals_:
            found.append(el)
    return found


def _iter_elements(el) -> list:
    out: list = [el]
    for child in el.children:
        out.extend(_iter_elements(child))
    return out


def _paragraph_candidate(el, candidate_id: str, a_sha256: str, index: int) -> tuple[Candidate | None, int]:
    """문단 요소에서 편집 후보를 만든다.

    공백 hp:t만 있거나 자체 닫힘 hp:t만 있거나 텍스트 없는 run만 있는 문단은
    고정 문구/보호 구간으로 본다.
    """
    text = _paragraph_text(el)
    control = _looks_like_control(el)
    fixed = _looks_like_fixed_text(text)

    if control or fixed or not text.strip():
        editable = False
        status = "protected" if control else ("fixed" if fixed else "empty")
    else:
        editable = True
        status = "normal"

    label = _make_label(el, text)
    original_text = text if text else ""
    context = _context(el, text)

    field_id = f"f-{candidate_id}"
    candidate_id_full = f"{candidate_id}-p{index:04d}"

    location = {
        "section": section_id(el),
        "paragraph": paragraph_id(el),
        "table": None,
        "row": None,
        "column": None,
    }

    return (
        Candidate(
            field_id=field_id,
            candidate_id=candidate_id_full,
            label=label,
            original_text=original_text,
            context=context,
            unit=None,
            editable=editable,
            required=False,
            status=status,
            location=location,
        ),
        index + 1,
    )


def _paragraph_text(el) -> str:
    """문단 요소의 텍스트를 수집한다.

    중첩 표 내부 텍스트는 수집하지 않는다(이번 번호는 문단 수준에서 다룬다).
    """
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el.children:
        if child.local == "tbl":
            continue
        parts.append(_node_text(child))
    return "\n".join(p for p in parts if p)


def _node_text(el) -> str:
    if el.text:
        return el.text
    parts: list[str] = []
    for child in el.children:
        parts.append(_node_text(child))
    return "\n".join(parts)


def _looks_like_control(el) -> bool:
    """제어 개체/편집 불가능 영역으로 보이는지 보수적으로 판정한다.

    이번 번호는 우선 namespace/요소 이름으로 판단한다.
    """
    # 예: 페이지 나누기, 머리글/바닥글 관련 요소 등은 편집 후보에서 제외할 수 있다.
    # 이번 범위는 우선 내용 없는 빈 문단/고정 문구 판정에 집중한다.
    return False


def _looks_like_fixed_text(text: str) -> bool:
    """고정 문구처럼 보이는 텍스트인지 판정한다.

    이번 번호는 비어 있지 않은 문장 중, 라벨/안내 형태로 보이는 것을
    고정 문구 후보로 본다. 실제 값 입력란과 구분한다.
    """
    t = text.strip()
    if not t:
        return False
    # 라벨 형태: 짧은 텍스트 + 끝 콜론
    if len(t) <= 12 and t.endswith(":"):
        return True
    # 매우 짧은 문구이면서, 라벨처럼 보이면 고정 문구 후보
    if len(t) <= 4 and t.isupper():
        return True
    return False


def _make_label(el, text: str) -> str:
    t = text.strip()
    if t:
        return t[:40]
    return f"paragraph-{el.local}"


def _context(el, text: str) -> list[str]:
    ctx: list[str] = []
    if text:
        ctx.append(text[:40])
    ctx.append(f"section-root")
    return ctx


def section_id(el) -> str:
    return "section-unknown"


def paragraph_id(el) -> str:
    return f"p-{el.tag}"


def _candidate_id(a_sha256: str, offset: int, el) -> str:
    return f"{a_sha256[:12]}-{offset:04d}"


class Candidate:
    """편집 후보 하나.

    안정적 ID와 편집 가능 여부를 가진다.
    """

    __slots__ = (
        "field_id",
        "candidate_id",
        "label",
        "original_text",
        "context",
        "unit",
        "editable",
        "required",
        "status",
        "location",
    )

    def __init__(
        self,
        *,
        field_id: str,
        candidate_id: str,
        label: str,
        original_text: str,
        context: list[str],
        unit: str | None,
        editable: bool,
        required: bool,
        status: str,
        location: dict[str, Any],
    ) -> None:
        self.field_id = field_id
        self.candidate_id = candidate_id
        self.label = label
        self.original_text = original_text
        self.context = context
        self.unit = unit
        self.editable = editable
        self.required = required
        self.status = status
        self.location = location


class AAnalysis:
    """analyze_a 결과."""

    __slots__ = (
        "analysis_id",
        "a_hash",
        "file_kind",
        "analysis_status",
        "warnings",
        "fields",
        "normalizedIndex",
    )

    def __init__(
        self,
        *,
        analysis_id: str,
        a_hash: str,
        file_kind: str,
        analysis_status: str,
        warnings: list[str],
        fields: list[dict[str, Any]],
        normalizedIndex: dict[str, str] | None,
    ) -> None:
        self.analysis_id = analysis_id
        self.a_hash = a_hash
        self.file_kind = file_kind
        self.analysis_status = analysis_status
        self.warnings = warnings
        self.fields = fields
        self.normalizedIndex = normalizedIndex


# ---------------------------------------------------------------------------
# 라벨과 복합 입력란: analyze_fields
# ---------------------------------------------------------------------------

def analyze_fields(
    xml_result,
    tables,
    candidates,
    *,
    a_bytes: bytes,
    a_sha256: str,
) -> FieldsAnalysis:
    """문단 라벨, 표 헤더, 구역, 단위를 이용해 입력란 목록을 만든다.

    이번 E05 번호의 실제 진입점은 analyze_fields 하나로 둔다.
    계약(docs/TEAM_CONTRACT.md)에는 아직 필드 분석 계약이 충분히 없으므로,
    이번 번호의 입출력은 내부 계약으로 사용한다.

    설계
    - 문단 라벨과 표의 상위/좌측 헤더, 구역, 단위를 이용한다.
    - 직명/성명과 주소/우편번호처럼 같은 셀이라도 별도 입력 구간으로 연결한다.
    - 빈 장식 셀은 입력란으로 오탐하지 않는다.
    """
    if xml_result is None:
        raise DomainError("invalid-input", "xml_result must not be None", {})
    if tables is None:
        raise DomainError("invalid-input", "tables must not be None", {})
    if candidates is None:
        raise DomainError("invalid-input", "candidates must not be None", {})

    fields = _build_fields(xml_result, tables, candidates)
    return FieldsAnalysis(
        analysis_id=_analysis_id(a_sha256),
        a_hash=a_sha256,
        file_kind="hwpx",
        analysis_status="partial",
        warnings=_field_warnings(fields),
        fields=fields,
        normalizedIndex=None,
    )


def _field_warnings(fields: list[dict[str, Any]]) -> list[str]:
    warns: list[str] = []
    if not fields:
        warns.append("no fields produced")
    return warns


def _build_fields(xml_result, tables, candidates) -> list[dict[str, Any]]:
    """현재 범위: 문단 라벨과 표 값을 묶어 fields를 만든다.

    이번 번호는 우선 간단한 결합 규칙만 구현한다.
    candidates는 Candidate 객체 또는 analyze_a의 fields(dict) 리스트일 수 있다.
    """
    fields: list[dict[str, Any]] = []
    counter = 0

    # 문단 라벨/입력 후보를 먼저 배치
    for c in candidates:
        if isinstance(c, Candidate):
            if c.editable and c.original_text.strip():
                fields.append(_field_from_candidate(c, counter))
                counter += 1
        elif isinstance(c, dict):
            if _dict_editable(c) and (c.get("originalText") or "").strip():
                fields.append(_field_from_dict(c, counter))
                counter += 1

    # 표는 표 헤더+값을 묶어 fields를 만든다
    for table in tables.tables:
        table_fields = _table_fields(table, candidates, counter)
        fields.extend(table_fields)
        counter += len(table_fields)

    return fields


def _dict_editable(c: dict[str, Any]) -> bool:
    return bool(c.get("editable"))


def _field_from_dict(c: dict[str, Any], index: int) -> dict[str, Any]:
    field_id = f"f-{index:04d}"
    return {
        "fieldId": field_id,
        "candidateId": c.get("candidateId"),
        "label": c.get("label"),
        "originalText": c.get("originalText", ""),
        "context": c.get("context", []),
        "unit": c.get("unit"),
        "editable": True,
        "required": c.get("required", False),
        "status": "input",
        "location": c.get("location", {}),
    }


def _field_from_candidate(c: Candidate, index: int) -> dict[str, Any]:
    field_id = f"f-{index:04d}"
    return {
        "fieldId": field_id,
        "candidateId": c.candidate_id,
        "label": c.label if c.label else None,
        "originalText": c.original_text,
        "context": c.context,
        "unit": c.unit,
        "editable": True,
        "required": c.required,
        "status": "input",
        "location": c.location,
    }


def _table_fields(table, candidates, base_index: int) -> list[dict[str, Any]]:
    """표의 헤더와 값을 묶어 fields를 만든다.

    이번 번호는 표의 헤더(첫 행/첫 열)와 값이 있는 셀을 엮어,
    같은 셀이라도 여러 입력 구간으로 나눌 수 있게 한다.
    """
    header = _header_labels(table)
    fields: list[dict[str, Any]] = []
    rows = table.rows

    for r_idx, row in enumerate(rows):
        cells = _row_cells(row)
        for c_idx, cell in enumerate(cells):
            # 헤더 행/열의 값은 필드로 만들지 않는다(이번 단순 구현).
            if r_idx == 0 or c_idx == 0:
                continue
            if not _cell_has_value(cell):
                continue
            label = _cell_label(table, header, cell)
            value = _cell_value(cell)
            if not value:
                continue
            field_index = base_index + len(fields)
            field_id = f"f-{field_index:04d}"
            fields.append({
                "fieldId": field_id,
                "candidateId": f"t-{field_index:04d}",
                "label": label,
                "originalText": value,
                "context": _cell_context(table, header, cell),
                "unit": None,
                "editable": True,
                "required": True,
                "status": "input",
                "location": _cell_location(cell),
            })

    return _split_composite_fields(fields, table)


def _row_cells(row) -> list:
    if isinstance(row, list):
        return row
    if hasattr(row, "cells"):
        return row.cells
    if hasattr(row, "cells_"):
        return row.cells_
    return []


def _header_labels(table) -> dict:
    """표의 상위/좌측 헤더 라벨을 수집한다.

    이번 번호는 우선 표의 첫 행과 첫 열 라벨을 헤더로 본다.
    첫 행 첫 열(왼쪽 위)은 헤더가 아니라 빈 칸/교차 셀로 보고 제외한다.
    """
    row_headers: list[str] = []
    col_headers: list[str] = []
    rows = table.rows if hasattr(table, "rows") else []
    if not rows:
        return {"row": row_headers, "col": col_headers}
    # 첫 행(첫 열 제외)
    first_row = rows[0]
    first_row_cells = _row_cells(first_row)
    for c_idx, cell in enumerate(first_row_cells):
        if c_idx == 0:
            continue
        txt = _cell_text(cell)
        if txt:
            col_headers.append(txt)
    # 첫 열(첫 행 제외)
    for row in rows[1:]:
        row_cells = _row_cells(row)
        if not row_cells:
            continue
        first_cell = row_cells[0]
        txt = _cell_text(first_cell)
        if txt:
            row_headers.append(txt)
    return {"row": row_headers, "col": col_headers}


def _cell_text(cell) -> str:
    if not cell:
        return ""
    if hasattr(cell, "text"):
        return cell.text or ""
    return ""


def _cell_has_value(cell) -> bool:
    return bool(_cell_text(cell).strip())


def _cell_value(cell) -> str:
    return _cell_text(cell)


def _cell_label(table, header, cell) -> str | None:
    """셀에 대응하는 라벨을 만든다.

    이번 번호는 셀의 행/열 위치로 행 헤더/열 헤더를 결합한다.
    """
    rows = table.rows if hasattr(table, "rows") else []
    if not rows:
        return None
    row_idx = _cell_row_index(cell, rows)
    col_idx = _cell_col_index(cell)

    label_parts: list[str] = []
    if 0 < row_idx < len(header["row"]) + 1:
        if row_idx - 1 < len(header["row"]):
            label_parts.append(header["row"][row_idx - 1])
    if col_idx < len(header["col"]):
        label_parts.append(header["col"][col_idx])
    if not label_parts:
        return None
    return " / ".join(label_parts)


def _cell_row_index(cell, rows) -> int:
    for i, row in enumerate(rows):
        if isinstance(row, list):
            if cell in row:
                return i
        elif hasattr(row, "cells") and cell in row.cells:
            return i
    return -1


def _cell_col_index(cell) -> int:
    if hasattr(cell, "column_index"):
        return cell.column_index
    if hasattr(cell, "start_col"):
        return cell.start_col
    return 0


def _cell_context(table, header, cell) -> list[str]:
    rows = table.rows if hasattr(table, "rows") else []
    ctx: list[str] = []
    ctx.append(f"row={_cell_row_index(cell, rows)}")
    ctx.append(f"col={_cell_col_index(cell)}")
    ctx.extend(header["row"])
    ctx.extend(header["col"])
    return ctx


def _cell_location(cell) -> dict[str, Any]:
    loc: dict[str, Any] = {
        "table": None,
        "row": _row_index(cell),
        "column": _cell_col_index(cell),
        "section": None,
    }
    return loc


def _row_index(cell) -> int | None:
    if hasattr(cell, "start_row"):
        return cell.start_row
    return None


def _split_composite_fields(fields: list[dict[str, Any]], table) -> list[dict[str, Any]]:
    """같은 셀에서 여러 입력 구간을 만들어야 할 때 필드를 나눈다.

    이번 번호는 우선 셀 값에 구분자 패턴이 있으면 나누는 규칙만 적용한다.
    예: "직명 / 성명", "주소 / 우편번호" 같은 패턴.
    """
    out: list[dict[str, Any]] = []
    for f in fields:
        text = f.get("originalText") or ""
        parts = _split_value(text)
        if len(parts) > 1 and f.get("label"):
            for i, part in enumerate(parts):
                if not part.strip():
                    continue
                field_index = int(f["fieldId"][2:]) + len(out)
                field_id = f"f-{field_index:04d}"
                out.append({
                    "fieldId": field_id,
                    "candidateId": f["candidateId"],
                    "label": f"{f['label']} #{i+1}",
                    "originalText": part,
                    "context": f["context"],
                    "unit": f.get("unit"),
                    "editable": True,
                    "required": True,
                    "status": "input",
                    "location": f["location"],
                })
        else:
            out.append(f)
    return out


def _split_value(text: str) -> list[str]:
    import re
    # "직명 / 성명"처럼 구분자로 이어진 복합 값만 나눈다.
    if re.search(r"\s*/\s*", text):
        return [p.strip() for p in text.split("/")]
    return [text]


class FieldsAnalysis:
    """analyze_fields 결과."""

    __slots__ = (
        "analysis_id",
        "a_hash",
        "file_kind",
        "analysis_status",
        "warnings",
        "fields",
        "normalizedIndex",
    )

    def __init__(
        self,
        *,
        analysis_id: str,
        a_hash: str,
        file_kind: str,
        analysis_status: str,
        warnings: list[str],
        fields: list[dict[str, Any]],
        normalizedIndex: dict[str, str] | None,
    ) -> None:
        self.analysis_id = analysis_id
        self.a_hash = a_hash
        self.file_kind = file_kind
        self.analysis_status = analysis_status
        self.warnings = warnings
        self.fields = fields
        self.normalizedIndex = normalizedIndex


# ---------------------------------------------------------------------------
# 복합 슬롯 분리: split_compound_slots
# ---------------------------------------------------------------------------

def split_compound_slots(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """라벨/값 패턴으로 복합 입력 구간을 독립 필드로 분리한다.

    이번 E05b 번호의 실제 진입점은 split_compound_slots 하나로 둔다.
    계약(docs/TEAM_CONTRACT.md)에는 아직 복합 슬롯 분리 계약이 충분히 없으므로,
    이번 번호의 입출력은 내부 계약으로 사용한다.

    구분
    - 콜론 뒤 공백, 중괄호 표시, 자리표시자임이 확인된 영으로 채운 금액,
      단위만 있는 칸, 글머리표 아래 빈 문단을 구분한다.
    - 주소/우편번호, 직명/성명, 시작 시각/종료 시각, 총사업비/보조금처럼
      한 표시 안에 여러 독립 구간이 있으면 별도 필드로 나눈다.
    - 글자 run이 나뉘어도 논리 문단으로 찾고, 원본 위치는 보존한다.
    - 실제 값 0을 자리표시자로 단정하지 않는다.
    - 라벨, 직인 문구, 실제로 기입된 날짜를 빈칸으로 지우지 않는다.
    """
    if not fields:
        return []

    out: list[dict[str, Any]] = []
    for f in fields:
        # 먼저 보호/고정/장식 후보를 그대로 보존한다.
        if not _slot_editable(f):
            out.append(f)
            continue

        text = f.get("originalText") or ""
        label = f.get("label") or ""

        # 단위만 있는 칸, 글머리표 아래 빈 문단, 중괄호 표시 등은
        # 입력 구간으로 열지 않거나 별도 처리 대상으로 남긴다.
        if _looks_like_unit_only(f) or _looks_like_bullet_blank(f):
            f = _mark_slot_status(f, "decoration")
            out.append(f)
            continue

        # 콜론으로 끝나는 라벨 뒤의 값 구간을 분리한다.
        if _looks_like_labeled_value(f):
            parts = _split_labeled_value(text, label)
            if len(parts) > 1:
                out.extend(_expand_slot(f, parts))
                continue

        # 복합 값 패턴(주소/우편번호, 직명/성명, 시작/종료 시각, 총사업비/보조금)을 분리한다.
        if _looks_like_compound_value(text):
            parts = _split_compound_value(text)
            if len(parts) > 1:
                out.extend(_expand_slot(f, parts))
                continue

        # 그 외 편집 가능 필드는 상태를 재계산해 추가한다.
        out.append(_mark_slot_status(f, _slot_status_for(text)))

    return out


def _slot_editable(f: dict[str, Any]) -> bool:
    return bool(f.get("editable"))


def _looks_like_unit_only(f: dict[str, Any]) -> bool:
    """단위만 있는 칸인지 판정한다.

    이번 번호는 텍스트가 단위 표현뿐이고, 라벨이 없거나 단위 라벨이면
    단위만 있는 칸으로 본다.
    """
    text = (f.get("originalText") or "").strip()
    if not text:
        return False
    unit = f.get("unit")
    label = (f.get("label") or "").strip()
    if unit and text.lower() == unit.lower():
        return True
    if label and label.lower() in ("단위", "단위:", "단위 :"):
        return True
    # 텍스트 자체가 단위처럼 보이기만 해도 단위만 있는 칸 후보
    if _is_unit_like(text):
        return True
    return False


def _is_unit_like(text: str) -> bool:
    import re
    t = text.strip().lower()
    if re.fullmatch(r"(원|천원|만원|달러|유로|명|개|건|회|부|각형)?$", t):
        return True
    if re.fullmatch(r"\d+\s*(원|천원|만원|달러|유로|명|개|건|회|부)$", t):
        return True
    return False


def _looks_like_bullet_blank(f: dict[str, Any]) -> bool:
    """글머리표 아래 빈 문단인지 판정한다.

    이번 번호는 context/라벨에 글머리표 표시가 있고 텍스트가 비어 있으면
    빈 문단으로 본다.
    """
    text = (f.get("originalText") or "").strip()
    if text:
        return False
    ctx = f.get("context") or []
    combined = " ".join(ctx).lower()
    if any(m in combined for m in ("bullet", "•", "-", "*", "글머리", "항목")):
        return True
    return False


def _looks_like_labeled_value(f: dict[str, Any]) -> bool:
    """콜론 뒤 공백 패턴으로 라벨+값 구조인지 판정한다.

    이번 번호는 원본 텍스트나 라벨이 콜론으로 끝나고, 값 부분이 있으면
    라벨/값 분리 대상으로 본다.
    """
    text = (f.get("originalText") or "").strip()
    if not text:
        return False
    # 라벨이 콜론 종료형이면 라벨+값 구조로 본다
    label = (f.get("label") or "").strip()
    if label and _ends_with_colon(label):
        return True
    # 원본 텍스트가 "라벨: 값" 형태이면 분리 대상으로 본다
    if _contains_colon_label(text):
        return True
    return False


def _ends_with_colon(s: str) -> bool:
    import re
    return bool(re.search(r":\s*$", s))


def _contains_colon_label(text: str) -> bool:
    import re
    # "라벨: 값" 패턴
    return bool(re.match(r"^[^:]+:\s*\S", text))


def _looks_like_compound_value(text: str) -> bool:
    """주소/우편번호, 직명/성명, 시작/종료 시각, 총사업비/보조금 패턴을 본다.

    이번 번호는 "/" 구분자가 있거나, 명시적 복합 패턴이 있으면 복합 값으로 본다.
    """
    if not text:
        return False
    # "/" 구분자 복합
    if "/" in text:
        return True
    # 시작/종료 시각 패턴
    if _looks_like_time_range(text):
        return True
    # 총사업비/보조금 형태
    if _looks_like_fund_split(text):
        return True
    return False


def _looks_like_time_range(text: str) -> bool:
    import re
    # "시작 시 분부터 종료 시 분까지" 형태나 "00:00~00:00" 형태
    if re.search(r"부터.*까지", text):
        return True
    if re.search(r"\d{1,2}:\d{2}\s*[-~]\s*\d{1,2}:\d{2}", text):
        return True
    return False


def _looks_like_fund_split(text: str) -> bool:
    import re
    # "총사업비 00원 / 보조금 00원" 형태
    if re.search(r"총사업비.*보조금|보조금.*총사업비", text):
        return True
    return False


def _split_labeled_value(text: str, label: str) -> list[str]:
    import re
    # 라벨이 이미 콜론 종료형이면, 원본 텍스트를 라벨과 값으로 분리
    if label and _ends_with_colon(label):
        # 원본 텍스트가 "라벨: 값"이면 값만 추출
        m = re.match(r"^[^:]+:\s*(.*)$", text)
        if m:
            return [label, m.group(1).strip()]
        # 원본 텍스트가 값만 있으면 라벨+값으로 간주
        if text:
            return [label, text]
        return [label]
    # 원본 텍스트가 "라벨: 값" 형태이면 라벨/값으로 분리
    if _contains_colon_label(text):
        m = re.match(r"^([^:]+):\s*(.*)$", text)
        if m:
            return [m.group(1).strip(), m.group(2).strip()]
    return [text]


def _split_compound_value(text: str) -> list[str]:
    import re
    # 주소/우편번호, 직명/성명 등 "/" 분리
    if "/" in text:
        return [p.strip() for p in text.split("/") if p.strip()]

    # 시작/종료 시각 범위 분리: "시작 시각 09시 00분 부터 종료 시각 18시 00분 까지" → 4구간
    m = re.search(r"(시작\s*시각)\s*(\d{1,2}시\s*\d{2}분)\s*부터\s*(종료\s*시각)\s*(\d{1,2}시\s*\d{2}분)\s*까지", text)
    if m:
        return [m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()]

    # 총사업비/보조금 분리
    # "총사업비 00원 / 보조금 00원" 또는 "총사업비 00원, 보조금 00원"
    parts = re.split(r"[/,]\s*", text)
    if len(parts) >= 2:
        return [p.strip() for p in parts if p.strip()]

    return [text]


def _expand_slot(f: dict[str, Any], parts: list[str]) -> list[dict[str, Any]]:
    """하나의 필드를 여러 슬롯으로 늘릴 때 라벨/값을 분할해 필드를 만든다."""
    out: list[dict[str, Any]] = []
    base_label = f.get("label")
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        # 복합 값이면 다시 분리한다.
        sub_parts = _split_compound_value(part)
        if len(sub_parts) > 1:
            for j, sub in enumerate(sub_parts):
                if not sub.strip():
                    continue
                field_index = _next_field_index(out)
                field_id = f"f-{field_index:04d}"
                slot_label = _slot_label(base_label, i + 1, sub)
                out.append({
                    "fieldId": field_id,
                    "candidateId": f.get("candidateId"),
                    "label": slot_label,
                    "originalText": sub,
                    "context": f.get("context", []),
                    "unit": f.get("unit"),
                    "editable": True,
                    "required": f.get("required", True),
                    "status": _slot_status_for(sub),
                    "location": f.get("location"),
                })
            continue
        field_index = _next_field_index(out)
        field_id = f"f-{field_index:04d}"
        slot_label = _slot_label(base_label, i + 1, part)
        out.append({
            "fieldId": field_id,
            "candidateId": f.get("candidateId"),
            "label": slot_label,
            "originalText": part,
            "context": f.get("context", []),
            "unit": f.get("unit"),
            "editable": True,
            "required": f.get("required", True),
            "status": _slot_status_for(part),
            "location": f.get("location"),
        })
    return out


def _next_field_index(out: list[dict[str, Any]]) -> int:
    if not out:
        return 0
    last = out[-1].get("fieldId", "")
    try:
        return int(last.split("-")[-1]) + 1
    except (TypeError, ValueError):
        return len(out)


def _slot_label(base_label: str | None, idx: int, part: str) -> str | None:
    if base_label:
        return f"{base_label} #{idx}"
    t = (part or "").strip()
    if t:
        return t[:40]
    return f"slot-{idx}"


def _slot_status_for(part: str) -> str:
    """자리표시자임이 확인된 영으로 채운 금액 등은 별도 상태로 표시한다.

    이번 번호는 실제 값 0을 자리표시자로 단정하지 않는다.
    라벨/중괄호/콜론 뒤 공백 자리표시자 패턴이 있을 때만 자리표시자 처리한다.
    """
    t = (part or "").strip()
    if _looks_like_placeholder(t):
        return "placeholder"
    if t == "0" and _looks_like_zero_placeholder_context(part):
        return "placeholder"
    return "input"


def _looks_like_placeholder(text: str) -> bool:
    import re
    t = text.strip()
    if not t:
        return False
    # 중괄호 표시
    if re.fullmatch(r"\{[^}]*\}", t):
        return True
    # 콜론 뒤 공백 자리표시자(예: "이름: "처럼 값 부분이 공백/빈 경우)는
    # 이 함수에서는 처리하지 않고, 라벨 분리 단계에서 값으로 남긴다.
    return False


def _looks_like_zero_placeholder_context(text: str) -> bool:
    """영으로 채운 금액이 자리표시자임이 확인된 경우만 처리한다.

    이번 번호는 실제 값 0을 자리표시자로 단정하지 않는다.
    문맥상 자리표시자임이 확인된 경우만 placeholder로 본다.
    """
    # 예: "{총사업비}"처럼 중괄호가 포함된 문단에서 나온 0은 자리표시자 후보
    # 이번 단순 구현에서는 원본 텍스트에 중괄호가 있으면 0을 자리표시자로 본다.
    if "{" in text or "}" in text:
        return True
    return False


def _mark_slot_status(f: dict[str, Any], status: str) -> dict[str, Any]:
    f = dict(f)
    f["status"] = status
    return f
