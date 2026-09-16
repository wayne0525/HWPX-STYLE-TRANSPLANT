"""analyze_a 프로토타입 검증 스크립트 (테스트 아님)."""
import json
import sys
sys.path.insert(0, ".")

from hwpx.analyze import analyze_a

result = analyze_a("tests/fixtures/A.hwpx")
print("=== 분석 상태 ===")
print("analysis_status:", result["analysis_status"])
print("a_hash:", result["a_hash"])
print("warnings:", result["warnings"])
print(f"\n총 필드 수: {len(result['fields'])}")
print()

# 필드 테이블 출력
print("=== 필드 목록 (field_id, label, location, unit) ===")
print(f"{'field_id':<8} {'label':<20} {'location':<60} {'unit':<12} {'required':<8} {'merge':<10}")
print("-" * 120)
for f in result["fields"]:
    loc = f["location"]
    loc_str = f"section={loc['section']}, table_path={loc['table_path']}, row={loc['row']}, col={loc['col']}"
    merge_str = "있음" if f.get("merge_info") else "-"
    req_str = "필수" if f["required"] else "-"
    print(f"{f['field_id']:<8} {f['label'][:20]:<20} {loc_str:<60} {f['unit']:<12} {req_str:<8} {merge_str:<10}")

print()
print("=== context 샘플 (처음 5개) ===")
for f in result["fields"][:5]:
    print(f"{f['field_id']}: {f['context']}")

print()
print("=== 예상 vs 실제: 프로그램명, 성명, 우편번호 ===")
for f in result["fields"]:
    label = f["label"]
    if "프로그램" in label or "성명" in label or "우편" in label:
        print(f"  {f['field_id']}: label='{label}', unit={f['unit']}, location={f['location']}")
