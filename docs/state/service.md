# 서비스 구성 상태 (확인일: 2026-09-16)

## 확인된 실제 작업 경로

- 작업 폴더: `/c/MABC/HWPX-STYLE-TRANSPLANT`
- 현재 브랜치: `team/service`
- 원격 저장소(origin): `https://github.com/wayne0525/HWPX-STYLE-TRANSPLANT.git`
- Git 계정: `Halley04 <dhshalley@gmail.com>`

## 확인된 서비스 경로 (실제 코드 기준)

- **api**: `api/transplant/index.py`
  - 진입점: `handler` (Vercel serverless)
  - entrypoint 설정: `pyproject.toml`의 `[tool.vercel] entrypoint = "api.transplant.index:handler"`
  - Vercel 함수 설정: `vercel.json` → `api/transplant/`
  - Solar 연동: `call_solar` (stdlib `urllib.request`, Bearer 토큰, 모델 `solar-pro4`)
- **web**: `public/index.html`
- **hwpx 엔진**: `hwpx_lib/` (아래 파일 포함)
  - `unpack.py`, `parse_header.py`, `parse_section.py`, `style_profile.py`,
    `summary.py`, `fontmap.py`, `units.py`, `build_section.py`, `repack.py`

## hwpx 엔진/문서 분석/편집 코드와 서비스 코드의 분리 상태

- `hwpx_lib/`는 서비스 코드와 같은 저장소에 있으나 별도 하위 디렉터리로 존재.
- `api/transplant/index.py`는 `hwpx_lib`를 import 해서 사용.
- 이번 브랜치에서 `hwpx_lib/build_section.py`가 수정된 상태(빈 문서 수정 관련). hwpx 엔진 파일 수정은 이 브랜치에 포함됨.

## tests와 solar, api, web 담당 검사

- 독립 `solar/`, `tests/` 디렉토리는 없음.
- Solar/API/화면 관련 검사는 현재 루트 수준의 `test_*.py`로 분산되어 있었음.
- 이번 작업에서 테스트용 `.py` 파일은 모두 삭제함:
  - `test_b_patterns.py`, `test_b_structure.py`, `test_b_types.py`,
    `test_fontfaces_probe.py`, `test_fontmap_integration.py`,
    `test_header_probe.py`, `test_page_validation.py`,
    `test_parse.py`, `test_validate_report.py`
  - `post_4.py`, `post_full.py`
- 테스트 실행 결과/data 파일도 함께 제거:
  - `solar_real_req.json`, `solar_real_req_A_b64.txt`, `solar_real_req_B_b64.txt`,
    `solar_real_resp.json`, `solar_real_resp_4.json`, `solar_real_resp_full.json`,
    `C_법인현황정리_서식이식.hwpx`, `C_법인현황정리_서식이식_v2.hwpx`

## import 경로 확인 결과

- 진입점 import: `api.transplant.index:handler`는 `pyproject.toml` 설정과 일치.
- `hwpx_lib` 내부 import: 빌드/패키징 없이 프로젝트 루트를 `sys.path`에 두는 방식으로 동작.
- 실제 import문에서 사용하는 최상위 패키지: `hwpx_lib`, `http`, `urllib`, `xml`, `zipfile`, `json`, `base64`, `os`, `sys`, `tempfile`, `re`, `shutil`, `typing`, `uuid`.
- 중복 경로: `hwpx/`는 존재하지 않음(현재 `hwpx_lib/`만 존재).

## 공통 문서 상태

- 있는 문서:
  - `SKILL.md` (루트)
- 없는 문서 (임의 생성하지 않음):
  - `PROJECT_BLUEPRINT.md` (루트)
  - `docs/WORK_RULES.md`
  - `docs/DESIGN.md`
  - `docs/TEAM_CONTRACT.md`
  - `docs/state/service.md` (이 파일 생성 전에는 없었음)

## 남은 계약 불일치 / 의문

- `TEAM_CONTRACT.md`가 없어서 아래 항목의 계약상 키·타입·함수 이름 정합성을 문서 기준으로 확인할 수 없음:
  - A 입력란 label/문맥/단위/위치/편집 가능 여부
  - fieldId / value / 원문 블록 ID / 근거 인용
  - B가 원문 그대로 보존되는지(SourceBlock) 여부
  - 표 행·열 위치, 제목, 병합 문맥
  - 사용자 선택/수동 수정 보존
  - 원본 A 해시 확인과 선택 구간 편집
  - API 요청/응답/오류/전송 크기 제한
  - Solar가 XML을 만들지 않고 서버가 근거와 편집 범위를 다시 검증하는 규칙
- 현재 코드만으로는 "계약과 다르다/같다"를 판정할 수 없고, 문서 부재로 인해 판단 유보함.

## 실행하지 않은 검사

- 공통 계약(`TEAM_CONTRACT.md`, `DESIGN.md`, `WORK_RULES.md`)이 없어서 정합성 검사 자체를 문서 기준으로 수행하지 않음.
- "문서 엔진과 HWPX 분석/편집 코드를 서비스 담당 범위에서 건드리지 않는다"는 원칙의 경계는 hwpx_lib와 api의 물리적 분리 기준으로는 유지했으나, TEAM_CONTRACT 기준 경계가 없으므로 계약상 위반 여부는 미확인.
- docs/state/service.md 기록 시점 기준, 실제 서비스 동작을 다시 검증하는 통합 테스트는 수행하지 않음.
ENDOFFILE && \
echo "=== 생성 완료 ===" && wc -l docs/state/service.md && echo "" && echo "=== 현재 Git 상태 ===" && git status --short
