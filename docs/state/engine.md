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

## 다음 번호

- P02: (미정 — 루트 SKILL.md와 reference/qualifier 예선 원본 사이의 폴백 방향 충돌을 정리한 뒤, 공통 계약과 준비 검사로 넘어감)
