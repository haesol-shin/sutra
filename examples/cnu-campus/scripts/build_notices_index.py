import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

CNU_LIST_URL = (
    "https://plus.cnu.ac.kr/_prog/_board/"
    "?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr"
)
CNU_BASE = "https://plus.cnu.ac.kr/_prog/_board/"
HEADERS = {"User-Agent": "Sutra/1.0"}
TIMEOUT = 15
MAX_REGULAR = 20
SLEEP = 0.5
MAX_BODY_CHARS = 2500
BOARD_SOURCE_NAME = "충남대학교 학사공지 게시판"


def _detect_encoding(content: bytes) -> str:
    """Detect encoding from HTML meta tag or fall back to utf-8."""
    head = content[:2048].decode("ascii", errors="ignore")
    m = re.search(r'charset\s*=\s*["\']?([a-zA-Z0-9_-]+)', head, re.IGNORECASE)
    if m:
        return m.group(1)
    return "utf-8"


def _clean(raw: str) -> str:
    s = re.sub(r"<[^>]+>", " ", raw)
    s = re.sub(r"&[a-z]+;", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip(raw: str) -> str:
    raw = re.sub(
        r"<(script|style)[^>]*>.*?</\1>", "", raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    raw = re.sub(r"<[^>]+>", " ", raw)
    for ent, ch in [
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
        ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " "),
    ]:
        raw = raw.replace(ent, ch)
    raw = re.sub(r"&[a-z]+;", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def _td_regex(class_name: str) -> str:
    return (
        r'<td[^>]*class=["\'][^"\']*'
        + class_name
        + r'[^"\']*["\'][^>]*>(.*?)</td>'
    )


def _fetch_detail(no: str) -> dict | None:
    url = urljoin(
        CNU_BASE,
        f"?mode=V&no={no}&code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr",
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Warning: {e}")
        return None

    resp.encoding = _detect_encoding(resp.content)
    html = resp.text

    # Title from board_viewTit h4
    title = ""
    title_m = re.search(
        r'class="[^"]*board_viewTit[^"]*"[^>]*>.*?<h4[^>]*>(.*?)</h4>',
        html, re.DOTALL,
    )
    if title_m:
        title = _clean(title_m.group(1))

    # Date from <li class="date">
    date = ""
    date_m = re.search(
        r'<li[^>]*class="[^"]*date[^"]*"[^>]*>.*?<span>[^<]*</span>(.*?)</li>',
        html, re.DOTALL,
    )
    if date_m:
        date_raw = _clean(date_m.group(1))
        date_match = re.search(r"(\d{4}[-.]\d{2}[-.]\d{2})", date_raw)
        if date_match:
            date = re.sub(r"\.", "-", date_match.group(1))

    # Department from <li class="writer">
    dept = ""
    writer_m = re.search(
        r'<li[^>]*class="[^"]*writer[^"]*"[^>]*>.*?<span>[^<]*</span>(.*?)</li>',
        html, re.DOTALL,
    )
    if writer_m:
        dept = _clean(writer_m.group(1))

    # Body from board_viewDetail divs (skip PDF viewer)
    body_parts = []
    detail_divs = re.findall(
        r'<div\s+class="[^"]*board_viewDetail[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL,
    )
    for d in detail_divs:
        if "board_pdf_viewer" in d:
            continue
        stripped = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", d,
                          flags=re.DOTALL | re.IGNORECASE)
        stripped = re.sub(r"<[^>]+>", " ", stripped)
        for ent, ch in [
            ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
            ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " "),
        ]:
            stripped = stripped.replace(ent, ch)
        stripped = re.sub(r"&[a-z]+;", " ", stripped)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if stripped:
            body_parts.append(stripped)

    body_text = " ".join(body_parts)
    if len(body_text) > MAX_BODY_CHARS:
        body_text = body_text[:MAX_BODY_CHARS]

    return {
        "no": no,
        "title": title,
        "date": date,
        "department": dept,
        "body": body_text,
        "url": url,
    }


def _parse_board_page(html: str) -> list[dict]:
    """Parse rows from a CNU board page HTML."""
    tbody_m = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL)
    if not tbody_m:
        return []

    rows_html = re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.DOTALL)
    rows = []
    for rh in rows_html:
        num_m = re.search(_td_regex("num"), rh, re.DOTALL)
        date_m = re.search(_td_regex("date"), rh, re.DOTALL)
        a_m = re.search(
            r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',
            rh, re.DOTALL,
        )
        if not (num_m and date_m and a_m):
            continue

        num_text = _clean(num_m.group(1))
        date_text = _clean(date_m.group(1))
        href = a_m.group(1).strip().replace("&amp;", "&")
        title = _clean(a_m.group(2))
        is_pinned = (num_text == "공지")

        no_m = re.search(r"no=(\d+)", href)
        post_no = no_m.group(1) if no_m else ""

        date_norm = re.sub(r"[/.]", "-", date_text)

        rows.append({
            "no": post_no,
            "title": title,
            "date": date_norm,
            "href": href,
            "is_pinned": is_pinned,
        })
    return rows


def _fetch_board_page(page: int) -> list[dict] | None:
    """Fetch and parse one page of the board. Returns rows or None on failure."""
    url = f"{CNU_LIST_URL}&GotoPage={page}"
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Warning: Failed to fetch page {page}: {e}")
        return None
    resp.encoding = _detect_encoding(resp.content)
    return _parse_board_page(resp.text)


def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    processed_dir = project_root / "examples" / "cnu-campus" / "data" / "processed"
    reports_dir = project_root / "examples" / "cnu-campus" / "data" / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    output_path = processed_dir / "notices-index.jsonl"
    report_path = reports_dir / "notices-build-report.json"

    # 1. Fetch board pages until enough regular posts
    print(f"Fetching board list: {CNU_LIST_URL}")
    all_rows = []
    pinned = []
    regular = []
    page = 1
    pages_fetched = 0

    while len(regular) < MAX_REGULAR and page <= 20:
        page_rows = _fetch_board_page(page)
        if page_rows is None:
            break
        pages_fetched += 1

        page_pinned = [r for r in page_rows if r["is_pinned"]]
        page_regular = [r for r in page_rows if not r["is_pinned"]]

        if page == 1:
            pinned = page_pinned
        elif page_pinned:
            # Deduplicate pinned posts that may appear on multiple pages
            seen_pinned_nos = {r["no"] for r in pinned}
            for r in page_pinned:
                if r["no"] not in seen_pinned_nos:
                    pinned.append(r)
                    seen_pinned_nos.add(r["no"])

        regular.extend(page_regular)
        all_rows.extend(page_rows)

        print(f"  Page {page}: {len(page_rows)} rows "
              f"({len(page_pinned)} pinned, {len(page_regular)} regular)")

        if not page_rows:
            break
        page += 1

    # Sort and select
    pinned.sort(key=lambda r: r["date"], reverse=True)
    regular.sort(key=lambda r: r["date"], reverse=True)

    # Deduplicate regular posts across pages
    seen_regular_nos = set()
    regular_deduped = []
    for r in regular:
        if r["no"] not in seen_regular_nos:
            regular_deduped.append(r)
            seen_regular_nos.add(r["no"])
    regular = regular_deduped

    selected_regular = regular[:MAX_REGULAR]
    selected = pinned + selected_regular

    print(
        f"Total: {len(all_rows)} rows across {pages_fetched} pages, "
        f"{len(pinned)} pinned, {len(regular)} regular"
    )
    print(
        f"Selected: {len(pinned)} pinned + {len(selected_regular)} regular "
        f"= {len(selected)} posts"
    )

    # 3. Fetch each detail page
    posts = []
    failed_nos = []
    for i, row in enumerate(selected):
        no = row["no"]
        print(
            f"  [{i + 1}/{len(selected)}] Fetching detail: "
            f"no={no} ({row['title'][:40]})"
        )
        detail = _fetch_detail(no)
        if detail is None:
            failed_nos.append(no)
            posts.append({
                "no": no,
                "title": row["title"],
                "date": row["date"],
                "department": "",
                "body": row["title"],
                "url": urljoin(CNU_BASE, row["href"]),
                "is_pinned": row["is_pinned"],
            })
        else:
            detail["is_pinned"] = row["is_pinned"]
            if not detail.get("title"):
                detail["title"] = row["title"]
            if not detail.get("date"):
                detail["date"] = row["date"]
            posts.append(detail)
        if i < len(selected) - 1:
            time.sleep(SLEEP)

    # 4. Write notices-index.jsonl
    docs = []
    for post in posts:
        doc_id = f"notices_{post['no']}"
        title = post.get("title") or f"공지사항 {post['no']}"
        body = post["body"]
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS]

        doc = {
            "id": doc_id,
            "domain": "notices",
            "title": title,
            "text": body,
            "source_url": post["url"],
            "source_name": BOARD_SOURCE_NAME,
            "source_path": None,
            "fetched_at": None,
            "derived_from": [],
            "generation_method": "board_snapshot",
            "metadata": {
                "date": post.get("date", ""),
                "department": post.get("department", ""),
                "pinned": post.get("is_pinned", False),
                "board": "univ_academic",
            },
        }
        docs.append(doc)

    # Board overview doc
    overview_lines = []
    recent_for_overview = sorted(
        [p for p in posts if not p.get("is_pinned")],
        key=lambda p: p["date"],
        reverse=True,
    )[:MAX_REGULAR]
    for p in recent_for_overview:
        overview_lines.append(f"[{p['date']}] {p['title']}")

    overview_doc = {
        "id": "notices_board_overview",
        "domain": "notices",
        "title": "최근 학사공지 목록",
        "text": (
            "충남대학교 학사공지 게시판 최근 게시글입니다.\n\n"
            + "\n".join(overview_lines)
        ),
        "source_url": CNU_LIST_URL,
        "source_name": BOARD_SOURCE_NAME,
        "source_path": None,
        "fetched_at": None,
        "derived_from": [],
        "generation_method": "board_snapshot",
        "metadata": {
            "date": "",
            "department": "",
            "pinned": False,
            "board": "univ_academic",
            "overview_post_count": len(recent_for_overview),
        },
    }
    docs.append(overview_doc)

    with open(output_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"Wrote {len(docs)} docs to {output_path}")

    # 5. Write build report
    report = {
        "pages_fetched": pages_fetched,
        "board_total_rows": len(all_rows),
        "pinned_count": len(pinned),
        "regular_count": len(regular),
        "selected_pinned": len(pinned),
        "selected_regular": len(selected_regular),
        "detail_fetch_success": len(selected) - len(failed_nos),
        "detail_fetch_failed": len(failed_nos),
        "failed_nos": failed_nos,
        "post_docs": len(docs) - 1,
        "overview_doc": 1,
        "total_output_docs": len(docs),
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote report to {report_path}")


if __name__ == "__main__":
    main()
