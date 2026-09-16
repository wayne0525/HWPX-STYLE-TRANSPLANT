# docs/contracts/engine.md — 엔진 단계 계약 초안

이 문서는 TEAM_CONTRACT.md의 A 분석 계약을 그대로 따르고,
단계 2~5에서 구현할 함수들의 입출력 형식을 정의한다.

> TEAM_CONTRACT.md의 3~12절을 대체하지 않는다. 이 문서는 그 위에
> 추가 함수(package, fill, verify)의 계약만 덧붙인다.

---

## 0. 공통 규칙

- 모든 함수는 서버 내부 전용이다. 클라이언트가 직접 호출하는 계약이 아니다.
- 입력 파일 경로를 받는 함수는 읽을 수 없으면 분석/처리를 중단하고 실패를 반환한다.
- 추측으로 결과를 만들지 않는다.
- 실패는 이유와 어디까지 진행했는지 함께 남긴다.

---

## 1. `hwpx/package.py`

### 1.1 `open_package(path) -> Package`

HWPX(ZIP) 파일을 열고 내부 구조를 읽을 수 있는 객체(Package)를 반환한다.

**입력**

- `path`: str — HWPX 파일 경로

**반환 `Package`**

```python
@dataclass
class Package:
    path: str                      # 열기 요청한 원본 경로
    is_valid: bool                 # ZIP으로 열리고 mimetype 규칙을 지키는지
    mimetype_first: bool           # mimetype이 첫 엔트리인지
    mimetype_stored: bool          # mimetype이 무압축(ZIP_STORED)인지
    mimetype_content: str          # mimetype 엔트리 텍스트
    entries: list[ZipEntry]        # ZIP 내 모든 엔트리 (순서 유지)
    section_paths: list[str]       # "Contents/section0.xml" 같은 섹션 경로 목록 (순서 유지)
```

```python
@dataclass
class ZipEntry:
    filename: str
    compress_type: int            # zipfile.ZIP_STORED 등
    file_size: int
    bytes: bytes                  # 엔트리 원본 바이트
```

**예외/실패**

- ZIP으로 열리지 않으면 `is_valid=False`, `entries=[]`로 반환한다.
- mimetype이 없거나 첫 엔트리가 아니면 `is_valid=False`로 두고, 처리는 계속한다.
- mimetype이 무압축이 아니면 경고만 남기고 처리는 계속한다 (단계 2 테스트에서 확인).

### 1.2 `file_hash(path) -> str`

파일의 SHA-256 해시를 `"sha256:<hex>"` 형식으로 반환한다.

**입력**

- `path`: str — 파일 경로

**반환**

- `"sha256:"`으로 시작하는 문자열. 예: `"sha256:a1b2c3..."`

**실패**

- 파일을 읽을 수 없으면 예외를 전파한다.

---

## 2. `hwpx/analyze.py`

### 2.1 `analyze_a(path) -> dict`

양식 원본 HWPX 파일 A를 받아 입력란 후보(필드) 목록과 메타데이터를 반환한다.
TEAM_CONTRACT.md §5의 반환값 구조를 그대로 따른다.

**입력**

- `path`: str — HWPX 파일 경로

**반환 dict (JSON 예시와 동일 구조)**

```json
{
  "analysis_id": "a-analyze-<uuid 또는 단조 증가 ID>",
  "a_hash": "sha256:<A의 file_hash 결과>",
  "file_kind": "hwpx",
  "analysis_status": "ok | partial | failed",
  "warnings": ["<문자열>"],
  "failure": null 또는 { "reason": "...", "progress": "..." },
  "fields": [
    {
      "field_id": "f-001",
      "label": "성명",
      "location": {
        "type": "cell",
        "section": "Contents/section0.xml",
        "table_path": [3, 0],
        "row": 2,
        "col": 1
      },
      "context": "라벨 '성명' 오른쪽 셀, 1행 1표",
      "unit": "text",
      "editable": true,
      "required": true,
      "merge_info": null 또는 { "type": "...", "span": {...} },
      "status": "ok" | "pending" | "deferred",
      "notes": null 또는 "..."
    }
  ]
}
```

**필드 설명 (TEAM_CONTRACT.md §5.2에 맞춤)**

- `field_id`: 고유 ID. MVP에서 표 셀만 다루므로 `f-<index>` 형태로 발행.
- `label`: 라벨 셀의 텍스트. 라벨이 없는 경우(헤더행 아래 빈 셀 등)는 빈 문자열 또는 단위/자리표시자 텍스트.
- `location.type`: MVP에서 `"cell"`만 사용.
- `location.section`: 섹션 파일 경로. A가 여러 section을 가지면 문서 순서대로 `section0.xml`, `section1.xml`, ...
- `location.table_path`: 문서 순서대로 센 **최상위 표** 기준. 0-기반 인덱스. 예: `[3, 0]`은 4번째 표의 병합그룹/행 기준이 필요하면 확장하나, MVP에서는 `[표인덱스, 0]` 형태를 쓴다. (TEAM_CONTRACT 예시의 `table_index`와 같은 의미 — 구현 시 키명은 합의가 필요하지만 여기서는 `table_path`로 표기.)
- `location.row`, `location.col`: 셀 주소. `hp:cellAddr`의 colAddr/rowAddr 기준(0-기반).
- `context`: 배경 텍스트(에이전트용). 라벨, 행·열 제목, 구역 정보 포함.
- `unit`: 예상 단위. `text`, `postal-code`, `date`, `number`, `money`, `phone`, `email`, `person-name` 등. 불명확하면 `"text"`나 빈 값.
- `editable`: 편집 가능 여부. MVP에서는 후보가 된 모든 셀을 `true`로 둔다(보호 구간 판단은 아직 미구현). candidates 중 안내문(※)이나 이미 값이 있는 셀은 제외한다.
- `required`: 값이 있으면(빈 셀인데 라벨 존재) `true`로 본다. 없으면 `false`.
- `merge_info`: 병합 셀이면 기록하고, 일반 셀이면 `null`.
- `rule`: 이 후보를 잡은 규칙. `"rule1"`(라벨 셀+오른쪽 빈 셀), `"rule2"`(헤더 행 아래 빈 셀), `"rule3"`(자리표시자/단위만 있는 셀), `"rule4"`(한 셀 안의 "라벨 :" 뒤 빈자리) 중 하나.

**분석 범위와 제외**

MVP(표 셀만 대상)에서 다음을 구현한다:

1. **라벨 셀 + 오른쪽 빈 셀**: 한 셀에 라벨 텍스트가 있고, 그 셀의 바로 오른쪽(동일 행, col+1) 셀이 비어 있으면(empty or whitespace-only) 후보로 잡는다. `label`에는 라벨 셀의 텍스트를 넣는다.
2. **헤더 행 아래의 빈 셀**: 첫 행이 헤더(텍스트 있음)인 표에서, 헤더 행 아래의 빈 셀도 후보로 잡는다. `label`은 빈 문자열, `unit`은 상황에 따라 `"text"` 등.
3. **자리표시자/단위만 있는 셀**: 공백, `"( )"`, `"원"`, `"년 월 일"` 등 자리표시자나 단위만 있는 셀도 후보로 잡되 `unit`에 표시한다. 예: `"( )"` → `unit: "text"`, `"천원"` → `unit: "money"` 등.
4. **한 셀 안의 "라벨 :" 뒤 빈자리**: 한 셀 안에 `라벨 :` 형태로 라벨과 입력 자리가 함께 있는 경우, 콜론 뒤가 비어 있으면 그 자리를 별도 후보로 잡는다. 예: `'직명 :교장성명 :'` → `직명`은 이미 값이 있으므로 후보 아님, `성명`은 콜론 뒤가 비어 후보. `'전화 :팩스 :'` → `전화`, `팩스` 각각 후보. 이 규칙의 후보는 `location`에 셀 좌표 외에도 `paragraph_index`(셀 내 문단 순서), `run_index`(문단 내 run 순서), `insert_offset`(run 텍스트 안에서 콜론 뒤 삽입 위치 문자 오프셋)을 함께 기록한다. 안내문(※로 시작)은 후보에서 제외한다. 단위는 라벨에 따라 `postal-code`, `phone`, `email`, `person-name` 등으로 추정할 수 있다.

**제외**

- 이미 값이 들어 있는 셀(텍스트가 있음, 공백 제외)은 후보에서 제외.
- 안내문(※로 시작하는 텍스트가 있는 셀/문단) 안의 셀은 후보에서 제외.
- 고정 문구 성격의 셀(예: 문서 제목이 들어 있는 셀)은 후보에서 제외.

**병합 셀**

- 병합 셀(`hp:cellSpan`의 colSpan/rowSpan이 1보다 큰 셀)은 `merge_info`에 기록한다.
- 병합으로 인해 실제로 편집할 셀 위치가 모호하면 `status: "deferred"`로 두고 notes에 남긴다.

**중첩 표**

- 셀 안에 표가 또 들어 있을 수 있다. 중첩 표는 `table_path`에 부모 표 인덱스를 포함하지 않고, 별도의 분석 단계로 다룬다. MVP에서는 중첩 표 내부 셀은 후보로 잡지 않는다(추후 확장).

**문서 순서**

- 여러 section이 있으면 `Contents/section0.xml`, `section1.xml`, ... 순서로 처리한다.
- `table_path`의 표 인덱스는 문서 전체의 최상위 표 기준(0-기반)이다.

**실패 케이스**

- HWPX로 읽을 수 없으면 `analysis_status: "failed"` + `failure` 반환.
- section XML이 파싱되지 않으면 부분 결과로 반환하거나 실패 처리.

---

## 3. `hwpx/fill.py`

### 3.1 `fill_a(a_path, analysis, fills, out_path) -> dict`

A 양식의 사본을 만들고, `analysis`로 찾은 입력란 중 `fills`에 지정된 값만 채운 새 HWPX(C)를 저장한다.

**입력**

- `a_path`: str — A HWPX 파일 경로
- `analysis`: dict — `analyze_a`의 반환값. `a_hash`와 `fields`를 포함한다.
- `fills`: list[dict] — 채울 값 목록. 예:
  ```json
  [
    { "field_id": "f-003", "value": "늘배움 평생학교" },
    { "field_id": "f-007", "value": "김하늘" },
    { "field_id": "f-012", "value": "00000" }
  ]
  ```
- `out_path`: str — 결과 C 저장 경로

**반환 dict**

```json
{
  "a_hash": "sha256:<분석 시 A의 해시>",
  "c_path": "<out_path와 동일>",
  "c_hash": "sha256:<결과 C의 해시>",
  "applied": [
    {
      "field_id": "f-003",
      "value": "늘배움 평생학교",
      "location": { "type": "cell", "section": "...", "table_path": [...], "row": 2, "col": 1 },
      "status": "applied",
      "reason": "라벨 '시설명' 오른쪽 빈 셀에 기입"
    }
  ],
  "rejected": [
    {
      "field_id": "f-999",
      "value": "...",
      "reason": "analysis에 없는 field_id",
      "status": "rejected"
    }
  ],
  "warnings": ["<문자열>"],
  "failure": null 또는 { "reason": "..." }
}
```

**동작 규칙 (단계 4 상세와 일치)**

1. **A 해시 검증**: 채우기 전에 A의 현재 해시를 `analysis["a_hash"]`와 비교한다. 다르면 전체를 거부하고 `failure`를 반환한다.
2. **수정 대상**: `analysis.fields` 중 `fills`에 선언된 `field_id`만 수정한다.
   - `editable`이 `false`인 칸은 거부.
   - `analysis.fields`에 없는 `field_id`는 거부.
3. **셀 편집 방식**:
   - 대상 셀의 첫 문단(hp:p)만 수정한다.
   - 그 문단에 `hp:run`이 있고 `hp:t`가 없으면: 기존 run 안에 `hp:t`를 추가한다(run의 `charPrIDRef` 유지).
   - `hp:t`가 있으면: `hp:t`의 텍스트만 바꾼다.
   - run이 아예 없으면: 새로 만들지 않고 거부("거부: run 없음 — 수동 편집 필요").
4. **ZIP 재조립**:
   - 수정한 section 외의 ZIP 엔트리는 원본 바이트를 그대로 복사한다.
   - 저장 시 XML 선언과 인코딩을 원본과 같게 유지한다.
5. **미수정**: `hp:linesegarray`는 건드리지 않는다. 결과 보고에는 "한글에서 열어 줄 배치 확인 필요"를 남긴다(단계 4 보고).

**실패 케이스**

- A 해시가 분석 시점과 다르면 전체 거부.
- ZIP 진입 미흡(mimetype 규칙 위배)이 있으면 실패.
- section XML 파싱 실패 등.

---

## 4. `hwpx/verify.py`

### 4.1 `verify_c(a_path, c_path, analysis, fills) -> dict`

C 결과 HWPX가 A의 보존 규칙을 지키고, `fills`가 의도한 칸에만 적용됐는지 검증한다.

**입력**

- `a_path`: str — 원본 A 경로
- `c_path`: str — 결과 C 경로
- `analysis`: dict — `analyze_a` 결과 (fields, a_hash 포함)
- `fills`: list[dict] — applied에 사용한 fills (field_id, value)

**반환 dict**

```json
{
  "c_openable": true,
  "c_mimetype_ok": true,
  "c_hash": "sha256:...",
  "sections_preserved": true,
  "unchanged_entries_match": true,
  "roundtrip_ok": true,
  "fixed_texts_preserved": true,
  "table_count_match": true,
  "paragraph_count_match": true,
  "edited_cells": [
    {
      "field_id": "f-003",
      "expected": "늘배움 평생학교",
      "actual": "늘배움 평생학교",
      "match": true
    }
  ],
  "unchanged_cells_sample": [
    {
      "location": { "type": "cell", "section": "...", "table_path": [...], "row": 0, "col": 0 },
      "expected_text": "2026년 학력미인정...",
      "actual_text": "2026년 학력미인정...",
      "match": true
    }
  ],
  "warnings": [],
  "failure": null 또는 { "reason": "...", "detail": "..." }
}
```

**검증 항목**

1. **ZIP/mimetype**: C가 ZIP으로 열리고, mimetype이 첫 엔트리·무압축인지.
2. **엔터리 보존**: 수정한 section 외의 모든 엔트리가 A와 바이트 단위로 같은지.
3. **선택 셀만 변경**: 수정한 section에서, 채운 칸의 텍스트를 A의 원래 값으로 되돌렸을 때 A와 XML 트리가 같은지(선택한 칸만 바뀌었음을 증명).
4. **구조 보존**: 표 개수, 문단(hp:p) 개수, 고정 문구(후보가 아닌 모든 `hp:t`)의 텍스트가 A와 같은지.
5. **기입값 확인**: `fills`의 각 값이 C의 해당 위치에 정확히 들어갔는지.

**실패**

- ZIP/mimetype 위배, 엔트리 불일치, 구조 변경 발견, 기입값 불일치 시 `failure` 반환.

---

## 5. field_id / location 표기 합의 (단계 2~5 공통)

TEAM_CONTRACT 예시에서는 `location.table_index`를 썼지만,
이 엔진 단계에서는 `table_path`를 쓴다. 이유는:

- 향후 중첩 표·여러 섹션으로 확장할 때 경로 체계로 쓰기 좋다.
- MVP 표 셀에서는 `table_path: [표인덱스, 0]` 형태로 쓰고,
  표인덱스만 의미가 있다(두 번째 요소는 향후 병합그룹/헤더 구분용 예약).

구현에서 키명이 충돌하면 이 문서를 업데이트한다.
