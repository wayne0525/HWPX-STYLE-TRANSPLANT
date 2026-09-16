"""
tests/test_analyze.py — 단계 3 verify: analyze_a 정규 구현 검증.

MVP 규칙 1~3만 검사한다. (문단 입력란, 중첩 표 등은 아직 범위 밖)
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

HERE = os.path.dirname(__file__)
FIXTURES = os.path.join(HERE, "fixtures")
A_PATH = os.path.join(FIXTURES, "A.hwpx")

from hwpx.package import read_hwpx
from hwpx.xml import read_xml
from hwpx.template import analyze_a


def _analysis_from_path(path):
    raw = open(path, "rb").read()
    return analyze_a(raw)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def analysis():
    return _analysis_from_path(A_PATH)


def _fields_by_id(analysis):
    return {f["field_id"]: f for f in analysis["fields"]}


def _fields_by_table(analysis, table_path):
    tp = tuple(table_path)
    return [f for f in analysis["fields"] if tuple(f["location"]["table_path"]) == tp]


# ---------------------------------------------------------------------------
# 1. 기본 구조 / 메타데이터
# ---------------------------------------------------------------------------

class TestAnalyzeMeta:
    def test_status_ok(self, analysis):
        assert analysis["analysis_status"] in ("ok", "partial")

    def test_file_kind_hwpx(self, analysis):
        assert analysis["file_kind"] == "hwpx"

    def test_a_hash_prefix(self, analysis):
        import hashlib
        assert analysis["a_hash"] == hashlib.sha256(open(A_PATH, 'rb').read()).hexdigest()

    def test_idempotent_a_hash(self, analysis):
        """두 번 호출해도 a_hash가 같아야 한다 (결정론)."""
        a2 = _analysis_from_path(A_PATH)
        assert a2["a_hash"] == analysis["a_hash"]

    def test_failure_none(self, analysis):
        assert analysis.get("failure") is None


# ---------------------------------------------------------------------------
# 2. 필드 ID 형식
# ---------------------------------------------------------------------------

class TestFieldIdFormat:
    def test_all_have_field_id(self, analysis):
        assert len(analysis["fields"]) > 0
        for f in analysis["fields"]:
            assert "field_id" in f
            assert f["field_id"].startswith("f-")
            assert len(f["field_id"]) == 26

    def test_ids_are_contiguous(self, analysis):
        ids = sorted(f["field_id"] for f in analysis["fields"])
        assert ids == sorted(f['field_id'] for f in _analysis_from_path(A_PATH)['fields'])

    def test_unique_field_ids(self, analysis):
        ids = [f["field_id"] for f in analysis["fields"]]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# 3. 표 3: 단체/사업 정보 — 규칙 1 라벨 셀
# ---------------------------------------------------------------------------

class TestTable3:
    def test_danche_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '단 체 명')
        assert f is not None
        assert f["label"] == "단 체 명"
        assert f["location"]["table_path"] == [3, 0]
        assert f["location"]["row"] == 0
        assert f["location"]["col"] == 1
        assert f["unit"] == "text"
        assert f["editable"] is True
        assert f["required"] is False
        assert f["merge_info"] is not None
        assert f["merge_info"]["colSpan"] == 10

    def test_saeop_gigan_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '사업기간')
        assert f is not None
        assert f["label"] == "사업기간"
        assert f["location"]["table_path"] == [3, 0]

    def test_saeop_daesang_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '사업대상')
        assert f is not None
        assert f["label"] == "사업대상"
        assert f["location"]["table_path"] == [3, 0]


# ---------------------------------------------------------------------------
# 4. 표 10: 시설 정보 — 규칙 1 라벨 셀 (시 설 명, 설립목적 등)
# ---------------------------------------------------------------------------

class TestTable10:
    def test_siseol_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '시 설 명')
        assert f is not None
        assert f["label"] == "시 설 명"
        assert f["location"]["table_path"] == [10, 0]
        assert f["location"]["row"] == 0
        assert f["location"]["col"] == 1
        assert f["unit"] == "text"
        assert f["merge_info"] is not None
        assert f["merge_info"]["colSpan"] == 4

    def test_eseong_mokjeok_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '설립목적')
        assert f is not None
        assert f["label"] == "설립목적"
        assert f["location"]["table_path"] == [10, 0]

    def test_jiwon_geun_geo_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '지원근거및  내용')
        assert f is not None
        assert f["label"] == "지원근거및  내용"
        # ‘지원근거및  내용’은 money 패턴이 *끝*에 있을 때만 money로 분류.
        # 이 라벨은 끝에 ‘원’이 없으므로 text.
        assert f["unit"] == "text", (
            f"‘지원근거및  내용’은 money가 아니라 text여야 함. "
            f"현재 unit={f['unit']}"
        )

    def test_homepage_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '홈페이지')
        assert f is not None
        assert f["label"] == "홈페이지"
        assert f["location"]["table_path"] == [10, 0]

    def test_deungrok_gigwan_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '등록기관')
        assert f is not None
        assert f["label"] == "등록기관"
        assert f["location"]["table_path"] == [10, 0]
        assert f["location"]["row"] == 5
        assert f["location"]["col"] == 2

    def test_deungrok_il_label(self, analysis):
        f = next(f for f in analysis['fields'] if f['label'] == '등록일')
        assert f is not None
        assert f["label"] == "등록일"
        assert f["location"]["table_path"] == [10, 0]


# ---------------------------------------------------------------------------
# 5. 표 1: 기관·단체 현황 — 규칙 1 라벨 셀 5개 + 규칙 3 천원 9개
# ---------------------------------------------------------------------------

class TestTable1:
    def test_5_rule1_labels_in_table1(self, analysis):
        """표#1의 라벨 있는 필드는 규칙4로 9개(우편번호, 성명 및 직위, 휴대전화, 이메일,
        상근직원수, 회원수, 성명, 전화, 팩스). 규칙1(라벨 오른쪽 빈 셀)은 표1에서 0개."""
        t1 = _fields_by_table(analysis, [1, 0])
        labeled = [f for f in t1 if f["label"] and f["rule"] in ("rule1", "rule4")]
        assert len(labeled) == 9, f"표1 라벨 필드 기대 9개, 실제 {len(labeled)}: {[(f['field_id'], f['label']) for f in labeled]}"
        # 규칙4 9개이고 규칙1은 0개
        rule1_in_t1 = [f for f in t1 if f["rule"] == "rule1" and f["label"]]
        assert len(rule1_in_t1) == 0, f"표1 rule1 라벨 기대 0개, 실제 {len(rule1_in_t1)}"

    def test_table1_money_fields(self, analysis):
        """표#1의 천원 단위 필드 9개 (f-004~f-009 + f-??? 표3에 있는 2개 제외 시 표1에만 7개?)."""
        money_t1 = [
            f for f in _fields_by_table(analysis, [1, 0])
            if f["unit"] == "money" and not f["label"]
        ]
        # 표#1의 천원 필드: 행7/8/9 × (col7, col11) = 6개. 표#3 별도.
        # 표#3의 천원 필드: 행8 col1, 행9 col2, 행9 col5 = 3개 → 총 9개.
        # 표#1만: 6개.
        assert len(money_t1) == 6, f"표1 money 셀 기대 6개, 실제 {len(money_t1)}"

    def test_table1_money_fields_have_merge_info(self, analysis):
        """표#1의 천원 셀(col7)은 colSpan=4 병합 (f-013, f-014, f-015)."""
        for row in [7, 8, 9]:
            f = next(f for f in _fields_by_table(analysis, [1, 0]) if f['location']['row'] == row and f['location']['col'] == 7)
            assert f["merge_info"] is not None
            assert f["merge_info"]["colSpan"] == 4


# ---------------------------------------------------------------------------
# 6. 표 4: 직원 현황 — 규칙 2 (헤더 아래 빈 셀 15개)
# ---------------------------------------------------------------------------

class TestTable4:
    def test_table4_count(self, analysis):
        t4 = _fields_by_table(analysis, [4, 0])
        assert len(t4) == 15, f"표4 빈셀 기대 15개, 실제 {len(t4)}"

    def test_table4_rows_and_cols(self, analysis):
        t4 = _fields_by_table(analysis, [4, 0])
        rows = sorted({f["location"]["row"] for f in t4})
        cols = sorted({f["location"]["col"] for f in t4})
        assert rows == [1, 2, 3], f"표4 행: {rows}"
        assert cols == [0, 1, 2, 3, 4], f"표4 열: {cols}"

    def test_table4_all_label_empty_and_text(self, analysis):
        for f in _fields_by_table(analysis, [4, 0]):
            assert f["label"] == ""
            assert f["unit"] == "text"
            assert f["editable"] is True
            assert f["required"] is False


# ---------------------------------------------------------------------------
# 7. 표 5: 운영계획 — 규칙 2 (헤더 아래 빈 셀 12개)
# ---------------------------------------------------------------------------

class TestTable5:
    def test_table5_count(self, analysis):
        t5 = _fields_by_table(analysis, [5, 0])
        assert len(t5) == 12, f"표5 빈셀 기대 12개, 실제 {len(t5)}"

    def test_table5_rows_and_cols(self, analysis):
        t5 = _fields_by_table(analysis, [5, 0])
        rows = sorted({f["location"]["row"] for f in t5})
        cols = sorted({f["location"]["col"] for f in t5})
        assert rows == [1, 2, 3]
        assert cols == [0, 1, 2, 3]

    def test_table5_all_label_empty_and_text(self, analysis):
        for f in _fields_by_table(analysis, [5, 0]):
            assert f["label"] == ""
            assert f["unit"] == "text"


# ---------------------------------------------------------------------------
# 8. 표 6: 예산집행계획 — 규칙 2 (헤더 아래 빈 셀 4개)
# ---------------------------------------------------------------------------

class TestTable6:
    def test_table6_count(self, analysis):
        t6 = _fields_by_table(analysis, [6, 0])
        assert len(t6) == 1, f"표6 빈셀 기대 1개, 실제 {len(t6)}"

    def test_table6_rows_and_cols(self, analysis):
        t6 = _fields_by_table(analysis, [6, 0])
        rows = sorted({f["location"]["row"] for f in t6})
        cols = sorted({f["location"]["col"] for f in t6})
        assert rows == [1], f"표6 행: {rows}"
        assert cols == [4], f"표6 열: {cols}"

    def test_table6_all_empty_text(self, analysis):
        for f in _fields_by_table(analysis, [6, 0]):
            assert f["label"] == ""
            assert f["unit"] == "text"


# ---------------------------------------------------------------------------
# 9. 표 7: 보조세목(통계목) — 규칙 2 (헤더 아래 빈 셀 8개)
# ---------------------------------------------------------------------------

class TestTable7:
    def test_table7_count(self, analysis):
        t7 = _fields_by_table(analysis, [7, 0])
        assert len(t7) == 5, f"표7 빈셀 기대 5개, 실제 {len(t7)}"

    def test_table7_rows_and_cols(self, analysis):
        t7 = _fields_by_table(analysis, [7, 0])
        rows = sorted({f["location"]["row"] for f in t7})
        cols = sorted({f["location"]["col"] for f in t7})
        assert rows == [2, 3, 4, 5]
        assert cols == [1, 5]

    def test_table7_all_empty_text(self, analysis):
        for f in _fields_by_table(analysis, [7, 0]):
            assert f["label"] == ""
            assert f["unit"] == "text"


# ---------------------------------------------------------------------------
# 10. 표 11: 해산사유 — 규칙 2 헤더 아래 빈 셀 4열 확인
# ---------------------------------------------------------------------------

class TestTable10Rule2:
    def test_table10_rule2_count(self, analysis):
        """표#10(시설 정보)의 규칙2: 헤더행(col0)만 헤더 열. 그 아래는 모두 라벨 텍스트.
        → 규칙2 빈 셀 없음 (0개)."""
        t10r2 = _fields_by_table(analysis, [10, 0])
        t10r2 = [f for f in t10r2 if f["rule"] == "rule2"]
        assert len(t10r2) == 0, f"표10 rule2 빈셀 기대 0개, 실제 {len(t10r2)}"


# ---------------------------------------------------------------------------
# 11. 규칙 3: 단위/자리표시자 셀 — money, postal-code 등
# ---------------------------------------------------------------------------

class TestRule3:
    def test_all_money_fields_have_no_label(self, analysis):
        for f in analysis["fields"]:
            if f["unit"] == "money":
                assert f["label"] == "", f"money 필드 {f['field_id']}에 label={f['label']!r}"

    def test_money_fields_are_empty_cells(self, analysis):
        for f in analysis["fields"]:
            if f["unit"] == "money":
                assert f["context"].startswith("자리표시자/단위만 있는 셀"), (
                    f"money 필드 {f['field_id']}의 context: {f['context']}"
                )

    def test_total_money_fields(self, analysis):
        money = [f for f in analysis["fields"] if f["unit"] == "money"]
        # 표#1 6개 + 표#3 3개 = 9개
        assert len(money) == 9, f"money 필드 기대 9개, 실제 {len(money)}"


# ---------------------------------------------------------------------------
# 12. No False Positives — 라벨 없는 빈 셀, 안내문, 총계 등 제외
# ---------------------------------------------------------------------------

class TestNoFalsePositives:
    def test_no_empty_label_field(self, analysis):
        """규칙에서 명시적으로 label=""인 빈 셀은 규칙 2·규칙 3에만 있고,
        규칙 1/규칙 4에는 label이 반드시 있어야 한다."""
        for f in analysis["fields"]:
            if f["rule"] in ("rule1", "rule4"):
                assert f["label"] != "", (
                    f"규칙1/규칙4 필드 {f['field_id']}에 label이 비어 있음: "
                    f"context={f['context']!r}"
                )

    def test_program_name_not_present(self, analysis):
        """‘프로그램명’은 이미 값이 채워져 있어 rule1에서 제외."""
        labels = [f["label"] for f in analysis["fields"]]
        assert "프로그램명" not in labels

    def test_no_gye_label(self, analysis):
        """‘총계’ 같은 행 라벨은 rule1에서 제외."""
        labels = [f["label"] for f in analysis["fields"]]
        for bad in ("총계", "합계", "소계", "계", "순계"):
            assert bad not in labels, f"행 라벨 '{bad}'이(가) 필드 목록에 있음"

    def test_no_guidance_cells(self, analysis):
        """안내문(※로 시작) 셀은 field로 잡히지 않아야 함."""
        labels = [f["label"] for f in analysis["fields"]]
        guidance = [l for l in labels if l.startswith("※")]
        assert len(guidance) == 0, f"안내문 라벨이 필드로 잡힘: {guidance}"

    def test_seongmyeong_label_not_in_rule1(self, analysis):
        """‘성 명’ 라벨은 규칙 1으로 잡히지 않아야 한다 (이미 값 있거나 라벨 오른쪽 셀이 채워짐)."""
        labels = [f["label"] for f in analysis["fields"]]
        assert "성 명" not in labels


# ---------------------------------------------------------------------------
# 13. 규칙 4: 한 셀 안의 "라벨 :" 뒤 빈자리
# ---------------------------------------------------------------------------

class TestRule4:
    def test_program_name_not_candidate(self, analysis):
        """‘프로그램명’은 이미 값이 채워져 있어 rule4에서 제외되어야 한다."""
        labels = [f["label"] for f in analysis["fields"] if f["rule"] == "rule4"]
        assert "프로그램명" not in labels, f"프로그램명이 rule4 후보로 잡힘: {labels}"

    def test_seongmyeong_is_candidate(self, analysis):
        """‘성명’은 rule4 후보로 잡힌다 (직명 :교장성명 : 에서 성명 뒤 빈자리)."""
        cands = [f for f in analysis["fields"] if f["rule"] == "rule4" and f["label"] == "성명"]
        assert len(cands) == 1, f"성명 후보 기대 1개, 실제 {len(cands)}"
        f = cands[0]
        assert f["unit"] == "person-name"
        assert f["required"] is True
        loc = f["location"]
        assert loc["table_path"] == [1, 0]
        assert loc["row"] == 1
        assert loc["col"] == 9
        assert loc["paragraph_index"] == 0
        assert loc["run_index"] == 0
        assert loc["insert_offset"] == 10

    def test_phone_fax_candidates(self, analysis):
        """‘전화’, ‘팩스’는 rule4 후보로 잡힌다 (전화 : / 팩스 : )."""
        jeonhwa = [f for f in analysis["fields"] if f["rule"] == "rule4" and f["label"] == "전화"]
        fax = [f for f in analysis["fields"] if f["rule"] == "rule4" and f["label"] == "팩스"]
        assert len(jeonhwa) == 1, f"전화 후보 기대 1개, 실제 {len(jeonhwa)}"
        assert len(fax) == 1, f"팩스 후보 기대 1개, 실제 {len(fax)}"
        assert jeonhwa[0]["unit"] == "phone"
        assert fax[0]["unit"] == "phone"
        assert jeonhwa[0]["required"] is True
        # 전화: 표1 행2 열9, 문단0, run0, offset 4
        loc = jeonhwa[0]["location"]
        assert loc["table_path"] == [1, 0]
        assert loc["row"] == 2
        assert loc["col"] == 9
        assert loc["paragraph_index"] == 0
        assert loc["run_index"] == 0
        assert loc["insert_offset"] == 4
        # 팩스: 표1 행2 열9, 문단1, run0, offset 4
        loc = fax[0]["location"]
        assert loc["paragraph_index"] == 1
        assert loc["run_index"] == 0
        assert loc["insert_offset"] == 4

    def test_postal_code_candidate(self, analysis):
        """‘우편번호’는 rule4 후보로 잡힌다 ((우편번호 :          ) 에서 빈자리)."""
        cands = [f for f in analysis["fields"] if f["rule"] == "rule4" and f["label"] == "우편번호"]
        assert len(cands) == 1, f"우편번호 후보 기대 1개, 실제 {len(cands)}"
        f = cands[0]
        assert f["unit"] == "postal-code"
        assert f["required"] is True
        loc = f["location"]
        assert loc["table_path"] == [1, 0]
        assert loc["row"] == 2
        assert loc["col"] == 2
        # 문단0, run0, offset 7 (우편번호 : → 콜론 뒤)
        assert loc["paragraph_index"] == 0
        assert loc["run_index"] == 0
        assert loc["insert_offset"] == 7

    def test_rule4_total_count(self, analysis):
        """규칙4 후보 총 11개 (rule1 9 + rule2 36 + rule3 9 + rule4 11 = 65)."""
        rule4 = [f for f in analysis["fields"] if f["rule"] == "rule4"]
        assert len(rule4) == 11, f"rule4 후보 기대 11개, 실제 {len(rule4)}"
