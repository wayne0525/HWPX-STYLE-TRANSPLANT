"""
tests/test_fill.py — fill_a 동작 검증.

계약에는 rule1, rule2, rule4만 채우고 rule3은 거부한다고 명시되어 있다.
"""
import os
import shutil
import zipfile
from lxml import etree

import pytest

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
A_PATH = os.path.join(PROJECT, "tests", "fixtures", "A.hwpx")
OUTPUT_DIR = os.path.join(HERE, "output")

NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _clean_output():
    if os.path.isdir(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _field_by_label(analysis, label):
    """라벨로 필드를 찾는다. 같은 라벨이 여러 개면 첫 번째를 반환."""
    for f in analysis["fields"]:
        if f["label"] == label:
            return f
    return None


def _field_ids_by_label(analysis, label):
    """라벨로 필드 ID 목록을 찾는다 (같은 라벨이 여러 개일 수 있음)."""
    return [f["field_id"] for f in analysis["fields"] if f["label"] == label]


def _read_section(root, sec_path="Contents/section0.xml"):
    """ZIP에서 섹션 XML을 파싱한 루트를 반환."""
    # root는 이미 파싱된 상태라고 가정하지 않고, 실제 파일에서 읽는다.
    # 이 헬퍼는 파일 경로를 받는 함수를 위해 쓴다.
    raise NotImplementedError("이 헬퍼는 직접 쓰지 않음 — pytest fixture 이용")


def _cell_text_after_fill(c_path, table_idx, row, col):
    """C 파일에서 특정 셀의 모든 hp:t 텍스트를 반환."""
    with zipfile.ZipFile(c_path) as zf:
        xml = zf.read("Contents/section0.xml")
    root = etree.fromstring(xml)
    tables = root.findall(".//hp:tbl", NS)
    tbl = tables[table_idx]
    for tc in tbl.findall(".//hp:tc", NS):
        addr = tc.find("hp:cellAddr", NS)
        c = int(addr.get("colAddr", 0)) if addr is not None else 0
        r = int(addr.get("rowAddr", 0)) if addr is not None else 0
        if r == row and c == col:
            return "".join((t.text or "") for t in tc.findall(".//hp:t", NS))
    return None


def _cell_text_rule4(c_path, table_idx, row, col, paragraph_index, run_index, insert_offset):
    """C 파일에서 rule4 셀의 특정 run 텍스트를 반환."""
    with zipfile.ZipFile(c_path) as zf:
        xml = zf.read("Contents/section0.xml")
    root = etree.fromstring(xml)
    tables = root.findall(".//hp:tbl", NS)
    tbl = tables[table_idx]
    for tc in tbl.findall(".//hp:tc", NS):
        addr = tc.find("hp:cellAddr", NS)
        c = int(addr.get("colAddr", 0)) if addr is not None else 0
        r = int(addr.get("rowAddr", 0)) if addr is not None else 0
        if r == row and c == col:
            sub = tc.find("hp:subList", NS)
            if sub is None:
                return None
            paragraphs = sub.findall("hp:p", NS)
            if paragraph_index >= len(paragraphs):
                return None
            p = paragraphs[paragraph_index]
            runs = p.findall("hp:run", NS)
            if run_index >= len(runs):
                return None
            t = runs[run_index].find("hp:t", NS)
            if t is None or t.text is None:
                return None
            return t.text
    return None


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def analysis():
    from hwpx.analyze import analyze_a
    return analyze_a(A_PATH)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    _clean_output()
    yield
    # teardown에서는 output을 삭제하지 않는다 — 같은 모듈의 테스트들이
    # C_sample.hwpx 등을 공유해야 하므로.


# ---------------------------------------------------------------------------
# tests/output/.gitignore 등록 확인
# ---------------------------------------------------------------------------

class TestOutputDirIgnored:
    def test_output_dir_in_gitignore(self):
        gitignore_path = os.path.join(PROJECT, ".gitignore")
        with open(gitignore_path) as f:
            content = f.read()
        assert "tests/output/" in content, (
            ".gitignore에 tests/output/이 등록되어 있어야 한다. "
            "출력 결과물은 커밋하지 않는다."
        )


# ---------------------------------------------------------------------------
# 1. A 해시 불일치 → 전체 거부
# ---------------------------------------------------------------------------

class TestHashMismatch:
    def test_wrong_hash_rejected(self, analysis):
        from hwpx.fill import fill_a
        fills = [{"field_id": "f-007", "value": "김하늘"}]
        out = os.path.join(OUTPUT_DIR, "C_hash_fail.hwpz")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is not None
        assert result["failure"]["reason"] == "A 해시 불일치"
        assert result["applied"] == []
        assert result["c_hash"] == ""


# ---------------------------------------------------------------------------
# 2. 없는 field_id → 거부
# ---------------------------------------------------------------------------

class TestUnknownFieldId:
    def test_unknown_field_id_rejected(self, analysis):
        from hwpx.fill import fill_a
        fills = [{"field_id": "f-9999", "value": "아무값"}]
        out = os.path.join(OUTPUT_DIR, "C_unknown.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        assert len(result["applied"]) == 0
        rejected = result["rejected"]
        assert len(rejected) == 1
        assert rejected[0]["field_id"] == "f-9999"
        assert rejected[0]["reason"] == "analysis에 없는 field_id"


# ---------------------------------------------------------------------------
# 3. rule3 → 거부 (단위 보존 규칙 미정)
# ---------------------------------------------------------------------------

class TestRule3Rejected:
    def test_rule3_rejected(self, analysis):
        from hwpx.fill import fill_a
        # f-013 ~ f-018은 rule3 (천원)
        fills = [{"field_id": "f-013", "value": "99999"}]
        out = os.path.join(OUTPUT_DIR, "C_rule3.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        assert len(result["applied"]) == 0
        rejected = result["rejected"]
        assert len(rejected) == 1
        assert rejected[0]["field_id"] == "f-013"
        assert rejected[0]["reason"] == "rule3은 단위 보존 규칙 미정 — 이번 단계 범위 밖"


# ---------------------------------------------------------------------------
# 4. rule1 필드 채우기
# ---------------------------------------------------------------------------

class TestRule1Fill:
    def test_danche_fill(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "단 체 명")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "늘배움 평생학교"}]
        out = os.path.join(OUTPUT_DIR, "C_rule1_danche.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids, f"f-019가 applied에 없음: {applied_ids}"
        # 셀 텍스트 확인
        txt = _cell_text_after_fill(out, 3, 0, 1)
        assert txt == "늘배움 평생학교", f"표3 [0,1] 텍스트: {txt!r}"

    def test_siseol_fill(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "시 설 명")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "늘배움 평생학교"}]
        out = os.path.join(OUTPUT_DIR, "C_rule1_siseol.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids
        txt = _cell_text_after_fill(out, 10, 0, 1)
        assert txt == "늘배움 평생학교", f"표10 [0,1] 텍스트: {txt!r}"


# ---------------------------------------------------------------------------
# 5. rule4 필드 채우기 — 개별 값 확인 (라벨 기반)
# ---------------------------------------------------------------------------

class TestRule4Fill:
    def test_seongmyeong_fill(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "성명")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "김하늘"}]
        out = os.path.join(OUTPUT_DIR, "C_rule4_seong.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids
        # 표1 [1,9], para0, run0, offset=10
        loc = f["location"]
        text = _cell_text_rule4(
            out,
            loc["table_path"][0], loc["row"], loc["col"],
            loc["paragraph_index"], loc["run_index"], loc["insert_offset"],
        )
        assert text is not None
        assert "김하늘" in text, f"성명 텍스트에 김하늘이 없음: {text!r}"

    def test_jeonhwa_fill(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "전화")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "02-0000-1000"}]
        out = os.path.join(OUTPUT_DIR, "C_rule4_jeonhwa.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids
        loc = f["location"]
        text = _cell_text_rule4(
            out,
            loc["table_path"][0], loc["row"], loc["col"],
            loc["paragraph_index"], loc["run_index"], loc["insert_offset"],
        )
        assert text is not None
        assert "02-0000-1000" in text, f"전화 텍스트: {text!r}"

    def test_fax_fill(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "팩스")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "02-0000-1001"}]
        out = os.path.join(OUTPUT_DIR, "C_rule4_fax.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids
        loc = f["location"]
        text = _cell_text_rule4(
            out,
            loc["table_path"][0], loc["row"], loc["col"],
            loc["paragraph_index"], loc["run_index"], loc["insert_offset"],
        )
        assert text is not None
        assert "02-0000-1001" in text, f"팩스 텍스트: {text!r}"

    def test_postal_code_fill(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "우편번호")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "03000"}]
        out = os.path.join(OUTPUT_DIR, "C_rule4_postal.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids
        loc = f["location"]
        text = _cell_text_rule4(
            out,
            loc["table_path"][0], loc["row"], loc["col"],
            loc["paragraph_index"], loc["run_index"], loc["insert_offset"],
        )
        assert text is not None
        assert "03000" in text, f"우편번호 텍스트: {text!r}"

    def test_email_fill(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "이메일")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "test@example.com"}]
        out = os.path.join(OUTPUT_DIR, "C_rule4_email.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids
        loc = f["location"]
        text = _cell_text_rule4(
            out,
            loc["table_path"][0], loc["row"], loc["col"],
            loc["paragraph_index"], loc["run_index"], loc["insert_offset"],
        )
        assert text is not None
        assert "test@example.com" in text, f"이메일 텍스트: {text!r}"


# ---------------------------------------------------------------------------
# 6. 같은 run 다중 삽입 — offset 역순
# ---------------------------------------------------------------------------

class TestSameRunMultiInsert:
    def test_same_run_reverse_order(self, analysis):
        """표1 [4,2]에는 상근직원수(off=8)와 회원수(off=20)가 같은 run에 있다.
        offset 역순(회원수 먼저, 상근직원수 나중)으로 적용해야 밀림이 없다."""
        from hwpx.fill import fill_a
        f_sang = _field_by_label(analysis, "상근직원수")
        f_hoe = _field_by_label(analysis, "회원수")
        assert f_sang is not None and f_hoe is not None
        assert f_sang["location"]["run_index"] == f_hoe["location"]["run_index"], (
            "두 필드가 같은 run에 있어야 테스트 의미가 있음"
        )
        assert f_sang["location"]["table_path"] == f_hoe["location"]["table_path"]
        assert f_sang["location"]["row"] == f_hoe["location"]["row"]
        assert f_sang["location"]["col"] == f_hoe["location"]["col"]

        fills = [
            {"field_id": f_sang["field_id"], "value": "5"},
            {"field_id": f_hoe["field_id"], "value": "100"},
        ]
        out = os.path.join(OUTPUT_DIR, "C_same_run.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f_sang["field_id"] in applied_ids
        assert f_hoe["field_id"] in applied_ids

        loc_s = f_sang["location"]
        loc_h = f_hoe["location"]
        table_idx = loc_s["table_path"][0]
        row = loc_s["row"]
        col = loc_s["col"]
        para = loc_s["paragraph_index"]
        run = loc_s["run_index"]
        text = _cell_text_rule4(out, table_idx, row, col, para, run, loc_s["insert_offset"])
        assert text is not None, "상근직원수 위치의 run 텍스트를 못 읽음"
        # 기대: 상근직원수 :5       회원수 :100
        # offset=8에 '5' 삽입, offset=20에 '100' 삽입 (역순 적용 → 밀림 없음)
        # 실제 텍스트에서 확인
        assert "상근직원수" in text
        assert "5" in text
        assert "회원수" in text
        assert "100" in text


# ---------------------------------------------------------------------------
# 7. XML 특수문자 — & < > 가 깨지지 않는지
# ---------------------------------------------------------------------------

class TestXmlSpecialChars:
    def test_ampersand(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "성명")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "A & B < C > D"}]
        out = os.path.join(OUTPUT_DIR, "C_special.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids

        loc = f["location"]
        text = _cell_text_rule4(
            out,
            loc["table_path"][0], loc["row"], loc["col"],
            loc["paragraph_index"], loc["run_index"], loc["insert_offset"],
        )
        assert text is not None
        # XML 엔티티가 아닌 실제 문자로 저장되어야 함
        assert "&" in text, f"&가 없음: {text!r}"
        assert "<" in text, f"<가 없음: {text!r}"
        assert ">" in text, f">가 없음: {text!r}"

        # 또한 C가 유효한 XML로 파싱되어야 함
        with zipfile.ZipFile(out) as zf:
            xml = zf.read("Contents/section0.xml")
        etree.fromstring(xml)  # 파싱 실패하면 여기서 예외

    def test_angle_brackets_in_value(self, analysis):
        from hwpx.fill import fill_a
        f = _field_by_label(analysis, "우편번호")
        assert f is not None
        fills = [{"field_id": f["field_id"], "value": "<>&test"}]
        out = os.path.join(OUTPUT_DIR, "C_angle.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None
        applied_ids = [a["field_id"] for a in result["applied"]]
        assert f["field_id"] in applied_ids

        loc = f["location"]
        text = _cell_text_rule4(
            out,
            loc["table_path"][0], loc["row"], loc["col"],
            loc["paragraph_index"], loc["run_index"], loc["insert_offset"],
        )
        assert text is not None
        assert "<>&test" in text, f"특수문자 값 텍스트: {text!r}"

        # XML 파싱 검증
        with zipfile.ZipFile(out) as zf:
            xml = zf.read("Contents/section0.xml")
        etree.fromstring(xml)


# ---------------------------------------------------------------------------
# 8. 수정 안 한 엔트리 바이트 동일
# ---------------------------------------------------------------------------

class TestUnchangedEntries:
    def test_non_modified_entries_match(self, analysis):
        """수정된 섹션 외의 모든 ZIP 엔트리가 A와 바이트 단위로 동일해야 한다."""
        from hwpx.fill import fill_a
        fills = [{"field_id": _field_by_label(analysis, "단 체 명")["field_id"], "value": "늘배움 평생학교"}]
        out = os.path.join(OUTPUT_DIR, "C_preserve.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None

        with zipfile.ZipFile(A_PATH) as zfA:
            a_entries = {info.filename: zfA.read(info.filename) for info in zfA.infolist()}

        with zipfile.ZipFile(out) as zfC:
            c_entries = {info.filename: zfC.read(info.filename) for info in zfC.infolist()}

        for name, a_bytes in a_entries.items():
            c_bytes = c_entries.get(name)
            assert c_bytes is not None, f"C에 {name} 엔트리가 없음"
            if name == "Contents/section0.xml":
                # section0.xml은 수정되었으므로 바이트가 다를 수 있음 (허용)
                continue
            assert a_bytes == c_bytes, f"엔트리 {name}이 A와 다름 (수정하면 안 되는 엔트리)"


# ---------------------------------------------------------------------------
# 9. C_sample.hwpx 생성 검증 (실제 산출물)
# ---------------------------------------------------------------------------

class TestCSampleGeneration:
    """과제 A 최종 산출물: tests/output/C_sample.hwpx"""
    EXPECTED_FILLS = [
        ("단 체 명", "늘배움 평생학교"),
        ("시 설 명", "늘배움 평생학교"),
        ("성 명", "김하늘"),
        ("전 화", "02-0000-1000"),
        ("팩 스", "02-0000-1001"),
        ("우편번호", "03000"),
        ("이메일", "test@example.com"),
    ]

    def test_c_sample_exists(self, analysis):
        from hwpx.fill import fill_a
        fills = []
        for label, value in self.EXPECTED_FILLS:
            f = _field_by_label(analysis, label)
            assert f is not None, f"라벨 '{label}'에 해당하는 필드가 분석 결과에 없음"
            fills.append({"field_id": f["field_id"], "value": value})

        out = os.path.join(OUTPUT_DIR, "C_sample.hwpx")
        result = fill_a(A_PATH, analysis, fills, out)
        assert result["failure"] is None, f"fill_a 실패: {result['failure']}"
        assert os.path.exists(out), "C_sample.hwpx가 생성되지 않음"
        assert os.path.getsize(out) > 0, "C_sample.hwpx가 비어 있음"

    def test_c_sample_applied_values(self, analysis):
        from hwpx.fill import fill_a
        fills = []
        for label, value in self.EXPECTED_FILLS:
            f = _field_by_label(analysis, label)
            fills.append({"field_id": f["field_id"], "value": value})

        out = os.path.join(OUTPUT_DIR, "C_sample.hwpx")
        if not os.path.exists(out):
            fill_a(A_PATH, analysis, fills, out)

        # applied 확인
        # (이미 생성된 파일을 다시 읽어서 검증할 수도 있지만, fill_a 결과를 바로 검증)
        result = fill_a(A_PATH, analysis, fills, out)
        applied_labels = {
            _field_by_label(analysis, a["field_id"])["label"]
            for a in result["applied"]
        }
        expected_labels = {label for label, _ in self.EXPECTED_FILLS}
        assert applied_labels == expected_labels, (
            f"applied 라벨: {applied_labels}, 기대: {expected_labels}"
        )

    def test_c_sample_mimetype_ok(self):
        """C_sample.hwpx의 mimetype이 첫 엔트리 + 무압축인지 확인."""
        out = os.path.join(OUTPUT_DIR, "C_sample.hwpx")
        assert os.path.exists(out)
        with zipfile.ZipFile(out) as zf:
            infolist = zf.infolist()
            assert len(infolist) > 0
            first = infolist[0]
            assert first.filename == "mimetype", f"첫 엔트리가 mimetype이 아님: {first.filename}"
            assert first.compress_type == zipfile.ZIP_STORED, "mimetype이 무압축이 아님"

    def test_c_sample_section_xml_parsable(self):
        """C_sample.hwpx의 section0.xml이 유효한 XML로 파싱되는지 확인."""
        out = os.path.join(OUTPUT_DIR, "C_sample.hwpx")
        assert os.path.exists(out)
        with zipfile.ZipFile(out) as zf:
            xml = zf.read("Contents/section0.xml")
        etree.fromstring(xml)  # 파싱 실패 시 예외

    def test_c_sample_unchanged_entries(self):
        """C_sample.hwpx에서 수정되지 않은 엔트리가 A와 동일한지 확인."""
        out = os.path.join(OUTPUT_DIR, "C_sample.hwpx")
        assert os.path.exists(out)
        with zipfile.ZipFile(A_PATH) as zfA:
            a_entries = {info.filename: zfA.read(info.filename) for info in zfA.infolist()}
        with zipfile.ZipFile(out) as zfC:
            c_entries = {info.filename: zfC.read(info.filename) for info in zfC.infolist()}
        for name, a_bytes in a_entries.items():
            c_bytes = c_entries.get(name)
            assert c_bytes is not None, f"C에 {name} 없음"
            if name == "Contents/section0.xml":
                continue  # 수정된 섹션
            assert a_bytes == c_bytes, f"엔트리 {name}이 A와 다름"
