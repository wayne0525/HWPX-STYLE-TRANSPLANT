"""공통 오류 계층 — hwpx 엔진 내부에서 쓰는 DomainError.

이번 E01 번호는 ZIP 안전 읽기 전용이므로, 패키지/파일 읽기에서 드러나는
문제 종류만 먼저 정의한다. 나중에 다른 모듈도 이 경계를 공유한다.

설계 원칙
- DomainError는 code, message, details를 가진다.
- 디스크에 압축을 푸는 작업이 아니라, 원본 bytes와 ZIP 항목 순서와 각
  항목 내용·메타데이터를 보존하며 안전하게 읽기만 하는 도중에 드러난
  문제만 DomainError로 올린다.
- 최상위 호출자는 이 예외만 잡으면 되고, 내부 구현 상세까지 밖으로
  새어 나가지 않게 한다.
"""

from __future__ import annotations


class DomainError(Exception):
    """hwpx 패키지 처리에서 드러나는 계약적 오류.

    Attributes
    - code: 문제 종류를 구분하는 기계 판독용 문자열
    - message: 사람이 읽을 수 있는 설명
    - details: 문제 판단에 필요한 추가 정보(항상 dict, 없으면 빈 dict)
    """

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details if details is not None else {}

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.details:
            return f"{base} | details={self.details}"
        return base


# ---------------------------------------------------------------------------
# ZIP 안전 읽기에서 쓰는 코드 체계
# ---------------------------------------------------------------------------
# 코드 명명 규칙: 소문자-하이픈, 계층은 콜론으로 구분하지 않는다.
# 이번 번호는 아직 analyze/source까지 안 가므로, 패키지 읽기 관련만 둔다.

INVALID_HWPX = "invalid-hwpx"
"""최상위: HWPX로 읽을 수 없는 입력"""

NO_MIMETYPE = "no-mimetype"
"""mimetype 항목이 없거나 첫 항목이 아니거나 bytes가 아님"""

BAD_MIMETYPE = "bad-mimetype"
"""mimetype 값이 HWPX 표준이 아님"""

MULTIPLE_MIMETYPE = "multiple-mimetype"
"""mimetype 항목이 둘 이상"""

NEEDED_XML_MISSING = "needed-xml-missing"
"""필수 XML(section0.xml 등)을 찾을 수 없음"""

# XML 읽기 관련 코드(아래는 hwpx/xml.py에서 사용하는 상수와 함께 쓴다).
# 이 errors 모듈은 아직 패키지/XML 공통 경계로 쓰이며, 이번 번호에서
# 외부 엔티티/DTD/네임스페이스 오취급 관련 코드를 덧붙인다.

UNSAFE_XML = "unsafe-xml"
"""DTD, 외부 엔티티, 허용되지 않는 XML 구문"""

BAD_XML = "bad-xml"
"""XML 구문 자체는 유효하나 이 엔진이 원하는 구조를 읽지 못함"""

NS_MIXED = "ns-mixed"
"""내부 namespace와 외부 namespace의 동일 이름 요소를 섞음"""

SECTION_ORDER_BAD = "section-order-bad"
"""content.hpf 기준 section 순서가 기대와 다름"""

TABLE_COORD_BAD = "table-coord-bad"
"""표 격자/병합/셀 좌표 구성에서 허용하지 않는 상태"""

DUPLICATE_PATH = "duplicate-path"
"""ZIP 내 동일 경로가 둘 이상"""

PATH_ESCAPE = "path-escape"
"""경로가 저장소 루트 밖으로 나가거나 상위 참조 포함"""

ENCRYPTED = "encrypted"
"""암호화된 항목 존재"""

CRC_ERROR = "crc-error"
"""CRC-32 불일치"""

DECOMPRESS_SIZE_EXCEEDED = "decompress-size-exceeded"
"""실제 누적 해제 크기가 제한을 초과"""

ENTRY_COUNT_EXCEEDED = "entry-count-exceeded"
"""ZIP 항목 수가 제한을 초과"""

UNSUPPORTED_COMPRESSION = "unsupported-compression"
"""허용하지 않는 압축 방식"""

BAD_ITEM = "bad-item"
"""ZIP 항목 자체 판독 불가(손상 등)"""
