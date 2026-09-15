# docs/state/engine.md — HWPX_TRANSPLANT

- 단계: **P01 준비 중**
- 브랜치: `team/engine`
- 대상 서비스: A 양식(표·문단·고정 문구) 유지 + B 내용 빈칸 채움
- 엔진/API 구현: 이번 단계에서 만들지 않음

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

## 실제 검사

- [ ] `reference/qualifier/` 아래 파일들이 예선 SKILL.md·references·schemas·examples·checklists와 동일한 내용으로 복사됐는지 확인
- [ ] 원본(예선 자료) 폴더가 삭제·덮어쓰기되지 않았는지 확인
- [ ] `team/engine` 브랜치가 이미 있으면 삭제하지 않고 상태만 확인했는지 확인
- [ ] docs/state/engine.md에 P02 항목이 다음 단계로만 적혀 있는지 확인

## 다음 번호

- P02: (미정 — 엔진/API 구현 금지 상태를 유지한 채로 다음 준비 항목 정의)
