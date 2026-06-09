import re
from typing import Optional, NamedTuple, List
from bs4 import BeautifulSoup, Tag

class RouteRecord(NamedTuple):
    route_name: str
    route_type: str  # "campus_circulation" or "campus_loop"
    time_table_text: str
    route_stops_text: str
    first_bus: Optional[str] = None
    last_bus: Optional[str] = None
    trips_per_day: Optional[str] = None
    operating_note: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None

class NoticeRecord(NamedTuple):
    title: str
    body_text: str
    posted_date: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None

class ParseResult(NamedTuple):
    status: str
    records: list
    error_msg: Optional[str] = None

def normalize_text(text: str) -> str:
    if not text:
        return ""
    lines = []
    for line in text.split('\n'):
        cleaned = re.sub(r'\s+', ' ', line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)

def parse_operating_summary(soup: BeautifulSoup) -> Optional[str]:
    txt_div = soup.find('div', id='txt')
    if not txt_div:
        return None
    h4 = txt_div.find('h4')
    ul = txt_div.find('ul', class_='h7_ul')
    if not h4 and not ul:
        return None
    parts = []
    if h4:
        parts.append(h4.get_text(strip=True))
    if ul:
        for li in ul.find_all('li'):
            t = li.get_text(strip=True)
            if t:
                parts.append(t)
    return "\n".join(parts) if parts else None

def parse_route_tables(soup: BeautifulSoup) -> List[RouteRecord]:
    txt_div = soup.find('div', id='txt')
    if not txt_div:
        return []
    tables = txt_div.find_all('table', class_='content_table')
    if len(tables) < 2:
        return []
    schedule_table = tables[0]
    route_table = tables[1]
    schedule_rows = _parse_schedule_table(schedule_table)
    route_rows = _parse_route_table(route_table)
    records = []
    for s_row in schedule_rows:
        r_name = s_row.get("name", "")
        matching = [r for r in route_rows if r.get("name") and r_name in r["name"] or (r_name and r.get("name") and r["name"] in r_name)]
        if not matching and route_rows:
            fallback = [r for r in route_rows if "순환" in r.get("name", "")]
            for fb in fallback:
                if ("교내" in r_name and "교내" in fb["name"]) or ("캠퍼스" in r_name and "캠퍼스" in fb["name"]):
                    matching.append(fb)
        route_info = matching[0] if matching else {}
        records.append(RouteRecord(
            route_name=r_name,
            route_type="campus_circulation" if "교내" in r_name else "campus_loop",
            time_table_text=s_row.get("schedule", ""),
            route_stops_text=route_info.get("stops", ""),
            first_bus=route_info.get("first_bus"),
            last_bus=route_info.get("last_bus"),
            trips_per_day=route_info.get("trips"),
            operating_note=s_row.get("note"),
            source_path=None,
            source_url=None,
            fetched_at=None
        ))
    return records

def _parse_schedule_table(table: Tag) -> list:
    rows = []
    tbody = table.find('tbody')
    if not tbody:
        return rows
    for tr in tbody.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if not cells:
            continue
        name_cell = cells[0]
        name = normalize_text(name_cell.get_text(separator='\n')).replace('\n', ' ')
        time_cells = cells[1:]
        times = []
        for tc in time_cells:
            t = normalize_text(tc.get_text(separator='\n'))
            times.append(t)
        schedule_text = " | ".join(t for t in times if t)
        rows.append({"name": name, "schedule": schedule_text})
    return rows

def _parse_route_table(table: Tag) -> list:
    rows = []
    tbody = table.find('tbody')
    if not tbody:
        return rows
    for tr in tbody.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if len(cells) < 5:
            continue
        name_cell = cells[0]
        first_cell = cells[1]
        last_cell = cells[2]
        stops_cell = cells[3]
        trips_cell = cells[4]
        name = normalize_text(name_cell.get_text(separator='\n')).replace('\n', ' ')
        first_bus = normalize_text(first_cell.get_text(separator='\n')).replace('\n', ' ') if first_cell else None
        last_bus = normalize_text(last_cell.get_text(separator='\n')).replace('\n', ' ') if last_cell else None
        stops = normalize_text(stops_cell.get_text(separator='\n'))
        trips = normalize_text(trips_cell.get_text(separator='\n')).replace('\n', ' ')
        rows.append({
            "name": name, "first_bus": first_bus,
            "last_bus": last_bus, "stops": stops, "trips": trips
        })
    return rows

def parse_geo_notice_content(soup: BeautifulSoup) -> Optional[NoticeRecord]:
    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else ""
    title = title.replace("Geological Sciences", "").replace("Notice", "").strip()
    posted_date = None
    board_title = soup.select_one('#mb_announcement_tr_title td span[style*="float:right"]')
    if board_title:
        date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', board_title.get_text())
        if date_match:
            posted_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    hwp_div = soup.select_one('#hwpEditorBoardContent')
    body_parts = []
    if hwp_div:
        raw = hwp_div.get_text(separator=' ')
        text_items = re.findall(r'"t"\s*:\s*"([^"]+)"', raw)
        if text_items:
            clean = []
            for item in text_items:
                if re.search(r'[\uac00-\ud7af]', item) and len(item) > 1:
                    clean.append(item)
            if clean:
                body_parts.append("\n".join(clean))
    meta_desc = soup.find('meta', attrs={'property': 'og:description'})
    if meta_desc and meta_desc.get('content'):
        body_parts.append(meta_desc['content'])
    body_text = "\n".join(body_parts) if body_parts else ""
    if not body_text:
        return None
    return NoticeRecord(
        title=title or "2026학년도 충남대학교 셔틀버스 운영 안내",
        body_text=body_text,
        posted_date=posted_date,
        source_path=None,
        source_url=None,
        fetched_at=None
    )

def parse_shuttle_file(path: str, source_meta: Optional[dict] = None) -> ParseResult:
    source_info = {
        "source_path": path,
        "source_url": source_meta.get("url") if source_meta else None,
        "fetched_at": source_meta.get("fetched_at") if source_meta else None
    }
    filename = path.replace('\\', '/').split('/')[-1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return ParseResult(status="skipped", records=[], error_msg=f"Failed to read file: {e}")
    soup = BeautifulSoup(content, 'html.parser')
    if "geo_notice" in filename:
        notice = parse_geo_notice_content(soup)
        if notice:
            notice = notice._replace(
                source_path=source_info["source_path"],
                source_url=source_info["source_url"],
                fetched_at=source_info["fetched_at"]
            )
            return ParseResult(status="success", records=[("notice", notice, source_info)])
        return ParseResult(status="skipped", records=[], error_msg="No notice content found in geo_notice file")
    txt_div = soup.find('div', id='txt')
    if not txt_div:
        return ParseResult(status="skipped", records=[], error_msg="No content div (#txt) found")
    summary = parse_operating_summary(soup)
    route_records = parse_route_tables(soup)
    if not route_records and not summary:
        return ParseResult(status="skipped", records=[], error_msg="No route tables or content found")
    route_records = [
        r._replace(
            source_path=source_info["source_path"],
            source_url=source_info["source_url"],
            fetched_at=source_info["fetched_at"]
        )
        for r in route_records
    ]
    records = []
    if summary:
        records.append(("operating_summary", summary, source_info))
    for r in route_records:
        records.append(("route", r, source_info))
    return ParseResult(status="success", records=records)


