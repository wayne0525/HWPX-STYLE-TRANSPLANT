"""tests/engine/test_table_mapping.py -- 표 제목/구역/열 의미/고정 행 이름 기반 규칙 연결 검사.

실제 hwpx.rules.connect_rules를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import unittest

from hwpx.analyze import SectionScope, TableAnalysisResult
from hwpx.rules import connect_rules
from hwpx.source import SourceBlock


def _field(
    field_id: str,
    label: str,
    *,
    context: list[str] | None = None,
    unit: str | None = None,
    location: dict | None = None,
) -> dict:
    return {
        "fieldId": field_id,
        "label": label,
        "originalText": label,
        "context": context or [],
        "unit": unit,
        "editable": True,
        "required": False,
        "status": "input",
        "location": location or {},
    }


def _location(
    *,
    table: dict | None = None,
    row: dict | None = None,
    column: dict | None = None,
    section: dict | None = None,
    paragraph: dict | None = None,
) -> dict:
    return {
        "table": table,
        "row": row,
        "column": column,
        "section": section,
        "paragraph": paragraph,
    }


def _block(
    block_id: str,
    text: str,
    *,
    context: list[str] | None = None,
    table_position: dict | None = None,
    facts: list | None = None,
    kind: str = "table-cell",
) -> SourceBlock:
    return SourceBlock(
        blockId=block_id,
        level=0,
        text=text,
        kind=kind,
        start=0,
        end=len(text),
        children=[],
        table_context={},
        context=context or [],
        table_position=table_position or {},
        facts=facts or [],
    )


def _table_analysis(
    *,
    element_tag: str = "hp:tbl",
    row_labels: list | None = None,
    col_labels: list | None = None,
    sections: list[SectionScope] | None = None,
    row_count: int = 0,
    column_count: int = 0,
) -> TableAnalysisResult:
    return TableAnalysisResult(
        element_tag=element_tag,
        row_count=row_count,
        column_count=column_count,
        row_labels=row_labels or [],
        col_labels=col_labels or [],
        sections=sections or [],
        units=[],
        regions=[],
        year_columns=[],
    )


class TestTableMapping(unittest.TestCase):
    def connect(
        self,
        fields,
        blocks,
        table_analysis=None,
        a_hash="ahash",
    ):
        return connect_rules(
            fields,
            blocks,
            normalizedIndex=None,
            a_hash=a_hash,
            table_analysis=table_analysis,
        )

    # ------------------------------------------------------------------
    # 표 제목/구역 우선 연결
    # ------------------------------------------------------------------
    def test_table_title_and_section_first(self):
        title = "비용 표"
        section = "2026년 1분기"
        fields = [
            _field(
                "f-001",
                "품명",
                context=[f"표: {title}", f"구역: {section}"],
                location=_location(
                    table={"tableId": "t-001"},
                    column={"columnIndex": 0},
                ),
            ),
            _field(
                "f-002",
                "금액",
                context=[f"표: {title}", f"구역: {section}"],
                location=_location(
                    table={"tableId": "t-001"},
                    column={"columnIndex": 1},
                ),
            ),
        ]
        blocks = [
            _block(
                "b-001",
                "재료비",
                context=[f"표: {title}", f"구역: {section}"],
                table_position={"rowIndex": 0, "colIndex": 0},
            ),
            _block(
                "b-002",
                "721",
                context=[f"표: {title}", f"구역: {section}"],
                table_position={"rowIndex": 0, "colIndex": 1},
            ),
            _block(
                "b-003",
                "운송료",
                context=[f"표: 다른 표"],
                table_position={"rowIndex": 0, "colIndex": 0},
            ),
        ]
        table_analysis = _table_analysis(
            row_labels=["재료비"],
            col_labels=["항목", "금액"],
            row_count=1,
            column_count=2,
        )
        result = self.connect(fields, blocks, table_analysis=table_analysis)
        by_id = {r["fieldId"]: r for r in result["results"]}

        # 같은 표 제목/구역 블록만 연결 대상
        self.assertEqual(by_id["f-001"]["status"], "suggested")
        self.assertEqual(by_id["f-001"]["value"], "재료비")
        self.assertIn("b-001", by_id["f-001"]["sourceBlockIds"])
        self.assertNotIn("b-003", by_id["f-001"]["sourceBlockIds"])

        self.assertEqual(by_id["f-002"]["status"], "suggested")
        self.assertEqual(by_id["f-002"]["value"], "721")
        self.assertIn("b-002", by_id["f-002"]["sourceBlockIds"])

    # ------------------------------------------------------------------
    # 열 위치가 바뀌어도 열 의미를 따라감
    # ------------------------------------------------------------------
    def test_column_meaning_follows_even_if_column_position_changed(self):
        fields = [
            _field(
                "f-001",
                "금액",
                context=["표: 비용 표"],
                location=_location(
                    table={"tableId": "t-001"},
                    column={"columnIndex": 0},
                ),
            ),
            _field(
                "f-002",
                "품명",
                context=["표: 비용 표"],
                location=_location(
                    table={"tableId": "t-001"},
                    column={"columnIndex": 1},
                ),
            ),
        ]
        # 열 라벨 순서: 실제 표는 [금액, 항목] 순서(현실의 열 위치 뒤집힘)
        table_analysis = _table_analysis(
            row_labels=["재료비"],
            col_labels=["금액", "항목"],
            row_count=1,
            column_count=2,
        )
        blocks = [
            _block(
                "b-001",
                "721",
                context=["표: 비용 표"],
                table_position={"rowIndex": 0, "colIndex": 0},
            ),
            _block(
                "b-002",
                "재료비",
                context=["표: 비용 표"],
                table_position={"rowIndex": 0, "colIndex": 1},
            ),
        ]
        result = self.connect(fields, blocks, table_analysis=table_analysis)
        by_id = {r["fieldId"]: r for r in result["results"]}
        # 필드 "금액"은 location.columnIndex=0이지만, 열 의미가 "금액"이므로 b-001 연결
        self.assertEqual(by_id["f-001"]["value"], "721")
        # 필드 "품명"은 location.columnIndex=1이지만, 열 의미가 "항목"이므로 b-002 연결
        self.assertEqual(by_id["f-002"]["value"], "재료비")

    # ------------------------------------------------------------------
    # 고정 행 이름으로 값 대응, 행 순서를 뒤집어도 각각 맞음
    # ------------------------------------------------------------------
    def test_fixed_row_name_matches_value_after_row_order_reversed(self):
        fields = [
            _field(
                "f-001",
                "재료비",
                context=["표: 비용 표"],
                location=_location(
                    table={"tableId": "t-001"},
                    row={"rowIndex": 0},
                    column={"columnIndex": 1},
                ),
            ),
            _field(
                "f-002",
                "운송료",
                context=["표: 비용 표"],
                location=_location(
                    table={"tableId": "t-001"},
                    row={"rowIndex": 1},
                    column={"columnIndex": 1},
                ),
            ),
        ]
        table_analysis = _table_analysis(
            row_labels=["재료비", "운송료"],
            col_labels=["항목", "금액"],
            row_count=2,
            column_count=2,
        )
        # 원문 행 순서를 뒤집은 블록 배치: 운송료 행이 먼저, 재료비 행이 나중
        blocks = [
            _block(
                "b-001",
                "39",
                context=["표: 비용 표"],
                table_position={"rowIndex": 1, "colIndex": 1},
            ),
            _block(
                "b-002",
                "운송료",
                context=["표: 비용 표"],
                table_position={"rowIndex": 1, "colIndex": 0},
            ),
            _block(
                "b-003",
                "721",
                context=["표: 비용 표"],
                table_position={"rowIndex": 0, "colIndex": 1},
            ),
            _block(
                "b-004",
                "재료비",
                context=["표: 비용 표"],
                table_position={"rowIndex": 0, "colIndex": 0},
            ),
        ]
        result = self.connect(fields, blocks, table_analysis=table_analysis)
        by_id = {r["fieldId"]: r for r in result["results"]}
        # 필드 "재료비"(rowIndex 0)는 행 라벨 "재료비"에 해당하는 블록과 연결
        self.assertEqual(by_id["f-001"]["status"], "suggested")
        self.assertEqual(by_id["f-001"]["value"], "721")
        self.assertIn("b-003", by_id["f-001"]["sourceBlockIds"])
        # 필드 "운송료"(rowIndex 1)는 행 라벨 "운송료"에 해당하는 블록과 연결
        self.assertEqual(by_id["f-002"]["status"], "suggested")
        self.assertEqual(by_id["f-002"]["value"], "39")
        self.assertIn("b-001", by_id["f-002"]["sourceBlockIds"])

    # ------------------------------------------------------------------
    # 이름 없는 반복 행은 표·열 대응만 확인하고 순서로 채움
    # ------------------------------------------------------------------
    def test_name_less_repeated_rows_only_position_fill(self):
        fields = [
            _field(
                "f-001",
                "항목",
                context=["표: 비용 표"],
                location=_location(
                    table={"tableId": "t-001"},
                    row={"rowIndex": 0},
                    column={"columnIndex": 0},
                ),
            ),
            _field(
                "f-002",
                "금액",
                context=["표: 비용 표"],
                location=_location(
                    table={"tableId": "t-001"},
                    row={"rowIndex": 0},
                    column={"columnIndex": 1},
                ),
            ),
            _field(
                "f-003",
                "항목",
                context=["표: 비용 표"],
                location=_location(
                    table={"tableId": "t-001"},
                    row={"rowIndex": 1},
                    column={"columnIndex": 0},
                ),
            ),
            _field(
                "f-004",
                "금액",
                context=["표: 비용 표"],
                location=_location(
                    table={"tableId": "t-001"},
                    row={"rowIndex": 1},
                    column={"columnIndex": 1},
                ),
            ),
        ]
        table_analysis = _table_analysis(
            row_labels=[None, None],
            col_labels=["항목", "금액"],
            row_count=2,
            column_count=2,
        )
        blocks = [
            _block(
                "b-001",
                "밀크",
                context=["표: 비용 표"],
                table_position={"rowIndex": 0, "colIndex": 0},
            ),
            _block(
                "b-002",
                "100",
                context=["표: 비용 표"],
                table_position={"rowIndex": 0, "colIndex": 1},
            ),
            _block(
                "b-003",
                "빵",
                context=["표: 비용 표"],
                table_position={"rowIndex": 1, "colIndex": 0},
            ),
            _block(
                "b-004",
                "200",
                context=["표: 비용 표"],
                table_position={"rowIndex": 1, "colIndex": 1},
            ),
        ]
        result = self.connect(fields, blocks, table_analysis=table_analysis)
        by_id = {r["fieldId"]: r for r in result["results"]}
        self.assertEqual(by_id["f-001"]["value"], "밀크")
        self.assertEqual(by_id["f-002"]["value"], "100")
        self.assertEqual(by_id["f-003"]["value"], "빵")
        self.assertEqual(by_id["f-004"]["value"], "200")

    # ------------------------------------------------------------------
    # 성명/연락처 칸에 품명/금액이 들어가면 실패
    # ------------------------------------------------------------------
    def test_name_and_contact_not_filled_with_item_or_amount(self):
        fields = [
            _field(
                "f-001",
                "성명",
                context=["표: 기본 정보"],
                location=_location(
                    table={"tableId": "t-001"},
                    column={"columnIndex": 0},
                ),
            ),
            _field(
                "f-002",
                "연락처",
                context=["표: 기본 정보"],
                location=_location(
                    table={"tableId": "t-001"},
                    column={"columnIndex": 1},
                ),
            ),
        ]
        table_analysis = _table_analysis(
            row_labels=["홍길동"],
            col_labels=["품명", "금액"],
            row_count=1,
            column_count=2,
        )
        blocks = [
            _block(
                "b-001",
                "품명",
                context=["표: 기본 정보"],
                table_position={"rowIndex": 0, "colIndex": 0},
            ),
            _block(
                "b-002",
                "금액",
                context=["표: 기본 정보"],
                table_position={"rowIndex": 0, "colIndex": 1},
            ),
        ]
        result = self.connect(fields, blocks, table_analysis=table_analysis)
        by_id = {r["fieldId"]: r for r in result["results"]}
        # 성명/연락처는 열 의미(품명/금액)와 맞지 않으므로 연결되지 않음
        self.assertEqual(by_id["f-001"]["status"], "missing")
        self.assertIsNone(by_id["f-001"]["value"])
        self.assertEqual(by_id["f-002"]["status"], "missing")
        self.assertIsNone(by_id["f-002"]["value"])


if __name__ == "__main__":
    unittest.main()
