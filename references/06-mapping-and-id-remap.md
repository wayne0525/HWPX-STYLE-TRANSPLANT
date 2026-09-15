# 매핑과 ID 재지정

목표: B의 블록 트리 + A의 역할 슬롯 → C.
**금지: B의 ID를 A 헤더에 붙여 넣기. A의 ID를 B XML에 숫자 그대로 남기기.**

## 역할 맵

| B 블록 | C에 적용할 A 슬롯 | 슬롯이 없을 때 |
|--------|-------------------|----------------|
| title | documentTitle | heading1, 없으면 body+굵게+가운데(가운데는 A heading1이 가운데일 때만). 가운데를 창작하지 말고 body 정렬을 따름 |
| heading level 1 | heading1 | documentTitle이 본문과 다를 때만 그것, 아니면 body+굵게 |
| heading level 2 | heading2 | heading1 |
| heading level 3+ | heading3 | heading2 → heading1 → body+굵게 |
| paragraph | body | (필수 슬롯. 없으면 A에서 최빈 char/para) |
| listItem | list | body + B의 기호 문자 유지 |
| table cells header row | tableHeader | tableBody, 없으면 body |
| table cells 나머지 | tableBody | body |
| caption | caption | body, 크기 창작 금지 |
| quote | quote | body |
| image caption | caption | body |
| footnote | body 크기 또는 A 각주 슬롯 | body보다 작게 창작하지 말고 body |
| emphasis run | emphasis | body+bold 플래그만 |

페이지 여백·용지·기본 줄간격은 블록과 무관하게 **문서 전체에 A 페이지 슬롯**을 깐다.

## ID 재지정 알고리즘

A를 골격으로 쓸 때:

1. C의 `header.xml` = A의 `header.xml` (fonts, charPr, paraPr, style, borderFill). B 헤더 항목을 merge하지 않는다.
2. C의 섹션 본문 = B에서 뽑은 블록을 **새로 쓴** `hp:p` / `hp:tbl`.
3. 각 새 문단에 A 슬롯의 `paraPrIDRef`, `styleIDRef`를 넣는다.
4. 각 새 런에 A 슬롯의 `charPrIDRef`를 넣는다. emphasis 런만 emphasis 슬롯 ID.
5. 표/셀에 A의 `borderFillIDRef` (tableHeader vs tableBody).
6. B에서 가져온 `charPrIDRef="2"` 같은 숫자는 **버린다.**

B XML을 거의 그대로 복사해야 하는 경우(복잡한 표 병합):

1. 표를 C(A 패키지)로 복사한다.
2. 표 안 모든 `paraPrIDRef`/`charPrIDRef`/`styleIDRef`/`borderFillIDRef`를 스캔한다.
3. B 헤더에서 그 ID가 가리키던 **역할**을 추정한다 (표 안이면 tableBody/tableHeader).
4. A 슬롯의 ID로 **전량 치환**한다.
5. B 헤더의 charPr 정의를 A 헤더에 추가하지 않는다. 추가하면 글꼴이 B로 돌아온다.

충돌: A에도 id 5가 있고 B에도 id 5가 있으면, 복사본의 5는 A의 5(전혀 다른 서식)가 된다. 그래서 **복사 후 전량 치환이 필수**다.

## itemCnt

header를 수정한 경우에만 `itemCnt`를 실제 자식 수와 맞춘다. A 헤더를 그대로 쓰면 손대지 않는다.

## nextStyleIDRef

A 스타일의 `nextStyleIDRef`는 A 안에서만 유효하다. 새 문단을 넣을 때 제목 다음 문단에 A의 “본문” 스타일을 쓰면 된다. B의 nextStyle을 따르지 마라.

## 글꼴 파일이 없는 경우

A가 `HY헤드라인M` 같이 환경에 없는 글꼴을 쓰면, C에도 그 **이름**을 그대로 둔다. `맑은 고딕`으로 바꿔 “개선”하지 마라. 그게 A의 보기이다.

## 본문 대표 슬롯이 비었을 때

A에서 `hp:p`를 세어 가장 많이 나온 `(styleIDRef, paraPrIDRef, charPrIDRef)` 조합을 body로 쓴다. 표 안 문단은 집계에서 빼는 것이 안전하다(표 글자가 본문보다 작아 최빈값이 표가 됨).

## 체크

매핑 테이블을 transplant-report의 `roleMap`에 남긴다.

```
B heading2 → A heading2 (para 8, char 4)
B heading3 → A heading2 (fallback, A에 heading3 없음)
```

사용자 요약에는 한두 줄로만.
