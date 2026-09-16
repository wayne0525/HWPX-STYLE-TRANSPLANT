import io
from pathlib import Path
import zipfile

import pytest

from hwpx.errors import DomainError
from hwpx.source import extract_b
from hwpx.xml import read_xml
from tests.engine.test_native_engine import document


def with_resources(href='Scripts/headerScripts.js', reference='script'):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(document())) as source, zipfile.ZipFile(out, 'w') as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == 'Contents/content.hpf':
                data = data.decode().replace('</opf:manifest>',
                    f'<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
                    f'<opf:item id="script" href="{href}" media-type="application/x-javascript"/></opf:manifest>')
                data = data.replace('<opf:spine>', f'<opf:spine><opf:itemref idref="header"/><opf:itemref idref="{reference}"/>').encode()
            target.writestr(info, data)
        target.writestr('Contents/header.xml', '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>')
        target.writestr('Scripts/headerScripts.js', 'function OnDocument_New() {}')
    return out.getvalue()


def test_spine_reads_only_body_sections_in_spine_order():
    parsed = read_xml(with_resources())
    assert parsed.section_paths_in_order == ['Contents/section2.xml', 'Contents/section0.xml']


@pytest.mark.parametrize('href,reference', [('Scripts/missing.js', 'script'), ('../Scripts/headerScripts.js', 'script'), ('Scripts/headerScripts.js', 'unknown'), ('Scripts/headerScripts.js', 's2')])
def test_broken_or_unsafe_references_still_rejected(href, reference):
    with pytest.raises(DomainError):
        read_xml(with_resources(href, reference))


def test_real_b_hwpx_extracts_body_without_script_or_header():
    raw = (Path(__file__).parents[1] / 'fixtures/B.hwpx').read_bytes()
    assert read_xml(raw).section_paths_in_order == ['Contents/section0.xml']
    result = extract_b(raw, kind='hwpx')
    assert result.blocks
    assert all('OnDocument_New' not in b.text for b in result.blocks)
