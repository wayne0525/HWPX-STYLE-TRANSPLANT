"""
tests/test_analyze_prototype.py — A.hwpx 입력란 후보 분석 프로토타입 검증.

모듈 로딩 시점에 분석을 실행하지 않고, 테스트 함수 안에서
read_hwpx → read_xml → analyze_a(a_bytes=, a_sha256=)를 호출한다.
반환은 AAnalysis 객체이며, 현재 공통 계약(dict 기반 fields)을 그대로 확인한다.
"""
import hashlib
import logging

import pytest

from hwpx.package import read_hwpx
from hwpx.xml import read_xml
from hwpx.analyze import analyze_a

LOG = logging.getLogger(__name__)

A_PATH = "tests/fixtures/A.hwpx"


def _raw_and_sha(path):
    raw = open(path, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    return raw, sha


def _analyze(path):
    raw, sha = _raw_and_sha(path)
    pkg = read_hwpx(raw)
    xml = read_xml(pkg)
    result = analyze_a(xml, a_bytes=raw, a_sha256=sha)
    return raw, sha, pkg, xml, result


class TestPrototypeAnalysis:
    def test_returns_aanalysis(self):
        _, _, _, _, result = _analyze(A_PATH)
        assert result is not None
        assert getattr(result, "analysis_id", None) is not None
        assert getattr(result, "a_hash", None) is not None
        assert getattr(result, "file_kind", None) == "hwpx"
        assert getattr(result, "analysis_status", None) in {"ok", "partial", "failed"}

    def test_a_hash_is_real_sha256(self):
        raw, sha, _, _, result = _analyze(A_PATH)
        assert result.a_hash == sha
        assert not sha.startswith("sha256:")
        hex_part = sha
        assert len(hex_part) == 64
        int(hex_part, 16)

    def test_raw_bytes_hashed_not_path(self):
        raw, sha, _, _, result = _analyze(A_PATH)
        fromhwpx = hashlib.sha256(raw).hexdigest()
        assert result.a_hash == fromhwpx

    def test_fields_are_field_id_mapping(self):
        _, _, _, _, result = _analyze(A_PATH)
        assert len(result.fields) > 0
        by_id = {f["fieldId"]: f for f in result.fields}
        assert len(by_id) == len(result.fields)
        for f in result.fields:
            assert isinstance(f["fieldId"], str)
            assert f["fieldId"].startswith("f-")

    def test_fields_carry_required_contract_keys(self):
        _, _, _, _, result = _analyze(A_PATH)
        required = {
            "fieldId", "candidateId", "label", "originalText", "context",
            "unit", "editable", "required", "status", "location",
        }
        for f in result.fields:
            missing = required - set(f.keys())
            assert not missing, f"필드 {f['fieldId']}에 누락된 키: {sorted(missing)}"

    def test_status_is_not_failed(self):
        _, _, _, _, result = _analyze(A_PATH)
        assert result.analysis_status != "failed", result.warnings

    def test_warnings_is_list(self):
        _, _, _, _, result = _analyze(A_PATH)
        assert isinstance(result.warnings, list)

    def test_normalized_index_is_none_on_native_path(self):
        _, _, _, _, result = _analyze(A_PATH)
        assert result.normalizedIndex is None
