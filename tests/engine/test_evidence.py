"""tests/engine/test_evidence.py -- 제안 검증(validate_proposals) 검사.

실제 hwpx.evidence.validate_proposals와 hwpx.rules.connect_rules를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import unittest

from hwpx.evidence import validate_proposals
from hwpx.rules import connect_rules
from hwpx.source import SourceBlock


def _field(field_id, label, *, context=None, unit=None, location=None):
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


def _block(block_id, text, *, context=None, facts=None, table_position=None, kind="md-text"):
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


def _rule_result(field_id, status, value, source_block_ids, *,
                 evidence_quote=None, evidence=None, value_transform="extract"):
    return {
        "fieldId": field_id,
        "status": status,
        "value": value,
        "valueTransform": value_transform,
        "sourceBlockIds": source_block_ids,
        "evidenceQuote": evidence_quote,
        "evidence": evidence or [],
        "reason": "",
        "needsReview": False,
        "alternatives": None,
    }


def _proposal(field_id, value, source_block_ids, *,
              evidence_quote=None, evidence=None, value_transform="extract"):
    return {
        "fieldId": field_id,
        "value": value,
        "valueTransform": value_transform,
        "sourceBlockIds": source_block_ids,
        "evidenceQuote": evidence_quote,
        "evidence": evidence or [],
    }


def _user_edit(field_id, value, *, source="manual", note=None):
    return {
        "fieldId": field_id,
        "value": value,
        "source": source,
        "note": note,
    }


class TestValidateProposals(unittest.TestCase):
    def test_valid_proposals_pass(self):
        fields = [
            _field("f-001", "성명", context=["표: 기본 정보"]),
            _field("f-002", "금액", context=["표: 예산"], unit="천원"),
        ]
        blocks = [
            _block("b-001", "성명: 김가람", context=["표: 기본 정보"]),
            _block("b-002", "금액 3천원", context=["표: 예산"]),
        ]
        connect_result = connect_rules(fields, blocks, None, "ahash")
        results = connect_result["results"]
        proposals = [
            _proposal("f-001", results[0]["value"], results[0]["sourceBlockIds"],
                      evidence_quote=results[0]["evidenceQuote"]),
            _proposal("f-002", results[1]["value"], results[1]["sourceBlockIds"],
                      evidence_quote=results[1]["evidenceQuote"],
                      value_transform=results[1]["valueTransform"]),
        ]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        self.assertFalse(result["errors"])
        by_id = {c["fieldId"]: c for c in result["checked"]}
        self.assertEqual(by_id["f-001"]["status"], "ok")
        self.assertEqual(by_id["f-002"]["status"], "ok")

    def test_unknown_field_id_rejected(self):
        fields = [_field("f-001", "성명")]
        blocks = [_block("b-001", "성명: 김가람")]
        results = [_rule_result("f-001", "suggested", "김가람", ["b-001"], evidence_quote="성명: 김가람")]
        proposals = [_proposal("f-999", "값", ["b-001"], evidence_quote="성명: 김가람")]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        self.assertTrue(any(e["type"] == "invalid_field_id" for e in result["errors"]))

    def test_missing_block_quote_rejected(self):
        fields = [_field("f-001", "성명")]
        blocks = [_block("b-001", "성명: 김가람")]
        results = [_rule_result("f-001", "suggested", "김가람", ["b-001"], evidence_quote="성명: 김가람")]
        proposals = [_proposal("f-001", "김가람", ["b-999"], evidence_quote="성명: 김가람")]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        self.assertTrue(any(e["type"] == "missing_quote" for e in result["errors"]))

    def test_quote_not_in_block_rejected(self):
        fields = [_field("f-001", "성명")]
        blocks = [_block("b-001", "성명: 김가람")]
        results = [_rule_result("f-001", "suggested", "김가람", ["b-001"], evidence_quote="성명: 김가람")]
        proposals = [_proposal("f-001", "김가람", ["b-001"], evidence_quote="성명: 홍길동")]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        self.assertTrue(any(e["type"] == "missing_quote" for e in result["errors"]))

    def test_value_mismatch_rejected(self):
        fields = [_field("f-001", "성명")]
        blocks = [_block("b-001", "성명: 김가람")]
        results = [_rule_result("f-001", "suggested", "김가람", ["b-001"], evidence_quote="성명: 김가람")]
        proposals = [_proposal("f-001", "홍길동", ["b-001"], evidence_quote="성명: 김가람")]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        self.assertTrue(any(e["type"] == "value_mismatch" for e in result["errors"]))

    def test_number_alone_not_rejected_when_matching(self):
        fields = [_field("f-002", "금액", unit="천원")]
        blocks = [_block("b-002", "금액 3천원")]
        connect_result = connect_rules(fields, blocks, None, "ahash")
        results = connect_result["results"]
        proposals = [_proposal("f-002", results[0]["value"], results[0]["sourceBlockIds"],
                               evidence_quote=results[0]["evidenceQuote"],
                               value_transform=results[0]["valueTransform"])]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        self.assertFalse(any(e["type"] == "value_mismatch" for e in result["errors"]))

    def test_unit_transform_without_reason_warning(self):
        fields = [_field("f-002", "금액", unit="천원")]
        blocks = [_block("b-002", "금액 3천원")]
        results = [_rule_result("f-002", "suggested", "3000", [], evidence_quote="3000", value_transform="unit")]
        proposals = [_proposal("f-002", "3000", [], evidence_quote="3천원", value_transform="unit")]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        self.assertTrue(any(w["type"] == "unit_unclear" for w in result["warnings"]))

    def test_multi_evidence_one_modified_rejected(self):
        fields = [_field("f-001", "성명")]
        blocks = [
            _block("b-001", "성명: 김가람"),
            _block("b-003", "성명: 김가람"),
        ]
        proposals = [_proposal(
            "f-001", "김가람", ["b-001", "b-003"],
            evidence_quote="성명: 김가람",
            evidence=[
                {"sourceBlockId": "b-001", "quote": "성명: 김가람"},
                {"sourceBlockId": "b-003", "quote": "성명: 홍길동"},
            ],
        )]
        results = [_rule_result(
            "f-001", "suggested", "김가람", ["b-001", "b-003"],
            evidence_quote="성명: 김가람",
            evidence=[
                {"sourceBlockId": "b-001", "quote": "성명: 김가람"},
                {"sourceBlockId": "b-003", "quote": "성명: 김가람"},
            ],
        )]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        self.assertTrue(any(e["type"] == "missing_quote" for e in result["errors"]))

    def test_conflict_preserved(self):
        fields = [_field("f-001", "성명")]
        blocks = [_block("b-001", "성명: 김가람")]
        results = [_rule_result("f-001", "conflict", None, ["b-001"], evidence_quote="여러 근거가 서로 다른 값을 가리킴")]
        proposals = [_proposal("f-001", "김가람", ["b-001"], evidence_quote="성명: 김가람")]
        result = validate_proposals(fields, results, proposals, blocks, None, None)
        by_id = {c["fieldId"]: c for c in result["checked"]}
        self.assertIn(by_id["f-001"]["status"], ("blocked", "review"))

    def test_user_edit_protected(self):
        fields = [_field("f-001", "성명")]
        blocks = [_block("b-001", "성명: 김가람")]
        results = [_rule_result("f-001", "suggested", "김가람", ["b-001"], evidence_quote="성명: 김가람")]
        proposals = [_proposal("f-001", "홍길동", ["b-001"], evidence_quote="성명: 김가람")]
        user_edits = [_user_edit("f-001", "김가람", source="manual", note="직접 입력")]
        result = validate_proposals(fields, results, proposals, blocks, None, user_edits)
        self.assertTrue(any(e["type"] == "user_value_protected" for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
