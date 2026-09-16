# HWPX 패키지 구조

HWPX는 ZIP + XML이다. 확장자를 `.zip`으로 바꿔 열 수 있다. 구형 `.hwp`는 OLE 바이너리라서 이 스킬의 대상이 아니다.

## 트리

```
document.hwpx
├── mimetype                 # 반드시 첫 엔트리, 비압축(ZIP_STORED)
│                            # 내용: application/hwp+zip
├── version.xml
├── settings.xml
├── META-INF/
│   ├── container.xml
│   ├── manifest.xml         # BinData 추가 시 함께 갱신
│   └── container.rdf
├── Contents/
│   ├── content.hpf          # 파트 목록 (header, section, 이미지)
│   ├── header.xml           # ★ A의 서식이 사는 곳
│   ├── section0.xml         # ★ B의 본문이 사는 곳 (섹션이 더 있을 수 있음)
│   └── sectionN.xml
├── BinData/                 # 그림, OLE
│   └── image*.png / .jpg
└── Preview/
    ├── PrvImage.png
    └── PrvText.txt
```

## 네임스페이스

| 접두사 | 용도 |
|--------|------|
| `hh` | header.xml — 글꼴, charPr, paraPr, style, borderFill |
| `hp` | 문단, 런, 텍스트, 표, 컨트롤 |
| `hs` | 섹션 루트 |
| `hc` | 공통 타입 (이미지 등) |
| `hpf` | content.hpf 매니페스트 |

URI는 보통 `http://www.hancom.co.kr/hwpml/2011/...` 이다. 2016/2024 변형이 있어도 로컬 태그 이름(`charPr`, `p`, `t`)으로 찾는다.

## 참조 사슬 (이게 이식의 핵심)

```
section*.xml
  hp:p     @paraPrIDRef  @styleIDRef
    hp:run @charPrIDRef
      hp:t  (실제 글자)          ← B에서만 가져옴
    hp:tbl @borderFillIDRef
      hp:tc @borderFillIDRef
        hp:subList > hp:p > hp:run > hp:t

header.xml
  hh:fontfaces / font
  hh:charPr    id=...           ← A에서 가져옴
  hh:paraPr    id=...
  hh:style     id=...  (paraPrIDRef, charPrIDRef 를 다시 가리킴)
  hh:borderFill id=...
```

문단은 스타일 이름을 들고 있지 않다. **정수 ID**만 들고 헤더를 찾아간다.
그래서 B 섹션을 A 패키지에 붙일 때 ID를 다시 매핑하지 않으면 서식이 엉킨다.

## 본문에서 글자 위치

```xml
<hp:p paraPrIDRef="3" styleIDRef="1">
  <hp:run charPrIDRef="7">
    <hp:t>여기가 내용</hp:t>
  </hp:run>
</hp:p>
```

- 같은 문단에 런이 여러 개일 수 있다 (일부만 굵게).
- 빈 칸은 `hp:run`만 있고 `hp:t`가 없을 수 있다.
- `hp:t` 안에 `hp:lineBreak`, `hp:fwSpace`가 있으면 태그를 지우지 말고 텍스트 노드만 건드린다.
- `hp:linesegarray`는 줄 배치 캐시다. 글을 바꾼 뒤에는 **삭제**해서 한컴이 다시 짜게 한다.

## 페이지

보통 섹션 첫 문단의 첫 런 안 `hp:secPr` > `hp:pagePr`:

```xml
<hp:pagePr landscape="WIDELY" width="59528" height="84186">
  <hp:margin header="4252" footer="4252" gutter="0"
             left="8504" right="8504" top="5668" bottom="4252"/>
</hp:pagePr>
```

`landscape="WIDELY"`는 가로, 그 외는 세로로 보면 된다. 숫자는 HWPUNIT (`02-units.md`).

## 생성·저장 시 깨지기 쉬운 것

- `mimetype`을 압축하거나 ZIP 중간으로 옮기면 한컴이 거부한다.
- 이미지는 `section`의 `binaryItemIDRef` + `content.hpf` + `BinData/` 파일 **세 곳이 같아야** 한다.
- `hh:styles` / `charProperties` 의 `itemCnt`는 실제 개수와 맞출 것.
- A의 `header.xml`을 쓸 때 B 헤더를 합치지 마라. 스타일은 A 헤더가 승자, 본문은 B 섹션이 승자다.

## Timely에서 ZIP을 못 열 때

추출된 본문·표 텍스트와 미리보기만 있다고 가정하고, 패키지 규칙 대신 `03-style-catalog.md`의 사람 단위 항목을 채운다. XML 경로를 지어내지 않는다.
