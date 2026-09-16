"""tests/engine/test_rules.py -- 규칙 연결 검사.

실제 hwpx.rules.connect_rules를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import unittest

from hwpx.rules import connect_rules
from hwpx.source import SourceBlock


def _field(
    fieldId: str,
    label: str,
    *,
    context: list[str] | None = None,
    unit: str | None = None,
) -> dict:
    return {
        "fieldId": fieldId,
        "label": label,
        "originalText": label,
        "context": context or [],
        "unit": unit,
        "editable": True,
        "required": False,
        "status": "input",
        "location": {},
    }


def _block(
    blockId: str,
    text: str,
    *,
    context: list[str] | None = None,
    facts: list[dict] | None = None,
    **kw,
) -> SourceBlock:
    defaults: dict = dict(
        level=0,
        kind="md-text",
        start=0,
        end=len(text),
        children=[],
        table_context={},
        context=context or [],
        table_position={},
        facts=facts or [],
    )
    defaults.update(kw)
    if "start" not in kw:
        defaults["start"] = 0
    if "end" not in kw:
        defaults["end"] = len(text)
    return SourceBlock(blockId=blockId, text=text, **defaults)


class TestConnectRules(unittest.TestCase):
    def test_clear_label_match_suggested(self):
        fields = [_field("f-001", "성명", context=["표: 기본", "row=0"])]
        blocks = [
            _block(
                "b-001",
                "성명: 김가람",
                context=["표: 기본", "row=0"],
                facts=[{"originalText": "성명: 김가람"}],
            ),
        ]
        result = connect_rules(fields, blocks, None, "ahash")
        res = next(r for r in result["results"] if r["fieldId"] == "f-001")
        self.assertEqual(res["status"], "suggested")
        self.assertEqual(res["value"], "김가람")
        self.assertEqual(res["valueTransform"], "extract")
        self.assertIn("b-001", res["sourceBlockIds"])
        self.assertIn("성명: 김가람", res["evidenceQuote"])

    def test_unit_conversion_thousand_to_won(self):
        fields = [_field("f-002", "총사업비", context=["표: 예산"], unit="천원")]
        blocks = [
            _block(
                "b-002",
                "총사업비 3천원",
                context=["표: 예산"],
                facts=[{"originalText": "총사업비 3천원"}],
            ),
        ]
        result = connect_rules(fields, blocks, None, "ahash")
        res = next(r for r in result["results"] if r["fieldId"] == "f-002")
        self.assertEqual(res["status"], "suggested")
        self.assertEqual(res["value"], "3000")
        self.assertEqual(res["valueTransform"], "unit")
        self.assertIn("b-002", res["sourceBlockIds"])
        self.assertIn("총사업비 3천원", res["evidenceQuote"])

    def test_same_label_different_rows_not_mixed(self):
        fields = [_field("f-001", "성명", context=["표: 기본"])]
        blocks = [
            _block(
                "b-001",
                "성명: 김가람",
                context=["표: 기본", "row=0"],
                facts=[{"originalText": "성명: 김가람"}],
            ),
            _block(
                "b-004",
                "성명: 이길동",
                context=["표: 기본", "row=1"],
                facts=[{"originalText": "성명: 이길동"}],
            ),
        ]
        result = connect_rules(fields, blocks, None, "ahash")
        res = next(r for r in result["results"] if r["fieldId"] == "f-001")
        self.assertEqual(res["status"], "conflict")
        self.assertIsNone(res["value"])
        self.assertIsNotNone(res["alternatives"])
        alt_values = [a["value"] for a in res["alternatives"]]
        self.assertIn("김가람", alt_values)
        self.assertIn("이길동", alt_values)
        self.assertIn("b-001", res["sourceBlockIds"])
        self.assertIn("b-004", res["sourceBlockIds"])

    def test_no_guess_amount_or_name(self):
        fields = [_field("f-006", "보조금", context=["표: 예산"], unit="천원")]
        blocks: list[SourceBlock] = []
        result = connect_rules(fields, blocks, None, "ahash")
        res = next(r for r in result["results"] if r["fieldId"] == "f-006")
        self.assertEqual(res["status"], "missing")
        self.assertIsNone(res["value"])
        self.assertIsNone(res["evidenceQuote"])

    def test_unit_unclear_no_auto_convert(self):
        fields = [_field("f-007", "수량", context=["표: 재고"], unit="개")]
        blocks = [
            _block(
                "b-007",
                "수량 5개",
                context=["표: 재고"],
                facts=[{"originalText": "수량 5개"}],
            ),
        ]
        result = connect_rules(fields, blocks, None, "ahash")
        res = next(r for r in result["results"] if r["fieldId"] == "f-007")
        self.assertEqual(res["status"], "suggested")
        self.assertEqual(res["value"], "5개")
        self.assertEqual(res["valueTransform"], "extract")

    def test_normalized_index_used_for_matching(self):
        fields = [_field("f-001", "성명", context=["표: 기본"])]
        blocks = [
            _block(
                "b-001",
                "성명: 김가람",
                context=["표: 기본"],
                facts=[{"originalText": "성명: 김가람"}],
            ),
        ]
        normalizedIndex = {"b-001": "성명 김가람"}
        result = connect_rules(fields, blocks, normalizedIndex, "ahash")
        res = next(r for r in result["results"] if r["fieldId"] == "f-001")
        self.assertEqual(res["status"], "suggested")
        self.assertEqual(res["value"], "김가람")


if __name__ == "__main__":
    unittest.main()
