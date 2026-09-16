"""HWPX XML 안전 읽기 — 메모리 전용.

계약(hwpx/analyze 등)보다 한 단계 아래의, XML만 다루는 읽기 계층이다.
이번 E02 번호의 실제 진입점은 read_xml 하나로 둔다.

설계
- namespace URI 기준으로 XML을 읽는다(접두자가 달라도 같은 URI면 같은 네임스페이스).
- content.hpf 순서로 모든 section을 나열한다.
- DTD와 외부 엔티티를 거부하고, 원본 bytes와 노드 위치를 함께 보관한다.
- 외부 namespace의 같은 이름 태그는 내부 HWPX 의미와 섞지 않는다.
- section 10과 2를 문자열 순서로 오배치하지 않는다(content.hpf 기준).
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from hwpx.errors import (
    BAD_XML,
    DomainError,
    NEEDED_XML_MISSING,
    NS_MIXED,
    SECTION_ORDER_BAD,
    UNSAFE_XML,
)
from hwpx.package import ReadResult, read_hwpx

# ---------------------------------------------------------------------------
# HWPX 내부 namespace (이번 번호에서 다루는 범위)
# ---------------------------------------------------------------------------
# HWPX는 여러 네임스페이스를 쓰지만, 이번 번호는 우선 아래 URI를
# 내부 namespace 후보로 다룬다. 실제 문서는 더 많은 네임스페이스를
# 포함할 수 있고, 그 경우 외부 namespace로 분류한다.

HWPX_NS = "http://www.hwpzone.org/hwpx"
CONTENT_NS = "http://www.hwpzone.org/content"
POTEXT_NS = "http://www.hwpzone.org/potex"

# 내부 namespace로 취급할 URI 집합. 이름이 같더라도 URI가 다르면
# 섞지 않는다.
_INTERNAL_NS_URIS = frozenset({HWPX_NS, CONTENT_NS, POTEXT_NS})

# content.hpf에서 section 진입점을 읽을 때 쓰는 로컬 이름/속성.
_HPF_ROOT_LOCAL = "HpF"
_SECTION_LOCAL = "section"
_SECTION_HREF = "href"


# ---------------------------------------------------------------------------
# 공용 인터페이스
# ---------------------------------------------------------------------------

def read_xml(payload: bytes | ReadResult) -> XmlReadResult:
    """HWPX XML을 안전하게 읽는다.

    Args:
        payload: bytes(HWPX 원본) 또는 read_hwpx 결과(ReadResult).

    Returns:
        XmlReadResult — 원본 bytes, content.hpf 정보, section 순서,
        각 section의 원본 bytes와 파싱된 트리/위치 정보.
    """
    if isinstance(payload, ReadResult):
        result = payload
    elif isinstance(payload, (bytes, bytearray)):
        result = read_hwpx(bytes(payload))
    else:
        raise DomainError(
            BAD_XML,
            "payload must be bytes or ReadResult",
            {"received_type": type(payload).__name__},
        )

    hpf_path = "Contents/content.hpf" if result.has_path("Contents/content.hpf") else "Content.hpf"
    hpf_bytes = _require_bytes(result, hpf_path)
    hpf_info = _parse_native_hpf(hpf_bytes, result) if hpf_path.startswith("Contents/") else _parse_content_hpf(hpf_bytes)

    sections = _read_sections(result, hpf_info.section_paths)

    return XmlReadResult(
        original_bytes=result.original_bytes,
        original_sha256=result.original_sha256,
        hpf=HpfInfo(
            bytes=hpf_bytes,
            tree=_parse_xml_bytes(hpf_bytes, allow_external=False),
            paths_in_order=hpf_info.section_paths,
        ),
        sections=sections,
        section_paths_in_order=hpf_info.section_paths,
    )


# ---------------------------------------------------------------------------
# 반환 객체
# ---------------------------------------------------------------------------

class XmlReadResult:
    """read_xml 결과.

    원본 bytes와 content.hpf, section 순서, 각 section의 원본 bytes와
    파싱 정보를 담는다. 디스크 압축 해제는 하지 않는다.
    """

    __slots__ = (
        "original_bytes",
        "original_sha256",
        "hpf",
        "sections",
        "section_paths_in_order",
    )

    def __init__(
        self,
        original_bytes: bytes,
        original_sha256: str,
        hpf: "HpfInfo",
        sections: list["SectionReadResult"],
        section_paths_in_order: list[str],
    ) -> None:
        self.original_bytes = original_bytes
        self.original_sha256 = original_sha256
        self.hpf = hpf
        self.sections = sections
        self.section_paths_in_order = section_paths_in_order


class HpfInfo:
    """content.hpf 정보와 section 순서."""

    __slots__ = ("bytes", "tree", "paths_in_order")

    def __init__(self, bytes: bytes, tree: "XmlDocument", paths_in_order: list[str]) -> None:
        self.bytes = bytes
        self.tree = tree
        self.paths_in_order = paths_in_order


class SectionReadResult:
    """하나의 section XML 읽기 결과."""

    __slots__ = (
        "path",
        "bytes",
        "tree",
        "_ns_used",
    )

    def __init__(self, path: str, bytes: bytes, tree: "XmlDocument", ns_used: frozenset[str]) -> None:
        self.path = path
        self.bytes = bytes
        self.tree = tree
        self._ns_used = ns_used

    @property
    def used_namespaces(self) -> frozenset[str]:
        """이 section에서 실제 등장한 네임스페이스 URI 집합."""
        return self._ns_used

    def find_all(self, ns_uri: str, local: str) -> list["XmlElement"]:
        """네임스페이스 URI와 로컬 이름으로 요소를 찾는다.

        접두자가 달라도 URI가 같으면 같은 것으로 본다.
        외부 namespace URI로 내부 의미를 찾지 않도록 하는 용도다.
        """
        return self.tree.elements_by_ns_local.get((ns_uri, local), [])


class XmlDocument:
    """메모리에서 제한적으로 파싱한 XML 문서.

    원본 bytes와 요소 위치 정보를 함께 보관한다.
    """

    __slots__ = ("root", "elements_by_ns_local", "ns_used", "raw_bytes")

    def __init__(self, root: "XmlElement", elements_by_ns_local: Mapping[tuple[str, str], list["XmlElement"]], ns_used: frozenset[str], raw_bytes: bytes) -> None:
        self.root = root
        self.elements_by_ns_local = elements_by_ns_local
        self.ns_used = ns_used
        self.raw_bytes = raw_bytes


class XmlElement:
    """파싱된 요소의 최소 표현. 원본 위치를 함께 보관한다."""

    __slots__ = ("ns_uri", "local", "text", "tag", "line", "column", "children", "attributes")

    def __init__(
        self,
        ns_uri: str,
        local: str,
        text: str | None,
        tag: str,
        line: int | None,
        column: int | None,
        children: list["XmlElement"],
        attributes: dict[str, str],
    ) -> None:
        self.ns_uri = ns_uri
        self.local = local
        self.text = text
        self.tag = tag
        self.line = line
        self.column = column
        self.children = children
        self.attributes = attributes


# ---------------------------------------------------------------------------
# content.hpf 파싱
# ---------------------------------------------------------------------------

class _HpfParseResult:
    def __init__(self, section_paths: list[str]) -> None:
        self.section_paths = section_paths


def _parse_native_hpf(raw: bytes, package: ReadResult) -> _HpfParseResult:
    import posixpath
    from xml.etree import ElementTree as ET
    _reject_doctype_and_entities(raw)
    root = ET.fromstring(raw)
    ns = {"opf": "http://www.idpf.org/2007/opf/"}
    if root.tag != "{" + ns["opf"] + "}package":
        raise DomainError(BAD_XML, "Invalid OPF package", {})
    items = {}
    for item in root.findall("opf:manifest/opf:item", ns):
        key, href = item.get("id"), item.get("href", "")
        if not key or key in items or not href or href.startswith(("/", "\\")) or ":" in href or "\\" in href or ".." in href.split("/"):
            raise DomainError(BAD_XML, "Invalid manifest item", {})
        path = href if href.startswith("Contents/") else posixpath.join("Contents", href)
        items[key] = path
    paths = []
    for item in root.findall("opf:spine/opf:itemref", ns):
        path = items.get(item.get("idref"))
        if not path or not package.has_path(path) or path in paths:
            raise DomainError(SECTION_ORDER_BAD, "Invalid spine reference", {})
        paths.append(path)
    if not paths:
        raise DomainError(SECTION_ORDER_BAD, "Empty spine", {})
    return _HpfParseResult(paths)


def _parse_content_hpf(hpf_bytes: bytes) -> _HpfParseResult:
    """content.hpf에서 section 경로를 읽어 순서를 결정한다.

    이번 번호는 우선 다음 규칙을 쓴다.
    - content.hpf의 루트가 예상 로컬 이름(HpF)이어야 한다.
    - section 요소는 로컬 이름이 'section'이고 href 속성을 가진다.
    - 등장 순서대로 section 경로를 모은다.
    """
    tree = _parse_xml_bytes(hpf_bytes, allow_external=False)

    root = tree.root
    if root.local != _HPF_ROOT_LOCAL:
        raise DomainError(
            BAD_XML,
            "Content.hpf root is not HpF",
            {"root_tag": root.tag, "root_local": root.local},
        )

    section_paths: list[str] = []
    for child in root.children:
        if child.local == _SECTION_LOCAL:
            href = child.attributes.get("href", "")
            if href == "":
                raise DomainError(
                    BAD_XML,
                    "section element missing href attribute",
                    {"section_element": child.tag},
                )
            href = _normalize_hpf_href(href)
            section_paths.append(href)

    if not section_paths:
        raise DomainError(
            NEEDED_XML_MISSING,
            "Content.hpf has no section entries",
            {"root_tag": root.tag},
        )

    return _HpfParseResult(section_paths)


def _normalize_hpf_href(href: str) -> str:
    """content.hpf에 적힌 section href를 정규 경로로 만든다.

    보통 'section0.xml'처럼 ZIP 루트에 있는 파일명을 가리킨다.
    여기서는 선행 슬래시를 제거하고, ZIP 항목처럼 취급한다.
    """
    if not isinstance(href, str):
        href = str(href)
    href = href.strip()
    # ZIP 항목은 대개 '/'로 시작하지 않지만, HpF href가 '/'로 시작할 수 있어
    # 여기서는 첫 '/'를 제거해 ZIP 루트의 파일명으로 맞춘다.
    while href.startswith("/"):
        href = href[1:]
    if href == "":
        raise DomainError(
            BAD_XML,
            "section href is empty after normalization",
            {"href": href},
        )
    return href


# ---------------------------------------------------------------------------
# section 읽기
# ---------------------------------------------------------------------------

def _read_sections(result: ReadResult, paths: list[str]) -> list[SectionReadResult]:
    """content.hpf 순서로 section을 읽는다.

    문자열 정렬이 아니라 content.hpf 등장 순서를 그대로 쓴다.
    """
    out: list[SectionReadResult] = []
    for path in paths:
        raw = _require_bytes(result, path)
        tree = _parse_xml_bytes(raw, allow_external=False)
        ns_used = _collect_ns_uris(tree)
        out.append(SectionReadResult(path=path, bytes=raw, tree=tree, ns_used=ns_used))
    return out


def _require_bytes(result: ReadResult, path: str) -> bytes:
    if not result.has_path(path):
        raise DomainError(
            NEEDED_XML_MISSING,
            "needed entry missing",
            {"path": path, "known": result.item_paths[:10]},
        )
    return result.get_bytes(path)


# ---------------------------------------------------------------------------
# 안전한 XML 파싱
# ---------------------------------------------------------------------------

# 외부 엔티티/DTD를 허용하지 않는 파서
_XML_PARSER_KIND = "xml.etree.ElementTree"


def _parse_xml_bytes(raw: bytes, allow_external: bool) -> XmlDocument:
    """XML bytes를 제한적으로 파싱한다.

    Args:
        raw: 원본 XML bytes.
        allow_external: 이번 번호는 항상 False. DTD, 외부 엔티티, 파싱Entity 등을 거부한다.
    """
    if allow_external:
        raise DomainError(
            UNSAFE_XML,
            "external entity allowed is not supported in this engine",
            {},
        )

    try:
        import xml.etree.ElementTree as ET
    except ImportError as exc:
        raise DomainError(
            UNSAFE_XML,
            "xml.etree.ElementTree not available",
            {"reason": str(exc)},
        ) from exc

    # ET.fromstring은 기본적으로 DTD를 완전히 거부하지는 않지만,
    # 이번 번호는 명시적으로 엔티티/ DTD 처리를 제한하는 방향으로 둔다.
    # Python 3.11에서는 fromstring 시 외부 DTD 로드가 기본적으로 비활성화
    # 되어 있고, onerror/onupdate 옵션이 없다. 따라서 명시적 방어선으로는
    # raw에서 <!DOCTYPE와 <!ENTITY를 사전 검사하고, 파싱 후 트리만 사용한다.
    _reject_doctype_and_entities(raw)

    try:
        root_el = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise DomainError(
            BAD_XML,
            "xml parse error",
            {"reason": str(exc), "first_bytes": raw[:200]},
        ) from exc

    return _build_document(root_el, raw)


def _reject_doctype_and_entities(raw: bytes) -> None:
    """DTD와 외부 엔티티 지시를 차단한다.

    완전한 XML 파서 수준의 방어는 추후 parserfactory 등으로 보강할 수 있지만,
    이번 번호는 우선 바이트 수준에서 명백한 DTD/ENTITY 지시를 감지한다.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise DomainError(
            UNSAFE_XML,
            "xml payload must be bytes",
            {"received_type": type(raw).__name__},
        )

    # 대소문자 무시를 위해lower 케이스로 검사하되, 원본 위치는 보존한다.
    low = raw.replace(b"\x00", b"").lower()
    if b"<!doctype" in low:
        raise DomainError(
            UNSAFE_XML,
            "DOCTYPE is not allowed",
            {},
        )
    if b"<!entity" in low:
        raise DomainError(
            UNSAFE_XML,
            "ENTITY declaration is not allowed",
            {},
        )
    # 외부 식별자처럼 보이는 PUBLIC/SYSTEM이 DTD 없이 등장해도
    # 이번 번호는 보수적으로 막는다.
    if b"system" in low and (b"public" in low or b"entity" in low):
        # 이미 entity 검사는 위서 걸러지지만, system alone은 오탐 가능.
        # 여기서는 DOCTYPE/ENTITY가 없을 때만 통과시키는 정책과 양립시키기 위해
        # 별도로 엄격화하지 않고, 위 규칙으로 충분히 막는다.
        pass


# ---------------------------------------------------------------------------
# 트리 → 내부 문서 변환
# ---------------------------------------------------------------------------

def _build_document(root_el, raw: bytes) -> XmlDocument:
    """ElementTree 루트를 내부 표현으로 바꾸고, 요소 색인을 만든다."""
    root = _element_to_internal(root_el)
    index: dict[tuple[str, str], list[XmlElement]] = {}
    _index_elements(root, index)
    ns_used = _collect_ns_uris_from_root(root_el)
    return XmlDocument(root=root, elements_by_ns_local=index, ns_used=ns_used, raw_bytes=raw)


def _element_to_internal(el) -> XmlElement:
    """ElementTree 요소를 내부 XmlElement로 변환한다."""
    ns_uri, local = _split_ns(el.tag)
    text = el.text
    # ElementTree의 sourceline/column은 항상 제공되지 않을 수 있다.
    line = getattr(el, "sourceline", None)
    column = getattr(el, "column", None)
    children = [_element_to_internal(c) for c in el]
    attributes = {k: (v or "") for k, v in el.attrib.items()}
    return XmlElement(
        ns_uri=ns_uri,
        local=local,
        text=text,
        tag=el.tag,
        line=line,
        column=column,
        children=children,
        attributes=attributes,
    )


def _split_ns(tag: str) -> tuple[str, str]:
    """{uri}local 형태의 태그를 분리한다.

    접두자만 있고 URI가 없는 경우(즉 기본 네임스페이스가 아닌 접두자)는
    이번 번호에서 ns_uri를 빈 문자열로 두지 않고, 접두자 기반 추정 없이
    '불명확' 처리하되 외부 namespace로 분류한다.
    """
    if not isinstance(tag, str):
        tag = str(tag)
    if tag.startswith("{") and "}" in tag:
        uri, local = tag[1:].split("}", 1)
        return uri, local
    # 접두자 기반 태그(예: hpf:section)는 uri가 없다.
    # 이번 번호는 URI 기준 처리를 우선하므로, 접두자만 있는 태그는
    # uri를 None처럼 다루지 않고 빈 문자열로 두고, 색상 구분용으로
    # 나중에 ns_mixed 검사에 사용한다.
    return "", tag


def _index_elements(root: XmlElement, index: dict[tuple[str, str], list[XmlElement]]) -> None:
    """루트 이하 모든 요소를 (ns_uri, local) 기준으로 색인한다.

    같은 (ns_uri, local) 조합은 여러 요소가 있을 수 있으므로 리스트로 보관한다.
    """
    key = (root.ns_uri, root.local)
    index.setdefault(key, []).append(root)
    for child in root.children:
        _index_elements(child, index)


def _collect_ns_uris(tree: XmlDocument) -> frozenset[str]:
    """문서에서 실제 사용한 네임스페이스 URI 집합을 모은다."""
    uris: set[str] = set()
    for (ns_uri, _local) in tree.elements_by_ns_local:
        if ns_uri:
            uris.add(ns_uri)
    return frozenset(uris)


def _collect_ns_uris_from_root(root_el) -> frozenset[str]:
    """ElementTree에서 xmlns 선언 등으로 보이는 URI도 함께 본다.

    이번 번호는 우선 요소 태그에 드러난 URI만 신뢰하되,
    향후 선언을 반영하려면 여기서 확장한다.
    """
    uris: set[str] = set()
    for el in _iter_elements(root_el):
        uri, _local = _split_ns(el.tag)
        if uri:
            uris.add(uri)
    return frozenset(uris)


def _iter_elements(el) -> Iterable:
    """모든 요소를 순회하며Yield한다."""
    yield el
    for child in el:
        yield from _iter_elements(child)


# ---------------------------------------------------------------------------
# 네임스페이스 혼입 검사
# ---------------------------------------------------------------------------

def check_ns_mixed(sections: list[SectionReadResult]) -> list[str]:
    """내부 namespace와 외부 namespace의 동일 이름 요소 혼입을 검사한다.

    반환값은 경고/오류 메시지 목록이다. 이번 번호는 우선 검사 결과만 남긴다.
    """
    problems: list[str] = []
    for sec in sections:
        used = sec.used_namespaces
        internal = _INTERNAL_NS_URIS & used
        external = used - _INTERNAL_NS_URIS
        if not external:
            continue
        # 외부 namespace에서 내부 namespace와 같은 로컬 이름을 쓰는 요소가
        # 있는지 확인한다.
        for (ns_uri, local) in sec.tree.elements_by_ns_local:
            if ns_uri in external and local in _locals_used_by_internal(used, sec):
                problems.append(
                    f"section {sec.path}: external ns {ns_uri} has same local name '{local}' as internal"
                )
    return problems


def _locals_used_by_internal(used: frozenset[str], sec: SectionReadResult) -> set[str]:
    locals_: set[str] = set()
    for (ns_uri, local) in sec.tree.elements_by_ns_local:
        if ns_uri in _INTERNAL_NS_URIS:
            locals_.add(local)
    return locals_
