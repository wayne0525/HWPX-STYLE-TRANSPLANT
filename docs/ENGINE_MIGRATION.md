# 실제 HWPX 엔진 전환

분석 규칙은 team/engine-dylan 7f44546에서 가져왔고 기존 로컬 변경은 삭제하지 않았다
이식한 분석 코드는 hwpx/template.py, 생성과 결과 비교는 hwpx/fill.py에 있다
기존 합성 fixture용 분석·생성은 호환 경로에 남아 있으며 운영용 실제 HWPX는 새 경로를 사용한다

## 연결

read_hwpx → read_xml → analyze_a → B 추출·제안·사용자 선택 → generate_result → validate_output

실제 패키지의 Contents/content.hpf와 OPF spine 순서로 section을 읽는다
analyze_a의 공개 반환은 AAnalysis와 camelCase 필드, 원본 해시는 접두사 없는 SHA-256이다
생성 시 fields의 클라이언트 위치를 사용하지 않고 원본을 다시 분석한다
selected=true인 편집만 적용하고 중복 ID, 해시 불일치, 보호 후보는 거부한다
origin=manual 또는 user는 수동 편집이며 자동 편집은 proposals의 fieldId/value/sourceBlockIds/evidenceQuote를 blocks와 다시 대조한다
자동 단위 변환은 아직 이 경로에서 확정하지 않으며 수동 검토가 필요하다

빈 셀과 라벨 뒤 삽입을 지원하며 여러 section과 같은 셀 안의 여러 삽입 위치를 구분한다
복잡한 제어 개체, 단위만 있는 후보, 지원하지 않는 텍스트 구조는 편집을 차단한다
선택 없음은 원본 바이트 그대로 반환한다
결과는 선택한 위치의 값과 XML 구조, 수정하지 않은 ZIP 항목을 다시 비교한다
생성 실패는 resultBytes=null과 errors를 반환하므로 서비스는 파일로 내려보내면 안 된다
한글 렌더링은 실행하지 않았고 모든 기입 결과에 배치 확인 경고를 반환한다

## 검증과 남은 작업

Python 3.14와 lxml 6.1.3 환경에서 새 회귀 12개 통과
전체는 143개 통과, 11개 실패, 1개 건너뜀
실제 두 양식에서 편집 가능 후보 10개와 75개를 동시에 기입하고 위치별 시험값 일치 확인
이는 입력란 탐지 정답률이나 실제 한글 표시 품질을 증명하지 않는다

남은 실패는 test_gold 2개, test_manual_candidates 1개, test_regression 1개,
test_source의 raw XML 입력 3개, test_table_mapping 4개다
검사를 삭제하거나 기대값을 완화하지 말고 유효한 HWPX fixture와 실제 공통 계약을 기준으로 수정해야 한다
기존 합성 경로의 평가 방식은 완성되지 않았으며 실제 HWPX 평가는 입력 위치 재추출과 실제 검증 결과를 사용한다
서비스 브랜치는 이 진입점으로 연결하고 오류·부분 실패·수동 변경 상태를 확인해야 한다
API부터 다운로드까지 통합 검사와 한글 시각 확인은 아직 하지 않았다

의존성은 루트 requirements.txt의 lxml이며 운영 환경에도 설치해야 한다
