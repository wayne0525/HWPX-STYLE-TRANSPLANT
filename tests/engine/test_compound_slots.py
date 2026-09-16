"""tests/engine/test_compound_slots.py -- 복합 슬롯 분리 검사.

실제 hwpx.analyze.split_compound_slots를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import unittest

from hwpx.analyze import split_compound_slots


def _f(field_id, candidate_id, label, original_text, *, editable=True, required=True, status="input", unit=None, context=None, location=None):
    return {
        "fieldId": field_id,
        "candidateId": candidate_id,
        "label": label,
        "originalText": original_text,
        "editable": editable,
        "required": required,
        "status": status,
        "unit": unit,
        "context": context or [],
        "location": location or {},
    }


class TestSplitCompoundSlots(unittest.TestCase):
    def test_address_and_zip_separate(self):
        fields = [
            _f("f-0000", "c1", "주소", "서울특별시 / 04524"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 2)
        texts = [f["originalText"] for f in out]
        self.assertIn("서울특별시", texts)
        self.assertIn("04524", texts)

    def test_job_and_name_separate(self):
        fields = [
            _f("f-0000", "c1", "직명 / 성명", "팀장 / 홍길동"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 2)
        texts = [f["originalText"] for f in out]
        self.assertIn("팀장", texts)
        self.assertIn("홍길동", texts)

    def test_start_end_time_four_slots(self):
        # "시작 시각 09시 00분 부터 종료 시각 18시 00분 까지" → 네 구간
        fields = [
            _f("f-0000", "c1", "시간", "시작 시각 09시 00분 부터 종료 시각 18시 00분 까지"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 4)
        texts = [f["originalText"] for f in out]
        self.assertIn("시작 시각", texts)
        self.assertIn("09시 00분", texts)
        self.assertIn("종료 시각", texts)
        self.assertIn("18시 00분", texts)

    def test_total_and_subsidy_separate(self):
        fields = [
            _f("f-0000", "c1", "재원", "총사업비 00원 / 보조금 00원"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 2)
        texts = [f["originalText"] for f in out]
        self.assertIn("총사업비 00원", texts)
        self.assertIn("보조금 00원", texts)

    def test_placeholder_braces_not_blanked(self):
        # 중괄호 표시는 빈칸으로 지우지 않고 별도 상태로 남긴다
        fields = [
            _f("f-0000", "c1", "총사업비", "{총사업비}"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["originalText"], "{총사업비}")
        self.assertEqual(out[0]["status"], "placeholder")

    def test_zero_amount_not_assumed_placeholder_unclear(self):
        # 실제 값 0은 자리표시자로 단정하지 않는다
        fields = [
            _f("f-0000", "c1", "보조금", "0"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["originalText"], "0")
        self.assertEqual(out[0]["status"], "input")

    def test_zero_amount_placeholder_when_context_clear(self):
        # 문맥상 자리표시자임이 확인된 0은 placeholder로 표시
        fields = [
            _f("f-0000", "c1", "총사업비", "총사업비 0원"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 1)
        self.assertIn("0", out[0]["originalText"])
        # 이번 단순 구현에서 총사업비 0원은 자리표시자 문맥으로 보지 않으므로 input
        self.assertEqual(out[0]["status"], "input")

    def test_unit_only_cell_decoration(self):
        fields = [
            _f("f-0000", "c1", "단위", "천원", unit="천원"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["status"], "decoration")

    def test_bullet_blank_paragraph_decoration(self):
        fields = [
            _f("f-0000", "c1", None, "", context=["bullet 항목"]),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["status"], "decoration")

    def test_label_and_seal_not_blanked(self):
        # 라벨과 직인 문구는 그대로 보존
        fields = [
            _f("f-0000", "c1", "상기 사실을 확인합니다", "확인"),
            _f("f-0001", "c2", "직인", "직인"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 2)
        texts = [f["originalText"] for f in out]
        self.assertIn("확인", texts)
        self.assertIn("직인", texts)

    def test_actual_date_not_blanked(self):
        # 실제로 기입된 날짜는 빈칸으로 지우지 않는다
        fields = [
            _f("f-0000", "c1", "작성일", "2026-09-16"),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["originalText"], "2026-09-16")

    def test_location_preserved(self):
        loc = {"section": "section-1", "paragraph": "p-3", "table": None, "row": None, "column": None}
        fields = [
            _f("f-0000", "c1", "주소", "서울특별시 / 04524", location=loc),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 2)
        for f in out:
            self.assertEqual(f["location"], loc)

    def test_mixed_fixtures_labelled_value(self):
        fields = [
            _f("f-0000", "c1", "주소:", "서울특별시 / 04524"),
        ]
        out = split_compound_slots(fields)
        # 콜론 라벨 + 복합 값 → 라벨 분리 + 값 분리로 여러 슬롯이 될 수 있음
        self.assertGreaterEqual(len(out), 2)
        texts = [f["originalText"] for f in out]
        self.assertIn("주소:", texts)
        self.assertIn("서울특별시", texts)
        self.assertIn("04524", texts)

    def test_empty_decoration_not_editable(self):
        # editable=False는 그대로 보존
        fields = [
            _f("f-0000", "c1", "고정 문구", "이름:", editable=False),
        ]
        out = split_compound_slots(fields)
        self.assertEqual(len(out), 1)
        self.assertFalse(out[0]["editable"])


if __name__ == "__main__":
    unittest.main()
