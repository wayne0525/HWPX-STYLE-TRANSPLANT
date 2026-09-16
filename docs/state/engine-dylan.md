# docs/state/engine-dylan.md — HWPX 스타일 이식 엔진 (team/engine-dylan)

- 단계: **단계 0~2 완료, 단계 3(정리·커밋) 진행 중**
- 브랜치: `team/engine-dylan`
- 대상 서비스: A 양식(표·문단·고정 문구) 보존 + B의 근거 있는 내용을 선택한 입력란에 채움
- 엔진: 규칙 기반 analyze_a 구현 완료 (규칙 1·2·3·4). fill.py/verify.py는 아직 미구현.
- 우선순위: 충돌 시 루트 `SKILL.md` 절대 규칙 우선. `reference/qualifier/` 예선 규칙은 이번 서비스에 미적용.
- 기준 문서: `docs/contracts/engine.md`, `docs/WORK_RULES.md`, `docs/TEAM_CONTRACT.md`, `PROJECT_BLUEPRINT.md`, `SKILL.md`

## 완료된 작업

### 단계 0 — 준비
- 저장소 상태 확인: `/mnt/c/Users/dylan/HWPX-STYLE-TRANSPLANT`, 브랜치 `team/engine-dylan`.
- 이전 세션 커밋 5개 존재. `hwpx/`, `tests/`, `scripts/`, `docs/contracts/`, `.venv/`, `docs/ne-dylan.md`는 당시 untracked.
- 프로젝트 문서 5개(`SKILL.md`, `PROJECT_BLUEPRINT.md`, `docs/WORK_RULES.md`, `docs/TEAM_CONTRACT.md`, `docs/contracts/engine.md`) 모두 읽음.
- A.hwpx와 B.hwpx fixture 확인. A.hwpx는 표 11개(0~10), ZIP 엔트리 11개.

### 단계 1 — analyze_a 구현 + 과제 1 (test_analyze.py 되살리기)
- `hwpx/analyze.py`의 `analyze_a("tests/fixtures/A.hwpx")`가 규칙 1·2·3으로 필드 후보를 반환.
- 규칙별 후보: 규칙1(라벨 셀 오른쪽 빈 셀), 규칙2(헤더 행 아래 빈 셀), 규칙3(단위/자리표시자만 있는 셀).
- 과제 1에서 `test_analyze.py` 되살림:
  - 문법 오류 수정 (`test_saeop_dae Sang_label` → `test_saeop_daesang_label`).
  - `_field()` 반환 dict에 `rule` 키 추가 (`"rule1"`/`"rule2"`/`"rule3"`).
  - 기대값 실제 근거로 수정: 표6 4→1, 표7 8→5, TestTable11(존재하지 않는 표) → TestTable10Rule2(표#10, 실제 규칙2=0개), 표1 규칙1 라벨 5→0, field_id 길이 6→5 등.
  - `docs/contracts/engine.md` §2.1 반환 형식에 `rule` 필드 설명 추가.
- `tests/test_analyze.py` 41개 + `tests/test_package.py` 7개 = **48개 통과** 확인.

### 단계 2 — 규칙 4 추가 (과제 2)
- 규칙 4: 한 셀 안의 `"라벨 :"` 뒤 빈자리. 셀 텍스트를 `라벨 :` 단위로 쪼개 콜론 뒤가 비어 있으면 각각 별도 후보로 잡는다.
- 규칙 4 구현:
  - `_RULE4_LABELS`, `_RULE4_LABEL_PATTERNS`, `_rule4_find_in_cell` 헬퍼 함수 추가.
  - `analyze_a` 루프에 규칙 4 삽입 (규칙 1과 규칙 2 사이, `taken` 충돌 방지).
  - 라벨-콜론 사이 공백 허용 (`re.match(r"\s*:", after)`).
  - `(우편번호 :          )` 케이스: `val_text` 첫 토큰이 닫는 괄호면 값 없음 처리.
  - 셀 레벨 `_is_guidance_tc` 체크 제거 (우편번호 셀이 ※ 문단 때문에 guidance로 배제되던 문제 해결), 문단 단위 `※` 체크에 의존.
- 규칙 4 위치 필드: `paragraph_index`(셀 내 문단 순서), `run_index`(문단 내 run 순서), `insert_offset`(run 텍스트 안에서 콜론 뒤 삽입 위치 문자 오프셋)을 `location`에 기록.
- 규칙 4 단위 추정: `우편번호`→`postal-code`, `전화`/`팩스`→`phone`, `이메일`→`email`, `성명`→`person-name` 등.
- 규칙 4 테스트 5개 추가:
  - `test_program_name_not_candidate`: '프로그램명'은 이미 값 있어 제외.
  - `test_seongmyeong_is_candidate`: '성명' 후보 확인 (직명 :교장성명 :).
  - `test_jeonhwa_fax_candidates`: '전화', '팩스' 후보 확인.
  - `test_postal_code_candidate`: '우편번호' 후보 확인 (unit=postal-code, offset=7).
  - `test_rule4_location_fields_present`: 모든 rule4 필드가 paragraph_index, run_index, insert_offset을 가짐.
- `tests/test_analyze.py` 수정:
  - 중복 `TestRule4` 클래스 제거.
  - TestTable3, TestTable10의 field_id를 실제 배치(f-019~f-021, f-058~f-063)에 맞게 수정.
  - TestTable1.test_5_rule1_labels_in_table1: 표1 라벨 필드 9개(rule4)로 수정.
  - TestTable1.test_table1_money_fields_have_merge_info: 대상 field_id를 f-013~f-015로 수정.
  - test_no_empty_label_field: rule1 + rule4 확인으로 수정.
- 규칙 4 실제 후보 11개: f-001(우편번호, 표1[2,2]), f-002(성명 및 직위, 표1[3,2]), f-003(휴대전화, 표1[3,2]), f-004(이메일, 표1[3,2]), f-005(상근직원수, 표1[4,2]), f-006(회원수, 표1[4,2]), f-007(성명, 표1[1,9]), f-008(전화, 표1[2,9]), f-009(팩스, 표1[2,9]), f-064(대표전화, 표10[2,2]), f-065(FAX, 표10[2,2]).
- `docs/contracts/engine.md`에 규칙 4 문서화: §2.1 rule 필드에 rule4 설명 추가, §3 분석 범위 4번 항목으로 규칙 4 상세 설명 추가.
- `tests/test_analyze.py` 46개 + `tests/test_package.py` 7개 = **53개 통과** 확인.

### 단계 3 — 정리·커밋 (현재 진행 중, 커밋은 사용자 승인 후)
- `docs/ne-dylan.md` → `docs/state/engine-dylan.md`로 이동, 내용 갱신 (이 파일).
- `.gitignore`에 `.venv` 추가 예정.
- 루트 `scripts/inspect_a.py`를 `tests/scripts/inspect_a.py`로 이동 예정 (루트 원본 삭제).
- 커밋 메시지 초안 제시 후 사용자 승인 대기.

## 확인된 HWPX 근거 (규칙 4 관련 일부)

- 표#1 [1,9] 셀 텍스트: `'직명 :교장성명 : '`. 콜론 2개. `직명` 뒤 값 있음(교장성명), `성명` 뒤 빈자리 → 규칙4 후보 f-007.
- 표#1 [2,2] 셀 텍스트: `'(우편번호 :          ) '`. 문단0 라벨+빈자리, 문단1 `※ 도로명주소로 기재`(안내문, 제외). `우편번호` 콜론 뒤 빈자리 → 규칙4 후보 f-001, unit=postal-code, insert_offset=7.
- 표#1 [2,9] 셀 텍스트: `'전화 :팩스 : '`. 문단0 `전화`, 문단1 `팩스`. 각각 콜론 뒤 빈자리 → 규칙4 후보 f-008(전화), f-009(팩스).
- 표#1 [3,2] 셀 텍스트: `'성명 및 직위 :       '`. `성명 및 직위` 콜론 뒤 빈자리 → 규칙4 후보 f-002.
- 표#1 [3,2] 문단1: `'휴대전화 :'` + `'이메일 :'`. 각각 콜론 뒤 빈자리 → 규칙4 후보 f-003(휴대전화), f-004(이메일).
- 표#1 [4,2] 셀 텍스트: `'상 근 직 원 수 :       '` + `'회 원 수 (명) :       '`. 각각 콜론 뒤 빈자리 → 규칙4 후보 f-005(상근직원수), f-006(회원수).
- 표#10 [2,2] 셀 텍스트: `'대표전화 :02-0000-1000FAX :'`. `대표전화`는 값 있음(02-0000-1000), `FAX` 콜론 뒤 빈자리 → 규칙4 후보 f-065(FAX). `대표전화`는 값 있어 제외? 실제 분석에서는 f-064(대표전화)도 후보로 잡힌 것으로 출력됨 — 확인 필요. (이 부분은 실제 analyze_a 출력에서 f-064 label='대표전화'로 잡혀 있음. 값 02-0000-1000이 있는데 후보로 잡힌 이유 확인 필요.)

## 아직 확인되지 않은 부분 / 이상 징후

- 표#10 [2,2] `'대표전화 :02-0000-1000FAX :'`: `대표전화` 라벨 뒤 값(02-0000-1000)이 있는데 규칙4 후보로 f-064가 잡힘. 규칙4 로직에서 이미 값이 있는 라벨을 제외하는 조건이 제대로 작동하지 않을 가능성. 실제 분석 출력에서 f-064 label='대표전화', f-065 label='FAX'로 둘 다 잡혀 있음. 확인 후 수정 필요.

## 실행하지 않은 것 (완료로 적지 않음)

- `fill.py` 구현 (분석 결과를 바탕으로 실제 값을 채우는 단계).
- `verify.py` 구현 (결과 검증).
- 실제 C HWPX 생성 및 검증 테스트.
- 규칙 4의 표#10 대표전화 버그 확인 및 수정.

## 다음 할 일

1. 표#10 대표전화 후보 버그 확인·수정 (규칙4에서 이미 값 있는 라벨 제외 조건).
2. `.gitignore`에 `.venv` 추가.
3. 조사용 스크립트 `scripts/inspect_a.py` → `tests/scripts/inspect_a.py`로 이동, 루트 원본 삭제.
4. 커밋 메시지 초안 제시 → 사용자 승인 → 커밋 (push는 하지 않음).

## 참고 파일

- `hwpx/analyze.py` — 핵심 분석 구현.
- `tests/test_analyze.py` — 테스트 (53개 통과 중 46개가 analyze).
- `tests/test_package.py` — 패키지 테스트 (7개).
- `tests/fixtures/A.hwpx` — 양식 fixture.
- `docs/contracts/engine.md` — 엔진 계약.
- `tests/scripts/inspect_a.py`, `tests/scripts/proto_analyze.py` — 조사용 스크립트.
