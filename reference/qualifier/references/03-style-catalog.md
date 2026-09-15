# A에서 뽑을 서식 카탈로그

A의 **모든 문장·표 값·날짜는 무시**한다. 아래 항목만 역할별로 뽑는다.
역할 목록은 `05-role-classification.md`. 스키마는 `schemas/style-profile.schema.json`.

값이 없으면 `null` + `unknownReason`. 없는 역할을 만들어 채우지 않는다.

## 1. 문서 페이지 (섹션)

| 필드 | XML 힌트 | 사람 단위 |
|------|----------|-----------|
| 용지 | `pagePr width height` | A4 / B5 / A3 / 기타 mm |
| 방향 | `landscape` | 세로 / 가로 |
| 여백 위아래좌우 | `pagePr/margin` | mm |
| 머리글·바닥글 간격 | `margin header footer` | mm |
| 다단 | `colPr colCount` | 단 수, 간격 mm |
| 그리드/줄 맞춤 | `snapToGrid` 등 | 있으면 기록 |

머리글·바닥글 **글자**(회사명, 페이지 번호 형식의 본문)는 가져오지 않는다. 글꼴·크기·정렬만.

## 2. 글자 (charPr) — font, color

역할마다 **대표 charPr 하나**를 고른다. 본문에 가장 많이 쓰인 id가 본문 대표다.

| 필드 | XML 힌트 | 비고 |
|------|----------|------|
| 한글 글꼴 | `fontRef @hangul` 또는 fontface 이름 | 함초롬바탕, 휴먼명조… A에 있는 문자열 그대로 |
| 영문 글꼴 | `fontRef @latin` | 없으면 한글과 동일하다고 쓰지 말고 실제 값 |
| 한글 전용 기호 글꼴 | `hangul`/`symbol`/`user` | 있으면 |
| 크기 | `@height` | pt |
| 글자색 | `@textColor` | #RRGGBB |
| 음영/형광 | `@shadeColor` | none이면 없음 |
| 굵게 | 자식 `bold` 존재 | true/false |
| 기울임 | `italic` | |
| 밑줄 | `underline @type @shape @color` | 없음이면 NONE |
| 취소선 | `strikeout` | |
| 위첨자/아래첨자 | `supscript` / `subscript` | |
| 자간 | `spacing` | |
| 장평 | `ratio` | % |
| 글자테두리 | `borderFillIDRef` on charPr | 드묾 |

영어/숫자만 다른 글꼴인 문서가 많다. C에서도 한글/영문을 **따로** 적용한다.

## 3. 문단 (paraPr) — line gap, indent, align

| 필드 | XML 힌트 | 사람 단위 |
|------|----------|-----------|
| 정렬 | `align` / `horizontal` | 양쪽/왼쪽/가운데/오른쪽 |
| 줄간격 | `lineSpacing @type @value` | % 또는 고정 pt |
| 문단 위 | spacing before | pt |
| 문단 아래 | spacing after | pt |
| 왼쪽 여백 | margin left | mm |
| 오른쪽 여백 | margin right | mm |
| 첫줄 들여쓰기 | indent / intent | mm. 음수=내어쓰기 |
| 문단 테두리 | border + borderFill | 선 굵기·색 (line width) |
| 개요 수준 | heading level | 0이면 본문 |

## 4. 선·면 (borderFill) — line width, color

표와 문단 테두리의 공통 정의.

| 필드 | 비고 |
|------|------|
| 선 종류 | SOLID, DASH, DOT, NONE… |
| 선 굵기 | mm (0.12mm 등) |
| 선 색 | #RRGGBB |
| 네 변 | 위/아래/좌/우가 다를 수 있음. 다르면 각각 |
| 배경 채움 | 없음 / 단색 #RRGGBB |
| 셀 안 여백 | cellMargin left/right/top/bottom |

**표 헤더 행**과 **표 본문 셀**의 borderFill이 다르면 둘 다 적는다. 헤더만 회색 배경인 양식이 많다.

## 5. 이름 있는 스타일 (hh:style)

있으면 역할 매핑이 쉬워진다.

```
style @id @name @type @engName
  paraPrIDRef, charPrIDRef, nextStyleIDRef
```

한글 기본 이름 예: `본문`, `개요 1`, `개요 2`, `제목`, `쪽 번호`.
A에 `본문`이 있으면 그것을 본문 역할의 1순위로 쓴다. 이름은 가져도 **A 문서 안의 정의**만 따른다. 다른 파일의 “본문”과 같다고 가정하지 않는다.

## 6. 목록

글머리표 `bullet`, 번호 `numbering` / headingType.
A의 목록 기호(•, -, ①)와 내어쓰기 값을 본문과 별도 역할로 저장한다.
B의 `1.` `2.` 문자열은 내용이다. 기호 모양만 A를 따른다.

## 7. 역할별로 반드시 채울 슬롯

가능한 한 아래 키를 다 둔다. 없으면 `present: false`.

- `documentTitle`
- `heading1` `heading2` `heading3`
- `body`
- `caption`
- `list`
- `tableHeader` `tableBody`
- `quote`
- `headerChrome` `footerChrome` (서식만)
- `emphasis` (본문 중 굵게/색 강조가 A에 반복되면)

각 슬롯: `{ char, para, borderFill?, sampleSource: "xml"|"visual-estimate" }`

## 8. 샘플을 고르는 법 (A 본문을 복사하지 않고)

A에서 각 역할의 **가장 긴 문단 하나가 아니라**, 그 역할로 보이는 문단의 **ID 조합**만 기록한다.

```
body: { paraPrIDRef: "3", charPrIDRef: "1", styleIDRef: "0" }
```

실제 문장 `"우리 회사는 창립 20주년…"` 은 저장하지 않는다.

빈도: 같은 ID가 가장 많이 나온 조합 = 본문.

## 9. 시각만 가능할 때 최소 세트

XML이 없으면 이것만이라도:

- 본문 글꼴 추정, 본문 pt, 본문 색
- 제목1 pt·굵기·정렬
- 줄간격 % (모르면 unknown)
- 용지 A4 여부, 여백 감(좁음/보통/넓음) — 감만 있으면 mm를 지어내지 말고 `unknown`
- 표 선 있음/없음, 헤더 배경 있음/없음
