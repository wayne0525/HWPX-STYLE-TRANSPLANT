"""tests/engine/test_source.py -- B 원문 추출 검사.

실제 hwpx.source.extract_b를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import unittest

from hwpx.source import extract_b, BExtractResult, SourceBlock


class TestExtractB(unittest.TestCase):
    def test_txt_extract_preserves_order(self):
        text = "첫째 줄\n둘째 줄\n셋째 줄"
        result = extract_b(text, kind="txt")
        self.assertIsInstance(result, BExtractResult)
        self.assertEqual(result.kind, "txt")
        self.assertEqual(len(result.blocks), 3)
        self.assertEqual(result.blocks[0].text, "첫째 줄")
        self.assertEqual(result.blocks[1].text, "둘째 줄")
        self.assertEqual(result.blocks[2].text, "셋째 줄")
        # 재결합이 원문과 일치
        rejoined = "\n".join(b.text for b in result.blocks)
        self.assertEqual(rejoined, text)

    def test_md_extract_preserves_order(self):
        text = "# 제목\n\n본문 줄\n- 목록 1\n- 목록 2"
        result = extract_b(text, kind="md")
        self.assertEqual(result.kind, "md")
        self.assertGreater(len(result.blocks), 0)
        rejoined = "\n".join(b.text for b in result.blocks)
        self.assertEqual(rejoined, text)

    def test_utf8_paste_as_txt(self):
        text = "붙여넣기 내용\n둘째 줄"
        result = extract_b(text)  # kind 미지정 → txt
        self.assertEqual(result.kind, "txt")
        rejoined = "\n".join(b.text for b in result.blocks)
        self.assertEqual(rejoined, text)

    def test_bytes_input(self):
        text = "바이트 입력\nUTF-8"
        result = extract_b(text.encode("utf-8"), kind="txt")
        self.assertEqual(result.kind, "txt")
        rejoined = "\n".join(b.text for b in result.blocks)
        self.assertEqual(rejoined, text)

    def test_hwpx_extract_text_only(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<hp:document xmlns:hp="http://www.hwpzone.org/hwpx">'
            '<hp:body>'
            '<hp:section>'
            '<hp:p><hp:t>첫째 문단</hp:t></hp:p>'
            '<hp:p><hp:t>둘째 문단</hp:t></hp:p>'
            '</hp:section>'
            '</hp:body>'
            '</hp:document>'
        )
        result = extract_b(xml.encode("utf-8"), kind="hwpx")
        self.assertEqual(result.kind, "hwpx")
        texts = [b.text for b in result.blocks]
        # 서식 없이 텍스트만 추출
        self.assertIn("첫째 문단", texts)
        self.assertIn("둘째 문단", texts)
        # 재결합에 XML 태그가 남지 않아야 함
        rejoined = "\n".join(texts)
        self.assertNotIn("<hp:p>", rejoined)
        self.assertNotIn("</hp:p>", rejoined)

    def test_no_duplicate_in_multi_section(self):
        # 여러 section이 있어도 중복/순서 뒤바뀜이 없어야 함
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<hp:document xmlns:hp="http://www.hwpzone.org/hwpx">'
            '<hp:body>'
            '<hp:section>'
            '<hp:p><hp:t>섹션1-A</hp:t></hp:p>'
            '<hp:p><hp:t>섹션1-B</hp:t></hp:p>'
            '</hp:section>'
            '<hp:section>'
            '<hp:p><hp:t>섹션2-A</hp:t></hp:p>'
            '</hp:section>'
            '</hp:body>'
            '</hp:document>'
        )
        result = extract_b(xml.encode("utf-8"), kind="hwpx")
        texts = [b.text for b in result.blocks if b.text.strip()]
        self.assertEqual(texts, ["섹션1-A", "섹션1-B", "섹션2-A"])

    def test_nested_table_text_once(self):
        # 중첩 표가 있어도 텍스트가 중복 집계되지 않아야 함
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<hp:document xmlns:hp="http://www.hwpzone.org/hwpx">'
            '<hp:body>'
            '<hp:section>'
            '<hp:p><hp:t>바깥</hp:t></hp:p>'
            '<hp:p>'
            '<hp:tbl xmlns:hp="http://www.hwpzone.org/hwpx">'
            '<hp:tr><hp:tc><hp:t>안쪽</hp:t></hp:tc></hp:tr>'
            '</hp:tbl>'
            '</hp:p>'
            '</hp:section>'
            '</hp:body>'
            '</hp:document>'
        )
        result = extract_b(xml.encode("utf-8"), kind="hwpx")
        texts = [b.text for b in result.blocks if b.text.strip()]
        # '안쪽'이 한 번만 나와야 함
        self.assertEqual(texts.count("안쪽"), 1)
        self.assertIn("바깥", texts)

    def test_long_block_split_preserves_position(self):
        # 긴 블록은 원문 위치가 유지되는 하위 블록으로 나눈다
        text = "긴 줄 " * 10
        result = extract_b(text, kind="txt")
        # 이번 번호의 split은 줄 단위이므로, 한 줄이 여러 하위 블록으로 나뉠 수 있다
        # 하위 블록이 있으면 각 블록의 start/end가 원문 위치를 유지해야 한다
        if any(b.children for b in result.blocks):
            pos = 0
            for b in result.blocks:
                for child in b.children:
                    self.assertEqual(child.start, pos)
                    pos += len(child.text)
                    self.assertEqual(child.end, pos)
        else:
            # 하위 블록이 없으면 블록 자체가 원문 위치를 유지한다
            pos = 0
            for b in result.blocks:
                self.assertEqual(b.start, pos)
                pos += len(b.text)
                self.assertEqual(b.end, pos)

    def test_block_ids_unique(self):
        text = "A\nB\nC"
        result = extract_b(text, kind="txt")
        ids = [b.blockId for b in result.blocks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_empty_input_no_blocks(self):
        result = extract_b("", kind="txt")
        self.assertEqual(len(result.blocks), 0)
        self.assertIn("no blocks extracted", result.warnings)

    def test_invalid_kind_raises(self):
        with self.assertRaises(Exception) as ctx:
            extract_b("텍스트", kind="unknown")
        self.assertIn("kind must be hwpx/txt/md", str(ctx.exception))

    def test_hash_consistent(self):
        text = "해시 확인\n동일 텍스트"
        r1 = extract_b(text, kind="txt", b_hash="fixed-hash")
        r2 = extract_b(text, kind="txt", b_hash="fixed-hash")
        self.assertEqual(r1.b_hash, r2.b_hash)
        self.assertEqual(r1.b_hash, "fixed-hash")

    def test_hash_auto_from_text(self):
        text = "자동 해시\n계산"
        r1 = extract_b(text.encode("utf-8"), kind="txt")
        r2 = extract_b(text, kind="txt")
        self.assertEqual(r1.b_hash, r2.b_hash)
        expected = __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(r1.b_hash, expected)


if __name__ == "__main__":
    unittest.main()
