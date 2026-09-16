"""hwpx 엔진 — 패키지/패키지 읽기 경계.

이 패키지는 서버 내부에서만 사용하는 문서 처리 계층이다.
외부 API 계약은 별도 계층이 정의한다.
"""

from hwpx.errors import DomainError
from hwpx.package import read_hwpx, ReadResult

__all__ = ["DomainError", "read_hwpx", "ReadResult"]
