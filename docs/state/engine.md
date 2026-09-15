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
