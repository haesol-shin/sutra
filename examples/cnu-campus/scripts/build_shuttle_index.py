import json
from pathlib import Path

SHUTTLE_SOURCE_NAME = "충남대학교 학교셔틀버스"
SHUTTLE_SOURCE_URL = "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html"

SUMMARY_TEXT = """2026학년도 학교셔틀버스 운영 안내
운영기준: 학기 중 평일 주간 운영. 평일 야간, 주말, 공휴일, 방학, 수학능력시험일 10시 이전 등은 미운영.
변경 가능: 운행 시간표와 운행 기간은 학교 사정 및 학사일정 변경에 따라 달라질 수 있으며, 천재지변, 학교행사, 교통상황, 탑승 인원 등에 따라 운행시간이 변경될 수 있음.
탑승 안내: 교통상황 등으로 전 구간에서 5분 내외 오차가 발생할 수 있으므로 탑승자는 사전 대기.
운행 주체: 학교버스
운행 내용: 운행 시간표 및 운행 노선 참고
운행 노선: 교내 순환(대덕캠퍼스 내), 캠퍼스 순환(대덕캠퍼스 ↔ 보운캠퍼스)
운영기간(원 공지 기준): 2026. 3. 3.(화) ~ 2026. 12. 18.(금)
차량(원 공지 기준): 학교버스 2대(41인승)
운영일수: 학기 중 운영, 총 150일"""

INTERNAL_ROUTE_TEXT = """노선: 교내 순환 (대덕캠퍼스 내)
운행 시간표: 오전 08:20 월평역 등교 1회, 오전 08:30, 09:30, 09:40, 10:30, 11:30 / 오후 13:30, 14:30, 15:30, 16:30, 17:30
첫차: 08:30
막차: 17:30
운행 횟수: 1일 10회, 학기 중 운영(총 150일)
운행 노선: 1. 정심화 국제문화회관 -> 2. 사회과학대학 입구(한누리회관 뒤) -> 3. 서문(공동실험실습관 앞) -> 4. 음악 2호관 앞 -> 5. 공동동물실험센터(회차) -> 6. 체육관 입구 -> 7. 예술대학 앞 -> 8. 도서관 앞(대학본부 옆 농대방향) -> 9. 학생생활관 3거리 -> 10. 농업생명과학대학 앞 -> 11. 동문주차장 -> 12. 농업생명과학대학 앞 -> 13. 도서관 앞(도서관삼거리 방향) -> 14. 예술대학 앞 -> 15. 서문(공동실험실습관 앞) -> 16. 사회과학대학 입구(한누리회관 뒤) -> 17. 산학연교육연구관 앞 -> 18. 정심화 국제문화회관
참고: 오전 등교 1회만 월평역에서 출발하며 정심화 국제문화회관에서 하차(종점)."""

CAMPUS_LOOP_TEXT = """노선: 캠퍼스 순환 (대덕캠퍼스 ↔ 보운캠퍼스)
운행 시간표: 오전 08:10 골프연습장 출발, 08:50 보운캠퍼스 회차 / 오후 미운영
첫차: 08:10(대덕)
막차: 08:50(보운)
운행 횟수: 1일 1회(회차), 학기 중 운영(총 150일)
운행 노선: 1. 골프연습장 출발(08:10) -> 2. 중앙도서관(08:11) -> 3. 산학연교육연구관(08:12) -> 4. 충남대학교입구 버스정류장(홈플러스유성점 방면)(08:13) -> 5. 월평역(08:15) -> 6. 보운캠퍼스(회차, 08:50) -> 7. 다솔아파트 건너편 -> 제2학생회관 -> 중앙도서관 -> 골프연습장 도착
참고: 캠퍼스 순환은 등교 시간대 1회 운행하며 오후는 미운영."""

def _canonical_chunks() -> list[dict]:
    return [
        {
            "id": "shuttle_summary_shuttle_bus",
            "domain": "shuttle",
            "title": "2026학년도 학교셔틀버스 운영 안내 요약",
            "text": SUMMARY_TEXT,
            "source_url": SHUTTLE_SOURCE_URL,
            "source_name": SHUTTLE_SOURCE_NAME,
            "source_path": "data/raw/shuttle/shuttle_bus.html",
            "generation_method": "structured_aggregate",
            "metadata": {
                "domain_type": "operating_summary",
                "effective_year": "2026",
            },
        },
        {
            "id": "shuttle_route_교내순환대덕캠퍼스내",
            "domain": "shuttle",
            "title": "셔틀버스 교내 순환 (대덕캠퍼스 내) 운행 정보",
            "text": INTERNAL_ROUTE_TEXT,
            "source_url": SHUTTLE_SOURCE_URL,
            "source_name": SHUTTLE_SOURCE_NAME,
            "source_path": "data/raw/shuttle/shuttle_bus.html",
            "generation_method": "structured_aggregate",
            "metadata": {
                "domain_type": "route",
                "route_name": "교내 순환 (대덕캠퍼스 내)",
                "route_type": "campus_circulation",
                "first_bus": "08:30",
                "last_bus": "17:30",
                "trips_per_day": "10회, 학기 중 운영(총 150일)",
            },
        },
        {
            "id": "shuttle_route_캠퍼스순환대덕캠퍼스보운캠퍼스",
            "domain": "shuttle",
            "title": "셔틀버스 캠퍼스 순환 (대덕캠퍼스 ↔ 보운캠퍼스) 운행 정보",
            "text": CAMPUS_LOOP_TEXT,
            "source_url": SHUTTLE_SOURCE_URL,
            "source_name": SHUTTLE_SOURCE_NAME,
            "source_path": "data/raw/shuttle/shuttle_bus.html",
            "generation_method": "structured_aggregate",
            "metadata": {
                "domain_type": "route",
                "route_name": "캠퍼스 순환 (대덕캠퍼스 ↔ 보운캠퍼스)",
                "route_type": "campus_loop",
                "first_bus": "08:10(대덕)",
                "last_bus": "08:50(보운)",
                "trips_per_day": "1회(회차), 학기 중 운영(총 150일)",
            },
        },
    ]


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parent
    repo_root = workspace_root.parent.parent
    processed_dir = workspace_root / "data" / "processed"
    reports_dir = workspace_root / "data" / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    chunks = _canonical_chunks()
    output_index_path = processed_dir / "shuttle-index.jsonl"
    with open(output_index_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    report = {
        "parsed_files": [],
        "curated_artifact_sources": ["tmp/shuttle_page_full.txt"],
        "skipped_files": [],
        "raw_records_count": 3,
        "unique_chunk_count": len(chunks),
        "duplicate_count": 0,
        "missing_source_url_count": 0,
        "missing_source_name_count": 0,
        "route_names_found": [
            "교내 순환 (대덕캠퍼스 내)",
            "캠퍼스 순환 (대덕캠퍼스 ↔ 보운캠퍼스)",
        ],
        "dates_found": [],
        "missing_source_meta": [],
        "known_limitations": [
            "셔틀버스 운영 시간표는 학기 중 평일 기준이며 방학/주말/공휴일은 미운영",
            "운행 시간은 교통 상황 등으로 5분 내외 오차 가능",
            "raw HTML은 git-ignored 상태라 summary/route 문서는 untracked review artifact인 tmp/shuttle_page_full.txt에서 도출한 curated constants로 작성",
            "운영기간과 차량 정보는 tmp/shuttle_page_full.txt에서 확인되지 않아 삭제된 지질환경과학과 공지 기준으로 summary에 명시",
        ],
    }
    output_report_path = reports_dir / "shuttle-build-report.json"
    with open(output_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Successfully wrote {len(chunks)} chunks to {output_index_path}")
    print(f"Successfully wrote build report to {output_report_path}")


if __name__ == "__main__":
    main()
