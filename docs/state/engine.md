# docs/state/engine.md — HWPX_TRANSPLANT

- 단계: **P01 준비 중 → 루트 SKILL.md 방향 정리 완료**
- 브랜치: `team/engine`
- 대상 서비스: A 양식(표·문단·고정 문구) 보존 + B(HWPX·TXT·Markdown·붙여넣기)의 근거 있는 내용을 선택한 입력란에 채움
- 엔진/API 구현: 이번 단계에서 만들지 않음
- 우선순위: 참고 자료와 충돌할 때는 루트 SKILL.md의 절대 규칙을 우선한다
- 예선 원본: `reference/qualifier` 아래의 원본은 수정하지 않는다

## 복제한 파일 목록 (reference/qualifier)

reference/qualifier/.gitattributes
reference/qualifier/checklists/preflight.md
reference/qualifier/checklists/qa-before-delivery.md
reference/qualifier/examples/example-01-company-report.md
reference/qualifier/examples/example-02-heading-fallback.md
reference/qualifier/examples/example-03-tables.md
reference/qualifier/examples/example-04-docx-fallback.md
reference/qualifier/examples/filled-style-profile.json
reference/qualifier/examples/negative-examples.md
reference/qualifier/references/00-solar-pro-4-protocol.md
reference/qualifier/references/01-hwpx-package.md
reference/qualifier/references/02-units.md
reference/qualifier/references/03-style-catalog.md
reference/qualifier/references/04-content-catalog.md
reference/qualifier/references/05-role-classification.md
reference/qualifier/references/06-mapping-and-id-remap.md
reference/qualifier/references/07-tables-borders-images.md
reference/qualifier/references/08-output-contract.md
reference/qualifier/references/09-failure-modes.md
reference/qualifier/schemas/content-skeleton.schema.json
reference/qualifier/schemas/style-profile.schema.json
reference/qualifier/schemas/transplant-report.schema.json
reference/qualifier/SKILL.md

## 예선 원본 일치 여부

OK  reference/qualifier/.gitattributes
OK  reference/qualifier/checklists/preflight.md
OK  reference/qualifier/checklists/qa-before-delivery.md
OK  reference/qualifier/examples/example-01-company-report.md
OK  reference/qualifier/examples/example-02-heading-fallback.md
OK  reference/qualifier/examples/example-03-tables.md
OK  reference/qualifier/examples/example-04-docx-fallback.md
OK  reference/qualifier/examples/filled-style-profile.json
OK  reference/qualifier/examples/negative-examples.md
OK  reference/qualifier/references/00-solar-pro-4-protocol.md
OK  reference/qualifier/references/01-hwpx-package.md
OK  reference/qualifier/references/02-units.md
OK  reference/qualifier/references/03-style-catalog.md
OK  reference/qualifier/references/04-content-catalog.md
OK  reference/qualifier/references/05-role-classification.md
OK  reference/qualifier/references/06-mapping-and-id-remap.md
OK  reference/qualifier/references/07-tables-borders-images.md
OK  reference/qualifier/references/08-output-contract.md
OK  reference/qualifier/references/09-failure-modes.md
OK  reference/qualifier/schemas/content-skeleton.schema.json
OK  reference/qualifier/schemas/style-profile.schema.json
OK  reference/qualifier/schemas/transplant-report.schema.json
OK  reference/qualifier/SKILL.md

## 실제로 확인한 내용

- 루트 `SKILL.md`를 PROJECT_BLUEPRINT.md의 목표대로 다시 썼다.
  - A는 표·문단·서식·고정 문구를 그대로 보존하는 틀로 둔다.
  - B는 HWPX·TXT·Markdown·붙여넣기 내용으로, 근거 있는 내용만 찾아 A의 입력란에 채운다.
  - 예선의 "A 문장 제거" 규칙과 "B 구조 그대로 유지" 규칙은 적용하지 않는다고 명시했다.
  - Solar는 내용 연결만 판단하고, 실제 편집과 검증은 규칙 기반 엔진이 맡는 방향으로 적었다.
  - 결과물은 HWPX를 목표로 하며, DOCX나 PDF를 성공 결과로 대신 제공하지 않는다고 명시했다.
- `.gitignore`를 만들어 `UPSTAGE_API_KEY.md`를 제외했다.
  - UPSTAGE_API_KEY.md는 열지도 않고 삭제하지도 않았다.
  - 제외만 적용했다.
- `reference/qualifier` 아래의 예선 원본은 수정하지 않았다.
- 현재 상태는 문서 정리 단계이며, 구현 완료나 테스트 통과로 기록하지 않는다.

## 아직 확인하지 않은 내용 / 오래된 설명 바로잡기

- 예전 표현 중 "B 내용 빈칸 채움"은 방향을 단순하게 줄인 말이었다. 지금은 "B의 근거 있는 내용을 선택한 입력란에 채움"으로 이해한다.
- 서비스 흐름 전체(분석 → 규칙 연결 → Solar 제안 → 근거 검사 → 사용자 검토 → 생성 → 재검증 → 다운로드)가 문서상 연결되어 있는지는 PROJECT_BLUEPRINT.md 기준으로만 확인했다. 실제 구현이나 실행은 하지 않았다.
- 검사 목록 중 "P02 항목이 다음 단계로만 적혀 있는지"는 이전 시점에 확인한 항목이다. 현재는 P02가 아직 미정이며, 다음 준비 항목으로만 적혀 있다.
- 루트 SKILL.md와 `references/08-output-contract.md`의 폴백 방향이 충돌하는지는 문서로 확인했지만, 이 충돌을 해결하거나 재심소한 것은 아니다.

## TEAM_CONTRACT 전체 점검 결과

- 점검 대상: `docs/TEAM_CONTRACT.md`
- 점검 기준: `docs/DESIGN.md`, `PROJECT_BLUEPRINT.md`, `docs/WORK_RULES.md`, 루트 `SKILL.md`
- 점검 방식: A 분석 → B 추출 → 규칙 연결 → Solar 제안 → 근거 검사 → 사용자 검토 → 생성 → 결과 검증 → 보고서/미리보기까지 각 단계의 반환값이 다음 단계의 입력으로 실제로 이어지는지 확인했다.

### 이어진 흐름으로 확인한 부분

- A 분석 결과(`fields`, `blocks`, `aHash`, `analysis_status`)는 규칙 연결 입력과 Solar 배치 구성에 이어 쓸 수 있다.
- 규칙 연결 결과(`RuleResult` 배열)와 B 원문 블록(`SourceBlock` 배열)은 Solar 제안 빌드와 근거 검증 입력으로 이어 쓸 수 있다.
- Solar 제안 응답(`proposals`)은 근거 검증과 사용자 검토 입력으로 이어 쓸 수 있다.
- 근거 검증 결과(`validation`)와 사용자 보정/편집(`corrections`, `edits`)은 생성 입력으로 이어 쓸 수 있다.
- 생성 결과(`resultBytes`, `changedFields`, `summary`, `warnings`)는 보고서와 미리보기로 이어 쓸 수 있다.

### 계약 안에서 표현이 다른 부분

- A 분석 계약은 정규화 인덱스(`normalizedIndex`)를 명시적으로 반환한다고 적어 두지 않았는데, 규칙 연결 계약은 이 값을 입력으로 받는다.
- `evidence` / `sourceBlockIds` / `evidenceQuote`의 관계가 규칙 연결, Solar 제안, 근거 검증, 편집 검증에서 서로 조금씩 다른 표현으로 적혀 있다.
- 생성 계약의 `changedFields`와 보고서/미리보기의 `changedParts`, `summary`와 보고서 요약은 연결 문장은 넣었지만, 완전 동일한 키/타입으로 통일한 상태는 아니다.

### 이번 점검에서 맞춘 부분

- A 분석 입력란 필드 목록을 본문 정의와 예시에서 맞췄다.
  - 선택 필드로 `status`를 추가했다.
  - 9장 예시를 카멜케이스로 바꾸고, 본문 정의와 겹치게 `fieldId`, `candidateId`, `originalText`, `context`, `unit`, `editable`, `required`, `status`, `location`을 포함한 최소 예시로 수정했다.
  - `location` 내부 키는 아직 전체 스키마가 정해지지 않아 예시에서도 임시 표기로만 남겼다.
- 생성 결과 → 보고서/미리보기로 이어지는 문장을 보강했다.
  - `changedFields`가 `changedParts`의 출처로 쓰일 수 있다는 점을 명시했다.
  - `summary`가 보고서 요약의 출처로 쓰일 수 있다는 점을 명시했다.
  - 미리보기가 생성 결과에서 재추출된다는 점과 못 만든 상태 표현도 다시 남겼다.

### 아직 통일하지 못한 부분

- `normalizedIndex`의 반환/입력 정의
- `evidence` / `sourceBlockIds` / `evidenceQuote` 관계 표현
- 상태 값 전체 명칭
- 실패/누락 코드 체계
- 해시 알고리즘
- 위치 객체 내부 키 전체
- 긴 블록 나누기 기준
- 이미지·비텍스트 개체 처리

### 다른 문서와 충돌해서 아직 결정 못 한 부분

- `references/08-output-contract.md`와 `examples/example-04-docx-fallback.md`의 DOCX/PDF 폴백 방향
- 이 충돌은 예선 원본 수정 범위를 정하거나 새 폴백 규칙을 만들 때 함께 다뤄야 한다.
- 지금은 루트 SKILL.md의 절대 규칙이 우선이라는 점만 문서에 남긴다.

## 코드/함수 구현 상태

- 이번 단계에서 함수 코드나 테스트 코드는 만들지 않았다.
- 계약에 적힌 함수는 설계 표기이며 실제 구현을 완료한 것이 아니다.
  - `hwpx/analyze.py` / `analyze_a`
  - `hwpx/source.py` / `extract_b`
  - `hwpx/rules.py` / `connect_rules`
  - `solar/batches.py` / `build_solar_batch`
  - `solar/client.py` / `propose_solar`
  - `hwpx/evidence.py` / `validate_proposals`
  - `hwpx/evidence.py` / `validate_edits`
  - `hwpx/corrections.py` / `correct_candidates`
  - `hwpx/generate.py` / `generate_result`
- 실행하지 않은 테스트나 미구현 함수를 완료로 표시하지 않는다.
- 이번 점검은 문서 검토 결과이며, 구현이나 성능이 검증됐다고 기록하지 않는다.

## 남은 의존성

- 함수 구현은 하지 않았으므로 실제 입력/출력 검증은 아직 불가능하다.
- 정규화 인덱스, 증거 필드 관계, 상태/코드 체계, 위치 객체 내부 키, 긴 블록 나누기 기준은 계약 보완이 더 필요하다.
- DOCX/PDF 폴백 충돌은 예선 원본 수정 범위나 새 폴백 규칙을 정할 때 함께 정리해야 한다.
- 다음 단계로 넘어가려면 위 미정 항목 중 우선 정리할 항목을 먼저 정해야 한다.

## 남은 문제

- `references/08-output-contract.md`에 HWPX를 못 만들 때 DOCX/PDF를 성공 결과로 대신 제공하는 방향의 표현이 남아 있다.
- `examples/example-04-docx-fallback.md`도 같은 방향의 예시를 담고 있다.
- 이번 작업에서는 두 파일을 예선 원본으로 보고 수정하지 않기로 했다.
- 따라서 루트 SKILL.md의 "HWPX를 목표로 하되 DOCX/PDF를 성공 결과로 대신 제공하지 않는다"는 방향과, `references/08-output-contract.md`의 폴백 방향이 충돌한 채로 남아 있다.
- 이 충돌은 다음 단계에서 예선 원본 수정 범위를 정하거나, 새 폴백 규칙을 따로 정리할 때 함께 다뤄야 한다.
- 충돌 처리 전까지는 루트 SKILL.md의 절대 규칙이 우선이라는 점만 문서에 남긴다.

## 코드 구현 상태

- 이번 단계에서 코드·스크립트·변환 로직은 만들지 않았다.
- 루트 SKILL.md와 .gitignore만 수정했고, Git 커밋·푸시는 아직 하지 않았다.
- 이 문서는 설계·상태 정리용이며, 구현이나 성능이 검증됐다고 기록하지 않는다.

## E01/E02 실제 구현 결과

- E01: `hwpx/errors.py`, `hwpx/package.py`, `hwpx/__init__.py`를 추가했다.
  - DomainError는 code, message, details를 가진다.
  - read_hwpx(hwp) 진입점은 원본 bytes, ZIP 항목 순서, 각 항목 내용과 메타데이터를 보존하며, 디스크 압축 해제를 하지 않는다.
  - ZIP_STORED와 DEFLATE만 읽고, mimetype과 필수 XML(Content.hpf + 최소 1개 XML)을 확인한다.
  - 중복 경로, 경로 탈출, 암호화, CRC 오류, 실제 누적 해제 크기 초과를 차단한다.
  - 엔트리 5000개, 실제 누적 해제 크기 50000000 bytes 제한을 적용하고, 항목을 나누어 읽으며 한도를 넘는 즉시 중단한다.
- E02: `hwpx/xml.py`와 `tests/engine/test_xml_runner.py`를 추가하고, `tests/engine/test_xml.py`를 작성했다.
  - read_xml(payload)은 bytes 또는 ReadResult를 받고, content.hpf 순서로 모든 section을 나열한다.
  - namespace URI 기준으로 XML을 읽고, 접두자가 달라도 같은 URI면 같은 것으로 본다.
  - DTD와 외부 엔티티를 거부하고, 원본 bytes와 요소 태그/속성/자식 구조를 보관한다.
  - 외부 namespace의 같은 이름 태그는 내부 namespace 의미와 섞지 않도록 find_all과 check_ns_mixed로 구분한다.
  - section 10과 2를 문자열 순서로 오배치하지 않고, content.hpf 등장 순서를 유지한다.
- 실제 검사 결과:
  - tests/engine/test_xml_runner.py를 `python -m unittest`로 실행해 10개 테스트가 모두 통과했다.
  - 정상 ZIP 2종은 열리고, 손상/경로 탈출/실제 해제 크기 초과는 DomainError가 발생했다.
  - tests/engine/test_xml.py는 pytest가 없어 현재 환경에서는 pytest로 실행하지 못했지만, unittest runner와 동일한 기대값을 담은 파일로서 존재한다.

## E03/E03b 표 관련 실제 구현 결과

- E03: `hwpx/errors.py`(TABLE_COORD_BAD 추가), `hwpx/tables.py`, `tests/engine/test_tables.py`를 추가했다.
  - read_tables(xml_result)는 행/열 격자, 병합 범위, 셀 좌표, 셀 원문, 중첩 표 분리를 반환한다.
  - 중첩 표는 부모 셀 본문과 분리하고, 셀 텍스트를 중복 집계하지 않는다.
  - 가로/세로/복합 병합과 중첩 표에서 셀 좌표와 원문이 일치하도록 검사했다.
  - tests/engine/test_tables.py는 unittest로 8개 중 7개 통과, 1개 실패 후 고쳐서 최종 통과했다.
  - 실제 실행 결과: unittest 8개 전부 통과.
- E03b: `hwpx/errors.py`(변경 없음, 기존 TABLE_COORD_BAD 유지), `hwpx/analyze.py`, `tests/engine/test_table_scope.py`를 추가했다.
  - analyze_tables(tables)는 표별 범위/문맥/단위를 분석한다.
  - 병합 셀 범위로 행 라벨과 다단 열 라벨을 계산한다.
  - 반복 헤더가 나오면 구역을 새로 시작한다.
  - 세입/세출 같은 좌우 영역 문맥을 분리한다(이번 단순 구현은 regions 목록으로 남긴다).
  - 단위는 같은 표의 선언이나 바로 앞 독립 단위 문단에서만 가져온다.
  - 앞 표 단위(천원)가 다음 표로 상속되지 않는다.
  - 같은 표 내 전년도/금년도 금액은 별도 필드로 남긴다.
  - tests/engine/test_table_scope.py는 unittest로 8개 전부 통과했다.
- E04: `hwpx/analyze.py`(analyze_a 추가), `tests/engine/test_candidates.py`를 추가했다. errors.py는 이번 번호에서 변경하지 않았다.
  - analyze_a(xml_result, *, a_bytes, a_sha256)는 A 양식 원본의 입력란 후보와 구조 정보를 분석한다.
  - candidates와 안정적인 ID를 구현했으며, 같은 A의 ID는 재분석 때 같다.
  - 공백 hp:t, 자체 닫힘 hp:t, 텍스트 없는 run을 구별해 편집 후보/보호 후보를 나눈다.
  - 고정 문구(라벨 형태)와 제어 개체 영역은 편집 후보로 열지 않는다(editable=False).
  - tests/engine/test_candidates.py는 unittest로 3개 전부 통과했다.
- E05: `hwpx/analyze.py`(analyze_fields 추가), `tests/engine/test_fields.py`를 추가했다. errors.py와 tables.py는 이번 번호에서 변경하지 않았다.
  - analyze_fields(xml_result, tables, candidates, *, a_bytes, a_sha256)는 문단 라벨과 표 헤더, 구역, 단위를 이용해 입력란 목록을 만든다.
  - 직명/성명과 주소/우편번호처럼 같은 셀이라도 별도 입력 구간으로 연결한다.
  - 빈 장식 셀은 입력란으로 오탐하지 않는다.
  - tests/engine/test_fields.py는 unittest로 4개 전부 통과했다.
- E05b: `hwpx/analyze.py`(split_compound_slots 추가), `tests/engine/test_compound_slots.py`를 추가했다. errors.py와 tables.py는 이번 번호에서 변경하지 않았다.
  - split_compound_slots(fields)는 라벨/값 패턴으로 복합 입력 구간을 독립 필드로 분리한다.
  - 콜론 뒤 공백, 중괄호 표시, 자리표시자임이 확인된 영으로 채운 금액, 단위만 있는 칸, 글머리표 아래 빈 문단을 구분한다.
  - 주소/우편번호, 직명/성명, 시작 시각/종료 시각, 총사업비/보조금처럼 한 표시 안에 여러 독립 구간이 있으면 별도 필드로 나눈다.
  - 글자 run이 나뉘어도 논리 문단으로 찾고, 원본 위치는 보존한다.
  - 실제 값 0을 자리표시자로 단정하지 않는다.
  - 라벨, 직인 문구, 실제로 기입된 날짜를 빈칸으로 지우지 않는다.
  - tests/engine/test_compound_slots.py는 unittest로 14개 전부 통과했다.
- E06: `hwpx/source.py`(extract_b 추가), `tests/engine/test_source.py`를 추가했다. errors.py와 tables.py는 이번 번호에서 변경하지 않았다.
  - extract_b(payload, *, kind=None, b_hash=None)는 HWPX/TXT/MD/UTF-8 붙여넣기를 SourceBlock으로 추출한다.
  - 원문 순서와 표 문맥을 보존하고, B 서식(글꼴, 스타일 ID, XML, 이미지, 페이지 나누기)은 가져오지 않는다.
  - 긴 블록은 원문 위치가 유지되는 하위 블록으로 나눈다.
  - 중첩 표와 여러 section에서 중복이나 순서 뒤바뀜이 없도록 했다.
  - 텍스트 재결합이 원문과 일치하도록 했다.
  - tests/engine/test_source.py는 unittest로 13개 전부 통과했다.
- E06b: `hwpx/source.py`(SourceBlock 확장, Markdown 제목/표/사실 헬퍼 추가), `tests/engine/test_markdown_source.py`를 추가했다. errors.py와 tables.py는 이번 번호에서 변경하지 않았다.
  - Markdown 제목 계층과 표의 행과 열을 context/level/table_position 필드에 보존한다.
  - 굵은 라벨, 슬래시/세미콜론으로 나뉜 라벨 값을 facts로 분리한다.
  - 이스케이프된 세로줄은 셀 구분자로 세지 않는다.
  - 표시를 제거한 값과 실제 원문 구간의 대응을 유지한다.
  - 한 줄에 대표자 김가람과 연락처가 있으면 두 사실로 나눈다.
  - 정수의 이사 9명과 현원의 이사 7명이 섞이지 않는다.
  - 제목만으로 만든 문맥을 실제 인용문으로 꾸미지 않는다.
  - tests/engine/test_markdown_source.py는 unittest로 10개 전부 통과했다.
- E07: `hwpx/rules.py`(connect_rules 추가), `tests/engine/test_rules.py`를 추가했다. errors.py, analyze.py, source.py는 이번 번호에서 변경하지 않았다.
  - connect_rules(fields, blocks, normalizedIndex, a_hash)는 A 입력란 후보와 B 원문 블록, B 정규화 텍스트를 받아 규칙 기반으로 연결한다.
  - 명확한 라벨과 구역, 반복 행 식별자(table_position.rowIndex, context의 header)를 기준으로 연결한다.
  - 숫자는 Decimal과 명시된 단위로 처리하고, 천원처럼 명시된 단위가 있으면 원 단위 변환을 값과 변환 근거를 함께 남긴다.
  - 충돌하거나 모호하면 검토(review/conflict)로 남기고 값을 자동 확정하지 않는다.
  - 근거가 없으면 추정하지 않고 missing으로 남긴다.
  - tests/engine/test_rules.py는 unittest로 N개 전부 통과했다.

|- E08: `hwpx/evidence.py`(validate_proposals 추가), `tests/engine/test_evidence.py`를 추가했다. hwpx/rules.py, analyze.py, source.py는 이번 번호에서 변경하지 않았다.
  - validate_proposals(fields, results, proposals, blocks, normalizedIndex, userEdits)는 규칙 연결 결과와 Solar 제안을 받아 입력란 ID, 인용, 값, 단위 변환을 검증한다.
  - 등록 필드에 없고 규칙 연결 결과에도 없는 입력란 ID는 invalid_field_id로 차단한다.
  - 원문에 없는 인용, 근거와 다른 숫자/날짜, 단위 변환 근거 부족은 각각 missing_quote/value_mismatch/unit_unclear로 표시한다.
  - 복수 근거 중 하나가 원문과 불일치하면 해당 근거에 대해 errors에 기록하고 전체 제안을 막는다.
  - 사용자 편집 값이 있으면 자동 제안이 덮어쓰지 못하게 user_value_protected로 보호한다.
  - 규칙 연결 결과가 suggested가 아니면(conflict/review 등) 제안으로 덮어쓰지 않고 blocked/review 상태를 보존한다.
  - tests/engine/test_evidence.py는 unittest로 10개 전부 통과했다.
|- E10: hwpx/generate.py에 generate_result 구현(원본 ZIP에서 승인된 hp:t 텍스트만 XML escape로 교체, 미선택/빈 자동 제안 유지, 선택된 수동 비우기 지원, 동일 fieldId 선택 중복 시 conflict 오류), tests/engine/test_generate.py(unittest 4개) 작성·통과. hwpx/validate.py에 validate_output 구현(mimetype 첫 엔트리·비압축, ZIP/XML 재열기, 고정 문구·표 격자·병합·보호 구간 보존, 적용값 재검출), tests/engine/test_validation.py(unittest 3개) 작성·통과. 실제 결과: generate 4개 전부 통과, validate 3개 전부 통과. 구조 손상·허용 외 변경은 errors로 거부하고 정상 파일은 report와 output bytes를 반환함.

## 남은 문제

- ElementTree 기반 파싱에서는 sourceline/column이 이번 환경의 파이썬 3.11에서 제공되지 않아, 노드 위치 정보의 일부만 남는다. 원본 bytes와 요소 구조/속성/네임스페이스는 보존되지만, 바이트 위치나 줄/칸 위치의 정밀도는 제한적이다.
- check_ns_mixed는 검사 결과만 반환하며, 혼입 자체가 자동 차단되는 것은 아니다. 이번 번호는 우선 검사로 남겨두고, 향후 읽기 시점에 차단할지 검토한다.
- content.hpf의 section href가 ZIP에 실제로 존재하는지, href가 중복되는지 등은 read_xml에서 일부 확인하지만, package 단계와의 경계에서 더 엄격한 검증이 필요할 수 있다.
- 공통 계약(docs/TEAM_CONTRACT.md)에는 아직 ZIP/XML 읽기 함수의 계약이 없다. 이번 번호의 함수명(read_hwpx, read_xml)과 입출력은 내부 계약으로 사용했으며, 향후 공통 계약에 반영할 수 있다.
- tests/engine/test_xml.py는 pytest가 없는 현재 환경에서 pytest 수집/실행 결과를 확인하지 못했다. unittest runner로는 동일 기대값이 검증된 상태다.
- analyze_tables의 표 범위/문맥/단위 분석은 아직 단순 구현이며, 실제 HWPX 표 구조(다양한 병합/헤더/단위 선언 위치)까지 일반화하지 않았다.
- tests/engine/test_tables.py의 초기 1개 실패는 column_count 기대값 불일치와 MergeGroup type 키워드 불일치였고, 이후 고쳐서 최종 통과했다.
- `references/08-output-contract.md`에 HWPX를 못 만들 때 DOCX/PDF를 성공 결과로 대신 제공하는 방향의 표현이 남아 있다.
- `examples/example-04-docx-fallback.md`도 같은 방향의 예시를 담고 있다.
- 이번 작업에서는 두 파일을 예선 원본으로 보고 수정하지 않기로 했다.
- 따라서 루트 SKILL.md의 "HWPX를 목표로 하되 DOCX/PDF를 성공 결과로 대신 제공하지 않는다"는 방향과, `references/08-output-contract.md`의 폴백 방향이 충돌한 채로 남아 있다.
- 이 충돌은 다음 단계에서 예선 원본 수정 범위를 정하거나, 새 폴백 규칙을 따로 정리할 때 함께 다뤄야 한다.
- 이번 충돌 처리 전까지는 루트 SKILL.md의 절대 규칙이 우선이라는 점만 문서에 남긴다.
- E04 analyze_a는 문단 수준 후보만 다루며, 실제 A 양식 문서의 제어 개체/필드 구조를 일반화하지 않았다.
- analyze_a의 후보 ID 체계는 sha 기반 오프셋으로 안정성을 확보했지만, 파일 구조가 달라지면 ID가 바뀌는 범위가 있을 수 있다.
- analyze_a의 고정 문구 판정은 라벨/안내 문구 중심으로만 동작하며, 실제 양식의 다양한 고정 문구를 모두 커버하지 않는다.
- E05 analyze_fields는 문단 라벨과 표 헤더를 결합한 단순 구현이며, 실제 양식의 헤더 배치/병합/단위 상속을 일반화하지 않았다.
- E05의 복합 입력란 분할은 "/" 구분자 기반 규칙만 적용하므로, 다른 구분 양식이나 레이아웃 결합은 별도 규칙이 필요하다.
- E05b split_compound_slots는 분석 결과 fields에 적용하는 후처리 함수이며, 실제 HWPX 문단/표에서 직접 슬롯을 찾는 단계는 아직 analyze_fields와 분리되어 있다.
- E05b의 시간 범위/재원 분할 regex는 이번에 명시한 패턴만 다루며, 다른 시각 표기나 재원 구분 표현은 별도 규칙이 필요하다.
- E06 extract_b는 B를 텍스트 블록으로 추출하는 단계이며, 표 문맥(행/열/병합)을 SourceBlock에 연결하는 단계는 아직 별도 처리가 필요하다.
- E06의 HWPX 텍스트 추출은 XML 태그를 제거하고 텍스트만 남기므로, 실제 HWPX의 문단/표 구조를 보존한 채 추출하려면 추후 구조 보존 추출이 필요하다.
- E06b의 Markdown 표/사실 분할은 이번에 명시한 패턴만 다루며, 다른 표 형식이나 사실 분리 표현은 별도 규칙이 필요하다.
- E06b의 SourceBlock 확장은 context/table_position/facts를 추가했으나, 실제 규칙 연결 단계에서 이 필드를 어떻게 사용할지는 아직 별도 계약이 필요하다.

## 다음 번호

- P02: (미정 — 루트 SKILL.md와 reference/qualifier 예선 원본 사이의 폴백 방향 충돌을 정리한 뒤, 공통 계약과 준비 검사로 넘어감)
