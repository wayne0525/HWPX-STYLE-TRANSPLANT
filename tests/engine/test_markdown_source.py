"""tests/engine/test_markdown_source.py -- Markdown/표/사실 추출 검사.

실제 hwpx.source.extract_b를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import unittest

from hwpx.source import extract_b, BExtractResult, SourceBlock


class TestMarkdownSource(unittest.TestCase):
    def test_heading_hierarchy_preserved(self):
        text = "# 제목1\n## 제목2\n### 제목3\n본문"
        result = extract_b(text, kind="md")
        self.assertEqual(result.kind, "md")
        md_blocks = [b for b in result.blocks if b.md_level is not None]
        self.assertEqual(md_blocks[0].md_level, 1)
        self.assertEqual(md_blocks[1].md_level, 2)
        self.assertEqual(md_blocks[2].md_level, 3)
        self.assertIn("h1", md_blocks[0].context)
        self.assertIn("h2", md_blocks[1].context)
        self.assertIn("h3", md_blocks[2].context)

    def test_table_row_and_column_in_context(self):
        text = "| 이름 | 값 |\n| --- | --- |\n| 김가람 | 010-1234-5678 |"
        result = extract_b(text, kind="md")
        table_blocks = [b for b in result.blocks if b.table_position]
        # 헤더 구분선과 데이터 행이 표 위치로 표시되어야 함
        self.assertTrue(any(b.context and "row=" in " ".join(b.context) for b in table_blocks))

    def test_escape_pipe_not_cell_separator(self):
        # 이스케이프된 세로줄은 셀 구분자로 세지 않음
        text = "| 이름 | 값 \\| 단위 |\n| --- | --- |\n| 김가람 | 10 \\| 개 |"
        result = extract_b(text, kind="md")
        data_blocks = [b for b in result.blocks if b.table_position and not b.table_position.get("is_header")]
        # 데이터 행이 있는지 확인
        self.assertTrue(data_blocks)
        # 원본 줄의 셀 개수가 2인지 확인(이스케이프 세로줄은 구분자로 세지 않음)
        data_line = next((b.text for b in result.blocks if b.text.strip().startswith("|") and "김가람" in b.text), None)
        self.assertIsNotNone(data_line)
        from hwpx.source import _md_table_cells
        cells = _md_table_cells(data_line)
        self.assertEqual(len(cells), 2)
        # 셀 내부에 이스케이프 세로줄 표현이 남아 있어야 함(원문 위치 보존)
        self.assertTrue(any("\\|" in c for c in cells))

    def test_split_label_value_by_slash_and_semicolon(self):
        # 슬래시/세미콜론으로 나뉜 라벨 값을 분리
        text = "이름: 김가람; 연락처: 010-1234-5678 / 주소: 서울특별시"
        result = extract_b(text, kind="md")
        # facts가 여러 개로 나뉘어야 함
        block = result.blocks[-1]
        self.assertGreaterEqual(len(block.facts), 2)

    def test_repr_and_contact_split_two_facts(self):
        # 한 줄에 대표자 김가람과 연락처가 있으면 두 사실로 나눔
        text = "대표자 김가람, 연락처 010-1234-5678"
        result = extract_b(text, kind="md")
        block = result.blocks[-1]
        texts = [f["originalText"] for f in block.facts]
        self.assertIn("대표자 김가람", texts)
        self.assertIn("연락처 010-1234-5678", texts)
        self.assertEqual(len(texts), 2)

    def test_two_board_counts_not_mixed(self):
        # 정수의 이사 9명과 현원의 이사 7명이 섞이지 않아야 함
        text = "정수 이사 9명, 현원 이사 7명"
        result = extract_b(text, kind="md")
        block = result.blocks[-1]
        texts = [f["originalText"] for f in block.facts]
        self.assertIn("정수 이사 9명", texts)
        self.assertIn("현원 이사 7명", texts)
        self.assertEqual(len(texts), 2)

    def test_plain_heading_context_not_faked_as_quote(self):
        # 제목만으로 만든 문맥을 실제 인용문으로 꾸미지 않음
        text = "#総会報告"
        result = extract_b(text, kind="md")
        block = result.blocks[-1]
        # 문맥에 실제 인용문이 들어가면 안 됨(이번 단순 구현은 제목 레벨만 넣음)
        self.assertNotIn("총회보고", block.context)
        self.assertIn("h1", block.context)

    def test_stripped_value_keeps_original_span(self):
        # 표시(제목 마크 등)를 제거한 값과 실제 원문 구간의 대응을 유지
        text = "## 대표자: 김가람"
        result = extract_b(text, kind="md")
        block = result.blocks[-1]
        # 원문 text는 그대로 보존되고, md_level만 분리됨
        self.assertEqual(block.text, "## 대표자: 김가람")
        self.assertEqual(block.md_level, 2)
        self.assertEqual(block.start, 0)  # 첫 블록이므로 시작 위치 0
        self.assertGreater(block.end, block.start)

    def test_table_header_and_data_position_distinct(self):
        text = "| 항목 | 값 |\n| --- | --- |\n| 대표자 | 김가람 |"
        result = extract_b(text, kind="md")
        blocks = result.blocks
        header_sep = [b for b in blocks if b.table_position.get("header")]
        data = [b for b in blocks if b.text and "김가람" in b.text and b.table_position.get("header")]
        self.assertTrue(header_sep)
        self.assertTrue(data)
        # データ行の table_position にヘッダーが接続されていること
        if data:
            self.assertIn("header", data[0].table_position)
            self.assertGreaterEqual(len(data[0].table_position["header"]), 1)

    def test_md_rejoin_preserves_empty_lines(self):
        text = "# 제목\n\n본문\n\n- 목록"
        result = extract_b(text, kind="md")
        rejoined = "\n".join(b.text for b in result.blocks)
        self.assertEqual(rejoined, text)


if __name__ == "__main__":
    unittest.main()
