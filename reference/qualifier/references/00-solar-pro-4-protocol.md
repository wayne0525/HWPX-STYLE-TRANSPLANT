# Solar Pro 4 — 이 스킬에서 일하는 방식

이 파일은 Timely AI의 **Solar Pro 4**가 HWPX 이식을 덜 틀리게 하기 위한 운영 규약이다.
모델은 한글 문서 XML을 DOCX만큼 안정적으로 기억하지 못한다. 그래서 **추측을 금지하고 스키마를 채운다.**

## 원칙

1. **숫자보다 출처.** `13pt`라고 쓰려면 XML의 `height="1300"`이거나, 한글 UI에서 읽었거나, 시각 추정이어야 한다. 출처 없는 숫자는 쓰지 않는다.
2. **한 번에 C를 짓지 않는다.** 반드시 (A 프로필) → (B 골격) → (역할 맵) → (C) 순이다. 중간을 건너뛰면 본문 글꼴이 B로 남거나 A 문장이 섞인다.
3. **ID는 이름이 아니다.** A의 `charPr id="2"`와 B의 `charPr id="2"`는 다른 글자 서식이다. 이식은 **역할(본문/제목1/표헤더)** 으로만 한다.
4. **한국어 실무 문서**는 함초롬바탕, 휴먼명조, 맑은 고딕, 굴림, 바탕이 흔하다. 없는 글꼴 이름을 넣지 마라. A에 있는 이름만 쓴다.
5. **토큰을 아낀다.** 사용자에게 XML 전문을 붙여 넣지 마라. 내부에서만 파싱하고, 바깥에는 사람 단위(pt/mm/%)만 보여 준다.
6. **불확실하면 좁게.** 표 병합·수식·글상자를 재구성하지 못하면 누락에 적고, 빈 껍데기를 만들지 않는다.

## Solar Pro 4가 특히 틀리는 지점 (먼저 막을 것)

| 실수 | 막기 |
|------|------|
| A의 표지 문장(“주식회사 ○○ 보고서”)을 C 제목으로 씀 | A에서는 서식만. 제목 문자열은 B |
| B의 맑은 고딕 12pt를 “원본이니까” 유지 | B 서식 전부 폐기 |
| 줄간격 160%를 1.6pt나 160pt로 씀 | `references/02-units.md` — PERCENT는 % |
| 선굵기 0.12mm를 12pt로 씀 | 테두리는 mm 또는 `0.1mm`/`0.12mm`/`0.2mm`/`0.4mm` |
| 여백 8504를 85mm로 읽음 | HWPUNIT. 8504 ≈ 30mm (`02-units.md`) |
| 글자 크기 1000을 1000pt로 씀 | height/100 = pt. 1000 → 10pt |
| 제목3이 A에 없다고 맑은 고딕 22pt를 새로 만듦 | 본문 또는 제목2로 폴백 |
| 표를 이미지로 스캔해 다시 타이핑하며 숫자 오타 | 셀 텍스트는 B를 그대로. 못 읽으면 누락 |
| 양쪽 정렬을 왼쪽 정렬로 바꿈 | A `align` 유지 |
| 머리글 텍스트(회사명)를 A에서 복사 | 머리글은 **서식만**. 텍스트는 B에 있을 때만 |

## 내부 사고 순서 (사용자에게 이 목록을 길게 풀지 말 것)

```
confirm_AB
→ unpack_or_render(A)
→ fill style-profile  (unknown 허용, 날조 금지)
→ unpack_or_render(B)
→ fill content-skeleton (텍스트 원문 보존)
→ classify roles using 05-role-classification.md
→ map via 06-mapping-and-id-remap.md
→ build C from A's header + B's body tree
→ drop hp:linesegarray after text moves
→ fill transplant-report
→ QA checklist
→ user-facing output only
```

## 파일을 읽는 우선순위

HWPX를 열 수 있을 때:

1. `Contents/header.xml` — 폰트, charPr, paraPr, styles, borderFill (A의 보기)
2. 첫 섹션 `hp:secPr` / `hp:pagePr` — 용지·여백
3. `Contents/section*.xml` — A에서는 **빈도 높은 charPr/paraPr**만 보고 본문 글은 무시
4. B의 `section*.xml` — `hp:t` 텍스트, 표 격자, 이미지 참조만

못 열 때:

1. 추출된 텍스트 + 미리보기 이미지
2. 역할은 시각(크기·굵기·가운데 정렬)으로만 추정하고 `source: "visual-estimate"`
3. 줄간격·여백을 못 보면 `unknown`

## 생성 전략 (우선순위)

1. **가장 안전:** A 패키지를 복제하고, 섹션 본문을 B의 내용 트리로 갈아 끼운 뒤, 각 문단/런의 `paraPrIDRef`/`charPrIDRef`/`styleIDRef`/`borderFillIDRef`를 **A 헤더에 있는 ID**로 다시 가리키게 한다.
2. **차선:** A의 스타일 프로필(사람 단위)로 새 문서를 만들고 B 텍스트를 넣는다. 글꼴 이름이 A와 같아야 한다.
3. **폴백:** DOCX/PDF. 같은 숫자(pt/mm/%)를 적용하고, 한글에서 재적용할 표를 남긴다.

B를 복제한 뒤 A의 글꼴만 덮어쓰는 방식은 금지에 가깝다. B 헤더에 남은 다른 문단 간격·표 테두리가 C에 남는다.

## 언어·톤 (Solar)

- 사고는 한국어로 해도 된다.
- 사용자 출력은 한국어, 짧은 실무체.
- 영어 필드명(`charPrIDRef`)은 내부 JSON에만 쓰고, 사용자 표에는 `글자 서식 번호`처럼 풀어 쓴다.
- “완벽히 이식했습니다” 금지. 측정한 것만 단정한다.
