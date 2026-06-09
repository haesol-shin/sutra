import re
from typing import Optional, NamedTuple, List
from bs4 import BeautifulSoup

class MenuRecord(NamedTuple):
    date: str
    cafeteria: str
    meal: str
    audience: str
    menu_text: str
    menu_name: Optional[str] = None
    price: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None

class ParseResult(NamedTuple):
    status: str  # "success" or "skipped"
    records: List[MenuRecord]
    error_msg: Optional[str] = None

def normalize_menu_text(text: str) -> str:
    if not text:
        return ""
    lines = []
    for line in text.split('\n'):
        cleaned = re.sub(r'\s+', ' ', line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)

def should_skip_record(menu_text: str) -> bool:
    if not menu_text:
        return True
    normalized = menu_text.replace(" ", "")
    if "메뉴는운영중입니다" in normalized:
        return True
    if "메뉴운영내역" in normalized:
        return True
    if "메뉴는준비중입니다" in normalized:
        return True
    return False

def parse_table_to_grid(table, rows_count: int) -> List[List[Optional[BeautifulSoup]]]:
    tbody = table.find('tbody')
    if not tbody:
        return []
    
    tr_tags = tbody.find_all('tr')
    if not tr_tags:
        return []
    
    # Calculate column count from thead (accounting for colspans)
    thead = table.find('thead')
    cols = 0
    if thead:
        first_tr = thead.find('tr')
        if first_tr:
            for th in first_tr.find_all(['th', 'td']):
                cols += int(th.get('colspan', 1))
    
    if cols == 0:
        for td in tr_tags[0].find_all(['td', 'th']):
            cols += int(td.get('colspan', 1))
            
    rows = len(tr_tags)
    grid = [[None] * cols for _ in range(rows)]
    
    for r, tr in enumerate(tr_tags):
        c = 0
        for td in tr.find_all(['td', 'th']):
            while c < cols and grid[r][c] is not None:
                c += 1
            if c >= cols:
                break
            
            rs = int(td.get('rowspan', 1))
            cs = int(td.get('colspan', 1))
            
            for dr in range(rs):
                for dc in range(cs):
                    if r + dr < rows and c + dc < cols:
                        grid[r + dr][c + dc] = td
            c += cs
            
    return grid

def parse_weekly_menu_table(soup: BeautifulSoup, source_info: dict) -> List[MenuRecord]:
    table = soup.find('table', class_='menu-tbl')
    if not table:
        return []
        
    # Cafeteria
    over_li = soup.select_one('#childTab li.over')
    cafeteria = over_li.get_text(strip=True) if over_li else "알수없음"
    
    # Dates
    date_list = []
    thead = table.find('thead')
    if thead:
        tr = thead.find('tr')
        if tr:
            for th in tr.find_all(['th', 'td']):
                t = th.get_text(strip=True)
                match = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', t)
                if match:
                    date_list.append(f"{match.group(1)}-{match.group(2)}-{match.group(3)}")
                    
    tbody = table.find('tbody')
    if not tbody:
        return []
    tr_tags = tbody.find_all('tr')
    grid = parse_table_to_grid(table, len(tr_tags))
    
    records = []
    current_meal = "알수없음"
    
    for r in range(len(grid)):
        meal_cell = grid[r][0]
        if meal_cell and meal_cell.get('class') and 'building' in meal_cell.get('class'):
            current_meal = meal_cell.get_text(strip=True)
            audience_cell = grid[r][1]
            menu_cells = grid[r][2:]
        else:
            audience_cell = grid[r][0]
            menu_cells = grid[r][1:]
            
        audience = audience_cell.get_text(strip=True) if audience_cell else "알수없음"
        
        for i, cell in enumerate(menu_cells):
            if i >= len(date_list) or cell is None:
                continue
            date = date_list[i]
            
            raw_text = cell.get_text(separator='\n')
            menu_text = normalize_menu_text(raw_text)
            
            if should_skip_record(menu_text):
                continue
                
            h3 = cell.find('h3', class_='menu-tit03')
            menu_name = h3.get_text(strip=True) if h3 else None
            price = None
            if menu_name:
                price_match = re.search(r'\((\d+)\)', menu_name)
                if price_match:
                    price = price_match.group(1)
                    
            records.append(MenuRecord(
                date=date,
                cafeteria=cafeteria,
                meal=current_meal,
                audience=audience,
                menu_text=menu_text,
                menu_name=menu_name,
                price=price,
                source_path=source_info.get("source_path"),
                source_url=source_info.get("source_url"),
                fetched_at=source_info.get("fetched_at")
            ))
            
    return records

def parse_daily_menu_table(soup: BeautifulSoup, source_info: dict) -> List[MenuRecord]:
    table = soup.find('table', class_='menu-tbl')
    if not table:
        return []
        
    # Date
    date_match = None
    term_span = soup.select_one('.menu-navi.weekly span.term')
    if term_span:
        date_match = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', term_span.get_text())
    if not date_match:
        over_li = soup.select_one('#childTab li.over')
        if over_li:
            date_match = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', over_li.get_text())
            
    if not date_match:
        return []
    date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    
    # Cafeterias from header
    cafeteria_list = []
    thead = table.find('thead')
    if thead:
        tr = thead.find('tr')
        if tr:
            for th in tr.find_all(['th', 'td']):
                t = th.get_text(strip=True)
                if "구분" in t or t == "":
                    continue
                cafeteria_list.append(t)
                
    tbody = table.find('tbody')
    if not tbody:
        return []
    tr_tags = tbody.find_all('tr')
    grid = parse_table_to_grid(table, len(tr_tags))
    
    records = []
    current_meal = "알수없음"
    
    for r in range(len(grid)):
        meal_cell = grid[r][0]
        if meal_cell and meal_cell.get('class') and 'building' in meal_cell.get('class'):
            current_meal = meal_cell.get_text(strip=True)
            audience_cell = grid[r][1]
            menu_cells = grid[r][2:]
        else:
            audience_cell = grid[r][0]
            menu_cells = grid[r][1:]
            
        audience = audience_cell.get_text(strip=True) if audience_cell else "알수없음"
        
        for i, cell in enumerate(menu_cells):
            if i >= len(cafeteria_list) or cell is None:
                continue
            cafeteria = cafeteria_list[i]
            
            raw_text = cell.get_text(separator='\n')
            menu_text = normalize_menu_text(raw_text)
            
            if should_skip_record(menu_text):
                continue
                
            h3 = cell.find('h3', class_='menu-tit03')
            menu_name = h3.get_text(strip=True) if h3 else None
            price = None
            if menu_name:
                price_match = re.search(r'\((\d+)\)', menu_name)
                if price_match:
                    price = price_match.group(1)
                    
            records.append(MenuRecord(
                date=date,
                cafeteria=cafeteria,
                meal=current_meal,
                audience=audience,
                menu_text=menu_text,
                menu_name=menu_name,
                price=price,
                source_path=source_info.get("source_path"),
                source_url=source_info.get("source_url"),
                fetched_at=source_info.get("fetched_at")
            ))
            
    return records

def parse_dining_file(path: str, source_meta: Optional[dict] = None) -> ParseResult:
    source_info = {
        "source_path": path,
        "source_url": source_meta.get("url") if source_meta else None,
        "fetched_at": source_meta.get("fetched_at") if source_meta else None
    }
    
    # Handle skips based on path or filename
    filename = re.split(r'[\\/]', path)[-1]
    if "notice" in filename.lower() or "dining_operation" in filename.lower():
        return ParseResult(status="skipped", records=[], error_msg="Skipped notice file")
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return ParseResult(status="skipped", records=[], error_msg=f"Failed to read file: {e}")
        
    soup = BeautifulSoup(content, 'html.parser')
    table = soup.find('table', class_='menu-tbl')
    if not table:
        return ParseResult(status="skipped", records=[], error_msg="No menu table found")
        
    # Detect View Type
    over_li = soup.select_one('#childTab li.over')
    active_tab_text = over_li.get_text(strip=True) if over_li else ""
    
    th_tags = table.find('thead').find_all('th') if table.find('thead') else []
    th_texts = [th.get_text(strip=True) for th in th_tags]
    
    date_pattern = re.compile(r'\d{4}[.-]\d{2}[.-]\d{2}')
    th_has_date = any(date_pattern.search(text) for text in th_texts)
    tab_has_date = bool(date_pattern.search(active_tab_text))
    
    cafeteria_keywords = ["학생회관", "대학", "교직원", "생활과학", "기숙사", "식당"]
    tab_has_cafeteria = any(k in active_tab_text for k in cafeteria_keywords)
    th_has_cafeteria = any(any(k in text for k in cafeteria_keywords) for text in th_texts)
    
    view_type = "skipped"
    if th_has_date and (tab_has_cafeteria or not tab_has_date):
        view_type = "weekly"
    elif tab_has_date and th_has_cafeteria:
        view_type = "daily"
        
    if view_type == "weekly":
        records = parse_weekly_menu_table(soup, source_info)
        return ParseResult(status="success", records=records)
    elif view_type == "daily":
        records = parse_daily_menu_table(soup, source_info)
        return ParseResult(status="success", records=records)
    else:
        return ParseResult(status="skipped", records=[], error_msg=f"Unknown view type or tab structure. active_tab: '{active_tab_text}'")
