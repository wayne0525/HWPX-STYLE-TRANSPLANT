# 표, 선 굵기, 이미지

사용자가 말한 **line width**는 거의 항상 표·상자 테두리 굵기다. 글자 윤곽선이 아니다.

## 표 구조 (B → C)

```
hp:tbl  @rowCnt @colCnt @borderFillIDRef
  hp:tr
    hp:tc  @borderFillIDRef
      hp:cellAddr colAddr rowAddr colSpan rowSpan
      hp:cellSz width height
      hp:cellMargin ...
      hp:subList
        hp:p → hp:run → hp:t
```

- `rowCnt`/`colCnt`는 B와 같게.
- 병합(`colSpan`/`rowSpan`)은 B 그대로. 잘못 풀면 내용이 밀린다.
- `cellSz` 절대값은 A의 본문 폭에 맞춰 **비율 유지**가 우선. 합이 A 용지 본문 폭을 넘으면 비율로 줄인다.
- 셀 텍스트만 바꾸고 격자를 A에서 가져오면, 열 개수가 다를 때 깨진다. **격자는 B, 선/배경은 A.**

## 선과 배경은 A

A의 대표 표에서:

- 바깥 선 굵기·색·종류
- 안쪽 선 (더 가늘 수 있음)
- 헤더 행 배경
- 본문 행 배경 (보통 없음 또는 흰 색)
- 헤더 글자 (굵게, 흰 글자 등)

C의 모든 표에 이 세트를 적용한다. B 표가 점선이어도 A가 실선이면 실선.

표가 A에 없으면: 본문 글꼴 + 아주 기본 실선. 굵기는 `unknown`이면 0.12mm를 **창작하지 말고** “표 테두리 원본 없음, 한컴 기본선”이라고 누락에 적는다. 기본선을 쓸 수밖에 없으면 report에 `usedEngineDefaultBorder: true`.

## 문단 밑줄·상자

본문 테두리(문단 박스)도 borderFill이다. A의 본문에 박스가 없으면 C 본문에 박스를 그리지 마라.

## 이미지

```
section: hc:img binaryItemIDRef="image1"
content.hpf: manifest item href="BinData/image1.png"
BinData/image1.png 실제 바이트
```

세 곳 중 하나라도 빠지면 한컴에서 깨지거나 X박스가 된다.

- 이미지는 **B에서** 가져온다 (내용).
- 캡션 서식은 **A caption 슬롯**.
- 테두리·그림자 서식은 A에 그림 스타일이 있을 때만.
- 크기는 B 비율을 유지하되 A 본문 폭을 넘지 않게.

옮길 수 없으면 누락에 `이미지 N: (설명 또는 파일명)` 을 적고 본문에 가짜 “【그림】”을 삽입하지 않는다. 사용자가 빈자리를 찾도록 위치만 `본문 n번째 블록 뒤`라고 적는다.

## 글상자·도형

가능하면 텍스트만 본문 블록으로 내린다. 레이아웃 도형은 A 양식의 장식이면 **가져오지 않는다** (A 내용 금지). B의 설명 도형은 unsupported.

## 수식

한컴 수식 컨트롤은 이식 실패 가능성이 높다. 원문 TeX/문자열이 있으면 텍스트로 두고 `unsupported: equation`. 추측한 기호로 대체하지 마라.
