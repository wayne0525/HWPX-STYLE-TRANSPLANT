# docs/TEAM_CONTRACT.md — HWPX 양식 채움 공통 계약

이 문서는 A 분석, B 추출, 규칙 연결, Solar 제안, 근거 검증, 사용자 보정과 편집, 생성, 보고서·미리보기와 API의 공통 계약을 정한다.

## 1. 목적

A 분석 계약(`hwpx/analyze.py`)은 양식 원본 HWPX 파일 A를 받아
채움 대상의 입력란 후보와 구조 정보를 반환한다.
이 계약의 목적은 “어디를 채울 수 있는지”를 정리하는 것이며,
실제 채우기는 하지 않는다.

## 2. 함수 이름과 경로

- 경로: `hwpx/analyze.py`
- 함수 이름: `analyze_a`
- 상태: 설계 단계(아직 구현하지 않음)

이 함수는 서버 내부에서만 호출하는 것을 전제로 한다.
클라이언트가 직접 호출하는 계약이 아니다.

## 3. 입력

### 3.1 파일 입력

- 파일 입력은 `name`과 `base64`를 문자열로 받는다.
- `name`은 파일 이름이다.
- `base64`는 원본 파일의 내용이다.
- A는 HWPX 파일 또는 HWPX로 읽을 수 있는 ZIP 패키징으로 받는다.
- A는 양식 원본이며, 표·문단·고정 문구·서식·페이지 설정을 포함한다.
- 읽지 못하거나 열 수 없으면 분석을 중단한다.
- 추측으로 분석 결과를 만들지 않는다.

### 3.2 B의 입력 종류

- B는 `kind`로 구분한다.
- `kind` 값은 `hwpx`, `txt`, `md` 중 하나로 적는다.
- 붙여넣기는 UTF-8 텍스트 파일 입력과 같은 방식으로 처리한다.
- B가 파일인지 붙여넣기인지 같은 출처 정보는 함께 받을 수 있다.
- B는 내용 원본이며, 서식은 이 계약에서 다루지 않는다.

### 3.3 원본 해시

- 입력과 함께 원본 A의 해시를 받는다.
- 해시는 이후에 A의 변경 여부를 다시 확인하는 데 쓴다.
- 모든 문서 해시는 해당 원본 바이트의 SHA-256을 소문자 16진수 64자리로 적는다.
- `sha256:` 같은 접두사는 붙이지 않는다.

### 3.4 부가 정보

- 필요시 분석 옵션이나 제한 조건을 함께 받을 수 있다.
- 지금은 필수 입력 외의 부가 옵션을 contracts로 열거하지 않는다.

## 4. 반환값 개요

반환값은 다음 두 부분으로 구성된다.

1. 분석 결과 메타데이터
2. 입력란 목록

반환값은 서버 내부 표현과 화면 표현을 구분해야 한다.
같은 객체 안에 편집 위치 정보와 화면 표시 위치 정보를 섞지 않는다.

## 5. 반환값 구조

### 5.1 분석 결과 메타데이터

메타데이터는 다음을 포함한다.

- `analysis_id`
  - 이 분석 결과를 구분하는 식별자
- `a_hash`
  - 입력 원본 A의 해시
- `file_kind`
  - 입력 파일의 종류나 판독 결과
- `analysis_status`
  - 정상 분석인지, 부분 분석인지, 실패인지
- `warnings`
  - 분석 중 남긴 경고 목록
- `failure`
  - 분석 실패 시 실패 이유와 구분 정보
  - 실패가 없으면 이 항목은 포함하지 않거나 빈 값으로 둔다.

- `normalizedIndex`
  - B 원문 블록 ID와 검색·대조용 정리 텍스트를 짝지은 맵
  - 타입: 객체 또는 null
  - 이 문서에서 B가 아직 추출되지 않았으면 null로 둔다.
  - A 분석 결과가 A 전용 결과만 담는 경우에는 포함하지 않는다.

### 5.2 입력란 목록

입력란 목록은 배열이며, 각 입력란은 다음 필드를 가진다.

#### 필수 필드

- `fieldId`
  - 입력란을 구분하는 고유 ID
  - 같은 A를 다시 분석해도 이 ID는 같아야 한다.
  - 서버 내부에서 일관되게 사용한다.

- `candidateId`
  - 분석 결과 안에서 이 후보를 구분하는 식별자
  - 화면과 검토 흐름에서 후보를 가리킬 때 사용한다.
  - 편집 위치 자체는 아니다.

- `label`
  - 화면과 판단에 쓰는 라벨
  - 라벨과 실제 입력 위치는 서로 다른 정보다.

- `originalText`
  - 입력란 주변에서 읽은 원본 텍스트
  - 분석 시점의 라벨, 안내문, 주변 문장 등 원본에 있는 텍스트를 기록한다.
  - 채움값이 아니다.

- `context`
  - 주변 문맥
  - 문자열 목록으로 받는다.
  - 주변 텍스트, 라벨, 행·열 제목, 구역 정보 등을 포함한다.

- `unit`
  - 예상되는 단위 정보
  - 문자열 또는 null이다.
  - 단위가 불명확하면 null로 두고 자동 확정하지 않는다.

- `editable`
  - 편집 가능 여부
  - 편집 가능 구간인지, 보호 구간인지 구분한다.

- `status`
  - 필드 단위 상태
  - 타입: 문자열 또는 null
  - 예: normal, pending, blocked, ambiguous
  - 분석 결과의 전체 상태가 아니라 개별 입력란 수준의 상태다.

- `location`
  - 서버 내부 편집 위치 정보
  - 표·문단·셀·섹션 등 편집 대상 위치를 기술한다.
  - 화면 좌표와는 다르다.
  - 각 정보는 객체 타입으로 명시하고, 해당하지 않으면 null로 둔다.

`location`은 다음 필드를 가진다.

- `section`
  - 구역 정보
  - 해당 구역이 있으면 구역 식별 정보를 적고, 없으면 null로 둔다.
  - 타입: 객체 또는 null

- `paragraph`
  - 문단 정보
  - 해당 문단이 있으면 문단 식별 정보를 적고, 없으면 null로 둔다.
  - 타입: 객체 또는 null

- `table`
  - 표 정보
  - 해당 표가 있으면 표 식별 정보를 적고, 없으면 null로 둔다.
  - 타입: 객체 또는 null

- `row`
  - 행 정보
  - 해당 행이 있으면 행 식별 정보를 적고, 없으면 null로 둔다.
  - 타입: 객체 또는 null

- `column`
  - 열 정보
  - 해당 열이 있으면 열 식별 정보를 적고, 없으면 null로 둔다.
  - 타입: 객체 또는 null

`location`의 각 항목은 편집 대상 구조를 식별하기 위한 정보이며,
서로 다른 항목을 같은 필드에 섞지 않는다.
예를 들어 표 셀 입력란은 table, row, column을 함께 갖고,
단순 문단 입력란은 paragraph만 가질 수 있다.

## 6. 서버 내부 위치와 화면 위치의 구분

- `location`은 서버 내부 편집 위치다.
  - 결과를 만들 때 실제로 수정하는 위치를 식별한다.
- 화면에 보여 주는 위치는 별도 표현으로 변환한다.
  - 사용자에게는 candidate ID와 구조 위치 정도만 보여 준다.
  - 실제 편집 좌표는 클라이언트나 화면에 그대로 노출하지 않는다.
- 클라이언트가 새 좌표를 지정해 편집 위치를 바꾸지 못하게 한다.

## 7. 필수 값과 선택 값

- 필수 값은 `required` 표시가 있는 입력란으로 다룬다.
- 선택 값은 `required`가 없거나 명시적으로 선택으로 표시된 입력란으로 다룬다.
- 빈 입력란 목록과 편집 가능 구간 밖의 고정 문단을 구분한다.
- 분석 시점에 값을 채우거나 추정하지 않는다.

## 8. 빈 입력란 목록과 분석 실패

### 8.1 빈 입력란 목록

- A에 입력 후보가 없으면 빈 목록을 반환할 수 있다.
- 빈 목록인 경우에도 메타데이터와 해시는 반환한다.
- “빈 목록”과 “분석 실패”는 구분해야 한다.

### 8.2 분석 실패

- 분석 실패는 읽기 실패, 구조 파악 실패, 허용되지 않은 형식 등으로 구분한다.
- 실패 시에는 실패 이유와 함께 어떤 단계까지 진행했는지 남긴다.
- 실패한 항목 때문에 정상 제안이나 정상 분석 결과를 버리지 않는다.
- 분석은 실패를 감추지 않고 그대로 표시한다.

## 9. 작은 반환 예시

아래는 설계 예시이며 실제 구현 결과가 아니다.

```json
{
  "analysis_id": "a-analyze-001",
  "a_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "file_kind": "hwpx",
  "analysis_status": "partial",
  "warnings": [
    "표의 일부 셀은 병합 범위를 확정하지 못해 후보로만 남김"
  ],
  "fields": [
    {
      "fieldId": "f-001",
      "candidateId": "c-001",
      "label": "성명",
      "originalText": "성명",
      "context": ["라벨 '성명'", "표 1행"],
      "unit": "text",
      "editable": true,
      "required": true,
      "status": "normal",
      "location": {
        "section": "section0.xml",
        "paragraph": "p-12",
        "table": "t-001",
        "row": 2,
        "col": 1
      }
    },
    {
      "fieldId": "f-002",
      "candidateId": "c-002",
      "label": "우편번호",
      "originalText": "우편번호",
      "context": ["주소 구역", "행 제목: 우편번호"],
      "unit": "postal-code",
      "editable": true,
      "required": false,
      "status": "pending",
      "location": {
        "section": "section0.xml",
        "paragraph": "p-18",
        "table": "t-002",
        "row": 5,
        "col": 2
      }
    }
  ]
}
```

이 예시에서
- `location`은 서버 내부 편집 위치 정보다.
- 화면에는 `fieldId`와 라벨, 구조 위치 정도만 보여 준다.
- `unit`이 불명확하면 자동 확정하지 않는다.
- `location`은 11.5의 서버 내부 위치 객체와 같은 키와 타입을 사용한다.

## 10. 계약 범위

이 문서는 A 분석, B 추출, 규칙 연결, Solar 제안, 근거 검증, 사용자 보정과 편집, 생성, 보고서/미리보기, API 계약을 다룬다.

## 11. B 추출 계약

B 추출 계약(`hwpx/source.py`)은 내용 원본 B를 받아
원문 블록과 근거 정보를 반환한다.
이 계약의 목적은 B에서 내용과 출처를 보존해
나중에 규칙 연결과 근거 검사에 쓸 수 있게 하는 것이며,
실제 채움이나 서식 이식은 하지 않는다.

### 11.1 함수 이름과 경로

- 경로: `hwpx/source.py`
- 함수 이름: `extract_b`
- 상태: 설계 단계(아직 구현하지 않음)

이 함수도 서버 내부에서만 호출하는 것을 전제로 한다.
클라이언트가 직접 호출하는 계약이 아니다.

### 11.2 입력

#### 11.2.1 입력 형태

- B는 HWPX, TXT, Markdown 파일 또는 붙여넣은 텍스트로 받는다.
- 입력과 함께 원본 B의 해시를 받는다.
- B가 파일인지 붙여넣기인지 같은 출처 정보를 함께 받을 수 있다.
- B는 내용 원본이며, 서식은 이 계약에서 다루지 않는다.

#### 11.2.2 지원하지 않는 입력

- 지원하지 않는 형식이거나 읽을 수 없으면 추출을 중단한다.
- 억지로 다른 형식으로 가정하지 않는다.
- 형식 판단이 애매하면 그 사실을 남겨야 한다.

### 11.3 반환값 개요

반환값은 다음 두 부분으로 구성된다.

1. 추출 메타데이터
2. 원문 블록 목록

원문 블록은 문서 순서대로 정리한다.
검색용으로 정리한 텍스트는 원문과 구분해 따로 관리한다.

### 11.4 추출 메타데이터

메타데이터는 다음을 포함한다.

- `extract_id`
  - 이 추출 결과를 구분하는 식별자
- `b_hash`
  - 입력 원본 B의 해시
- `source_kind`
  - B가 파일인지, 붙여넣기인지, 혹은 판독이 애매한지
- `file_format`
  - 지원 형식으로 판독한 경우 그 형식
- `extract_status`
  - 타입: 문자열
  - 가능한 값: `extracted`, `partial`, `empty`, `unsupported`, `failed`
- `warnings`
  - 추출 중 남긴 경고 목록
- `missing`
  - 추출하지 못한 부분의 사유 목록
  - 타입: `Problem` 배열
- `failure`
  - 추출 실패 시 실패 이유와 구분 정보
  - 타입: `Problem` 또는 null
  - 실패가 없으면 이 항목은 포함하지 않거나 빈 값으로 둔다.

### 11.5 위치 객체 규칙

위치 정보는 서버 내부 편집 위치 정보와 화면 표시용 위치 정보로 구분한다.

#### 서버 내부 위치 객체

- 위치 객체의 기본 키는 `section`, `paragraph`, `table`, `row`, `col`이다.
- `section`: 문자열
- `paragraph`: 문자열
- `table`: 문자열 또는 null
- `row`: 정수 또는 null
- `col`: 정수 또는 null
- 해당 구조가 없으면 null로 둔다.
- 표 문맥인 `tableId`, `rowHeaders`, `columnHeaders`, `columnGroup`, `mergedRange`는 `location`에 넣지 않고 원문 블록의 표 관련 필드나 `context`에 둔다.
- 붙여넣기 텍스트는 `section`을 `pasted-text`, `paragraph`를 안정적인 블록 ID로 적고 표 위치는 null로 둔다.
- XML 경로, 바이트 위치, 화면 좌표는 이 객체에 넣지 않는다.
- 클라이언트나 화면에 보내는 안전한 위치 정보는 아래 화면 표시용 구조만 사용한다.

#### 화면 표시용 위치 표현

- 화면에 보여 주는 위치는 `fieldId`, `label`, `section`, `tableId`, `row`, `col`, `context`만 사용한다.
- 이 정보만으로 새 위치를 만들거나 편집 위치를 수정할 수 없게 한다.
- 실제 편집 위치는 서버에서 다시 계산한다.

#### 긴 블록 나누기

- UTF-8 기준 6000바이트를 넘는 원문 블록은 문자 경계를 깨지 않고 나눈다.
- 나뉜 조각은 `parentSourceBlockId`, `partIndex`, `partCount`를 남긴다.
- `partIndex` 순서로 `text`를 합치면 원문과 정확히 같아야 한다.
- 원문을 복원하거나 문서에 넣을 때 `normalizedText`를 사용하지 않는다.

- `sourceBlockId`
  - 원문 블록을 구분하는 고유 ID
  - 같은 B에서는 안정적으로 유지되어야 한다.
  - 서버 내부에서 일관되게 사용한다.
  - 타입: 문자열

- `kind`
  - 블록 종류
  - 타입: 문자열
  - 예: paragraph, heading, list-item, table, table-row, table-cell, misc

- `text`
  - 원문 텍스트
  - 타입: 문자열
  - 원문 그대로 둔다.
  - 가능한 한 원문의 텍스트와 순서를 보존한다.

- `order`
  - 문서에서의 순서
  - 타입: 정수
  - 같은 원본 안에서는 이 순서로 원문을 재결합할 수 있어야 한다.

- `context`
  - 문맥 정보
  - 타입: 문자열 목록
  - 제목 계층, 표 제목, 구역, 행·열 제목, 병합 관계 등 해석에 필요한 문맥을 남긴다.

- `sourceLocation`
  - 출처 위치
  - 타입: 객체 또는 null
  - 파일 안 위치, 섹션, 표·행·열, 붙여넣기 위치 등 근거를 확인할 수 있는 정보를 담는다.
  - 해당 정보가 없으면 null로 둔다.

#### 표 관련 필드

표 블록은 값과 함께 표 문맥을 보존한다.

- `tableId`
  - 표 식별자
  - 타입: 문자열 또는 null
  - 표 블록이나 표 셀 블록에서 표를 가리킬 때 사용한다.
  - 해당 표가 없으면 null로 둔다.

- `rowPosition`
  - 표에서의 행 위치
  - 타입: 정수 또는 null
  - 해당 행이 없으면 null로 둔다.

- `columnPosition`
  - 표에서의 열 위치
  - 타입: 정수 또는 null
  - 해당 열이 없으면 null로 둔다.

- `rowTitles`
  - 행 제목
  - 타입: 문자열 목록 또는 null

- `columnTitles`
  - 열 제목
  - 타입: 문자열 목록 또는 null

- `mergeInfo`
  - 병합 관계 정보
  - 타입: 객체 또는 null
  - 병합 셀이나 여러 항목이 함께 있는 칸이 있으면 그 관계를 남긴다.

#### 제목 계층 문맥

제목 계층은 별도 구조 객체로 강제하지 않고, `context`에 문맥으로 남긴다.
필요하면 계층 정보를 담은 객체를 `context` 항목으로 포함할 수 있다.

#### 검색용 정규화 텍스트

- `normalizedText`
  - 검색·대조용으로 정리한 텍스트
  - 타입: 문자열 또는 null
  - `text`와 같은 필드로 섞지 않는다.
  - 원문과 별도로 관리한다.
  - 원문 블록 ID로 원문과 정리 텍스트를 함께 참조할 수 있어야 한다.

#### 선택 필드

- `notes`
  - 판단에 필요한 추가 메모
  - 타입: 문자열 또는 null
  - 채움값이 아니다.

- `status`
  - 블록 상태
  - 타입: 문자열 또는 null
  - 예: normal, partial, uncertain, skipped, empty

### 11.6 원문과 검색용 정리 텍스트의 구분

- `text`는 원문 그대로다.
- `normalizedText`는 검색·대조용으로 정리한 텍스트다.
- 두 텍스트를 같은 필드로 섞지 않는다.
- 외부 화면에 보이는 값을 그대로 근거처럼 쓰지 않는다.
- 원문 블록 ID로 원문과 정리 텍스트를 함께 참조할 수 있어야 한다.

### 11.7 B의 서식을 가져오지 않음

- B는 내용 원본이므로, B의 서식·스타일 ID·이미지 개체·페이지 나누기를
  결과 문서의 A 서식으로 가져오지 않는다.
- 이미지·비텍스트 개체는 위치와 종류만 메타데이터로 기록한다. 실제 분석이 없으면 텍스트 근거로 사용하지 않는다.
- 표 구조는 값의 의미를 판단하는 데만 사용한다.
- 추출 과정에서 B의 글꼴이나 스타일 참조를 결과에 기록하지 않는다.

### 11.8 필수 키와 선택 키의 타입

#### 필수 키

- `sourceBlockId`: 문자열
- `kind`: 문자열
- `text`: 문자열
- `order`: 정수
- `context`: 문자열 목록
- `sourceLocation`: 객체 또는 null

#### 표 관련 선택 키

- `tableId`: 문자열 또는 null
- `rowPosition`: 정수 또는 null
- `columnPosition`: 정수 또는 null
- `rowTitles`: 문자열 목록 또는 null
- `columnTitles`: 문자열 목록 또는 null
- `mergeInfo`: 객체 또는 null

#### 일반 선택 키

- `normalizedText`: 문자열 또는 null
- `parentSourceBlockId`: 문자열 또는 null
- `partIndex`: 정수 또는 null
- `partCount`: 정수 또는 null
- `notes`: 문자열 또는 null
- `status`: 문자열 또는 null

### 11.9 빈 내용, 지원하지 않는 형식, 추출 실패, 일부 누락의 반환 방식

#### 11.9.1 빈 내용

- B에 내용이 없으면 빈 블록 목록을 반환할 수 있다.
- 빈 목록인 경우에도 메타데이터와 해시는 반환한다.
- “빈 내용”과 “추출 실패”는 구분해야 한다.
- 이 경우 `extract_status`는 `empty`다.

#### 11.9.2 지원하지 않는 형식

- 지원하지 않는 형식이면 추출을 중단한다.
- 형식을 억지로 가정하지 않는다.
- 이 사실은 `failure`에 남기고, `extract_status`는 `unsupported`다.

#### 11.9.3 추출 실패

- 읽기 실패, 구조 파악 실패, 허용되지 않은 형식 등으로 구분할 수 있다.
- 아무 블록도 보존하지 못한 실패의 `extract_status`는 `failed`다.
- 실패 시에는 실패 이유와 함께 어떤 단계까지 진행했는지 남긴다.
- 추출한 부분이 있으면 그 부분은 블록으로 남기고, 나머지는 누락으로 표시한다.
- 실패한 항목 때문에 정상적인 블록까지 버리지 않는다.

#### 11.9.4 일부 누락

- 일부만 추출했으면 추출하지 못한 부분을 `missing`으로 남긴다.
- 일부 블록을 보존한 상태에서 누락이 있으면 `extract_status`는 `partial`이다.
- 누락 사유는 가능한 한 구체적으로 적는다.
- 누락이 있다고 해서 추출한 정상 블록까지 버리지 않는다.

### 11.10 작은 반환 예시

아래는 설계 예시이며 실제 구현 결과가 아니다.

```json
{
  "extract_id": "b-extract-001",
  "b_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "source_kind": "file",
  "file_format": "txt",
  "extract_status": "partial",
  "warnings": [
    "일부 표 셀은 행·열 위치만 확인하고 값은 누락으로 남김"
  ],
  "blocks": [
    {
      "sourceBlockId": "b-001",
      "kind": "heading",
      "text": "2026년 상반기 보고",
      "order": 1,
      "context": ["제목 1", "섹션 0"],
      "sourceLocation": {
        "section": "section0.xml",
        "paragraph": "p-1",
        "table": null,
        "row": null,
        "col": null
      }
    },
    {
      "sourceBlockId": "b-002",
      "kind": "table",
      "text": "성명\t홍길동\n주소\t서울시",
      "order": 2,
      "context": ["표: 기본 정보", "행 제목: 성명, 주소"],
      "sourceLocation": {
        "section": "section0.xml",
        "paragraph": "p-2",
        "table": "t-001",
        "row": 0,
        "col": 1
      },
      "tableId": "t-001",
      "rowPosition": 0,
      "columnPosition": 1,
      "rowTitles": ["성명", "주소"],
      "columnTitles": ["항목", "값"],
      "mergeInfo": null
    },
    {
      "sourceBlockId": "b-003",
      "kind": "table-cell",
      "text": "",
      "order": 3,
      "context": ["표: 기본 정보", "행 제목: 성명, 주소"],
      "sourceLocation": {
        "section": "section0.xml",
        "paragraph": "p-3",
        "table": "t-001",
        "row": 2,
        "col": 1
      },
      "tableId": "t-001",
      "rowPosition": 2,
      "columnPosition": 1,
      "status": "empty",
      "notes": "빈 셀"
    },
    {
      "sourceBlockId": "b-004",
      "kind": "paragraph",
      "text": "매우 긴 문단...",
      "order": 4,
      "context": ["본문"],
      "sourceLocation": {
        "section": "section1.xml",
        "paragraph": "p-12",
        "table": null,
        "row": null,
        "col": null
      },
      "parentSourceBlockId": "b-004-source",
      "partIndex": 0,
      "partCount": 2,
      "normalizedText": "매우 긴 문단...",
      "status": "partial"
    }
  ],
  "normalizedIndex": {
    "b-001": "2026년 상반기 보고",
    "b-002": "성명 홍길동 주소 서울시",
    "b-003": "",
    "b-004": "매우 긴 문단..."
  },
  "missing": [
    {
      "reason": "표 1의 세 번째 행 값이 범위를 벗어나 읽히지 않음",
      "affected": {
        "section": "section1.xml",
        "paragraph": "p-20",
        "table": "t-002",
        "row": 2,
        "col": 0
      }
    }
  ]
}
```

이 예시에서
- `text`는 원문이고, `normalizedIndex`는 검색·대조용 정리 텍스트다.
- 표 블록은 `tableId`, 행·열 위치, 행·열 제목, 병합 정보를 문맥으로 남긴다.
- 제목 계층은 `context`에 문맥으로 남긴다.
- 긴 블록은 `parentSourceBlockId`, `partIndex`, `partCount`로 나누고 원문을 정확히 재결합할 수 있게 한다.
- 빈 셀은 별도 블록으로 남기고 상태를 표시한다.
- 일부만 읽힌 표는 `missing`으로 사유를 남긴다.

## 12. 규칙 연결 계약

규칙 연결 계약(`hwpx/rules.py`)은 A 입력란 후보와 B 원문 블록, B 정규화 텍스트를 받아
규칙 기반으로 채워질 수 있는 후보를 연결한다.
이 계약의 목적은 명확한 근거부터 값 연결을 확정하고, 애매한 항목은 뒤로 남기는 것이다.
실제 편집이나 XML 생성은 하지 않는다.

### 12.1 함수 이름과 경로

- 경로: `hwpx/rules.py`
- 함수 이름: `connect_rules`
- 상태: 설계 단계(아직 구현하지 않음)

이 함수는 서버 내부에서만 호출하는 것을 전제로 한다.
클라이언트가 직접 호출하는 계약이 아니다.

### 12.2 입력

- `fields`
  - A 분석 결과의 입력란 목록
  - 타입: `Field` 배열
- `blocks`
  - B 추출 결과의 원문 블록 목록
  - 타입: `SourceBlock` 배열
- `normalizedIndex`
  - B 원문 블록 ID와 검색·대조용 정리 텍스트를 짝지은 맵
  - 타입: 객체 또는 null
- `aHash`
  - 원본 A의 해시
  - 타입: 문자열

입력란 문맥과 관련 원문만 사용한다.
표 연결과 단위 변환은 이 함수가 맡는다.
Solar에는 입력란 문맥과 관련 원문만 보낸다.

### 12.3 반환값 개요

반환값은 연결 결과 목록과 메타데이터를 포함한다.

- `connect_id`
  - 이 규칙 연결 결과를 구분하는 식별자
  - 타입: 문자열
- `results`
  - 입력란별 연결 결과 목록
  - 타입: `RuleResult` 배열

### 12.4 연결 결과 구조

`RuleResult`는 다음 필드를 가진다.

#### 필수 필드

- `fieldId`
  - 연결 대상 입력란 ID
  - 타입: 문자열
- `status`
  - 연결 상태
  - 타입: 문자열
  - 제안 상태: suggested, review, missing, conflict, analysis_failed.
- `value`
  - 연결·제안된 값
  - 타입: 문자열 또는 null
  - 확정되지 않았으면 null일 수 있다.
- `valueTransform`
  - 값의 변환 방식
  - 타입: 문자열
  - 가능한 값: `none`, `unit`, `extract`, `compose`
- `sourceBlockIds`
  - 근거로 사용한 B 원문 블록 ID 목록
  - 타입: 문자열 배열
  - `evidence`와 같은 내용을 다르게 표현하지 않는다.
- `evidenceQuote`
  - 대표 근거 인용문
  - 타입: 문자열 또는 null
  - `evidence`에 근거가 있으면 첫 번째 항목의 `quote`를 그대로 적는다.
  - `evidence`와 다른 내용을 담지 않는다.
- `evidence`
  - 여러 근거의 목록
  - 타입: `EvidenceEntry` 배열 또는 null
  - 각 항목은 `sourceBlockId`와 `quote`를 짝으로 기록한다.
  - `sourceBlockIds`와 같은 근거를 목록 형태로 풀어 쓴 것이다.
  - 두 필드가 서로 다른 근거를 가리키지 않는다.
- `reason`
  - 연결·제안 이유
  - 타입: 문자열 또는 null
- `needsReview`
  - 검토가 필요한지 여부
  - 타입: 불리언
- `alternatives`
  - 대안이 여러 개일 때 남기는 목록
  - 타입: `AlternativeEntry` 배열 또는 null

#### EvidenceEntry

- `sourceBlockId`
  - 근거 원문 블록 ID
  - 타입: 문자열
- `quote`
  - 근거 인용문
  - 타입: 문자열

#### AlternativeEntry

- `value`
  - 대안 값
  - 타입: 문자열
- `reason`
  - 대안 제안 이유
  - 타입: 문자열 또는 null
- `sourceBlockIds`
  - 대안 근거 블록 ID
  - 타입: 문자열 배열 또는 null

### 12.5 상태 구분

- `suggested`
  - 규칙 연결로 제안할 수 있는 상태
- `review`
  - 사용자가 검토·선택해야 하는 상태
- `missing`
  - 근거가 없어 연결하지 못한 상태
- `conflict`
  - 근거가 서로 충돌한 상태
- `analysis_failed`
  - 연결 이전에 분석 또는 추출 실패로 판단하지 못한 상태

### 12.6 값 변환 구분

- `none`
  - 값 변환 없이 연결
- `unit`
  - 단위 변환을 포함한 연결
- `extract`
  - 원문 추출을 통한 연결
- `compose`
  - 여러 근거를 조합해 만든 연결

복수 사실 조합으로 하나의 값을 만드는 경우에는 모든 근거를 남기고 검토를 요구한다.
근거가 하나로 압축되지 않은 조합 결과는 확정 값으로 쓰지 않는다.
근거 없는 요약이나 창작은 허용하지 않는다.

### 12.7 근거 관계 규칙

- `sourceBlockIds`와 `evidence`는 같은 근거를 서로 다른 형태로 표현한 것이다.
- `evidenceQuote`는 `evidence` 첫 번째 항목의 `quote`이며, 별개의 새 근거가 아니다.
- 세 필드가 서로 다른 내용을 담지 않도록 유지한다.
- evidence는 [{sourceBlockId, quote}, …] 목록으로 하고, sourceBlockIds는 evidence의 ID 목록, evidenceQuote는 evidence가 있으면 첫 번째 quote로 정의한다. sourceBlockIds 또는 evidenceQuote가 evidence와 일치하지 않으면 검증 실패로 처리한다.
- 대안이 여러 개면 `alternatives`에 남기고, 대표 값은 `value`에 둔다.

### 12.8 작은 반환 예시

아래는 설계 예시이며 실제 구현 결과가 아니다.

```json
{
  "connect_id": "connect-001",
  "results": [
    {
      "fieldId": "f-001",
      "status": "suggested",
      "value": "홍길동",
      "valueTransform": "extract",
      "sourceBlockIds": ["b-002"],
      "evidenceQuote": "성명\t홍길동",
      "evidence": [
        {
          "sourceBlockId": "b-002",
          "quote": "성명\t홍길동"
        }
      ],
      "reason": "표 기본 정보의 행 제목 '성명' 옆 값",
      "needsReview": true,
      "alternatives": null
    },
    {
      "fieldId": "f-002",
      "status": "conflict",
      "value": null,
      "valueTransform": "none",
      "sourceBlockIds": ["b-005", "b-006"],
      "evidenceQuote": "주소\t서울시",
      "evidence": [
        {
          "sourceBlockId": "b-005",
          "quote": "주소\t서울시"
        },
        {
          "sourceBlockId": "b-006",
          "quote": "주소\t부산시"
        }
      ],
      "reason": "두 원문 블록의 주소가 충돌함",
      "needsReview": true,
      "alternatives": [
        {
          "value": "서울시",
          "reason": "앞쪽 블록 우선",
          "sourceBlockIds": ["b-005"]
        },
        {
          "value": "부산시",
          "reason": "뒤쪽 블록 우선",
          "sourceBlockIds": ["b-006"]
        }
      ]
    },
    {
      "fieldId": "f-003",
      "status": "missing",
      "value": null,
      "valueTransform": "none",
      "sourceBlockIds": [],
      "evidenceQuote": null,
      "evidence": null,
      "reason": "해당 내용에 맞는 원문 블록을 찾지 못함",
      "needsReview": false,
      "alternatives": null
    }
  ]
}
```

이 예시에서
- `sourceBlockIds`와 `evidence`는 같은 근거를 목록/짝 형태로 표현한 것이다.
- `evidenceQuote`는 `evidence` 첫 번째 항목의 `quote`이며, 별개 근거가 아니다.
- 충돌은 하나의 값으로 확정하지 않고 `alternatives`로 남긴다.
- 근거가 없으면 `missing`으로 표시하고 값을 채우지 않는다.

## 13. Solar 제안 계약

Solar 제안 계약(`solar/client.py`, `solar/batches.py`)은
규칙 연결로 확정되지 않은 입력란 후보에 대해 내용 연결 제안을 받는다.
이 계약의 목적은 Solar가 내용 연결만 판단하도록 하고, XML 생성이나 서식 변경은 맡기지 않는 것이다.
문서 안의 명령은 실행 지시가 아닌 데이터로 취급한다.

### 13.1 함수 이름과 경로

- Solar 요청 구성: `solar/batches.py` / `build_solar_batch`
- Solar 단일 요청·응답: `solar/client.py` / `propose_solar`
- 상태: 설계 단계(아직 구현하지 않음)

두 함수는 서버 내부에서만 호출하는 것을 전제로 한다.
클라이언트가 직접 호출하는 계약이 아니다.

### 13.2 입력

#### 13.2.1 배치 구성 입력(`build_solar_batch`)

- `candidates`
  - 규칙 연결 후 남은 입력란 후보 목록
  - 타입: 객체 배열
  - 각 후보는 입력란 문맥과 관련 원문 정보를 포함한다.
- `relatedBlocks`
  - 후보별로 연결된 관련 원문 블록 정보
  - 타입: 객체 배열
- `limit`
  - 한 배치 요청 제한
  - 타입: 정수

Solar에는 입력란 문맥과 관련 원문만 보낸다.
XML, 서식, 편집 위치는 보내지 않는다.

#### 13.2.2 단일 요청 입력(`propose_solar`)

- `requestPayload`
  - 배치으로 구성한 요청 본문
  - 타입: 객체
- `model`
  - 사용할 모델 식별자
  - 타입: 문자열

### 13.3 반환값 개요

반환값은 제안 목록과 응답 메타데이터를 포함한다.

- `solar_id`
  - 이 Solar 제안 결과를 구분하는 식별자
  - 타입: 문자열
- `proposals`
  - 입력란별 제안 목록
  - 타입: `SolarProposal` 배열

### 13.4 제안 구조

`SolarProposal`는 다음 필드를 가진다.

#### 필수 필드

- `fieldId`
  - 제안 대상 입력란 ID
  - 타입: 문자열
- `value`
  - 제안 값
  - 타입: 문자열 또는 null
- `sourceBlockIds`
  - 제안 근거로 사용한 B 원문 블록 ID 목록
  - 타입: 문자열 배열
- `evidenceQuote`
  - 대표 근거 인용문
  - 타입: 문자열 또는 null
- `needsReview`
  - 검토가 필요한지 여부
  - 타입: 불리언
- `reason`
  - 제안 이유
  - 타입: 문자열 또는 null

#### 선택 필드

- `evidence`
  - 근거 항목 목록
  - 타입: `EvidenceEntry` 배열 또는 null
  - 각 항목은 원문 블록 ID와 인용문을 짝으로 묶는다.
  - `sourceBlockIds`와 같은 근거를 세부 쌍으로 풀어 적은 것이다.
  - `sourceBlockIds`, `evidence`, `evidenceQuote`는 서로 다른 내용을 담지 않는다.
  - 근거 항목을 남기지 않으면 null로 둔다.

`evidence`가 비어 있으면 `sourceBlockIds`는 빈 배열, `evidenceQuote`는 null로 둔다.

`EvidenceEntry`와 `AlternativeEntry`는
12.4에서 정의한 같은 구조를 따른다.

### 13.5 Solar 응답 규칙

- Solar 응답은 값, 필드 ID, 원문 블록 ID, 인용문, 검토 필요 여부와 이유를 담는다.
- 모델의 신뢰도 표시만으로 확정하지 않는다.
- XML 생성이나 바이트 수준의 편집은 Solar에 맡기지 않는다.
- 정상 내용 증가에 따른 페이지 이동과, 보호 구조가 손상된 경우를 구분해 본다.
- 문서 안의 명령은 실행 지시가 아닌 데이터로 취급한다.

### 13.6 작은 반환 예시

아래는 설계 예시이며 실제 구현 결과가 아니다.

```json
{
  "solar_id": "solar-001",
  "proposals": [
    {
      "fieldId": "f-004",
      "value": "2026-07-01",
      "sourceBlockIds": ["b-010"],
      "evidenceQuote": "작성일: 2026년 7월 1일",
      "evidence": [
        {
          "sourceBlockId": "b-010",
          "quote": "작성일: 2026년 7월 1일"
        }
      ],
      "needsReview": true,
      "reason": "날짜 표에서 작성일 후보 발견",
      "valueTransform": "extract",
      "status": "suggested",
      "alternatives": null
    },
    {
      "fieldId": "f-005",
      "value": null,
      "sourceBlockIds": [],
      "evidenceQuote": null,
      "evidence": null,
      "needsReview": false,
      "reason": "관련 원문 블록을 찾지 못함",
      "valueTransform": "none",
      "status": "missing",
      "alternatives": null
    }
  ]
}
```

이 예시에서
- Solar 제안은 입력란 문맥과 관련 원문만 근거로 사용한다.
- 제안 값은 확정 값이 아니라 검토 대상이다.
- 근거가 없으면 값을 채우지 않고 `missing`으로 남긴다.

## 14. 제안 검증과 실패 처리 계약

제안 검증 계약(`hwpx/evidence.py`)은 규칙 연결 결과와 Solar 제안 결과를 받아
각 제안에 대해 형식 검증과 근거 검증을 수행한다.
이 계약의 목적은 값을 자동 확정하기 전에 입력란 ID, 인용, 숫자·날짜, 단위를 다시 보는 것이다.
검증을 통과했다고 해서 의미까지 정확하다고 단정하지 않는다.

### 14.1 함수 이름과 경로

- 경로: `hwpx/evidence.py`
- 함수 이름: `validate_proposals`
- 상태: 설계 단계(아직 구현하지 않음)

이 함수는 서버 내부에서만 호출하는 것을 전제로 한다.
클라이언트가 직접 호출하는 계약이 아니다.

### 14.2 입력

- `fields`
  - A 분석 결과의 입력란 목록
  - 타입: `Field` 배열
- `results`
  - 규칙 연결 결과 목록
  - 타입: `RuleResult` 배열
- `proposals`
  - Solar 제안 결과 목록
  - 타입: `SolarProposal` 배열
- `blocks`
  - B 추출 결과의 원문 블록 목록
  - 타입: `SourceBlock` 배열
- `normalizedIndex`
  - B 원문 블록 ID와 검색·대조용 정리 텍스트를 짝지은 맵
  - 타입: 객체 또는 null
- `userEdits`
  - 사용자가 직접 수정한 값 목록
  - 타입: `UserEdit` 배열 또는 null

`userEdits`는 사용자가 직접 입력한 값과 선택 상태를 담는다.
근거 없는 자동 제안과 사용자가 직접 입력한 값은 구분해서 기록한다.

#### UserEdit

- `fieldId`
  - 수정 대상 입력란 ID
  - 타입: 문자열
- `value`
  - 사용자 입력 값
  - 타입: 문자열 또는 null
- `source`
  - 사용자 직접 입력 여부
  - 타입: 문자열
  - 가능한 값: `manual`, `selected`, `rejected`
- `note`
  - 사용자 메모
  - 타입: 문자열 또는 null

### 14.3 반환값 개요

반환값은 검증 결과와 오류·경고 목록을 포함한다.

- `validation_id`
  - 이 검증 결과를 구분하는 식별자
  - 타입: 문자열
- `checked`
  - 검증한 항목 목록
  - 타입: `ValidationEntry` 배열
- `errors`
  - 오류 목록
  - 타입: `Problem` 배열
- `warnings`
  - 경고 목록
  - 타입: `Problem` 배열

### 14.4 검증 항목 구조

`ValidationEntry`는 다음 필드를 가진다.

- `fieldId`
  - 대상 입력란 ID
  - 타입: 문자열
- `source`
  - 값의 출처
  - 타입: 문자열
  - 가능한 값: `rule`, `solar`, `user`, `unmatched`
- `status`
  - 검증 상태
  - 타입: 문자열
  - 가능한 값: `ok`, `review`, `blocked`, `failed`
- `value`
  - 검증 대상 값
  - 타입: 문자열 또는 null
- `notes`
  - 검증 메모
  - 타입: 문자열 또는 null

### 14.5 자동 확정 금지 규칙

다음 경우에는 값을 자동 확정하지 않는다.

- 존재하지 않는 입력란 ID를 참조하는 제안
- 원문에 없는 인용을 근거로 사용하는 제안
- 근거와 다른 숫자나 날짜를 담은 제안
- 단위가 불명확한 제안
- 단위 변환 결과가 원래 값과 변환 근거로 재검증되지 않는 제안

단위 변환은 원래 값과 변환 근거를 함께 남겨 재검증할 수 있어야 한다.
형식 검증을 통과했다는 이유만으로 의미까지 정확하다고 단정하지 않는다.

### 14.6 오류와 경고 형식

`Problem`은 다음 필드를 가진다.

- `type`
  - 문제 종류
  - 타입: 문자열
  - 가능한 값: `unsupported_format`, `read_failed`, `parse_failed`, `content_missing`, `invalid_field_id`, `missing_quote`, `value_mismatch`, `unit_unclear`, `duplicate_response`, `batch_partial_failure`, `call_failed`, `conflict`, `empty_proposal`, `response_missing`, `user_value_protected`, `other`
- `fieldId`
  - 관련 입력란 ID
  - 타입: 문자열 또는 null
- `message`
  - 문제 설명
  - 타입: 문자열
- `severity`
  - 심각도
  - 타입: 문자열
  - 가능한 값: `error`, `warning`
- `detail`
  - 추가 정보
  - 타입: 객체 또는 null

#### 주요 문제 구분

- `unsupported_format`
  - 지원하지 않는 입력 형식인 경우
  - 심각도: error
- `read_failed`
  - 입력 파일을 읽지 못한 경우
  - 심각도: error
- `parse_failed`
  - 파일은 읽었지만 구조를 해석하지 못한 경우
  - 심각도: error
- `content_missing`
  - 일부 내용이나 구조를 추출하지 못한 경우
  - 심각도: warning 또는 error
- `invalid_field_id`
  - 존재하지 않는 입력란 ID를 참조한 경우
  - 심각도: error
- `missing_quote`
  - 원문에 없는 인용을 근거로 사용한 경우
  - 심각도: error
- `value_mismatch`
  - 근거와 다른 숫자나 날짜를 담은 경우
  - 심각도: error
- `unit_unclear`
  - 단위가 불명확한 경우
  - 심각도: warning 또는 error
- `duplicate_response`
  - 같은 입력란에 중복 응답이 온 경우
  - 심각도: warning
- `batch_partial_failure`
  - 일부 배치가 실패한 경우
  - 심각도: warning
- `call_failed`
  - Solar 호출 실패 등 호출 실패가 발생한 경우
  - 심각도: error
- `conflict`
  - 근거가 충돌한 경우
  - 심각도: warning 또는 error
- `empty_proposal`
  - 빈 제안이 포함된 경우
  - 심각도: warning
- `response_missing`
  - 응답이 누락된 경우
  - 심각도: error
- `user_value_protected`
  - 사용자 수정 값이나 선택 상태를 덮어쓰려 한 경우
  - 심각도: error

### 14.7 실패 처리 규칙

- 빈 제안, 응답 누락, 충돌, 호출 실패는 서로 구분해 다룬다.
- 일부 배치가 실패해도 정상 결과는 보존한다.
- 실패한 항목만 다시 처리할 수 있게 남긴다.
- 같은 입력란에 중복 응답이 오면 임의로 마지막 값을 선택하지 않는다.
- 중복 응답은 그대로 표시하고, 자동 선택하지 않는다.

### 14.8 사용자 값과 선택 상태 보호

- 사용자가 수정한 값과 선택 상태는 재분석으로 덮어쓰지 않는다.
- 근거 없는 자동 제안과 사용자가 직접 입력한 값은 구분해서 기록한다.
- 사용자 직접 입력 값은 `userEdits` 출처와 함께 남기고, 자동 제안과 섞어 확정하지 않는다.
- 시스템에서 사용자 선택을 바꾸려면 명시적 재검증과 새 사용자 확인이 필요하다.

### 14.9 작은 반환 예시

아래는 설계 예시이며 실제 구현 결과가 아니다.

```json
{
  "validation_id": "val-001",
  "checked": [
    {
      "fieldId": "f-001",
      "source": "rule",
      "status": "ok",
      "value": "홍길동",
      "notes": "표 기본 정보에서 인용 확인"
    },
    {
      "fieldId": "f-002",
      "source": "solar",
      "status": "blocked",
      "value": "부산시",
      "notes": "근거 인용이 원문과 일치하지 않음"
    },
    {
      "fieldId": "f-003",
      "source": "user",
      "status": "ok",
      "value": "서울시",
      "notes": "사용자 직접 입력 값"
    },
    {
      "fieldId": "f-004",
      "source": "solar",
      "status": "review",
      "value": "2026-07-01",
      "notes": "날짜 형식이 맞으나 의미 검증은 별도 필요"
    }
  ],
  "errors": [
    {
      "type": "missing_quote",
      "fieldId": "f-002",
      "message": "제시된 인용이 원문 블록에서 확인되지 않음",
      "severity": "error",
      "detail": {
        "sourceBlockId": "b-007",
        "quote": "주소\t부산시"
      }
    },
    {
      "type": "duplicate_response",
      "fieldId": "f-005",
      "message": "같은 입력란에 중복 응답이 도착함",
      "severity": "warning",
      "detail": {
        "count": 2
      }
    }
  ],
  "warnings": [
    {
      "type": "unit_unclear",
      "fieldId": "f-006",
      "message": "단위가 불명확해 자동 확정하지 않음",
      "severity": "warning",
      "detail": null
    },
    {
      "type": "batch_partial_failure",
      "fieldId": null,
      "message": "일부 Solar 배치 요청이 실패함",
      "severity": "warning",
      "detail": {
        "failedCount": 1,
        "preservedCount": 3
      }
    }
  ]
}
```

이 예시에서
- 존재하지 않는 입력란 ID, 원문에 없는 인용, 근거와 다른 값은 자동 확정하지 않는다.
- 단위가 불명확하면 경고로 남기고 확정하지 않는다.
- 형식 검증이 통과돼도 의미 정확성은 따로 단정하지 않는다.
- 중복 응답은 마지막 값으로 임의 선택하지 않고 그대로 표시한다.
- 일부 배치 실패는 정상 결과를 보존하고 실패한 항목만 재처리 대상으로 남긴다.
- 사용자 직접 입력 값은 자동 제안과 구분해서 기록한다.

## 15. 후보 보정과 사용자 편집 계약

후보 보정 계약과 사용자 편집 계약은
입력란 후보 표시를 조정하고, 사용자가 선택한 값만 결과에 반영하게 하는 범위를 정한다.
서버 내부의 편집 위치 지정이나 임의 값 확정은 이 계약의 범위가 아니다.

### 15.1 후보 보정 계약

후보 보정 계약(`hwpx/corrections.py`)은
분석 결과의 입력란 후보 표시를 조정한다.

- 경로: `hwpx/corrections.py`
- 함수 이름: `correct_candidates`
- 상태: 설계 단계(아직 구현하지 않음)

이 함수는 서버 내부에서만 호출하는 것을 전제로 한다.
클라이언트가 직접 호출하는 계약이 아니다.

#### 입력

- `fields`
  - A 분석 결과의 입력란 목록
  - 타입: `Field` 배열
- `corrections`
  - 후보 보정 목록
  - 타입: `CandidateCorrection` 배열
- `aHash`
  - 원본 A의 해시
  - 타입: 문자열

#### CandidateCorrection

- `candidateId`
  - 보정 대상 후보 ID
  - 타입: 문자열
- `label`
  - 화면에서 사용할 라벨
  - 타입: 문자열 또는 null
- `enabled`
  - 후보 사용 여부
  - 타입: 불리언

#### 반환값 개요

- `correction_id`
  - 이 보정 결과를 구분하는 식별자
  - 타입: 문자열
- `corrected`
  - 보정된 후보 목록
  - 타입: `CandidateCorrectionResult` 배열
- `warnings`
  - 보정 중 발생한 경고 목록
  - 타입: `Problem` 배열

#### CandidateCorrectionResult

- `candidateId`
  - 대상 후보 ID
  - 타입: 문자열
- `label`
  - 적용된 라벨
  - 타입: 문자열 또는 null
- `enabled`
  - 적용된 사용 여부
  - 타입: 불리언
- `aHash`
  - 이 보정이 연결된 A 해시
  - 타입: 문자열

#### 규칙

- 후보 보정은 `candidateId`, `label`, `enabled`로만 표현한다.
- 사용자는 후보의 라벨과 사용 여부를 바꿀 수 있다.
- 사용자는 서버 내부 편집 위치를 지정할 수 없다.
- 보정 내용은 A 해시와 연결한다.
- 같은 보정 설정을 다른 A에 그대로 적용하지 않는다.
- 교정할 후보 ID가 없거나 이미 처리 범위를 벗어난 경우 오류나 경고로 남긴다.
- 편집 위치, 표·행·열坐标, 내부 좌표 계열 정보는 이 계약에서 받지 않는다.

### 15.2 사용자 편집 계약

사용자 편집 계약(`Edit`)은
사용자가 선택한 값과 상태를 기록한다.
이 계약은 실제 편집 위치를 정하는 계약이 아니라,
사용자가 무엇을 선택했는지와 그 출처를 남기는 계약이다.

#### Edit

- `fieldId`
  - 편집 대상 입력란 ID
  - 타입: 문자열
- `value`
  - 사용자 값
  - 타입: 문자열 또는 null
- `selected`
  - 적용 선택 여부
  - 타입: 불리언
- `origin`
  - 값의 출처
  - 타입: 문자열
  - 가능한 값: `rule`, `solar`, `manual`
- `evidence`
  - 자동 제안의 근거 정보
  - 타입: `EvidenceEntry` 배열 또는 null
- `note`
  - 사용자 메모
  - 타입: 문자열 또는 null

#### 규칙

- `origin`은 `rule`, `solar`, `manual`로 구분한다.
- 자동 제안의 근거 형식은 기존 계약(`RuleResult`, `SolarProposal`의 근거 형식)과 같게 유지한다.
- `evidence`는 `sourceBlockId`와 `quote`를 짝으로 기록한다.
- `evidence`와 `sourceBlockIds`를 서로 다른 내용으로 표현하지 않는다.
- 미선택 항목은 그대로 둔다.
- 빈 제안으로 기존 값을 지우지 않는다.
- 명시적인 수동 비우기는 지원한다.
  - 단, 수동 비우기는 사용자가 명시적으로 선택한 경우에만 적용한다.
  - 빈 값 제안이 들어왔거나, 검토가 끝나지 않은 상태에서 기존 값을 자동으로 지우지 않는다.
- 같은 입력란에 대해 여러 번 편집이 들어오면, 가장 최근의 명시적 선택을 기준으로 기록한다.
- 규칙이나 Solar 제안이라고 해서 자동으로 기존 선택 상태를 덮어쓰지 않는다.

### 15.3 편집 구간 중복 적용 금지

- 서로 겹치는 편집 구간은 중복 적용하지 않는다.
- 두 편집이 같은 입력 구간 또는 같은 표 셀을 가리키면,
  한쪽만 적용하거나 충돌로 표시한다.
- 중복 적용 가능 여부를 추측으로 판단하지 않는다.
- 중복이 있으면 오류나 경고로 남기고, 적용 전 사용자에게 알린다.

### 15.4 편집 검증 계약

편집 검증 계약(`hwpx/evidence.py`)은
후보 보정과 사용자 편집이 서로 충돌하지 않는지 확인한다.

- 경로: `hwpx/evidence.py`
- 함수 이름: `validate_edits`
- 상태: 설계 단계(아직 구현하지 않음)

이 함수는 서버 내부에서만 호출하는 것을 전제로 한다.
클라이언트가 직접 호출하는 계약이 아니다.

#### 입력

- `fields`
  - A 분석 결과의 입력란 목록
  - 타입: `Field` 배열
- `corrections`
  - 후보 보정 목록
  - 타입: `CandidateCorrection` 배열
- `edits`
  - 사용자 편집 목록
  - 타입: `Edit` 배열
- `aHash`
  - 원본 A의 해시
  - 타입: 문자열

#### 반환값 개요

- `validation_id`
  - 이 검증 결과를 구분하는 식별자
  - 타입: 문자열
- `checked`
  - 검증한 항목 목록
  - 타입: `EditValidationEntry` 배열
- `errors`
  - 오류 목록
  - 타입: `Problem` 배열
- `warnings`
  - 경고 목록
  - 타입: `Problem` 배열

#### EditValidationEntry

- `fieldId`
  - 대상 입력란 ID
  - 타입: 문자열
- `source`
  - 값의 출처
  - 타입: 문자열
  - 가능한 값: `candidate_correction`, `user_edit`, `rule`, `solar`, `unmatched`
- `status`
  - 검증 상태
  - 타입: 문자열
  - 가능한 값: `ok`, `review`, `blocked`, `failed`
- `notes`
  - 검증 메모
  - 타입: 문자열 또는 null

#### 주요 검증 항목

- 후보 보정에 존재하지 않는 `candidateId`가 있는지 확인한다.
- 사용자 편집에 존재하지 않는 `fieldId`가 있는지 확인한다.
- 같은 입력란에 대해 편집 구간이 겹치는지 확인한다.
- 선택된 편집이 서로 충돌하는지 확인한다.
- 사용자가 편집 위치를 지정하려고 한 경우 오류로 처리한다.
- 후보 보정과 사용자 편집이 서로 다른 A를 기준으로 섞인 경우 오류나 경고로 남긴다.

### 15.5 작은 반환 예시

아래는 설계 예시이며 실제 구현 결과가 아니다.

```json
{
  "validation_id": "edit-val-001",
  "checked": [
    {
      "fieldId": "f-001",
      "source": "user_edit",
      "status": "ok",
      "notes": "사용자 선택 반영"
    },
    {
      "fieldId": "f-002",
      "source": "candidate_correction",
      "status": "ok",
      "notes": "라벨과 사용 여부만 보정됨"
    },
    {
      "fieldId": "f-003",
      "source": "user_edit",
      "status": "blocked",
      "notes": "편집 구간이 다른 선택과 겹침"
    }
  ],
  "errors": [
    {
      "type": "invalid_field_id",
      "fieldId": "f-999",
      "message": "존재하지 않는 입력란 ID를 편집함",
      "severity": "error",
      "detail": null
    },
    {
      "type": "conflict",
      "fieldId": "f-003",
      "message": "편집 구간이 다른 선택과 겹침",
      "severity": "error",
      "detail": {
        "overlapWith": "f-003-alt"
      }
    }
  ],
  "warnings": [
    {
      "type": "empty_proposal",
      "fieldId": "f-004",
      "message": "빈 제안이 포함됐으나 기존 값은 유지함",
      "severity": "warning",
      "detail": null
    }
  ]
}
```

이 예시에서
- 후보 보정은 라벨과 사용 여부만 바꾼다.
- 편집 위치는 지정되지 않는다.
- 편집 구간이 겹치면 중복 적용하지 않고 충돌로 남긴다.
- 빈 제안은 기존 값을 지우지 않는다.

## 16. 생성 계약

생성 계약(`hwpx/generate.py`)은 검증된 선택 값과 근거, 원본 A를 받아
A의 복사본에서 선택한 구간만 수정하고 결과를 만든다.
이 계약은 실제 편집과 결과 생성, 재검증, 캐시 처리를 맡는다.

### 16.1 함수 이름과 경로

- 경로: `hwpx/generate.py`
- 함수 이름: `generate_result`
- 상태: 설계 단계(아직 구현하지 않음)

이 함수는 서버 내부에서만 호출하는 것을 전제로 한다.
클라이언트가 직접 호출하는 계약이 아니다.

### 16.2 입력

- `aBytes`
  - 원본 A의 바이트
  - 타입: 문자열 또는 바이트
- `aHash`
  - 원본 A의 해시
  - 타입: 문자열
- `fields`
  - A 분석 결과의 입력란 목록
  - 타입: `Field` 배열
- `edits`
  - 사용자 편집 목록
  - 타입: `Edit` 배열
- `proposals`
  - 최종 제안 목록
  - 타입: `SolarProposal` 배열 또는 null
- `blocks`
  - B 추출 결과의 원문 블록 목록
  - 타입: `SourceBlock` 배열
- `normalizedIndex`
  - B 원문 블록 ID와 검색·대조용 정리 텍스트를 짝지은 맵
  - 타입: 객체 또는 null
- `validation`
  - 제안 검증 결과
  - 타입: 제안 검증 결과 객체 또는 null

### 16.3 입력 확인 규칙

생성 전에 다음을 다시 확인한다.

- 원본 A의 해시와 현재 입력란 위치, 편집 가능 구간을 다시 확인한다.
- 자동 제안의 B 근거도 재검증한다.
- 클라이언트가 보낸 위치나 편집 정보를 그대로 신뢰하지 않는다.
- 편집이 필요한 위치가 실제로 편집 가능 구간인지 확인한다.
- 존재하지 않는 입력란 ID나 편집 구간 밖의 요청은 처리하지 않는다.

### 16.4 반환값 개요

반환값은 결과 HWPX와 결과 메타데이터, 경고 목록을 포함한다.

- `result_id`
  - 이 생성 결과를 구분하는 식별자
  - 타입: 문자열
- `resultHash`
  - 생성된 결과 문서의 해시
  - 타입: 문자열
- `resultBytes`
  - 생성된 결과 문서의 바이트
  - 타입: 문자열 또는 바이트
- `changedFields`
  - 실제로 수정된 입력란 목록
  - 타입: `ChangedField` 배열
- `unchanged`
  - 수정되지 않은 입력란과 보존 정보
  - 타입: 객체 또는 null
- `warnings`
  - 생성 중 발생한 경고 목록
  - 타입: `Problem` 배열
- `summary`
  - 채움 항목, 미기입 항목, 충돌, 수동 수정, 경고를 요약한 정보
  - 타입: 객체 또는 null

### 16.5 편집 규칙

- A의 복사본에서 선택한 구간만 수정한다.
- 표·문단·서식·고정 문구·이미지·머리글과 바닥글·페이지 설정은 보존한다.
- 미선택 입력란과 편집 구간 밖의 내용은 그대로 둔다.
- 빈 제안으로 기존 값을 지우지 않는다.
- 기존 A 서식과 스타일 참조를 사용하고, B의 스타일 ID나 서식 참조를 복사하지 않는다.
- 글자 축소나 내용 생략으로 넘침을 숨기지 않는다.

### 16.6 변경 없을 때 처리

- 편집이 없으면 원본 바이트를 그대로 반환한다.
- 이 경우 결과 해시는 원본 해시와는 별개로 기록한다.
- “변경 없음” 상태임을 분명히 남긴다.

### 16.7 캐시 처리 규칙

- 수정한 문단의 배치 캐시와 같이 갱신이 필요한 항목만 정리한다.
- 오래된 미리보기처럼 무효해지는 항목은 필요한 범위에서만 무효화한다.
- 문서 전체의 캐시를 무조건 지우지 않는다.
- 어떤 캐시를 건드렸는지 구체적으로 남긴다.

### 16.8 재검증 규칙

생성 결과를 다시 열어 다음을 검사한다.

- ZIP과 XML 구조를 검사한다.
- 표와 병합 구조, 스타일 참조를 확인한다.
- 실제 입력값이 지정한 위치에 들어갔는지 확인한다.
- 변경 범위를 확인해 수정하지 않은 부분의 변경도 살핀다.
- 손상이나 허용되지 않은 변경이 있으면 결과를 제공하지 않는다.
- 내용 넘침 예상은 경고로 처리한다.
- 실제 렌더링 없이 페이지 보존을 보장하지 않는다.

### 16.9 결과 제공 조건

- 구조 검증에 실패하면 결과 파일을 제공하지 않는다.
- 경고만 있는 경우에는 결과를 제공할 수 있지만, 경고 내용을 함께 남긴다.
- 자동 제안 값은 B의 근거와 대조하고, 수동 수정 값은 별도로 표시한다.
- 내용을 임의로 요약하거나 줄이지 않는다.

### 16.10 작은 반환 예시

아래는 설계 예시이며 실제 구현 결과가 아니다.

```json
{
  "result_id": "result-001",
  "resultHash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "resultBytes": "...base64 또는 바이트...",
  "changedFields": [
    {
      "fieldId": "f-001",
      "value": "홍길동",
      "origin": "rule",
      "sourceBlockIds": ["b-002"]
    },
    {
      "fieldId": "f-003",
      "value": "서울시",
      "origin": "manual",
      "sourceBlockIds": null
    }
  ],
  "unchanged": [
    {
      "fieldId": "f-002",
      "label": "우편번호",
      "reason": "선택되지 않음"
    }
  ],
  "warnings": [
    {
      "type": "unit_unclear",
      "fieldId": "f-004",
      "message": "단위가 불명확해 자동 확정하지 않음",
      "severity": "warning",
      "detail": null
    },
    {
      "type": "overflow_risk",
      "fieldId": "f-005",
      "message": "내용 길이 증가로 넘침 가능성이 있음",
      "severity": "warning",
      "detail": {
        "estimatedIncrease": 1200
      }
    }
  ],
  "summary": {
    "filled": 2,
    "leftEmpty": 1,
    "manualEdits": 1,
    "autoSuggestionsUsed": 1,
    "conflicts": 0
  }
}
```

이 예시에서
- 변경된 입력란과 변경되지 않은 입력란을 구분해 남긴다.
- 경고는 구조 실패가 아니라 예상 문제나 불확실한 항목을 표시한다.
- 요약은 실제 채움 계약과 맞게 남기고, 중간 JSON을 길게 노출하지 않는다.

## 17. 보고서와 미리보기 계약

보고서와 미리보기 계약은 생성 결과를 사용자에게 전달할 때 쓸 형식과 구분을 정한다.
보고서는 실제 채움 계약과 맞게 작성하고, 구조 미리보기와 실제 렌더링은 구분한다.

### 17.1 보고서 형식

보고서는 `Report`로 표현한다.

#### 필수 필드

- `checks`
  - 검사 결과 목록
  - 타입: `CheckResult` 배열
- `warnings`
  - 경고 목록
  - 타입: `Problem` 배열
- `appliedFieldIds`
  - 실제로 적용한 입력란 ID 목록
  - 타입: 문자열 배열
- `skippedFieldIds`
  - 적용하지 않고 건너뛴 입력란 ID 목록
  - 타입: 문자열 배열
- `pendingFieldIds`
  - 검토나 확정이 남아 있는 입력란 ID 목록
  - 타입: 문자열 배열
- `changedParts`
  - 변경된 부분 정보
  - 타입: `ChangedPart` 배열
- `inputHash`
  - 입력 원본 A의 해시
  - 타입: 문자열
- `outputHash`
  - 생성된 결과 문서의 해시
  - 타입: 문자열

#### CheckResult

- `name`
  - 검사 이름
  - 타입: 문자열
- `status`
  - 검사 상태
  - 타입: 문자열
  - 가능한 값: `passed`, `failed`, `not_verified`
- `message`
  - 검사 설명
  - 타입: 문자열 또는 null
- `fields`
  - 관련 입력란 ID
  - 타입: 문자열 배열 또는 null

#### ChangedPart

- `fieldId`
  - 변경 대상 입력란 ID
  - 타입: 문자열 또는 null
- `location`
  - 변경 위치
  - 타입: 객체 또는 null
- `type`
  - 변경 유형
  - 타입: 문자열
  - 예: text-replacement, cell-update, paragraph-update, structural-unchanged
- `notes`
  - 변경 메모
  - 타입: 문자열 또는 null

### 17.2 검사 상태 구분

- `passed`
  - 검사를 통과함
- `failed`
  - 검사를 통과하지 못함
- `not_verified`
  - 아직 검증하지 못함

검사를 통과하지 못한 경우에는 이유를 함께 남긴다.
검사가 통과했다고 해서 의미까지 정확하다고 단정하지 않는다.

### 17.3 경고 구분

경고는 다음처럼 구분해 알린다.

- 입력 누락
- 넘침 예상
- 합계 불일치
- 반복 값 의심

각 경고에는 `code`, `message`, 관련 `fieldId`를 담는다.
필요하면 `detail`도 남긴다.

#### 경고 표현

- `code`
  - 경고 코드
  - 타입: 문자열
- `message`
  - 경고 설명
  - 타입: 문자열
- `fieldId`
  - 관련 입력란 ID
  - 타입: 문자열 또는 null
- `severity`
  - 심각도
  - 타입: 문자열
  - 가능한 값: `warning`, `error`

#### 경고 코드 예시

- `missing-input`
  - 입력 누락
- `overflow-risk`
  - 넘침 예상
- `sum-mismatch`
  - 합계 불일치
- `repeat-value-suspected`
  - 반복 값 의심

경고만으로 구조가 정상인 파일의 제공을 막지 않는다.
구조 검증에 실패한 경우에만 결과 제공을 막는다.

### 17.4 미리보기 형식

구조 미리보기는 입력란 위치를 보여 주는 용도이고,
실제 렌더링과 구분한다.

- 미리보기는 생성된 파일에서 다시 추출한 내용으로 만든다.
- 결과 문서의 실제 구조에서 재추출한 값, 위치, 변경 범위를 반영한다.
- 미리보기를 만들지 못한 상태도 표현한다.
  - 예: 미리보기 생성 실패, 일부 추출 불가, 미완성 상태
- 미리보기 상태에는 성공/실패/부분 제공 여부를 함께 남긴다.

미리보기 결과 객체는 다음 필드를 가질 수 있다.

- `previewStatus`
  - 미리보기 상태
  - 타입: 문자열
  - 가능한 값: `available`, `partial`, `unavailable`
- `source`
  - 미리보기 출처
  - 타입: 문자열
  - 가능한 값: `generated-file`, `re-extracted`, `not-available`
- `fields`
  - 미리보기에 포함할 입력란 요약
  - 타입: 객체 배열 또는 null
- `notes`
  - 미리보기 한계나 사유
  - 타입: 문자열 또는 null

### 17.5 이전 결과와 다운로드 무효화

- 사용자 입력이 바뀌면 이전 결과와 다운로드가 최신 결과처럼 남지 않게 한다.
- 같은 요청이라도 입력이나 선택이 바뀌면 이전 결과를 그대로 쓰지 않는다.
- 이전 다운로드 링크나 이전 보고서는 현재 입력과 연결되지 않았으면 무효로 표시한다.
- 최신 결과만 현재 유효한 결과처럼 보여 준다.

### 17.6 작은 반환 예시

아래는 설계 예시이며 실제 구현 결과가 아니다.

```json
{
  "report": {
    "checks": [
      {
        "name": "zip-structure",
        "status": "passed",
        "message": "ZIP 구조와 XML 진입이 정상",
        "fields": null
      },
      {
        "name": "input-value-placement",
        "status": "passed",
        "message": "선택한 값이 지정한 위치에 들어감",
        "fields": ["f-001", "f-003"]
      },
      {
        "name": "table-merge-preservation",
        "status": "not_verified",
        "message": "병합 보존은 시각 확인 전이라 미검증",
        "fields": null
      }
    ],
    "warnings": [
      {
        "code": "overflow-risk",
        "message": "내용 길이 증가로 넘침 가능성이 있음",
        "fieldId": "f-004",
        "severity": "warning"
      },
      {
        "code": "repeat-value-suspected",
        "message": "같은 값이 다른 입력란에도 반복된 것으로 보임",
        "fieldId": "f-005",
        "severity": "warning"
      },
      {
        "code": "missing-input",
        "message": "일부 입력란은 값이 없음",
        "fieldId": "f-006",
        "severity": "warning"
      }
    ],
    "appliedFieldIds": ["f-001", "f-003"],
    "skippedFieldIds": ["f-002"],
    "pendingFieldIds": ["f-005"],
    "changedParts": [
      {
        "fieldId": "f-001",
        "location": null,
        "type": "cell-update",
        "notes": "표 셀 값 교체"
      },
      {
        "fieldId": "f-003",
        "location": null,
        "type": "text-replacement",
        "notes": "문단 일부 텍스트 교체"
      }
    ],
    "inputHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "outputHash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  },
  "preview": {
    "previewStatus": "available",
    "source": "re-extracted",
    "fields": [
      {
        "fieldId": "f-001",
        "previewValue": "홍길동",
        "location": null
      },
      {
        "fieldId": "f-002",
        "previewValue": "우편번호 자리표시 유지",
        "location": null
      }
    ],
    "notes": "실제 렌더링 결과는 아님"
  }
}
```

이 예시에서
- 보고서는 `passed`, `failed`, `not_verified`를 구분한다.
- 경고는 입력 누락, 넘침 예상, 합계 불일치, 반복 값 의심으로 구분해서 알린다.
- 경고만으로 구조 정상 파일의 제공을 막지 않는다.
- 미리보기는 생성된 파일에서 다시 추출한 내용으로 만들고, 실제 렌더링과 구분한다.
- 미리보기를 만들지 못한 상태도 표현할 수 있다.
- 사용자 입력이 바뀌면 이전 결과와 다운로드는 최신 결과처럼 남기지 않는다.

## 18. API 계약

하나의 API 진입점이 JSON 본문의 `action`에 따라 `status`, `analyze`, `suggest`, `generate`, `preview`를 처리한다. 성공 응답에는 요청한 `action`과 `status: "ok"`를 넣는다.

### 18.1 공통 입력

- `FileInput`: `{ "name": "양식.hwpx", "base64": "..." }`
- `SourceInput`: `{ "kind": "hwpx|txt|md", "name": "원본.txt", "base64": "..." }` 또는 `{ "kind": "txt|md", "text": "..." }`
- 파일 바이트는 base64 문자열로 전송한다.
- 클라이언트는 XML 경로, 바이트 위치, 편집 범위를 지정하지 않는다.
- 서버는 생성 시 원본 A 해시와 편집 위치를 다시 검증한다.

### 18.2 상태 확인

- 요청: `{ "action": "status" }`
- 응답: `{ "action": "status", "status": "ok", "version": "<semver>" }`

### 18.3 분석

- 요청: `{ "action": "analyze", "a": <FileInput>, "b": <SourceInput> }`
- 응답: `{ "action": "analyze", "status": "ok", "analysis": { ... }, "source": { ... } }`
- `analysis`는 `analyze_a` 결과이고, `source`는 `extract_b` 결과다.

### 18.4 제안

- 요청: `{ "action": "suggest", "fields": [ ... ], "blocks": [ ... ], "ruleResults": [ ... ] }`
- 응답: `{ "action": "suggest", "status": "ok", "suggestions": [ ... ], "warnings": [ ... ] }`
- `fields`, `blocks`, `ruleResults`, `suggestions`는 각각 `Field`, `SourceBlock`, `RuleResult`, `SolarProposal` 계약을 따른다.
- Solar에는 입력란 ID·문맥·단위와 관련 원문만 보내며 XML과 내부 편집 위치는 보내지 않는다.

### 18.5 생성

- 요청: `{ "action": "generate", "a": <FileInput>, "aHash": "<64자리 해시>", "fields": [ ... ], "blocks": [ ... ], "edits": [ ... ], "suggestions": [ ... ] }`
- 응답: `{ "action": "generate", "status": "ok", "result": { ... }, "report": { ... } }`
- `edits`는 `Edit`, `result`는 16.4의 생성 결과, `report`는 `Report` 계약을 따른다.
- 검증된 선택만 적용하며 구조 검증에 실패하면 결과 파일을 반환하지 않는다.

### 18.6 미리보기

- 요청: `{ "action": "preview", "resultBytes": "...base64..." }`
- 응답: `{ "action": "preview", "status": "ok", "preview": { ... } }`
- 미리보기는 결과 HWPX에서 다시 추출하며 실제 렌더링 결과로 표시하지 않는다.

### 18.7 오류 형식

- 오류 응답: `{ "code": "<기계 판독 코드>", "message": "<사람이 읽는 메시지>", "details": { ... } }`
- `code`와 `message`는 필수이며 `details`는 객체 또는 null이다.
- 크기 초과, 지원하지 않는 입력, 잘못된 action, 구조 검증 실패, Solar 부분 실패를 서로 다른 `code`로 구분한다.
- 일부 항목만 실패한 경우 정상 결과를 보존하고 실패 항목을 `details`에 남긴다.

### 18.8 전송과 Solar 제한

- 인코딩된 요청과 응답은 각각 3,800,000바이트 이하다.
- base64를 해제한 A와 B의 합계는 2,500,000바이트 이하다.
- 결과 HWPX ZIP은 2,500,000바이트 이하다.
- ZIP 전체 압축 해제 크기와 개별 파일의 압축 해제 크기는 각각 50,000,000바이트 이하다.
- ZIP 엔트리는 5,000개 이하다.
- 보고서와 미리보기도 응답 크기에 포함한다.
- Solar 한 배치는 입력란 20개 이하, 요청 본문은 48,000바이트 이하로 제한한다.
- Solar 동시 요청은 최대 2개다. 전체 입력란을 240개로 제한하지 않고 배치로 나눠 처리한다.
- Solar 모델은 `solar-pro4`, 서버 환경 변수는 `UPSTAGE_API_KEY`를 사용한다.

## 19. 관련 문서

### 2026-09-16 웹 연결 구현 보충

- 공개 경로는 `/api/transplant`, 실제 함수 파일은 `api/transplant/index.py`
- 서비스 로직은 `web_service.py`에 둔다 API 디렉터리의 보조 파일이 별도 Vercel 함수로 배포되지 않도록 분리한다
- `analyze` 응답에는 기존 analysis/source 외에 rules 기반 `suggestions`, `ruleResults`, `warnings`가 포함된다 화면은 미제안 필드를 `suggest`로 요청한다
- 자동 값 생성 시 `generate` 요청에 원본 `b: SourceInput`을 함께 보낸다 서버는 B를 다시 추출하며 클라이언트의 blocks와 fields의 편집 위치는 사용하지 않는다 수동 편집만 있다면 b 생략 가능
- `result.resultBytes`는 base64 문자열이다 구조 검사 실패 응답에는 result를 넣지 않는다
- 이번 운영 경로는 status/analyze/suggest/generate다 preview 액션은 미구현이며 INVALID_ACTION을 반환한다 화면의 입력란 위치 정보는 렌더링 미리보기가 아니다
- 환경 변수는 UPSTAGE_API_KEY를 우선하고 기존 SOLAR_API_KEY를 대체 키 이름으로 지원한다 키가 없거나 Solar 배치가 실패해도 분석 결과를 보존하고 수동 입력을 허용한다

- 루트 `SKILL.md`
- `PROJECT_BLUEPRINT.md`
- `docs/WORK_RULES.md`
- `docs/TEAM_CONTRACT.md`의 공통 계약
- `reference/qualifier` 아래 예선 원본

충돌이 생기면 루트 SKILL.md의 절대 규칙을 우선한다.
예선 원본은 수정하지 않는다.
