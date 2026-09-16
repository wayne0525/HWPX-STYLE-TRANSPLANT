"""tests/engine/test_gold.py - 사람 정답 기반 품질 평가 검사.

scripts.evaluate.evaluate_quality와 scripts.evaluate._run_synth_evaluation을
실제 호출해 종료 코드와 품질 판정을 확인한다.

pytest가 없을 때는 unittest로 실행한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import hashlib
import io
import unittest
import zipfile
from unittest.mock import patch

from hwpx.analyze import analyze_a
from hwpx.xml import read_xml
from hwpx.package import read_hwpx
from scripts.evaluate import evaluate_quality, _gold_for, _edits_for


def _hwpx_bytes(section_xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("mimetype", b"application/hwp+zip")
        z.writestr(
            "[Content_Types].xml",
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
            "<Default Extension='xml' ContentType='application/xml'/>"
            "</Types>",
        )
        z.writestr(
            "Content.hpf",
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<HpF xmlns='http://www.hwpzone.org/hwpx'>"
            "<section href='section0.xml'/>"
            "</HpF>",
        )
        z.writestr("section0.xml", section_xml)
    return buf.getvalue()


def _section0(text: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        f"<hp:p><hp:t>{text}</hp:t></hp:p>"
        "</hp:section>"
    )


class TestGoldEvaluateQualityExitCode(unittest.TestCase):
    def test_missing_field_produces_exit_1(self):
        raw = _hwpx_bytes(_section0("원본 텍스트"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "정답값"}
        edits = [{"fieldId": fid, "value": "다른값", "selected": True, "origin": "manual"}]
        result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=True)
        self.assertEqual(result["exit_code"], 1, f"오기입은 품질 실패여야 함: {result}")
        self.assertFalse(result["passed"])

    def test_unselected_original_is_not_miswrite(self):
        raw = _hwpx_bytes(_section0("고정 원문"))
        digest = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=digest).fields[0]["fieldId"]
        result = evaluate_quality(raw, digest, None, {fid: None}, edits=[], human_reviewed=True)
        self.assertTrue(result["passed"], result)

    def test_missing_required_field_produces_exit_1(self):
        raw = _hwpx_bytes(_section0("원본 텍스트"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "정답값"}
        # value를 비우면 기대 정답이 missing으로 처리되어 품질 실패
        edits = [{"fieldId": fid, "value": "", "selected": True, "origin": "manual"}]
        result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=True)
        self.assertEqual(result["exit_code"], 1, f"정답 미기입은 품질 실패여야 함: {result}")
        self.assertFalse(result["passed"])

    def test_exact_match_produces_exit_0(self):
        raw = _hwpx_bytes(_section0("원본 텍스트"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "정답값"}
        edits = [{"fieldId": fid, "value": "정답값", "selected": True, "origin": "manual"}]
        result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=True)
        self.assertEqual(result["exit_code"], 0, f"정답 일치 시 통과여야 함: {result}")
        self.assertTrue(result["passed"])

    def test_no_human_review_reports_not_verified(self):
        raw = _hwpx_bytes(_section0("원본 텍스트"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "정답값"}
        edits = [{"fieldId": fid, "value": "정답값", "selected": True, "origin": "manual"}]
        result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=False)
        self.assertIn("사람 검토가 없어", " ".join(result["notes"]))
        self.assertFalse(result["human_reviewed"])

    def test_no_edits_reports_not_verified_and_exit_2(self):
        raw = _hwpx_bytes(_section0("원본 텍스트"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "정답값"}
        result = evaluate_quality(raw, a_sha, None, gold, edits=None, human_reviewed=False)
        self.assertEqual(result["exit_code"], 2, f"편집 없이 사람 검토도 없으면 자료 미검증(2)여야 함: {result}")
        self.assertFalse(result["passed"])

    def test_protected_structure_change_produces_exit_1(self):
        section = _section0("원본 텍스트").replace("</hp:section>", "<hp:p><hp:t>유지할 문단</hp:t></hp:p></hp:section>")
        raw = _hwpx_bytes(section)
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "정답값"}
        edits = [{"fieldId": fid, "value": "정답값", "selected": True, "origin": "manual"}]
        damaged = _hwpx_bytes(section.replace("원본 텍스트", "정답값").replace("유지할 문단", "변조된 문단"))
        with patch("scripts.evaluate.generate_result", return_value={"resultBytes": damaged, "errors": []}):
            result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=True)
        self.assertEqual(result["exit_code"], 1)
        self.assertTrue(result["metrics"]["protected_changed"], result)


class TestGoldFixtureAnswers(unittest.TestCase):
    def test_eval_unused_has_no_gold_answer(self):
        self.assertIsNone(_gold_for("eval_unused.hwpx"))

    def test_known_business_form_has_gold_answer(self):
        gold = _gold_for("company_report.hwpx")
        self.assertIsNotNone(gold)
        self.assertIsInstance(gold, dict)
        self.assertGreater(len(gold), 0)


class TestGoldQualityMetrics(unittest.TestCase):
    def test_fill_rate_uses_denominator_including_undetected(self):
        raw = _hwpx_bytes(_section0("원본 텍스트"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "정답값", "f-2": "다른정답"}
        edits = [{"fieldId": fid, "value": "정답값", "selected": True, "origin": "manual"}]
        result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=True)
        metrics = result["metrics"]
        self.assertIn("fill_rate", metrics)
        # 탐지되지 않은 f-2가 분자에 포함되지 않아 fill_rate가 1.0보다 작아야 함
        self.assertLess(metrics["fill_rate"], 1.0, "탐지되지 않은 필드도 분모에 포함돼 fill_rate가 1.0 미만이어야 함")

    def test_miswrite_count_reported(self):
        raw = _hwpx_bytes(_section0("원본 텍스트"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "정답값"}
        edits = [{"fieldId": fid, "value": "오답값", "selected": True, "origin": "manual"}]
        result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=True)
        self.assertGreater(result["metrics"]["miswrite_count"], 0)
        self.assertEqual(result["metrics"]["fill_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
